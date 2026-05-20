"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: confirmation.py
@DateTime: 2026-05-20
@Docs: Human-in-the-loop confirmation state machine for dangerous ops.
    人工确认状态机：危险操作需人工放行。
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PendingConfirmation:
    """A pending human confirmation request for a dangerous tool call.
    危险工具调用的人工确认待办记录。

    Attributes:
        request_id: Opaque id for callbacks and audit.
            供回调与审计使用的不透明请求 ID。
        tool: Tool name awaiting approval.
            待审批的工具名称。
        tool_input: Raw tool input that was blocked.
            被拦截时的工具输入原文。
        token: Secret token required to confirm (not guessable by LLM).
            确认所需密钥（LLM 不可预测）。
        expires_at: Monotonic clock expiry timestamp.
            基于 monotonic 时钟的过期时间戳。
    """

    request_id: str
    tool: str
    tool_input: str
    token: str
    expires_at: float


class ConfirmationStore:
    """In-process store for HITL confirmation of dangerous operations.
    进程内人工确认存储，用于危险操作的人工放行。
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._pending: dict[str, PendingConfirmation] = {}
        self._confirmed_by: dict[str, str] = {}

    def request(self, tool: str, tool_input: str) -> PendingConfirmation:
        """Register a new pending confirmation for a blocked dangerous call.
        为被拦截的危险调用登记新的待确认记录。

        Args:
            tool: Tool name.
                工具名称。
            tool_input: Raw tool input.
                工具输入原文。

        Returns:
            PendingConfirmation with request_id and token.
                含 request_id 与 token 的 PendingConfirmation。
        """
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
        """Approve a pending request with token; records confirming actor.
        使用 token 批准待确认请求并记录确认人。

        Args:
            request_id: Pending request id.
                待确认请求 ID。
            token: Secret token from the approval channel.
                审批通道提供的密钥。
            actor: Human operator identifier.
                人工操作者标识。

        Returns:
            True if confirmation succeeded; False if invalid or expired.
                确认成功为 True；无效或过期为 False。
        """
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
        """Return whether request_id has been confirmed but not yet consumed.
        返回 request_id 是否已确认且尚未被 consume。

        Args:
            request_id: Pending request id.
                待确认请求 ID。

        Returns:
            True if confirmed and awaiting consume.
                已确认待消费时为 True。
        """
        with self._lock:
            return request_id in self._confirmed_by

    def get_pending(self, request_id: str) -> PendingConfirmation | None:
        """Read-only lookup for UI (e.g. Feishu card); does not confirm or consume.
        只读查询待确认记录（如飞书卡片）；不放行、不消费。

        Args:
            request_id: Pending request id.
                待确认请求 ID。

        Returns:
            PendingConfirmation if valid and not expired, else None.
                有效且未过期时返回 PendingConfirmation，否则 None。
        """
        with self._lock:
            pc = self._pending.get(request_id)
            if pc is None:
                return None
            if time.monotonic() > pc.expires_at:
                self._pending.pop(request_id, None)
                self._confirmed_by.pop(request_id, None)
                return None
            return pc

    def consume(self, request_id: str) -> str | None:
        """Consume confirmation (one-shot); return actor or None if not confirmed.
        消费确认（一次性）；返回确认人 actor，未确认则 None。

        Args:
            request_id: Request id to consume.
                要消费的请求 ID。

        Returns:
            Confirming actor string, or None if not confirmed.
                确认人标识，未确认时为 None。
        """
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
