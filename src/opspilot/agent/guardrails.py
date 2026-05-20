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
    """Return True if the tool is high-risk or input shows destructive intent.
    若工具为高风险或输入含破坏性意图则返回 True。

    Args:
        tool_name: Registered tool name.
            已注册的工具名称。
        raw_input: Raw Action Input string from the agent.
            智能体传入的 Action Input 原始字符串。

    Returns:
        True when execution should require human confirmation.
            为 True 时表示应触发人工确认流程。
    """
    tools = get_registered_tools()
    info = tools.get(tool_name)
    if info is not None and info.risk == "high":
        return True
    return bool(_DANGEROUS_INPUT_RE.search(raw_input or ""))


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
