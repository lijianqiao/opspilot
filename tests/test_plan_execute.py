import pytest

from opspilot.agent.plan_execute import run_plan_execute


class FakeLLM:
    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append([dict(m) for m in messages])
        return self._replies.pop(0)


@pytest.mark.anyio
async def test_planner_then_executes_each_step_then_final() -> None:
    llm = FakeLLM(
        [
            # Planner: numbered steps (2 steps)
            "1. 查 user-service pod 状态\n2. 总结是否健康",
            # Executor step 1: tool call
            "Action: kubectl_get\nAction Input: pods",
            # Executor step 2: final answer
            "Final Answer: user-service 有 pod 处于 CrashLoopBackOff。",
            # Replan: done
            "DONE",
        ]
    )
    answer = await run_plan_execute("user-service 健康吗", llm, max_steps=6)
    assert "CrashLoopBackOff" in answer
    # planner produced 2 steps -> executor ran twice + replan once = 4 calls
    assert len(llm.calls) >= 3


@pytest.mark.anyio
async def test_replan_can_request_more_steps() -> None:
    # Call order: planner, executor, replan(REPLAN), planner, executor, replan(DONE)
    llm = FakeLLM(
        [
            "1. 第一步",  # planner (cycle 1)
            "Final Answer: 部分完成",  # executor (cycle 1)
            "REPLAN",  # replan -> routes back to plan
            "1. 追加步骤",  # planner (cycle 2)
            "Final Answer: 全部完成",  # executor (cycle 2)
            "DONE",  # replan -> done
        ]
    )
    answer = await run_plan_execute("多步任务", llm, max_steps=8)
    assert "全部完成" in answer


@pytest.mark.anyio
async def test_max_steps_guards_plan_execute() -> None:
    # Call order per cycle: planner, executor, replan.
    # With max_steps=3, _route_after_executor routes to END (not replan)
    # after the 3rd executor run because steps_taken=3 >= max_steps.
    # run_plan_execute's fallback returns the "达到最大步数" message.
    # Total LLM calls: 3 planners + 3 executors + 2 replans = 8.
    action = "Action: kubectl_get\nAction Input: pods"
    llm = FakeLLM(
        ["1. 永远做不完"]  # planner (cycle 1)
        + [action]  # executor (cycle 1)
        + ["REPLAN"]  # replan (cycle 1)
        + ["1. 永远做不完"]  # planner (cycle 2)
        + [action]  # executor (cycle 2)
        + ["REPLAN"]  # replan (cycle 2)
        + ["1. 永远做不完"]  # planner (cycle 3)
        + [action]  # executor (cycle 3)
        # _route_after_executor sends to END; replan is never entered
    )
    answer = await run_plan_execute("infinite", llm, max_steps=3)
    assert "达到最大" in answer
