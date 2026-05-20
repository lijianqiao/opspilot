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
from dataclasses import dataclass, field

ConfirmationContext = dict[str, str]


def _normalize_context(context: ConfirmationContext | None) -> ConfirmationContext:
    """Filter out empty values from a confirmation context dict.
    过滤掉确认上下文中的空值字段。

    Args:
        context: Optional raw context dict.
            可选原始上下文字典。

    Returns:
        New dict containing only non-empty entries.
            仅包含非空条目的新字典。
    """
    return {k: v for k, v in (context or {}).items() if v}


def _context_matches(expected: ConfirmationContext, current: ConfirmationContext | None) -> bool:
    """Return True when expected context is fully matched by current context.
    返回 expected 是否被 current 完全匹配。

    Legacy pending confirmations with empty expected context match anything;
    this preserves backwards compatibility for API callers without channel info.
    expected 为空时视为兼容旧记录，匹配任意 current。

    Args:
        expected: Context stored on the pending confirmation.
            待确认记录上保存的上下文。
        current: Context supplied by the caller attempting to confirm/consume.
            尝试确认/消费时调用方提供的上下文。

    Returns:
        True if every key in expected appears in current with the same value.
            当 expected 中每个键值都与 current 一致时返回 True。
    """
    if not expected:
        return True
    actual = _normalize_context(current)
    return all(actual.get(key) == value for key, value in expected.items())


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
        context: Channel-bound context (channel/chat_id/requester) that any
            confirm/consume must match; empty dict means legacy/unbound.
            渠道绑定上下文（channel/chat_id/requester），任何确认/消费需匹配；
            为空字典表示旧记录或未绑定。
    """

    request_id: str
    tool: str
    tool_input: str
    token: str
    expires_at: float
    context: ConfirmationContext = field(default_factory=dict)


class ConfirmationStore:
    """In-process store for HITL confirmation of dangerous operations.
    进程内人工确认存储，用于危险操作的人工放行。
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._pending: dict[str, PendingConfirmation] = {}
        self._confirmed_by: dict[str, str] = {}

    def request(
        self,
        tool: str,
        tool_input: str,
        context: ConfirmationContext | None = None,
    ) -> PendingConfirmation:
        """Register a new pending confirmation for a blocked dangerous call.
        为被拦截的危险调用登记新的待确认记录。

        Args:
            tool: Tool name.
                工具名称。
            tool_input: Raw tool input.
                工具输入原文。
            context: Optional channel-bound context (channel/chat_id/requester)
                that any later confirm/consume must match. Empty values are
                dropped; an all-empty context leaves the request legacy/unbound.
                可选渠道绑定上下文（channel/chat_id/requester），后续确认/消费需匹配；
                空值会被丢弃；全为空时记录为旧式未绑定状态。

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
            context=_normalize_context(context),
        )
        with self._lock:
            self._gc_locked()
            self._pending[pc.request_id] = pc
        return pc

    def confirm(
        self,
        request_id: str,
        token: str,
        actor: str,
        context: ConfirmationContext | None = None,
    ) -> bool:
        """Approve a pending request with token; records confirming actor.
        使用 token 批准待确认请求并记录确认人。

        Args:
            request_id: Pending request id.
                待确认请求 ID。
            token: Secret token from the approval channel.
                审批通道提供的密钥。
            actor: Human operator identifier.
                人工操作者标识。
            context: Optional context describing where the approval click
                actually happened. Must match the context recorded on the
                pending request (empty pending context matches anything).
                可选上下文，描述本次审批实际发生的位置；必须与待确认记录的上下文匹配
                （pending 上下文为空时表示旧记录，匹配任意 current）。

        Returns:
            True if confirmation succeeded; False if invalid, expired,
            or context mismatch.
                确认成功为 True；无效、过期或上下文不匹配时为 False。
        """
        with self._lock:
            pc = self._pending.get(request_id)
            if pc is None or time.monotonic() > pc.expires_at:
                self._pending.pop(request_id, None)
                return False
            if not secrets.compare_digest(token, pc.token):
                return False
            if not _context_matches(pc.context, context):
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

    def confirmed_actor_if_matches(
        self,
        request_id: str,
        tool: str,
        tool_input: str,
        context: ConfirmationContext | None = None,
    ) -> str | None:
        """Return confirming actor if pending matches, without consuming state.

        在不消费状态的前提下，校验待确认记录是否匹配并返回确认人。

        Args:
            request_id: Pending request id.
                待确认请求 ID。
            tool: Tool name.
                工具名称。
            tool_input: Raw tool input.
                工具输入原文。
            context: Optional context of the current call site; must match the
                context recorded on the pending request.
                可选当前调用方上下文；必须与待确认记录上下文匹配。

        Returns:
            Confirming actor string if pending exists, is unexpired, matches
            the tool/input/context, and was already confirmed; otherwise None.
            **Does not consume or remove any state.**
                当待确认记录存在、未过期、与工具/入参/上下文匹配且已被确认时
                返回确认人；否则返回 None。**此方法不消费、不移除任何状态。**
        """
        with self._lock:
            pc = self._pending.get(request_id)
            if pc is None:
                return None
            if time.monotonic() > pc.expires_at:
                self._pending.pop(request_id, None)
                self._confirmed_by.pop(request_id, None)
                return None
            if pc.tool != tool or pc.tool_input != tool_input:
                return None
            if not _context_matches(pc.context, context):
                return None
            return self._confirmed_by.get(request_id)

    def consume_if_matches(
        self,
        request_id: str,
        tool: str,
        tool_input: str,
        context: ConfirmationContext | None = None,
    ) -> str | None:
        """Consume a confirmed request only when it matches the original call.
        消费已确认请求，仅当与原始调用匹配时。

        Args:
            request_id: Request id to consume.
                要消费的请求 ID。
            tool: Tool name.
                工具名称。
            tool_input: Raw tool input.
                工具输入原文。
            context: Optional context of the current call site; must match the
                context recorded on the pending request.
                可选当前调用方上下文；必须与待确认记录上下文匹配。

        Returns:
            Confirming actor string, or None if not confirmed, mismatched,
            or context bound to a different channel.
                确认人标识，未确认/不匹配/上下文不一致时返回 None。
        """
        with self._lock:
            pc = self._pending.get(request_id)
            if pc is None:
                return None
            if time.monotonic() > pc.expires_at:
                self._pending.pop(request_id, None)
                self._confirmed_by.pop(request_id, None)
                return None
            if pc.tool != tool or pc.tool_input != tool_input:
                return None
            if not _context_matches(pc.context, context):
                return None
            actor = self._confirmed_by.pop(request_id, None)
            if actor is None:
                return None
            self._pending.pop(request_id, None)
            return actor

    def _gc_locked(self) -> None:
        """Garbage collect expired pending confirmations.
        垃圾收集过期待确认记录。
        """
        now = time.monotonic()
        dead = [rid for rid, pc in self._pending.items() if now > pc.expires_at]
        for rid in dead:
            self._pending.pop(rid, None)
            self._confirmed_by.pop(rid, None)


def _build_default_store() -> ConfirmationStore:
    """Build the default confirmation store.
    构建默认确认状态存储。
    """
    from opspilot.config import get_settings

    return ConfirmationStore(ttl_seconds=get_settings().confirm_ttl_seconds)


# 进程级单例（被 tool_exec 与 feishu 回调共享）
STORE = _build_default_store()
