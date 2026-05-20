"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: context.py
@DateTime: 2026-05-20
@Docs: Per-request trace id ContextVar helpers for cross-boundary correlation.
    跨边界请求关联用的 trace id ContextVar 工具集（API/Agent/Tool/审计/渠道共用）。
"""

from __future__ import annotations

import secrets
from contextvars import ContextVar, Token

_trace_id: ContextVar[str | None] = ContextVar("opspilot_trace_id", default=None)


def new_trace_id() -> str:
    """Generate a fresh URL-safe trace id.

    生成一个 URL 安全的新 trace id。

    Returns:
        Random URL-safe token string.
            随机的 URL 安全 token 字符串。
    """
    return secrets.token_urlsafe(12)


def get_trace_id() -> str | None:
    """Read the current trace id from the ContextVar.

    读取当前 ContextVar 中的 trace id。

    Returns:
        Current trace id or None when unset.
            当前 trace id；未设置时为 None。
    """
    return _trace_id.get()


def set_trace_id(trace_id: str | None) -> Token[str | None]:
    """Set the current trace id and return the reset token.

    设置当前 trace id 并返回用于恢复的 token。

    Args:
        trace_id: New trace id to bind, or None to clear.
            新的 trace id；为 None 表示清空。

    Returns:
        ContextVar reset token to be passed to reset_trace_id().
            ContextVar 重置 token，需传给 reset_trace_id()。
    """
    return _trace_id.set(trace_id)


def reset_trace_id(token: Token[str | None]) -> None:
    """Restore the prior trace id using the token from set_trace_id.

    使用 set_trace_id 返回的 token 恢复之前的 trace id。

    Args:
        token: Token previously returned from set_trace_id.
            set_trace_id 返回的 token。
    """
    _trace_id.reset(token)


def choose_trace_id(trace_id: str | None = None) -> str:
    """Pick a trace id, preferring an explicit one over the context, else mint.

    选择 trace id：优先使用显式入参，其次使用上下文，最后新建。

    Args:
        trace_id: Optional explicit trace id (e.g. from incoming header/body).
            可选显式 trace id（如来自入站 header/body）。

    Returns:
        Non-empty trace id string.
            非空的 trace id 字符串。
    """
    return trace_id or get_trace_id() or new_trace_id()


def bind_trace_id(trace_id: str | None = None) -> tuple[str, Token[str | None]]:
    """Choose an effective trace id, set it on the ContextVar, and return both.

    确定有效 trace id、绑定到 ContextVar，并返回 (trace_id, token)。

    Args:
        trace_id: Optional explicit trace id; falls back to context or new.
            可选显式 trace id；缺省回退到上下文或新生成。

    Returns:
        Tuple of (resolved trace id, reset token for finally-reset_trace_id).
            (已确定的 trace id, 用于 finally 调用 reset_trace_id 的 token) 元组。
    """
    current = choose_trace_id(trace_id)
    return current, set_trace_id(current)
