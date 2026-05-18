"""Supervisor agent: classify intent and route to specialized sub-agents.

Architecture:
  START -> classify -> log_analyzer / k8s_operator / generic_react -> END

Each sub-agent node calls its own compiled graph internally, passing
a filtered tool prompt so each agent only sees its relevant tools.

Handoff: after a sub-agent returns, the Supervisor can dispatch to
another sub-agent if needed (e.g., Alert Handler calls Log Analyzer).
"""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from typing import Annotated, Any, Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from opspilot.agent.langgraph_agent import run_react_graph

logger = logging.getLogger(__name__)

_INTENT_RE = re.compile(r"INTENT:\s*(\S+)", re.IGNORECASE)

# Tool sets per agent type
_LOG_ANALYZER_TOOLS = {"query_loki", "kubectl_get", "query_prometheus", "aggregate_errors", "tail_pod_logs"}
_K8S_OPERATOR_TOOLS = {"kubectl_get", "kubectl_describe", "kubectl_scale",
                       "kubectl_rollout_restart", "confirm_dangerous_op", "query_prometheus"}
_GENERIC_TOOLS = {"get_pod_status", "kubectl_get", "kubectl_describe", "query_loki", "query_prometheus"}


class SupportsChat(Protocol):
    async def chat(self, messages: list[dict[str, str]]) -> str: ...


class SupervisorState(TypedDict):
    question: str
    intent: str
    final_answer: str


_current_llm: ContextVar[SupportsChat] = ContextVar("_sup_current_llm")


def _llm() -> SupportsChat:
    llm = _current_llm.get(None)
    if llm is None:
        raise RuntimeError("LLM not set. Call run_supervisor().")
    return llm


async def classify_node(state: SupervisorState) -> dict[str, Any]:
    """Classify user intent into one of: log_analyzer, k8s_operator, generic_react."""
    prompt = (
        "你是 OpsPilot 的意图分类器。分析用户消息，回复 INTENT: <类别>。\n\n"
        "类别定义：\n"
        "- log_analyzer: 查日志、错误统计、日志分析、查看 pod 日志\n"
        "- k8s_operator: K8s 资源操作、扩缩容、重启、describe、pod 状态\n"
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
    """Run the Log Analyzer sub-agent (ReAct with log tools)."""
    answer = await run_react_graph(state["question"], _llm(), tool_filter=_LOG_ANALYZER_TOOLS)
    return {"final_answer": answer}


async def k8s_operator_node(state: SupervisorState) -> dict[str, Any]:
    """Run the K8s Operator sub-agent (Plan-Execute with K8s tools)."""
    from opspilot.agent.plan_execute import run_plan_execute

    answer = await run_plan_execute(state["question"], _llm(), tool_filter=_K8S_OPERATOR_TOOLS)
    return {"final_answer": answer}


async def generic_react_node(state: SupervisorState) -> dict[str, Any]:
    """Fallback: generic ReAct with general tools."""
    answer = await run_react_graph(state["question"], _llm(), tool_filter=_GENERIC_TOOLS)
    return {"final_answer": answer}


def _route_by_intent(state: SupervisorState) -> str:
    intent = state.get("intent", "generic_react")
    if intent == "log_analyzer":
        return "log_analyzer"
    if intent == "k8s_operator":
        return "k8s_operator"
    return "generic_react"


def _build_supervisor_graph() -> Any:
    g = StateGraph(SupervisorState)
    g.add_node("classify", classify_node)
    g.add_node("log_analyzer", log_analyzer_node)
    g.add_node("k8s_operator", k8s_operator_node)
    g.add_node("generic_react", generic_react_node)
    g.add_edge(START, "classify")
    g.add_conditional_edges(
        "classify",
        _route_by_intent,
        {
            "log_analyzer": "log_analyzer",
            "k8s_operator": "k8s_operator",
            "generic_react": "generic_react",
        },
    )
    g.add_edge("log_analyzer", END)
    g.add_edge("k8s_operator", END)
    g.add_edge("generic_react", END)
    return g.compile()


_compiled_supervisor = _build_supervisor_graph()


async def run_supervisor(question: str, llm: SupportsChat) -> str:
    """Run the Supervisor: classify intent -> dispatch to sub-agent.

    API-compatible with run_react_graph() — same (question, llm) signature.
    """
    _current_llm.set(llm)
    init: dict[str, Any] = {"question": question, "intent": "", "final_answer": ""}
    result = await _compiled_supervisor.ainvoke(init, config={"recursion_limit": 50})
    return result.get("final_answer", "") or "未能得到最终答案。"
