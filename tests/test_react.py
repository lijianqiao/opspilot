import pytest

from opspilot.agent.react import run_react
from opspilot.tools.registry import _registry, ToolInfo


class FakeLLM:
    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append([dict(m) for m in messages])
        return self._replies.pop(0)


@pytest.mark.anyio
async def test_react_calls_tool_then_returns_final_answer() -> None:
    llm = FakeLLM(
        [
            "Thought: 查一下\nAction: get_pod_status\nAction Input: default",
            "Thought: 有了\nFinal Answer: default 下 order-service 处于 CrashLoopBackOff。",
        ]
    )
    answer = await run_react("default 有几个 pod", llm)  # type: ignore[arg-type]
    assert "CrashLoopBackOff" in answer
    assert len(llm.calls) == 2
    assert any("Observation:" in m["content"] for m in llm.calls[1])


@pytest.mark.anyio
async def test_react_unknown_tool_is_reported_then_recovers() -> None:
    llm = FakeLLM(
        [
            "Action: delete_everything\nAction Input: x",
            "Final Answer: 已向用户说明该工具不可用。",
        ]
    )
    answer = await run_react("q", llm)  # type: ignore[arg-type]
    assert "已向用户说明" in answer
    obs = llm.calls[1][-1]["content"]
    assert "不存在" in obs


@pytest.mark.anyio
async def test_react_stops_at_max_steps() -> None:
    llm = FakeLLM(["Action: get_pod_status\nAction Input: default"] * 10)
    answer = await run_react("q", llm, max_steps=3)  # type: ignore[arg-type]
    assert "最大推理步数" in answer
    assert len(llm.calls) == 3


@pytest.mark.anyio
async def test_react_auto_generates_system_prompt_from_registry() -> None:
    """System prompt should be auto-generated, not hardcoded."""
    llm = FakeLLM(["Final Answer: done"])
    await run_react("q", llm)  # type: ignore[arg-type]
    system_msg = llm.calls[0][0]["content"]
    assert "get_pod_status" in system_msg
    assert "query_loki" in system_msg


@pytest.mark.anyio
async def test_react_json_action_input() -> None:
    """Action Input can be JSON for multi-arg tools."""
    llm = FakeLLM(
        [
            'Thought: 查日志\nAction: query_loki\nAction Input: {"query": "error", "namespace": "default"}',
            "Thought: 找到了\nFinal Answer: 发现 ERROR 日志。",
        ]
    )
    answer = await run_react("查错误日志", llm)  # type: ignore[arg-type]
    assert "ERROR" in answer or "发现" in answer


@pytest.mark.anyio
async def test_react_retries_on_tool_exception() -> None:
    """When a tool raises, the agent should get an error observation and retry."""
    call_count = 0

    def flaky_tool(query: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("connection timeout")
        return "success data"

    _registry["_flaky_test"] = ToolInfo(
        name="_flaky_test",
        description="flaky",
        func=flaky_tool,
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    try:
        llm = FakeLLM(
            [
                "Action: _flaky_test\nAction Input: test",
                "Action: _flaky_test\nAction Input: test",
                "Final Answer: got data after retry",
            ]
        )
        answer = await run_react("q", llm)  # type: ignore[arg-type]
        assert "got data" in answer
        obs = llm.calls[1][-1]["content"]
        assert "connection timeout" in obs
    finally:
        _registry.pop("_flaky_test", None)


@pytest.mark.anyio
async def test_react_tools_prompt_includes_all_registered() -> None:
    """The system prompt should list all registered tools, not just one."""
    llm = FakeLLM(["Final Answer: ok"])
    await run_react("q", llm)  # type: ignore[arg-type]
    system_msg = llm.calls[0][0]["content"]
    for name in [
        "get_pod_status",
        "query_loki",
        "kubectl_get",
        "kubectl_describe",
        "query_prometheus",
    ]:
        assert name in system_msg, f"{name} missing from system prompt"
