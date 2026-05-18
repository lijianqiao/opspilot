"""ReAct agent implemented as a LangGraph StateGraph.

This is the LangGraph migration of the hand-written loop in react.py.
Same SupportsChat protocol, same tool registry, same regex parsing —
but using StateGraph for state management, conditional edges, and
future checkpoint support.

Learning comparison (see docs/stages/stage1_agent_core.md):
- Hand-written: explicit for-loop, manual message list append
- LangGraph: declarative graph, state reducer, conditional routing
"""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any, Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from opspilot.tools.registry import build_tools_prompt, call_tool, get_registered_tools

logger = logging.getLogger(__name__)


# --- Protocol (same as react.py) ---


class SupportsChat(Protocol):
    async def chat(self, messages: list[dict[str, str]]) -> str: ...


# --- State ---


def _append_messages(left: list[dict[str, str]], right: list[dict[str, str]]) -> list[dict[str, str]]:
    """Reducer: append new messages to the existing list."""
    return left + right


class AgentState(TypedDict):
    messages: Annotated[list[dict[str, str]], _append_messages]
    question: str
    steps_taken: int
    max_steps: int
    final_answer: str | None


# --- Regex patterns ---

_ACTION_RE = re.compile(r"Action:\s*(\S+)")
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.*)", re.DOTALL)
_FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)


# --- Nodes ---

# Module-level LLM reference — set by run_react_graph() before ainvoke().
# LangGraph StateGraph only processes keys declared in the schema, so we
# can't pass the LLM through state. A module-level variable is the
# simplest workaround for a single-threaded agent loop.
_current_llm: SupportsChat | None = None


async def agent_node(state: AgentState) -> dict[str, Any]:
    """Call the LLM and append the reply to messages."""
    if _current_llm is None:
        raise RuntimeError("LLM not set. Call run_react_graph() which sets _current_llm.")

    messages = state["messages"]
    reply = await _current_llm.chat(messages)
    return {
        "messages": [{"role": "assistant", "content": reply}],
        "steps_taken": state["steps_taken"] + 1,
    }


async def tool_node(state: AgentState) -> dict[str, Any]:
    """Parse Action from last message, execute tool, return Observation."""
    last_msg = state["messages"][-1]["content"]

    action = _ACTION_RE.search(last_msg)
    if not action:
        return {"messages": [{"role": "user", "content": "Observation: 未检测到 Action。"}]}

    tool_name = action.group(1)
    arg_match = _ACTION_INPUT_RE.search(last_msg)
    raw_input = arg_match.group(1).strip() if arg_match else ""

    observation = call_tool(tool_name, raw_input)
    return {"messages": [{"role": "user", "content": f"Observation: {observation}"}]}


# --- Conditional edge ---


def should_continue(state: AgentState) -> str:
    """Decide whether to call tools, stop (final answer), or give up (max steps)."""
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


def _build_graph() -> Any:
    """Build the ReAct StateGraph: START → agent → (tools → agent | end)."""
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "agent")
    return graph.compile()


# Compiled graph instance (module-level singleton)
_compiled_graph = _build_graph()


async def run_react_graph(
    question: str,
    llm: SupportsChat,
    max_steps: int = 5,
) -> str:
    """Run the ReAct loop via LangGraph StateGraph.

    API-compatible with run_react() from react.py — same inputs, same
    outputs. The difference is internal: uses a compiled StateGraph
    with conditional edges instead of a for-loop.
    """
    tools = get_registered_tools()
    system_prompt = f"你是运维助手 OpsPilot。\n\n{build_tools_prompt()}"

    global _current_llm
    _current_llm = llm

    initial_state: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        "question": question,
        "steps_taken": 0,
        "max_steps": max_steps,
        "final_answer": None,
    }

    result = await _compiled_graph.ainvoke(initial_state)

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
