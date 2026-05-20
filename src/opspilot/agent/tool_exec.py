"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: tool_exec.py
@DateTime: 2026-05-20
@Docs: Unified guarded tool execution chokepoint for every agent.
    统一受控工具执行入口，供所有智能体共用。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import opspilot.tools  # noqa: F401 - register built-in tools before execution
from opspilot.agent.confirmation import STORE, ConfirmationStore
from opspilot.agent.guardrails import is_dangerous, redact
from opspilot.observability.audit import record_operation
from opspilot.observability.metrics import record_guardrail_block
from opspilot.tools.kubectl_write import rollback_info_for
from opspilot.tools.registry import call_tool

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuardedResult:
    """Result of a guarded tool invocation.
    受控工具调用的执行结果。

    Attributes:
        observation: Redacted tool output or block message for the agent.
            脱敏后的工具输出或拦截提示，供智能体观测。
        blocked: True when the call was not executed (cap, danger, pending).
            为 True 表示未实际执行（超限、危险、待确认）。
        request_id: Pending confirmation id when blocked for HITL, else None.
            因人工确认被拦截时的 request_id，否则为 None。
    """

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
    allowed_tools: set[str] | None = None,
    confirmation_context: dict[str, str] | None = None,
) -> GuardedResult:
    """All-in-one safety gate: cap, danger check, HITL, audit, execute, redact.
    一体化安全门：调用上限、危险判定、人工确认、审计、执行、脱敏。

    Args:
        tool_name: Registered tool name.
            已注册的工具名称。
        raw_input: Raw Action Input string.
            Action Input 原始字符串。
        calls: Current tool call count (1-based for this attempt).
            当前工具调用次数（本次尝试为第几次）。
        max_calls: Maximum allowed tool calls per run.
            单次运行允许的最大工具调用次数。
        store: Confirmation store; defaults to process-wide STORE.
            确认状态存储；默认使用进程级 STORE。
        confirmed_request_id: Prior HITL approval id to allow dangerous ops.
            已获批的危险操作 request_id。
        audit_path: Optional audit log file path.
            可选审计日志文件路径。
        actor: Actor label recorded in audit entries.
            审计记录中的操作者标识。
        allowed_tools: Optional hard allowlist of tool names; calls outside it
            are rejected at this chokepoint regardless of prompt content.
            可选的工具名硬白名单；不在其中的调用在此入口被拒绝，不依赖提示词过滤。
        confirmation_context: Optional channel-bound context
            (channel/chat_id/requester) recorded on new pending confirmations
            and checked when consuming an existing approval. Prevents approvals
            from one chat being replayed against a tool call originating
            elsewhere.
            可选渠道绑定上下文（channel/chat_id/requester）：登记新待确认时写入、
            消费既有审批时校验，防止跨会话越权放行。

    Returns:
        GuardedResult with observation and blocked flag.
            含 observation 与 blocked 标志的 GuardedResult。
    """
    store = store if store is not None else STORE

    if allowed_tools is not None and tool_name not in allowed_tools:
        record_guardrail_block(tool_name)
        return GuardedResult(
            observation=f"Tool {tool_name} is not allowed in this agent context.",
            blocked=True,
        )

    if calls > max_calls:
        return GuardedResult(
            observation=f"工具调用次数已达上限（{max_calls}），请直接给出 Final Answer。",
            blocked=True,
        )

    if is_dangerous(tool_name, raw_input):
        # 已有人工确认 → 先只读校验 → 写 approved 审计（fail-closed）→ 消费 → 执行
        if confirmed_request_id is not None:
            confirmer = store.confirmed_actor_if_matches(
                confirmed_request_id,
                tool_name,
                raw_input,
                context=confirmation_context,
            )
            if confirmer is not None:
                rollback = rollback_info_for(tool_name, raw_input)
                # STEP A: approved-status audit must be persisted before we
                # consume the confirmation token. If the audit write fails we
                # abort the operation and leave the confirmation intact so
                # the operator can retry without re-issuing a new approval.
                # Catch broadly (Exception) on purpose: any backend failure
                # — including non-OSError surprises from mocked/monkey-patched
                # record_operation in tests — must trigger fail-closed.
                try:
                    record_operation(
                        tool=tool_name,
                        tool_input=raw_input,
                        actor=actor,
                        confirmed_by=confirmer,
                        status="approved",
                        result="approved for execution",
                        rollback=rollback,
                        path=audit_path,
                        fail_closed=True,
                    )
                except Exception:
                    logger.exception("approved-audit write failed; high-risk op aborted")
                    return GuardedResult(
                        observation=("Audit log is unavailable; high-risk operation was not executed."),
                        blocked=True,
                    )
                # STEP B: consume only after the approved audit is safely on disk.
                consume_actor = store.consume_if_matches(
                    confirmed_request_id,
                    tool_name,
                    raw_input,
                    context=confirmation_context,
                )
                if consume_actor is None:
                    # Race: another caller consumed between our check and our consume.
                    return GuardedResult(
                        observation=(
                            "Confirmation expired or was already consumed; high-risk operation was not executed."
                        ),
                        blocked=True,
                    )
                # STEP C: execute + executed-audit (best-effort; op already ran).
                observation = redact(call_tool(tool_name, raw_input))
                record_operation(
                    tool=tool_name,
                    tool_input=raw_input,
                    actor=actor,
                    confirmed_by=consume_actor,
                    status="executed",
                    result=observation,
                    rollback=rollback,
                    path=audit_path,
                )
                return GuardedResult(observation=observation, blocked=False)

        # 无确认 → 登记 pending，拦截
        record_guardrail_block(tool_name)
        pc = store.request(tool_name, raw_input, context=confirmation_context)
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
