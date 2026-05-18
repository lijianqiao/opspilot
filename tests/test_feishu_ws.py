import anyio
import pytest

from opspilot.entrypoints.feishu_ws import (
    _run_blocking,
    handle_question,
)


@pytest.mark.anyio
async def test_handle_question_delegates_and_trims() -> None:
    async def agent(text: str) -> str:
        return f"answered: {text}"

    assert await handle_question("  pod 状态  ", agent) == "answered: pod 状态"


@pytest.mark.anyio
async def test_handle_question_rejects_empty() -> None:
    async def agent(text: str) -> str:
        raise AssertionError("空输入不应调用 agent")

    assert "请输入" in await handle_question("   ", agent)


@pytest.mark.anyio
async def test_handle_question_returns_error_message_on_agent_failure() -> None:
    async def boom(text: str) -> str:
        raise RuntimeError("LLM connection refused")

    result = await handle_question("pod 状态", boom)
    assert "出错" in result
    assert "LLM connection refused" in result


@pytest.mark.anyio
async def test_bare_anyio_run_fails_inside_running_loop() -> None:
    # 复现根因：lark WS 回调跑在“已有运行中事件循环”的线程里，
    # 此时直接 anyio.run() 必抛 RuntimeError: Already running asyncio。
    # 本测试本身就跑在 anyio 事件循环里，正好复现该环境。
    async def agent(text: str) -> str:
        return text

    with pytest.raises(RuntimeError, match="Already running"):
        anyio.run(handle_question, "x", agent)


@pytest.mark.anyio
async def test_run_blocking_works_inside_running_loop() -> None:
    # 与上面相同的“已有运行循环”环境，_run_blocking 必须正常返回。
    async def agent(text: str) -> str:
        return f"answered: {text}"

    assert _run_blocking("  pod 状态  ", agent) == "answered: pod 状态"


@pytest.mark.anyio
async def test_run_blocking_propagates_agent_error() -> None:
    async def boom(text: str) -> str:
        raise ValueError("agent failed")

    # handle_question now catches errors and returns a user-friendly message
    # instead of propagating the exception.
    result = _run_blocking("hi", boom)
    assert "出错" in result
    assert "agent failed" in result
