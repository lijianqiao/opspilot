import os

import pytest

from opspilot.agent.langgraph_agent import build_checkpointed_runner


class FakeLLM:
    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self.calls = 0

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        return self._replies.pop(0)


@pytest.mark.anyio
async def test_checkpoint_preserves_message_history() -> None:
    from langgraph.checkpoint.memory import InMemorySaver

    run = build_checkpointed_runner(InMemorySaver())

    llm1 = FakeLLM(["Final Answer: 第一轮：user-service 有 3 个 pod。"])
    a1 = await run("user-service 几个 pod", llm1, thread_id="chatA")
    assert "3 个 pod" in a1

    # second turn, same thread -> prior messages are in the checkpoint,
    # so the new question sees history (the LLM receives >2 messages)
    seen: dict[str, int] = {}

    class CountingLLM:
        async def chat(self, messages: list[dict[str, str]]) -> str:
            seen["n"] = len(messages)
            return "Final Answer: 续上文。"

    a2 = await run("它健康吗", CountingLLM(), thread_id="chatA")
    assert "续上文" in a2
    assert seen["n"] > 2  # history from turn 1 was restored from checkpoint

    # different thread starts fresh
    seen2: dict[str, int] = {}

    class CountingLLM2:
        async def chat(self, messages: list[dict[str, str]]) -> str:
            seen2["n"] = len(messages)
            return "Final Answer: 新会话。"

    await run("无关问题", CountingLLM2(), thread_id="chatB")
    assert seen2["n"] == 2  # system + user only, no chatA history


@pytest.mark.skipif(
    not os.getenv("OPSPILOT_PG_DSN"),
    reason="set OPSPILOT_PG_DSN to run the Postgres integration test",
)
@pytest.mark.anyio
async def test_postgres_checkpointer_smoke() -> None:
    from opspilot.agent.langgraph_agent import build_postgres_runner

    run, cm = build_postgres_runner(os.environ["OPSPILOT_PG_DSN"])
    try:
        llm = FakeLLM(["Final Answer: pg ok"])
        out = await run("ping", llm, thread_id="pg-smoke")
        assert "pg ok" in out
    finally:
        cm.__exit__(None, None, None)
