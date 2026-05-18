"""Guardrails: dangerous-op detection, output redaction, call-cap constant.

Pure functions — no I/O, no graph state. Wired into the LangGraph
tool_node in Task 4. Designed so the agent never silently executes a
destructive op and never echoes secrets back to the user.
"""

from __future__ import annotations

import re

from opspilot.tools.registry import get_registered_tools

# Destructive intent in the raw tool input, regardless of tool risk level.
_DANGEROUS_INPUT_RE = re.compile(
    r"\b(rm\s+-rf|drop\s+table|drop\s+database|delete\s+from|truncate|"
    r"mkfs|shutdown|reboot|kill\s+-9|:\s*0\s*$)|--force\b|\bscale\b.*\b0\b",
    re.IGNORECASE,
)

# Secrets / PII to mask before any text reaches the user or logs.
_REDACT_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{6,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{6,}", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S+"),
)


def is_dangerous(tool_name: str, raw_input: str) -> bool:
    """True if the tool is registered high-risk OR the input shows destructive intent."""
    tools = get_registered_tools()
    info = tools.get(tool_name)
    if info is not None and info.risk == "high":
        return True
    return bool(_DANGEROUS_INPUT_RE.search(raw_input or ""))


def redact(text: str) -> str:
    """Mask secrets / PII. Returns text unchanged when nothing matches."""
    out = text
    for pat in _REDACT_RES:
        out = pat.sub("***", out)
    return out
