"""Plan-Execute agent as a LangGraph StateGraph.

Planner -> Executor (per step, reuses tool registry) -> Replan.
Sibling of langgraph_agent.py (ReAct). Same _current_llm ContextVar
pattern, same regex tool protocol, same guardrail-aware execution.
"""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from typing import Annotated, Any, Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from opspilot.agent.guardrails import is_dangerous, redact
from opspilot.config import get_settings
from opspilot.observability.metrics import record_guardrail_block
from opspilot.tools.registry import build_tools_prompt, call_tool

logger = logging.getLogger(__name__)

_ACTION_RE = re.compile(r"Action:\s*(\S+)")
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.*)", re.DOTALL)
_FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)
_STEP_RE = re.compile(r"^\s*\d+[.)]\s*(.+)$", re.MULTILINE)


class SupportsChat(Protocol):
    async def chat(self, messages: list[dict[str, str]]) -> str: ...


def _append(left: list[dict[str, str]], right: list[dict[str, str]]) -> list[dict[str, str]]:
    return left + right


class PlanState(TypedDict):
    question: str
    plan: list[str]
    cursor: int
    results: Annotated[list[dict[str, str]], _append]
    final: str
    steps_taken: int
    max_steps: int
    tool_calls: int


_current_llm: ContextVar[SupportsChat] = ContextVar("_pe_current_llm")
_pe_tool_filter: ContextVar[set[str] | None] = ContextVar("_pe_tool_filter", default=None)


def _llm() -> SupportsChat:
    llm = _current_llm.get(None)
    if llm is None:
        raise RuntimeError("LLM not set. Call run_plan_execute().")
    return llm


async def planner_node(state: PlanState) -> dict[str, Any]:
    prompt = (
        f"你是运维助手 OpsPilot 的规划器。请把用户任务拆成有序的执行步骤。\n\n"
        f"要求：\n"
        f"- 每个步骤应该是可独立执行的具体操作（如查询状态、检查日志、分析指标）\n"
        f"- 步骤之间有逻辑顺序，先收集信息再分析总结\n"
        f"- 最后一步通常是汇总结果并给出结论\n"
        f"- 步骤数量根据任务复杂度决定，简单任务 2-3 步，复杂任务可适当增加\n\n"
        f"格式：每行一个步骤，形如 `1. 查看 default 命名空间的 pod 状态`\n\n"
        f"任务：{state['question']}"
    )
    reply = await _llm().chat([{"role": "user", "content": prompt}])
    logger.info("Planner reply: %s", reply[:300])
    plan = [m.group(1).strip() for m in _STEP_RE.finditer(reply)]
    if not plan:
        plan = [state["question"]]
    logger.info("Parsed plan (%d steps): %s", len(plan), plan)
    return {"plan": plan, "cursor": 0}


async def executor_node(state: PlanState) -> dict[str, Any]:
    step = state["plan"][state["cursor"]]
    sys = f"你是运维助手 OpsPilot。\n\n{build_tools_prompt(tool_filter=_pe_tool_filter.get())}"
    reply = await _llm().chat(
        [
            {"role": "system", "content": sys},
            {
                "role": "user",
                "content": (
                    f"请执行以下任务，直接调用合适的工具获取信息。\n\n"
                    f"任务：{step}\n\n"
                    f"请直接输出 Action 和 Action Input 来调用工具，或直接输出 Final Answer。"
                    f"不要输出思考过程，不要输出模板，直接行动。"
                ),
            },
        ]
    )
    logger.info("Executor reply (step %d): %s", state["cursor"], reply[:300])
    calls = state["tool_calls"]
    if (action := _ACTION_RE.search(reply)) is not None:
        calls += 1
        arg = _ACTION_INPUT_RE.search(reply)
        raw = arg.group(1).strip() if arg else ""
        tool_name = action.group(1)
        if calls > get_settings().agent_max_tool_calls:
            obs = "工具调用次数已达上限。"
        elif is_dangerous(tool_name, raw):
            record_guardrail_block(tool_name)
            obs = f"危险操作被拦截，需人工确认：{tool_name} {raw}（confirm_dangerous_op token=CONFIRM 放行）"
        else:
            obs = redact(call_tool(tool_name, raw))
        result = obs
    elif (final := _FINAL_RE.search(reply)) is not None:
        result = final.group(1).strip()
    else:
        result = reply.strip()
    return {
        "results": [{"step": step, "result": result}],
        "cursor": state["cursor"] + 1,
        "steps_taken": state["steps_taken"] + 1,
        "tool_calls": calls,
    }


async def replan_node(state: PlanState) -> dict[str, Any]:
    summary = "\n".join(f"- {r['step']}: {r['result']}" for r in state["results"])
    reply = await _llm().chat(
        [
            {
                "role": "user",
                "content": (
                    f"任务：{state['question']}\n\n已完成的步骤：\n{summary}\n\n"
                    f"请只回复一个单词：DONE（如果任务已完成）或 REPLAN（如果需要更多步骤）。"
                    f"不要输出分析过程。如果回复 DONE，请在同一行后面跟上最终答案。"
                ),
            }
        ]
    )
    logger.info("Replan reply: %s", reply[:200])
    if reply.strip().upper().startswith("REPLAN"):
        return {"final": ""}
    final = reply.strip()
    if final.upper().startswith("DONE"):
        final = final[4:].strip(" :：\n") or (state["results"][-1]["result"] if state["results"] else "")
    return {"final": final or (state["results"][-1]["result"] if state["results"] else "")}


def _route_after_executor(state: PlanState) -> str:
    if state["steps_taken"] >= state["max_steps"]:
        logger.info("Route: max_steps reached (%d), stopping", state["steps_taken"])
        return "stop"
    if state["cursor"] >= len(state["plan"]):
        logger.info("Route: cursor >= plan length, going to replan")
        return "replan"
    logger.info("Route: more steps in plan, continuing execute")
    return "execute"


def _route_after_replan(state: PlanState) -> str:
    if state["steps_taken"] >= state["max_steps"]:
        return "stop"
    return "end" if state["final"] else "plan"


def _build_graph() -> Any:
    g = StateGraph(PlanState)
    g.add_node("plan", planner_node)
    g.add_node("execute", executor_node)
    g.add_node("replan", replan_node)
    g.add_edge(START, "plan")
    g.add_edge("plan", "execute")
    g.add_conditional_edges(
        "execute",
        _route_after_executor,
        {"execute": "execute", "replan": "replan", "stop": END},
    )
    g.add_conditional_edges("replan", _route_after_replan, {"plan": "plan", "end": END, "stop": END})
    return g.compile()


_compiled = _build_graph()


async def run_plan_execute(
    question: str, llm: SupportsChat, max_steps: int = 20, tool_filter: set[str] | None = None
) -> str:
    """Run the Plan-Execute loop. API-shaped like run_react_graph()."""
    _current_llm.set(llm)
    _pe_tool_filter.set(tool_filter)
    init: dict[str, Any] = {
        "question": question,
        "plan": [],
        "cursor": 0,
        "results": [],
        "final": "",
        "steps_taken": 0,
        "max_steps": max_steps,
        "tool_calls": 0,
    }
    result = await _compiled.ainvoke(init, config={"recursion_limit": 100})
    if result["final"]:
        return result["final"]
    if result["steps_taken"] >= max_steps:
        return "达到最大步数，任务未完成。" + (
            f"\n已完成：{result['results'][-1]['result']}" if result["results"] else ""
        )
    return result["results"][-1]["result"] if result["results"] else "无结果。"
