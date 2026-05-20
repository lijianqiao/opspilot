"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: react.py
@DateTime: 2026-05-20
@Docs: Hand-written ReAct loop — Stage 0 reference, no guardrails.
    手写 ReAct 循环：Stage 0 参照实现，无安全护栏。
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
    """Run a ReAct loop: Reason, Act, Observe, repeat until Final Answer.
    运行 ReAct 循环：推理、行动、观测，直至得到 Final Answer。

    Learning reference only — no guardrails. Production uses langgraph_agent.

    Args:
        question: User question or task description.
            用户问题或任务描述。
        llm: Chat backend implementing SupportsChat.
            实现 SupportsChat 的对话后端。
        max_steps: Maximum reasoning steps before giving up.
            放弃前的最大推理步数。

    Returns:
        Final Answer text, last assistant reply, or step-limit message.
            Final Answer 文本、最后一条助手回复或步数上限提示。
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
