"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: react_protocol.py
@DateTime: 2026-05-20
@Docs: Shared ReAct text protocol: regexes and parser for all agents.
    共享 ReAct 文本协议：正则与解析器，供各智能体复用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ACTION_RE = re.compile(r"Action:\s*(\S+)")
ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.*)", re.DOTALL)
FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)
STEP_RE = re.compile(r"^\s*\d+[.)]\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ReactOutput:
    """Parsed fields from one LLM ReAct turn.
    单次 LLM ReAct 输出的解析结果。

    Attributes:
        action: Tool name if an Action line is present, else None.
            若存在 Action 行则为工具名，否则为 None。
        action_input: Raw Action Input text (may be JSON).
            Action Input 原始文本（可为 JSON）。
        final: Final Answer text if present, else None.
            若存在 Final Answer 则为最终答案文本，否则为 None。
    """

    action: str | None
    action_input: str
    final: str | None


def parse_react_output(reply: str) -> ReactOutput:
    """Parse one LLM turn into action, action_input, and final answer.
    将单次 LLM 输出解析为 action、action_input 与 final。

    Final Answer takes precedence over Action when both appear.

    Args:
        reply: Raw assistant message text.
            助手消息的原始文本。

    Returns:
        ReactOutput with parsed fields; empty strings/None when absent.
            解析后的 ReactOutput；缺失字段为空字符串或 None。
    """
    if m := FINAL_RE.search(reply):
        return ReactOutput(action=None, action_input="", final=m.group(1).strip())
    if a := ACTION_RE.search(reply):
        ai = ACTION_INPUT_RE.search(reply)
        return ReactOutput(action=a.group(1), action_input=ai.group(1).strip() if ai else "", final=None)
    return ReactOutput(action=None, action_input="", final=None)
