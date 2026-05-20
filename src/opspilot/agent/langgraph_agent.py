"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: langgraph_agent.py
@DateTime: 2026-05-20
@Docs: ReAct agent as LangGraph StateGraph with guarded tool execution.
    ReAct 智能体的 LangGraph 实现，集成受控工具执行。
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Annotated, Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from opspilot.agent.protocols import SupportsChat
from opspilot.agent.react_protocol import (
    ACTION_RE as _ACTION_RE,
)
from opspilot.agent.react_protocol import (
    FINAL_RE as _FINAL_RE,
)
from opspilot.agent.react_protocol import parse_react_output
from opspilot.agent.tool_exec import guarded_call_tool
from opspilot.config import get_settings
from opspilot.tools.registry import build_tools_prompt

logger = logging.getLogger(__name__)


# --- State ---


def _append_messages(left: list[dict[str, str]], right: list[dict[str, str]]) -> list[dict[str, str]]:
    """Reducer: append new messages to the existing list."""
    return left + right


class AgentState(TypedDict):
    """LangGraph state for the ReAct agent graph.
    ReAct 智能体图的 LangGraph 状态。

    Attributes:
        messages: Conversation history with append reducer.
            带追加归约器的对话历史。
        question: Original user question (informational).
            用户原始问题（信息字段）。
        steps_taken: LLM turns completed so far.
            已完成的 LLM 轮次数。
        max_steps: Maximum LLM turns before stop.
            停止前的最大 LLM 轮次数。
        tool_calls: Tool invocations counted toward the cap.
            计入上限的工具调用次数。
    """

    messages: Annotated[list[dict[str, str]], _append_messages]
    question: str
    confirmed_request_id: str | None
    steps_taken: int
    max_steps: int
    tool_calls: int
    allowed_tools: list[str] | None


# --- Nodes ---

# ContextVar for LLM reference — set by run_react_graph() before ainvoke().
# LangGraph StateGraph only processes keys declared in the schema, so we
# can't pass the LLM through state. ContextVar is async-safe: each
# concurrent task gets its own copy automatically.
_current_llm: ContextVar[SupportsChat] = ContextVar("_current_llm")


async def agent_node(state: AgentState) -> dict[str, Any]:
    """Call the LLM and append the assistant reply to messages.
    调用 LLM 并将助手回复追加到 messages。

    Args:
        state: Current agent state including messages.
            含 messages 的当前智能体状态。

    Returns:
        State update with one assistant message and incremented steps_taken.
            含一条助手消息且 steps_taken 加一的状态更新。
    """
    llm = _current_llm.get(None)
    if llm is None:
        raise RuntimeError("LLM not set. Call run_react_graph() which sets _current_llm.")

    messages = state["messages"]
    reply = await llm.chat(messages)
    return {
        "messages": [{"role": "assistant", "content": reply}],
        "steps_taken": state["steps_taken"] + 1,
    }


async def tool_node(state: AgentState) -> dict[str, Any]:
    """Parse Action and run guarded_call_tool; append Observation message.
    解析 Action 并经 guarded_call_tool 执行；追加 Observation 消息。

    Args:
        state: Agent state with latest assistant message.
            含最新助手消息的智能体状态。

    Returns:
        State update with Observation user message and tool_calls count.
            含 Observation 用户消息与 tool_calls 计数的状态更新。
    """
    last_msg = state["messages"][-1]["content"]
    parsed = parse_react_output(last_msg)
    if parsed.action is None:
        return {
            "messages": [{"role": "user", "content": "Observation: 未检测到 Action。"}],
            "tool_calls": state["tool_calls"],
        }
    calls = state["tool_calls"] + 1
    allowed = state.get("allowed_tools")
    allowed_tools = set(allowed) if allowed is not None else None
    result = guarded_call_tool(
        parsed.action,
        parsed.action_input,
        calls=calls,
        max_calls=get_settings().agent_max_tool_calls,
        confirmed_request_id=state.get("confirmed_request_id"),
        allowed_tools=allowed_tools,
    )
    return {
        "messages": [{"role": "user", "content": f"Observation: {result.observation}"}],
        "tool_calls": calls,
    }


# --- Conditional edge ---


def should_continue(state: AgentState) -> str:
    """Route to tools, end on Final Answer, or end on limits / no Action.
    路由到 tools、因 Final Answer 结束，或因上限/无 Action 结束。

    Args:
        state: Current agent state.
            当前智能体状态。

    Returns:
        Edge label "tools" or "end".
            边标签 "tools" 或 "end"。
    """
    if state["tool_calls"] > get_settings().agent_max_tool_calls:
        return "end"

    if state["steps_taken"] >= state["max_steps"]:
        return "end"

    last_msg = state["messages"][-1]["content"]

    if _FINAL_RE.search(last_msg):
        return "end"

    if _ACTION_RE.search(last_msg):
        return "tools"

    # No Action and no Final Answer → treat as final
    return "end"


# --- Graph construction ---


def _build_graph(checkpointer: Any | None = None) -> Any:
    """Build the ReAct StateGraph. Optional checkpointer enables memory."""
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "agent")
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


# Compiled graph instance (module-level singleton)
_compiled_graph = _build_graph()


async def run_react_graph(
    question: str,
    llm: SupportsChat,
    max_steps: int = 5,
    tool_filter: set[str] | None = None,
    confirmed_request_id: str | None = None,
) -> str:
    """Run the ReAct loop via LangGraph StateGraph.
    通过 LangGraph StateGraph 运行 ReAct 循环。

    API-compatible with run_react() from react.py.

    Args:
        question: User question or task.
            用户问题或任务。
        llm: Chat backend implementing SupportsChat.
            实现 SupportsChat 的对话后端。
        max_steps: Maximum LLM turns.
            最大 LLM 轮次数。
        tool_filter: Optional tool name subset for the system prompt.
            系统提示中可选的工具名子集。

    Returns:
        Final Answer text or step/limit message.
            Final Answer 文本或步数/上限提示。
    """
    system_prompt = f"你是运维助手 OpsPilot。\n\n{build_tools_prompt(tool_filter=tool_filter)}"

    _current_llm.set(llm)

    initial_state: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        "question": question,
        "confirmed_request_id": confirmed_request_id,
        "steps_taken": 0,
        "max_steps": max_steps,
        "tool_calls": 0,
        "allowed_tools": sorted(tool_filter) if tool_filter else None,
    }

    result = await _compiled_graph.ainvoke(initial_state)

    if result.get("tool_calls", 0) > get_settings().agent_max_tool_calls:
        for msg in reversed(result["messages"]):
            if msg["role"] == "assistant" and (final := _FINAL_RE.search(msg["content"])):
                return final.group(1).strip()
        return "工具调用次数已达上限，已停止。"

    # Check if we hit max steps without a Final Answer
    if result["steps_taken"] >= max_steps:
        last_assistant = None
        for msg in reversed(result["messages"]):
            if msg["role"] == "assistant":
                last_assistant = msg["content"]
                break
        if last_assistant is None or not _FINAL_RE.search(last_assistant):
            return "达到最大推理步数，未能得到最终答案。"

    # Extract final answer from last assistant message
    for msg in reversed(result["messages"]):
        if msg["role"] == "assistant":
            content = msg["content"]
            if final := _FINAL_RE.search(content):
                return final.group(1).strip()
            return content.strip()

    return "未能得到最终答案。"


def build_checkpointed_runner(checkpointer: Any) -> Any:
    """Return async run() bound to a checkpointer, keyed by thread_id.
    返回绑定 checkpointer 的 async run()，按 thread_id 恢复会话。

    Args:
        checkpointer: LangGraph checkpointer instance.
            LangGraph checkpointer 实例。

    Returns:
        Async callable (question, llm, thread_id, max_steps) -> str.
            异步可调用对象 (question, llm, thread_id, max_steps) -> str。
    """
    compiled = _build_graph(checkpointer)

    async def _run(question: str, llm: SupportsChat, thread_id: str, max_steps: int = 5) -> str:
        system_prompt = f"你是运维助手 OpsPilot。\n\n{build_tools_prompt()}"
        _current_llm.set(llm)
        config = {"configurable": {"thread_id": thread_id}}
        initial_state: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            "question": question,
            "confirmed_request_id": None,
            "steps_taken": 0,
            "max_steps": max_steps,
            "tool_calls": 0,
            "allowed_tools": None,
        }
        result = await compiled.ainvoke(initial_state, config=config)
        for msg in reversed(result["messages"]):
            if msg["role"] == "assistant":
                if final := _FINAL_RE.search(msg["content"]):
                    return final.group(1).strip()
                return msg["content"].strip()
        return "未能得到最终答案。"

    return _run


def build_postgres_runner(dsn: str) -> tuple[Any, Any]:
    """Create Postgres-backed checkpointed runner; returns (run_fn, context_manager).
    创建 Postgres 持久化 checkpoint 运行器；返回 (run_fn, context_manager)。

    Args:
        dsn: PostgreSQL connection string for LangGraph checkpointer.
            LangGraph checkpointer 的 PostgreSQL 连接串。

    Returns:
        Tuple of (run callable, context manager to close on shutdown).
            (run 可调用对象, 关闭时调用的上下文管理器) 元组。
    """
    from langgraph.checkpoint.postgres import PostgresSaver

    cm = PostgresSaver.from_conn_string(dsn)
    saver = cm.__enter__()
    saver.setup()
    return build_checkpointed_runner(saver), cm
