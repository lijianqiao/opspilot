"""Hand-written ReAct loop — Stage 0 reference implementation, enhanced for Stage 1.

This module is the learning artifact: the same ReAct logic as the LangGraph
version (langgraph_agent.py) but implemented without any framework. Kept
as a reference for the stage summary comparison.
"""

from __future__ import annotations

import logging
import re

from opspilot.agent.protocols import SupportsChat
from opspilot.tools.registry import build_tools_prompt, call_tool

logger = logging.getLogger(__name__)


_ACTION_RE = re.compile(r"Action:\s*(\S+)")
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.*)", re.DOTALL)
_FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)


async def run_react(
    question: str,
    llm: SupportsChat,
    max_steps: int = 5,
) -> str:
    """Run a ReAct loop: Reason → Act → Observe → repeat.

    Enhanced from Stage 0:
    - System prompt auto-generated from tool registry
    - Action Input parsed as JSON when possible (multi-arg support)
    - Tool execution errors caught and fed back as observations via call_tool()
    """
    system_prompt = f"你是运维助手 OpsPilot。\n\n{build_tools_prompt()}"

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    for _ in range(max_steps):
        reply = await llm.chat(messages)
        messages.append({"role": "assistant", "content": reply})

        # Final Answer → return
        if final := _FINAL_RE.search(reply):
            return final.group(1).strip()

        # No Action → return raw reply
        action = _ACTION_RE.search(reply)
        if action is None:
            return reply.strip()

        tool_name = action.group(1)

        # Parse Action Input
        arg_match = _ACTION_INPUT_RE.search(reply)
        raw_input = arg_match.group(1).strip() if arg_match else ""

        # Execute tool with error handling
        observation = call_tool(tool_name, raw_input)

        messages.append({"role": "user", "content": f"Observation: {observation}"})

    return "达到最大推理步数，未能得到最终答案。"
