"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: audit.py
@DateTime: 2026-05-20
@Docs: Append-only JSONL audit log for write and dangerous operations.
    追加式 JSONL 操作审计日志（写操作与危险操作落盘，进程内线程安全）。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_MAX_FIELD_CHARS = 2000


def _default_path() -> str:
    """Resolve audit log path from application settings.

    从应用配置解析审计日志文件路径。

    Returns:
        Configured audit_log_path string.
            配置项 audit_log_path 的路径字符串。
    """
    from opspilot.config import get_settings

    return get_settings().audit_log_path


def _safe_field(value: str) -> str:
    """Safely truncate the value to the maximum field length.
    安全地截断值到最大字段长度。

    Args:
        value: String value to truncate.
            要截断的字符串值。

    Returns:
        Truncated string value.
            截断后的字符串值。
    """
    from opspilot.agent.guardrails import redact

    return redact(value)[:_MAX_FIELD_CHARS]


def record_operation(
    *,
    tool: str,
    tool_input: str,
    actor: str,
    confirmed_by: str | None,
    status: str,
    result: str,
    rollback: dict[str, Any] | None,
    path: str | None = None,
) -> None:
    """Append one audit record. Never raises into the caller's hot path.

    追加一条审计记录；不向调用方热路径抛出异常。

    Args:

        Each line records who/when/tool/params/confirmation/result/rollback hints.
        每行记录：操作者、时间、工具、参数、确认人、状态、结果与回滚信息。
        tool: Tool name invoked.
            调用的工具名称。
        tool_input: Serialized tool input (truncated in storage if needed).
            工具入参序列化字符串。
        actor: Identity performing the operation.
            执行操作的主体标识。
        confirmed_by: Human confirmer id when applicable; else None.
            人工确认者标识；无则为 None。
        status: Outcome status label.
            结果状态标签。
        result: Human-readable result text (stored truncated).
            人类可读的结果文本（写入时会截断）。
        rollback: Optional rollback metadata dict.
            可选的回滚元数据字典。
        path: Override audit file path; defaults to settings.
            覆盖审计文件路径；默认使用配置路径。
    """
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "tool": tool,
        "tool_input": _safe_field(tool_input),
        "actor": actor,
        "confirmed_by": confirmed_by,
        "status": status,
        "result": _safe_field(result),
        "rollback": rollback,
    }
    target = path or _default_path()
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with _lock, open(target, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        logger.exception("audit write failed (operation still proceeds): %s/%s", tool, status)
