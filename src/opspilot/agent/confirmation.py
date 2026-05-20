"""Human-in-the-loop confirmation state machine.

安全属性：
- token 由 secrets.token_urlsafe 生成，LLM 不可预测（堵死自确认）。
- 放行需 confirm(request_id, token, actor)，actor 记录"是谁确认的"。
- 一次性：consume() 后失效，防重放。
- TTL：过期自动失效，避免悬挂 pending 内存泄漏（替代旧 feishu_card 无 TTL dict）。
进程内实现；接口与后端解耦，Stage 6 可换 Redis/Postgres。
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PendingConfirmation:
    request_id: str
    tool: str
    tool_input: str
    token: str
    expires_at: float


class ConfirmationStore:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._pending: dict[str, PendingConfirmation] = {}
        self._confirmed_by: dict[str, str] = {}

    def request(self, tool: str, tool_input: str) -> PendingConfirmation:
        pc = PendingConfirmation(
            request_id=secrets.token_urlsafe(12),
            tool=tool,
            tool_input=tool_input,
            token=secrets.token_urlsafe(24),
            expires_at=time.monotonic() + self._ttl,
        )
        with self._lock:
            self._gc_locked()
            self._pending[pc.request_id] = pc
        return pc

    def confirm(self, request_id: str, token: str, actor: str) -> bool:
        with self._lock:
            pc = self._pending.get(request_id)
            if pc is None or time.monotonic() > pc.expires_at:
                self._pending.pop(request_id, None)
                return False
            if not secrets.compare_digest(token, pc.token):
                return False
            self._confirmed_by[request_id] = actor
            return True

    def is_confirmed(self, request_id: str) -> bool:
        with self._lock:
            return request_id in self._confirmed_by

    def consume(self, request_id: str) -> str | None:
        """放行并失效（一次性）。返回确认人 actor，未确认返回 None。"""
        with self._lock:
            actor = self._confirmed_by.pop(request_id, None)
            self._pending.pop(request_id, None)
            return actor

    def _gc_locked(self) -> None:
        now = time.monotonic()
        dead = [rid for rid, pc in self._pending.items() if now > pc.expires_at]
        for rid in dead:
            self._pending.pop(rid, None)
            self._confirmed_by.pop(rid, None)


def _build_default_store() -> ConfirmationStore:
    from opspilot.config import get_settings

    return ConfirmationStore(ttl_seconds=get_settings().confirm_ttl_seconds)


# 进程级单例（被 tool_exec 与 feishu 回调共享）
STORE = _build_default_store()
