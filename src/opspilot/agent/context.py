"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: context.py
@DateTime: 2026-05-26
@Docs: Shared ContextVar utilities for agent runners (current LLM binding).
    智能体运行时共享的 ContextVar 工具：当前 LLM 绑定。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from opspilot.agent.protocols import SupportsChat

# Single shared ContextVar across all agent flavors. Each `run_*` runner
# wraps its `await _compiled.ainvoke(...)` with `use_llm(llm)`, which
# pushes/pops via `ContextVar.set()` + `reset(token)`. ContextVar is
# isolated per async task, so concurrent supervisor → sub-agent calls
# do not collide even though they share this single var.
# 所有智能体共用同一 ContextVar。各 `run_*` runner 用 `use_llm(llm)`
# 包裹 `await _compiled.ainvoke(...)`，通过 `set()` + `reset(token)` 入/出栈。
# ContextVar 在异步任务间天然隔离，supervisor → 子智能体并发调用不会互相串扰。
_current_llm: ContextVar[SupportsChat | None] = ContextVar("_current_llm", default=None)


def current_llm() -> SupportsChat | None:
    """Return the LLM bound to this async task, or None if unbound.
    返回当前异步任务绑定的 LLM；未绑定时返回 None。

    Returns:
        The bound chat backend or None.
            已绑定的对话后端或 None。
    """
    return _current_llm.get()


def require_llm() -> SupportsChat:
    """Return the bound LLM or raise RuntimeError when unset.
    返回已绑定的 LLM；未绑定时抛出 RuntimeError。

    Returns:
        The bound chat backend.
            已绑定的对话后端。

    Raises:
        RuntimeError: When no LLM is bound in the current context.
            当前上下文未绑定 LLM 时抛出。
    """
    llm = _current_llm.get()
    if llm is None:
        raise RuntimeError("LLM not set. Wrap the run in `with use_llm(llm): ...`.")
    return llm


@contextmanager
def use_llm(llm: SupportsChat) -> Iterator[None]:
    """Bind ``llm`` to the current async task; reset on exit.
    将 ``llm`` 绑定到当前异步任务；退出时还原。

    Usage:
        with use_llm(llm):
            await _compiled.ainvoke(...)

    Sync ``@contextmanager`` is fine because ``ContextVar.set()`` works in
    both sync and async contexts, and the wrapped ``await`` inherits the
    bound value per async-task isolation.
    使用同步 ``@contextmanager`` 即可：``ContextVar.set()`` 在同步/异步上下文都生效，
    被包裹的 ``await`` 通过异步任务隔离继承当前绑定值。

    Args:
        llm: Chat backend to bind for the duration of the block.
            代码块期间需要绑定的对话后端。

    Yields:
        None.
    """
    token = _current_llm.set(llm)
    try:
        yield
    finally:
        _current_llm.reset(token)
