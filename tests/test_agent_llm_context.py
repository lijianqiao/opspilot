"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_agent_llm_context.py
@DateTime: 2026-05-26
@Docs: Tests for the shared _current_llm ContextVar utilities.
    共享 _current_llm ContextVar 工具的测试。
"""

from __future__ import annotations

import pytest


def test_use_llm_resets_after_block() -> None:
    """use_llm sets the LLM inside the block and restores on exit.
    use_llm 在代码块内设置 LLM，退出时恢复原值。
    """
    from opspilot.agent.context import current_llm, use_llm

    class _Stub:
        async def chat(self, messages: list[dict[str, str]]) -> str:
            return ""

    stub = _Stub()
    assert current_llm() is None
    with use_llm(stub):
        assert current_llm() is stub
    assert current_llm() is None


def test_require_llm_raises_when_unset() -> None:
    """require_llm raises RuntimeError when no LLM is bound.
    未绑定 LLM 时 require_llm 抛出 RuntimeError。
    """
    from opspilot.agent.context import require_llm

    with pytest.raises(RuntimeError):
        require_llm()


def test_require_llm_returns_bound_llm() -> None:
    """require_llm returns the bound LLM inside a use_llm block.
    require_llm 在 use_llm 代码块中返回已绑定的 LLM。
    """
    from opspilot.agent.context import require_llm, use_llm

    class _Stub:
        async def chat(self, messages: list[dict[str, str]]) -> str:
            return ""

    stub = _Stub()
    with use_llm(stub):
        assert require_llm() is stub


def test_nested_use_llm_restores_outer() -> None:
    """Nested use_llm blocks restore the outer LLM on inner exit.
    嵌套 use_llm：内层退出时恢复外层 LLM。

    This protects the supervisor → sub-agent path where each runner
    wraps its own use_llm scope.
    这保证 supervisor → 子智能体路径下各 runner 各自的 use_llm 作用域正确。
    """
    from opspilot.agent.context import current_llm, use_llm

    class _Stub:
        async def chat(self, messages: list[dict[str, str]]) -> str:
            return ""

    outer = _Stub()
    inner = _Stub()
    with use_llm(outer):
        assert current_llm() is outer
        with use_llm(inner):
            assert current_llm() is inner
        assert current_llm() is outer
    assert current_llm() is None
