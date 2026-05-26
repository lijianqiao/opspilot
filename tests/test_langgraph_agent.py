"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_langgraph_agent.py
@DateTime: 2026-05-20
@Docs: Tests LangGraph ReAct graph vs handwritten react.
    测试 LangGraph ReAct 图与手写 react 行为一致。
"""

from __future__ import annotations

import pytest

from opspilot.agent.confirmation import STORE
from opspilot.agent.langgraph_agent import run_react_graph


class FakeLLM:
    """Same FakeLLM as test_react.py — duck-types SupportsChat."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append([dict(m) for m in messages])
        return self._replies.pop(0)


@pytest.mark.anyio
async def test_graph_calls_tool_then_returns_final_answer() -> None:
    """
    Verify graph calls tool then returns final answer.

    验证：graph calls tool then returns final answer。
    """
    llm = FakeLLM(
        [
            "Thought: 查一下\nAction: get_pod_status\nAction Input: default",
            "Thought: 有了\nFinal Answer: default 下 order-service 处于 CrashLoopBackOff。",
        ]
    )
    answer = await run_react_graph("default 有几个 pod", llm)
    assert "CrashLoopBackOff" in answer
    assert len(llm.calls) == 2


@pytest.mark.anyio
async def test_graph_unknown_tool_is_reported() -> None:
    """
    Verify graph unknown tool is reported.

    验证：graph unknown tool is reported。
    """
    llm = FakeLLM(
        [
            "Action: nonexistent_tool\nAction Input: x",
            "Final Answer: 已向用户说明该工具不可用。",
        ]
    )
    answer = await run_react_graph("q", llm)
    assert "已向用户说明" in answer
    obs = llm.calls[1][-1]["content"]
    assert "不存在" in obs


@pytest.mark.anyio
async def test_graph_stops_at_max_steps() -> None:
    """
    Verify graph stops at max steps.

    验证：graph stops at max steps。
    """
    llm = FakeLLM(["Action: get_pod_status\nAction Input: default"] * 10)
    answer = await run_react_graph("q", llm, max_steps=3)
    assert "最大推理步数" in answer
    assert len(llm.calls) == 3


@pytest.mark.anyio
async def test_graph_json_action_input() -> None:
    """
    Verify graph json action input.

    验证：graph json action input。
    """
    llm = FakeLLM(
        [
            'Thought: 查日志\nAction: query_loki\nAction Input: {"query": "error"}',
            "Thought: 找到了\nFinal Answer: 发现 ERROR 日志。",
        ]
    )
    answer = await run_react_graph("查错误日志", llm)
    assert "发现" in answer


@pytest.mark.anyio
async def test_graph_matches_handwritten_behavior() -> None:
    """LangGraph version should produce the same result as hand-written for identical input."""
    from opspilot.agent.react import run_react

    replies_1 = [
        "Thought: 查一下\nAction: get_pod_status\nAction Input: default",
        "Thought: 有了\nFinal Answer: order-service CrashLoopBackOff。",
    ]
    replies_2 = list(replies_1)

    llm1 = FakeLLM(replies_1)
    llm2 = FakeLLM(replies_2)

    answer_hand = await run_react("default pod 状态", llm1)
    answer_graph = await run_react_graph("default pod 状态", llm2)
    assert answer_hand == answer_graph


@pytest.mark.anyio
async def test_react_graph_hard_rejects_tool_outside_filter() -> None:
    """
    Verify ReAct graph hard-rejects tool not in the configured filter.

    验证：ReAct 图在执行入口硬拒绝不在 tool_filter 内的工具。
    """
    llm = FakeLLM(
        [
            'Action: kubectl_scale\nAction Input: {"deployment":"user-service","replicas":0}',
            "Final Answer: done",
        ]
    )
    answer = await run_react_graph("check logs", llm, tool_filter={"kubectl_get"})
    assert "not allowed" in answer.lower() or "not allowed" in llm.calls[1][-1]["content"].lower()


@pytest.mark.anyio
async def test_graph_confirmed_request_executes_once() -> None:
    """
    Verify graph confirmed request executes once.

    验证：graph confirmed request executes once。
    """
    raw = '{"deployment":"user-service","replicas":0}'
    pc = STORE.request("kubectl_scale", raw)
    assert STORE.confirm(pc.request_id, pc.token, actor="feishu:ou_42") is True

    llm = FakeLLM(
        [
            f"Action: kubectl_scale\nAction Input: {raw}",
            "Final Answer: scaled",
        ]
    )
    answer = await run_react_graph("scale user-service to zero", llm, confirmed_request_id=pc.request_id)

    assert "scaled" in answer
    assert "scaled" in llm.calls[1][-1]["content"]
    assert STORE.is_confirmed(pc.request_id) is False

    llm_reuse = FakeLLM(
        [
            f"Action: kubectl_scale\nAction Input: {raw}",
            "Final Answer: blocked",
        ]
    )
    await run_react_graph("scale user-service to zero", llm_reuse, confirmed_request_id=pc.request_id)

    observation = llm_reuse.calls[1][-1]["content"]
    assert "request_id=" in observation
    assert "scaled:" not in observation


@pytest.mark.anyio
async def test_graph_stops_at_max_tool_calls_without_extra_llm_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """should_continue ends the graph at == max_calls (no wasted LLM turn).

    验证：到达 max_tool_calls 时 should_continue 直接结束图，不再多跑一轮 LLM。
    """
    from opspilot.config import get_settings

    monkeypatch.setenv("OPSPILOT_AGENT_MAX_TOOL_CALLS", "2")
    get_settings.cache_clear()

    llm_calls: list[int] = []

    class _StubLLM:
        async def chat(self, messages: list[dict[str, str]]) -> str:
            llm_calls.append(len(messages))
            return "Thought: x\nAction: get_pod_status\nAction Input: default"

    try:
        await run_react_graph("test", _StubLLM(), max_steps=10)
        # 2 tool calls max → 2 LLM turns that produced Actions, no 3rd wasted turn.
        # With the old `>` boundary, this would be 3 (one extra wasted turn).
        assert len(llm_calls) == 2, f"expected exactly 2 LLM turns, got {len(llm_calls)}"
    finally:
        get_settings.cache_clear()
