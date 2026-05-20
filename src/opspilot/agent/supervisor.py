"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: supervisor.py
@DateTime: 2026-05-20
@Docs: Supervisor agent: classify intent and route to sub-agents.
    监督者智能体：意图分类并路由到专用子智能体。
"""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from opspilot.agent.langgraph_agent import run_react_graph
from opspilot.agent.protocols import SupportsChat

logger = logging.getLogger(__name__)

_INTENT_RE = re.compile(r"INTENT:\s*(\S+)", re.IGNORECASE)

# Tool sets per agent type
_LOG_ANALYZER_TOOLS = {"query_loki", "kubectl_get", "query_prometheus", "aggregate_errors", "tail_pod_logs"}
_OPS_OPERATOR_TOOLS = {
    "kubectl_get",
    "kubectl_describe",
    "kubectl_scale",
    "kubectl_rollout_restart",
    "confirm_dangerous_op",
    "query_prometheus",
    "restart_service",
    "scale_service",
    "run_remediation",
}
_GENERIC_TOOLS = {"get_pod_status", "kubectl_get", "kubectl_describe", "query_loki", "query_prometheus"}


class SupervisorState(TypedDict):
    """LangGraph state for the supervisor routing graph.
    监督者路由图的 LangGraph 状态。

    Attributes:
        question: Original user message.
            用户原始消息。
        intent: Classified intent label (log_analyzer, ops_operator, generic_react).
            分类后的意图标签。
        final_answer: Sub-agent result returned to the caller.
            子智能体返回给调用方的最终答案。
    """

    question: str
    confirmed_request_id: str | None
    intent: str
    final_answer: str


_current_llm: ContextVar[SupportsChat] = ContextVar("_sup_current_llm")


def _llm() -> SupportsChat:
    llm = _current_llm.get(None)
    if llm is None:
        raise RuntimeError("LLM not set. Call run_supervisor().")
    return llm


async def classify_node(state: SupervisorState) -> dict[str, Any]:
    """Classify user intent into log_analyzer, ops_operator, or generic_react.
    将用户意图分类为 log_analyzer、ops_operator 或 generic_react。

    Args:
        state: Current supervisor state with question.
            含 question 的当前监督者状态。

    Returns:
        State update dict with intent field.
            含 intent 字段的状态更新字典。
    """
    prompt = (
        "你是 OpsPilot 的意图分类器。分析用户消息，回复 INTENT: <类别>。\n\n"
        "类别定义：\n"
        "- log_analyzer: 查日志、错误统计、日志分析、查看 pod 日志\n"
        "- ops_operator: 服务/基础设施动作（重启、扩缩容、补救、发布操作），以及 K8s 资源操作\n"
        "- generic_react: 其他运维问题或不清楚意图\n\n"
        f"用户消息：{state['question']}\n\n"
        "只回复 INTENT: <类别>，不要输出其他内容。"
    )
    reply = await _llm().chat([{"role": "user", "content": prompt}])
    logger.info("Classification reply: %s", reply[:100])
    match = _INTENT_RE.search(reply)
    intent = match.group(1).strip().lower() if match else "generic_react"
    return {"intent": intent}


async def log_analyzer_node(state: SupervisorState) -> dict[str, Any]:
    """Run the Log Analyzer sub-agent (ReAct with log-focused tools).
    运行日志分析子智能体（ReAct，仅日志相关工具）。

    Args:
        state: Supervisor state with question.
            含 question 的监督者状态。

    Returns:
        State update with final_answer from the sub-agent.
            含子智能体 final_answer 的状态更新。
    """
    answer = await run_react_graph(
        state["question"],
        _llm(),
        tool_filter=_LOG_ANALYZER_TOOLS,
        confirmed_request_id=state.get("confirmed_request_id"),
    )
    return {"final_answer": answer}


async def ops_operator_node(state: SupervisorState) -> dict[str, Any]:
    """Run the Ops Operator sub-agent (Plan-Execute with service/infra action tools).
    运行运维操作子智能体（Plan-Execute，服务/基础设施动作工具集）。

    Args:
        state: Supervisor state with question.
            含 question 的监督者状态。

    Returns:
        State update with final_answer from Plan-Execute.
            含 Plan-Execute 返回的 final_answer 的状态更新。
    """
    from opspilot.agent.plan_execute import run_plan_execute

    answer = await run_plan_execute(
        state["question"],
        _llm(),
        tool_filter=_OPS_OPERATOR_TOOLS,
        confirmed_request_id=state.get("confirmed_request_id"),
    )
    return {"final_answer": answer}


async def generic_react_node(state: SupervisorState) -> dict[str, Any]:
    """Fallback generic ReAct sub-agent with general-purpose tools.
    回退通用 ReAct 子智能体，使用通用运维工具集。

    Args:
        state: Supervisor state with question.
            含 question 的监督者状态。

    Returns:
        State update with final_answer from ReAct.
            含 ReAct 返回的 final_answer 的状态更新。
    """
    answer = await run_react_graph(
        state["question"],
        _llm(),
        tool_filter=_GENERIC_TOOLS,
        confirmed_request_id=state.get("confirmed_request_id"),
    )
    return {"final_answer": answer}


def _route_by_intent(state: SupervisorState) -> str:
    intent = state.get("intent", "generic_react")
    if intent == "log_analyzer":
        return "log_analyzer"
    # Backwards-compatible: accept legacy "k8s_operator" label.
    if intent in {"ops_operator", "k8s_operator"}:
        return "ops_operator"
    return "generic_react"


def _build_supervisor_graph() -> Any:
    g = StateGraph(SupervisorState)
    g.add_node("classify", classify_node)
    g.add_node("log_analyzer", log_analyzer_node)
    g.add_node("ops_operator", ops_operator_node)
    g.add_node("generic_react", generic_react_node)
    g.add_edge(START, "classify")
    g.add_conditional_edges(
        "classify",
        _route_by_intent,
        {
            "log_analyzer": "log_analyzer",
            "ops_operator": "ops_operator",
            "generic_react": "generic_react",
        },
    )
    g.add_edge("log_analyzer", END)
    g.add_edge("ops_operator", END)
    g.add_edge("generic_react", END)
    return g.compile()


_compiled_supervisor = _build_supervisor_graph()


async def run_supervisor(question: str, llm: SupportsChat, confirmed_request_id: str | None = None) -> str:
    """Run supervisor: classify intent then dispatch to a sub-agent.
    运行监督者：分类意图后分派到对应子智能体。

    API-compatible with run_react_graph — same (question, llm) signature.

    Args:
        question: User question or task.
            用户问题或任务。
        llm: Chat backend implementing SupportsChat.
            实现 SupportsChat 的对话后端。

    Returns:
        Sub-agent final answer text.
            子智能体返回的最终答案文本。
    """
    _current_llm.set(llm)
    init: dict[str, Any] = {
        "question": question,
        "confirmed_request_id": confirmed_request_id,
        "intent": "",
        "final_answer": "",
    }
    result = await _compiled_supervisor.ainvoke(init, config={"recursion_limit": 50})
    return result.get("final_answer", "") or "未能得到最终答案。"
