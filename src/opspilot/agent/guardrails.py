"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: guardrails.py
@DateTime: 2026-05-20
@Docs: Guardrails: dangerous-op detection and output redaction.
    安全护栏：危险操作检测与输出脱敏。
"""

from __future__ import annotations

import re

from opspilot.tools.registry import get_registered_tools

# Secrets / PII to mask before any text reaches the user or logs.
_REDACT_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{6,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{6,}", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S+"),
)


def is_dangerous(tool_name: str, raw_input: str) -> bool:
    """Return True if the tool is registered with risk='high'.
    仅当工具在注册表中标记为 risk='high' 时返回 True。

    Args:
        tool_name: Registered tool name.
            已注册的工具名称。
        raw_input: Raw Action Input string from the agent (unused; kept for
            signature stability with prior callers).
            智能体传入的 Action Input 原始字符串（当前未使用，仅保留签名以兼容旧调用方）。

    Returns:
        True when execution should require human confirmation.
            为 True 时表示应触发人工确认流程。
    """
    del raw_input  # raw-input text scanning was removed; see commit message.
    tools = get_registered_tools()
    info = tools.get(tool_name)
    return info is not None and info.risk == "high"


def redact(text: str) -> str:
    """Mask secrets and PII in text before returning to user or logs.
    在返回用户或写入日志前对文本中的密钥与 PII 脱敏。

    Args:
        text: Raw observation or log line.
            原始观测结果或日志行。

    Returns:
        Text with matched secrets replaced by ***; unchanged if no match.
            匹配到的敏感内容替换为 ***；无匹配时原文返回。
    """
    out = text
    for pat in _REDACT_RES:
        out = pat.sub("***", out)
    return out
