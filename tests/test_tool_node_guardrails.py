"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_tool_node_guardrails.py
@DateTime: 2026-05-20
@Docs: Tests LangGraph tool_node cap, danger block, redact.
    测试 LangGraph tool_node 上限/拦截/脱敏。
"""

import pytest

from opspilot.agent.langgraph_agent import run_react_graph


class FakeLLM:
    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append([dict(m) for m in messages])
        return self._replies.pop(0)


@pytest.mark.anyio
async def test_dangerous_tool_is_blocked_not_executed() -> None:
    """
    Verify dangerous tool is blocked not executed.

    验证：dangerous tool is blocked not executed。
    """
    llm = FakeLLM(
        [
            'Thought: scale down\nAction: kubectl_scale\nAction Input: {"deployment": "user-service", "replicas": 0}',
            "Thought: 需要确认\nFinal Answer: 该操作需人工确认。",
        ]
    )
    answer = await run_react_graph("把 user-service 缩到 0", llm, max_steps=4)
    obs_turns = [m for c in llm.calls for m in c if m["role"] == "user"]
    assert any("需人工确认" in m["content"] or "需要人工确认" in m["content"] for m in obs_turns)
    assert "scaled" not in answer


@pytest.mark.anyio
async def test_tool_call_cap_stops_runaway_loop() -> None:
    """
    Verify tool call cap stops runaway loop.

    验证：tool call cap stops runaway loop。
    """
    llm = FakeLLM(["Action: kubectl_get\nAction Input: pods"] * 30)
    answer = await run_react_graph("loop", llm, max_steps=50)
    assert "工具调用次数已达上限" in answer or "达到最大推理步数" in answer
    assert len(llm.calls) <= 20


@pytest.mark.anyio
async def test_observation_is_redacted() -> None:
    """
    Verify observation is redacted.

    验证：observation is redacted。
    """
    llm = FakeLLM(
        [
            "Action: leaky_tool\nAction Input: x",
            "Final Answer: done",
        ]
    )
    from opspilot.tools.registry import register_tool

    @register_tool(name="leaky_tool")
    def leaky_tool(x: str) -> str:
        """leak."""
        return "token=sk-DEADBEEF123456 ok"

    await run_react_graph("q", llm, max_steps=3)
    obs = [m for c in llm.calls for m in c if m["role"] == "user"]
    assert all("sk-DEADBEEF123456" not in m["content"] for m in obs)
