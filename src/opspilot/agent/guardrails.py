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
    r"\b("
    r"rm\s+-rf|"  # 递归强制删除
    r"drop\s+table|drop\s+database|"  # SQL 删表/库
    r"delete\s+from|truncate|"  # 批量删数据
    r"mkfs|"  # 格式化磁盘
    r"shutdown|reboot|"  # 关机/重启
    r"kill\s+-9|"  # 强制杀进程
    r":\s*0\s*$"  # YAML/配置里 replicas/resources 缩到 0 的简写
    r")|--force\b|"  # 强制标志（如 kubectl delete --force）
    r"\bscale\b.*\b0\b",  # kubectl scale ... 0
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
