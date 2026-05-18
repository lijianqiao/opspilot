"""Plan-Execute agent as a LangGraph StateGraph.

Planner -> Executor (per step, reuses tool registry) -> Replan.
Sibling of langgraph_agent.py (ReAct). Same _current_llm ContextVar
pattern, same regex tool protocol, same guardrail-aware execution.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Annotated, Any, Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from opspilot.agent.guardrails import is_dangerous, redact
from opspilot.config import get_settings
from opspilot.tools.registry import build_tools_prompt, call_tool

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


def _llm() -> SupportsChat:
    llm = _current_llm.get(None)
    if llm is None:
        raise RuntimeError("LLM not set. Call run_plan_execute().")
    return llm


async def planner_node(state: PlanState) -> dict[str, Any]:
    prompt = (
        f"你是运维助手 OpsPilot 的规划器。把用户任务拆成有序步骤，"
        f"每行一个步骤，形如 `1. ...`。任务：{state['question']}"
    )
    reply = await _llm().chat([{"role": "user", "content": prompt}])
    plan = [m.group(1).strip() for m in _STEP_RE.finditer(reply)]
    if not plan:
        plan = [state["question"]]
    return {"plan": plan, "cursor": 0}


async def executor_node(state: PlanState) -> dict[str, Any]:
    step = state["plan"][state["cursor"]]
    sys = f"你是运维助手 OpsPilot。\n\n{build_tools_prompt()}"
    reply = await _llm().chat(
        [
            {"role": "system", "content": sys},
            {"role": "user", "content": f"执行这一步并给出 Final Answer：{step}"},
        ]
    )
    calls = state["tool_calls"]
    if (action := _ACTION_RE.search(reply)) is not None:
        calls += 1
        arg = _ACTION_INPUT_RE.search(reply)
        raw = arg.group(1).strip() if arg else ""
        tool_name = action.group(1)
        if calls > get_settings().agent_max_tool_calls:
            obs = "工具调用次数已达上限。"
        elif is_dangerous(tool_name, raw):
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
    # Guard: if we already hit max steps, stop before calling LLM.
    if state["steps_taken"] >= state["max_steps"]:
        last = state["results"][-1]["result"] if state["results"] else "任务未完成。"
        return {"final": f"达到最大步数，任务未完成。{last}"}
    summary = "\n".join(f"- {r['step']}: {r['result']}" for r in state["results"])
    reply = await _llm().chat(
        [
            {
                "role": "user",
                "content": (
                    f"任务：{state['question']}\n已完成：\n{summary}\n"
                    "如果任务已完成，回复以 DONE 开头并给出最终答案；"
                    "如果还需要更多步骤，只回复 REPLAN。"
                ),
            }
        ]
    )
    if reply.strip().upper().startswith("REPLAN"):
        return {"final": ""}
    final = reply.strip()
    if final.upper().startswith("DONE"):
        final = final[4:].strip(" :：\n") or (state["results"][-1]["result"] if state["results"] else "")
    return {"final": final or (state["results"][-1]["result"] if state["results"] else "")}


def _route_after_executor(state: PlanState) -> str:
    if state["steps_taken"] >= state["max_steps"]:
        return "stop"
    if state["cursor"] >= len(state["plan"]):
        return "replan"
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


async def run_plan_execute(question: str, llm: SupportsChat, max_steps: int = 8) -> str:
    """Run the Plan-Execute loop. API-shaped like run_react_graph()."""
    _current_llm.set(llm)
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
