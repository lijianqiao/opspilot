import anyio
import pytest

from opspilot.entrypoints.feishu_ws import (
    _run_blocking,
    _select_agent,
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

    assert "Please enter" in await handle_question("   ", agent)


@pytest.mark.anyio
async def test_handle_question_redacts_agent_failure_detail() -> None:
    # 审查报告 feishu_ws:46-47：原实现 f"Error: {exc}" 把异常字符串直传给用户，
    # 泄露 DSN/堆栈/密钥。新实现：固定脱敏文案，详情仅写日志。
    async def boom(text: str) -> str:
        raise RuntimeError("LLM connection refused")

    result = await handle_question("pod 状态", boom)
    assert "LLM connection refused" not in result
    assert "出错" in result


@pytest.mark.anyio
async def test_handle_question_does_not_leak_dsn_or_secrets() -> None:
    async def boom(text: str) -> str:
        raise RuntimeError("postgresql://opspilot:opspilot@db:5432 connect failed; api_key=sk-LEAK")

    result = await handle_question("hi", boom)
    assert "postgresql://" not in result
    assert "opspilot:opspilot" not in result
    assert "sk-LEAK" not in result
    assert "api_key" not in result.lower()


@pytest.mark.anyio
async def test_bare_anyio_run_fails_inside_running_loop() -> None:
    # Reproduce root cause: lark WS callback runs on a thread with an
    # existing event loop, so anyio.run() raises RuntimeError.
    async def agent(text: str) -> str:
        return text

    with pytest.raises(RuntimeError, match="Already running"):
        anyio.run(handle_question, "x", agent)


@pytest.mark.anyio
async def test_run_blocking_works_inside_running_loop() -> None:
    # Same running-loop environment; _run_blocking must succeed.
    async def agent(text: str) -> str:
        return f"answered: {text}"

    assert _run_blocking("  pod 状态  ", agent) == "answered: pod 状态"


@pytest.mark.anyio
async def test_run_blocking_returns_redacted_message_on_agent_error() -> None:
    async def boom(text: str) -> str:
        raise ValueError("agent failed with secret=sk-XYZ")

    # handle_question catches the error and returns a redacted generic message
    # (审查报告：之前是 f"Error: {exc}"，会泄露 secret-shaped 错误内容)
    result = _run_blocking("hi", boom)
    assert "agent failed" not in result
    assert "sk-XYZ" not in result
    assert "出错" in result


def test_select_agent_plan_prefix():
    text, use_plan = _select_agent("规划：查看 pod")
    assert use_plan is True
    assert text == "查看 pod"


def test_select_agent_plan_prefix_half_width():
    text, use_plan = _select_agent("规划:查看 pod")
    assert use_plan is True
    assert text == "查看 pod"


def test_select_agent_slash_plan():
    text, use_plan = _select_agent("/plan 查看 pod")
    assert use_plan is True
    assert text == "查看 pod"


def test_select_agent_no_prefix():
    text, use_plan = _select_agent("查看 pod")
    assert use_plan is False
    assert text == "查看 pod"


def test_select_agent_strips_feishu_mention():
    text, use_plan = _select_agent("@_user_1 规划：查看 pod")
    assert use_plan is True
    assert text == "查看 pod"


def test_select_agent_strips_mention_no_plan():
    text, use_plan = _select_agent("@_user_1 查看 pod")
    assert use_plan is False
    assert text == "查看 pod"


def test_select_agent_routes_normal_message_to_default():
    text, use_plan = _select_agent("查看 pod 状态")
    assert use_plan is False
    assert text == "查看 pod 状态"


def test_select_agent_preserves_plan_prefix_behavior():
    text, use_plan = _select_agent("规划：重启 order-service")
    assert use_plan is True
    assert text == "重启 order-service"
