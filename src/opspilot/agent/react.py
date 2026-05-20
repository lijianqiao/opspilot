"""Hand-written ReAct loop — Stage 0 reference implementation, enhanced for Stage 1.

⚠️ 学习参照实现：无 guardrails（无 is_dangerous / redact / 人工确认门 / 审计）。
禁止接入任何 entrypoint。生产路径请用 langgraph_agent / plan_execute（经 guarded_call_tool）。

This module is the learning artifact: the same ReAct logic as the LangGraph
version (langgraph_agent.py) but implemented without any framework. Kept
as a reference for the stage summary comparison.
"""

from __future__ import annotations

import logging

from opspilot.agent.protocols import SupportsChat
from opspilot.agent.react_protocol import parse_react_output
from opspilot.tools.registry import build_tools_prompt, call_tool

logger = logging.getLogger(__name__)


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

        parsed = parse_react_output(reply)

        # Final Answer → return
        if parsed.final is not None:
            return parsed.final

        # No Action → return raw reply
        if parsed.action is None:
            return reply.strip()

        # Execute tool with error handling
        observation = call_tool(parsed.action, parsed.action_input)

        messages.append({"role": "user", "content": f"Observation: {observation}"})

    return "达到最大推理步数，未能得到最终答案。"
