"""Shared ReAct text protocol: regexes + parser. Single source for all agents."""

from __future__ import annotations

import re
from dataclasses import dataclass

ACTION_RE = re.compile(r"Action:\s*(\S+)")
ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.*)", re.DOTALL)
FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)
STEP_RE = re.compile(r"^\s*\d+[.)]\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ReactOutput:
    action: str | None
    action_input: str
    final: str | None


def parse_react_output(reply: str) -> ReactOutput:
    """Parse one LLM turn into (action, action_input, final). Final wins over Action."""
    if m := FINAL_RE.search(reply):
        return ReactOutput(action=None, action_input="", final=m.group(1).strip())
    if a := ACTION_RE.search(reply):
        ai = ACTION_INPUT_RE.search(reply)
        return ReactOutput(action=a.group(1), action_input=ai.group(1).strip() if ai else "", final=None)
    return ReactOutput(action=None, action_input="", final=None)
