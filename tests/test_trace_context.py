"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_trace_context.py
@DateTime: 2026-05-20
@Docs: Tests trace id ContextVar helpers in opspilot.observability.context.
    测试 opspilot.observability.context 中的 trace id ContextVar 工具。
"""

from __future__ import annotations

from opspilot.observability.context import (
    bind_trace_id,
    choose_trace_id,
    get_trace_id,
    new_trace_id,
    reset_trace_id,
    set_trace_id,
)


def test_trace_context_round_trip() -> None:
    """set_trace_id binds id, reset_trace_id restores previous (None) state.
    set_trace_id 绑定 trace id，reset_trace_id 还原至原状态（None）。
    """
    assert get_trace_id() is None
    token = set_trace_id("trace-123")
    try:
        assert get_trace_id() == "trace-123"
    finally:
        reset_trace_id(token)
    assert get_trace_id() is None


def test_new_trace_id_is_non_empty_and_unique() -> None:
    """new_trace_id returns a non-empty unique string each call.
    new_trace_id 每次返回非空且唯一的字符串。
    """
    a = new_trace_id()
    b = new_trace_id()
    assert a and b and a != b


def test_choose_trace_id_prefers_explicit_then_context_then_new() -> None:
    """Precedence: explicit arg > current ContextVar > newly minted.
    优先级：显式入参 > 当前 ContextVar > 新生成。
    """
    # No context, no arg → new
    minted = choose_trace_id()
    assert minted

    token = set_trace_id("ctx-trace")
    try:
        # Context only
        assert choose_trace_id() == "ctx-trace"
        # Explicit overrides context
        assert choose_trace_id("explicit") == "explicit"
    finally:
        reset_trace_id(token)


def test_bind_trace_id_sets_and_returns_token() -> None:
    """bind_trace_id sets ContextVar and returns (trace_id, token) for reset.
    bind_trace_id 绑定 ContextVar，并返回 (trace_id, token) 供 finally 重置。
    """
    assert get_trace_id() is None
    trace_id, token = bind_trace_id("incoming-x")
    try:
        assert trace_id == "incoming-x"
        assert get_trace_id() == "incoming-x"
    finally:
        reset_trace_id(token)
    assert get_trace_id() is None


def test_bind_trace_id_mints_when_no_incoming() -> None:
    """bind_trace_id mints when neither arg nor ContextVar provides one.
    入参与 ContextVar 均为空时，bind_trace_id 应新生成一个。
    """
    assert get_trace_id() is None
    trace_id, token = bind_trace_id(None)
    try:
        assert trace_id
        assert get_trace_id() == trace_id
    finally:
        reset_trace_id(token)
