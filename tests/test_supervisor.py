"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_supervisor.py
@DateTime: 2026-05-20
@Docs: Tests multi-agent supervisor routing.
    测试多智能体 Supervisor 路由。
"""

import pytest

from opspilot.agent.confirmation import STORE
from opspilot.agent.supervisor import run_supervisor


class FakeLLM:
    """Scripted replies: first call = classify, subsequent = sub-agent work."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append([dict(m) for m in messages])
        return self._replies.pop(0)


@pytest.mark.anyio
async def test_supervisor_routes_log_query_to_log_analyzer():
    """Supervisor classifies a log query -> routes to Log Analyzer."""
    llm = FakeLLM(
        [
            # classify: this is a log query
            "INTENT: log_analyzer",
            # log_analyzer: ReAct
            "Action: query_loki\nAction Input: user-service",
            # log_analyzer: Final Answer
            "Final Answer: 发现 user-service 有 23 次 NullPointerException。",
        ]
    )
    answer = await run_supervisor("查一下 user-service 的错误日志", llm)
    assert "NullPointerException" in answer


@pytest.mark.anyio
async def test_supervisor_routes_k8s_query_to_k8s_operator():
    """Supervisor classifies a K8s ops query -> routes to K8s Operator.

    run_plan_execute makes 3 internal LLM calls (planner, executor, replan),
    so this test provides 4 replies total (1 classify + 3 plan-execute).
    """
    llm = FakeLLM(
        [
            # 1. classify
            "INTENT: k8s_operator",
            # 2. plan_execute: planner (won't match plan regex,
            #    falls back to question as single step)
            "Plan: just check the service status",
            # 3. plan_execute: executor
            "Final Answer: order-service 处于 CrashLoopBackOff。",
            # 4. plan_execute: replan
            "DONE",
        ]
    )
    answer = await run_supervisor("order-service 状态怎么样", llm)
    assert "CrashLoopBackOff" in answer


@pytest.mark.anyio
async def test_supervisor_unknown_intent_falls_back_to_react():
    """Unknown intent -> falls back to generic ReAct."""
    llm = FakeLLM(
        [
            "INTENT: unknown",
            "Action: kubectl_get\nAction Input: pods",
            "Final Answer: 当前有 3 个 pod 运行正常。",
        ]
    )
    # Even with unknown intent, should produce an answer via fallback
    answer = await run_supervisor("hello", llm)
    assert len(answer) > 0


@pytest.mark.anyio
async def test_supervisor_k8s_operator_propagates_confirmed_request_id():
    """
    Verify supervisor k8s operator propagates confirmed request id.

    验证：supervisor k8s operator propagates confirmed request id。
    """
    raw = '{"deployment":"user-service","replicas":0}'
    pc = STORE.request("kubectl_scale", raw)
    assert STORE.confirm(pc.request_id, pc.token, actor="feishu:ou_42") is True
    llm = FakeLLM(
        [
            "INTENT: k8s_operator",
            "1. scale user-service",
            f"Action: kubectl_scale\nAction Input: {raw}",
            "DONE",
        ]
    )

    answer = await run_supervisor("scale user-service to zero", llm, confirmed_request_id=pc.request_id)

    assert "scaled:" in answer
    assert STORE.is_confirmed(pc.request_id) is False
