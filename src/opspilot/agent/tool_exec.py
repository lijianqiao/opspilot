"""Unified guarded tool execution — single chokepoint for every agent.

合并原本在 langgraph_agent.tool_node 与 plan_execute.executor_node 重复的逻辑：
  调用上限 → 危险判定 → 人工确认门（ConfirmationStore）→ 审计 → 执行 → redact。
任何 agent 执行工具都必须走这里，确保安全策略只有一处实现。
"""

from __future__ import annotations

from dataclasses import dataclass

from opspilot.agent.confirmation import STORE, ConfirmationStore
from opspilot.agent.guardrails import is_dangerous, redact
from opspilot.observability.audit import record_operation
from opspilot.observability.metrics import record_guardrail_block
from opspilot.tools.kubectl_write import rollback_info_for
from opspilot.tools.registry import call_tool


@dataclass(frozen=True)
class GuardedResult:
    observation: str
    blocked: bool
    request_id: str | None = None


def guarded_call_tool(
    tool_name: str,
    raw_input: str,
    *,
    calls: int,
    max_calls: int,
    store: ConfirmationStore | None = None,
    confirmed_request_id: str | None = None,
    audit_path: str | None = None,
    actor: str = "agent",
) -> GuardedResult:
    """All-in-one safety gate: cap → danger check → HITL → audit → execute → redact."""
    store = store if store is not None else STORE

    if calls > max_calls:
        return GuardedResult(
            observation=f"工具调用次数已达上限（{max_calls}），请直接给出 Final Answer。",
            blocked=True,
        )

    if is_dangerous(tool_name, raw_input):
        # 已有人工确认 → 放行执行
        if confirmed_request_id is not None and store.is_confirmed(confirmed_request_id):
            confirmer = store.consume(confirmed_request_id)
            rollback = rollback_info_for(tool_name, raw_input)
            observation = redact(call_tool(tool_name, raw_input))
            record_operation(
                tool=tool_name,
                tool_input=raw_input,
                actor=actor,
                confirmed_by=confirmer,
                status="executed",
                result=observation,
                rollback=rollback,
                path=audit_path,
            )
            return GuardedResult(observation=observation, blocked=False)

        # 无确认 → 登记 pending，拦截
        record_guardrail_block(tool_name)
        pc = store.request(tool_name, raw_input)
        record_operation(
            tool=tool_name,
            tool_input=raw_input,
            actor=actor,
            confirmed_by=None,
            status="blocked",
            result="awaiting human confirmation",
            rollback=rollback_info_for(tool_name, raw_input),
            path=audit_path,
        )
        return GuardedResult(
            observation=(
                f"危险操作被拦截，需人工确认：{tool_name} {raw_input}。"
                f"已生成确认请求 request_id={pc.request_id}，等待运维人员通过审批通道放行。"
                "未经人工确认不会执行，请勿尝试自行放行。"
            ),
            blocked=True,
            request_id=pc.request_id,
        )

    # 安全工具：直接执行 + 审计 + redact
    observation = redact(call_tool(tool_name, raw_input))
    record_operation(
        tool=tool_name,
        tool_input=raw_input,
        actor=actor,
        confirmed_by=None,
        status="executed",
        result=observation,
        rollback=None,
        path=audit_path,
    )
    return GuardedResult(observation=observation, blocked=False)
