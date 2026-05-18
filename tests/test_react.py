import pytest

from opspilot.agent.react import run_react


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
