"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: plan_execute.py
@DateTime: 2026-05-20
@Docs: Plan-Execute agent as LangGraph: plan, execute, replan.
    Plan-Execute 智能体：规划、执行、再规划的 LangGraph 实现。
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Annotated, Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from opspilot.agent.protocols import SupportsChat
from opspilot.agent.react_protocol import (
    STEP_RE as _STEP_RE,
)
from opspilot.agent.react_protocol import parse_react_output
from opspilot.agent.tool_exec import guarded_call_tool
from opspilot.config import get_settings
from opspilot.tools.registry import build_tools_prompt

logger = logging.getLogger(__name__)


def _append(left: list[dict[str, str]], right: list[dict[str, str]]) -> list[dict[str, str]]:
    return left + right


class PlanState(TypedDict):
    """LangGraph state for the Plan-Execute graph.
    Plan-Execute 图的 LangGraph 状态。

    Attributes:
        question: Original user task.
            用户原始任务。
        plan: Ordered list of step descriptions from the planner.
            规划器生成的有序步骤描述列表。
        cursor: Index of the next step to execute.
            下一个待执行步骤的索引。
        results: Accumulated per-step execution results.
            各步骤执行结果的累积列表。
        final: Synthesized final answer when replan decides DONE.
            再规划判定 DONE 时的综合最终答案。
        steps_taken: Number of executor iterations so far.
            已执行的执行器迭代次数。
        max_steps: Step budget before forced stop.
            强制停止前的步数预算。
        tool_calls: Tool invocations counted toward the cap.
            计入上限的工具调用次数。
    """

    question: str
    confirmed_request_id: str | None
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
    """LLM planner: decompose the user task into ordered executable steps.
    LLM 规划节点：将用户任务拆解为有序可执行步骤。

    Args:
        state: Plan state with question.
            含 question 的规划状态。

    Returns:
        State update with plan list and cursor reset to 0.
            含 plan 列表且 cursor 置 0 的状态更新。
    """
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
    """Execute one plan step via ReAct tool protocol and guarded_call_tool.
    通过 ReAct 工具协议与 guarded_call_tool 执行单个规划步骤。

    Args:
        state: Plan state with plan, cursor, and counters.
            含 plan、cursor 与计数器的规划状态。

    Returns:
        State update with one result row and advanced cursor.
            含一条 result 记录且 cursor 前进的状态更新。
    """
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
    parsed = parse_react_output(reply)
    calls = state["tool_calls"]
    if parsed.action is not None:
        calls += 1
        guarded = guarded_call_tool(
            parsed.action,
            parsed.action_input,
            calls=calls,
            max_calls=get_settings().agent_max_tool_calls,
            confirmed_request_id=state.get("confirmed_request_id"),
            allowed_tools=_pe_tool_filter.get(),
        )
        result = guarded.observation
    elif parsed.final is not None:
        result = parsed.final
    else:
        result = reply.strip()
    return {
        "results": [{"step": step, "result": result}],
        "cursor": state["cursor"] + 1,
        "steps_taken": state["steps_taken"] + 1,
        "tool_calls": calls,
    }


async def replan_node(state: PlanState) -> dict[str, Any]:
    """LLM replan: decide DONE with final answer or request more planning.
    LLM 再规划节点：判定 DONE 并给出最终答案，或要求继续规划。

    Args:
        state: Plan state with question and accumulated results.
            含 question 与累积 results 的规划状态。

    Returns:
        State update with final answer or empty final to trigger replan.
            含 final 答案或空 final 以触发再规划的状态更新。
    """
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
    question: str,
    llm: SupportsChat,
    max_steps: int = 20,
    tool_filter: set[str] | None = None,
    confirmed_request_id: str | None = None,
) -> str:
    """Run the Plan-Execute loop; API-shaped like run_react_graph().
    运行 Plan-Execute 循环；API 形态与 run_react_graph() 一致。

    Args:
        question: User task description.
            用户任务描述。
        llm: Chat backend implementing SupportsChat.
            实现 SupportsChat 的对话后端。
        max_steps: Maximum executor/replan iterations.
            执行器/再规划的最大迭代次数。
        tool_filter: Optional subset of tool names for the executor prompt.
            执行器提示中可选的工具名子集。

    Returns:
        Final synthesized answer or last step result / limit message.
            综合最终答案、最后一步结果或步数上限提示。
    """
    _current_llm.set(llm)
    token = _pe_tool_filter.set(tool_filter)
    init: dict[str, Any] = {
        "question": question,
        "confirmed_request_id": confirmed_request_id,
        "plan": [],
        "cursor": 0,
        "results": [],
        "final": "",
        "steps_taken": 0,
        "max_steps": max_steps,
        "tool_calls": 0,
    }
    try:
        result = await _compiled.ainvoke(init, config={"recursion_limit": 100})
    finally:
        _pe_tool_filter.reset(token)
    if result["final"]:
        return result["final"]
    if result["steps_taken"] >= max_steps:
        return "达到最大步数，任务未完成。" + (
            f"\n已完成：{result['results'][-1]['result']}" if result["results"] else ""
        )
    return result["results"][-1]["result"] if result["results"] else "无结果。"
