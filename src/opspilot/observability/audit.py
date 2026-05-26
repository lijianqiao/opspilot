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

from opspilot.observability.context import get_trace_id

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_MAX_FIELD_CHARS = 2000


class AuditWriteError(RuntimeError):
    """Raised when an audit log write fails and the caller opted into fail-closed.

    审计日志写入失败时抛出（仅在调用方选择 fail-closed 时抛出）。
    """


def _default_path() -> str:
    """Resolve audit log path from application settings.

    从应用配置解析审计日志文件路径。

    Returns:
        Configured audit_log_path string.
            配置项 audit_log_path 的路径字符串。
    """
    from opspilot.config import get_settings

    return get_settings().audit_log_path


def _redact_and_truncate(value: str) -> str:
    """Redact secrets/PII then truncate to _MAX_FIELD_CHARS.
    先脱敏（密钥/敏感信息）再截断到 _MAX_FIELD_CHARS。

    Args:
        value: String value to redact and truncate.
            要脱敏并截断的字符串值。

    Returns:
        Redacted and truncated string value.
            脱敏并截断后的字符串值。
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
    fail_closed: bool = False,
) -> bool:
    """Append one audit record; report success and optionally fail closed.

    追加一条审计记录；返回写入是否成功，可选 fail-closed 抛错。

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
        fail_closed: When True, raise AuditWriteError on write failure;
            when False (default), only log and return False.
            为 True 时写失败抛 AuditWriteError；默认 False 仅记录日志并返回 False。

    Returns:
        True if the record was successfully appended; False if write failed
        and fail_closed is False.
            成功写入返回 True；写失败且非 fail_closed 时返回 False。

    Raises:
        AuditWriteError: When write fails and fail_closed is True.
            当 fail_closed 为 True 且写入失败时抛出。
    """
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "trace_id": get_trace_id(),
        "tool": tool,
        "tool_input": _redact_and_truncate(tool_input),
        "actor": actor,
        "confirmed_by": confirmed_by,
        "status": status,
        "result": _redact_and_truncate(result),
        "rollback": rollback,
    }
    target = path or _default_path()
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with _lock, open(target, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True
    except OSError as exc:
        logger.exception("audit write failed (operation still proceeds): %s/%s", tool, status)
        if fail_closed:
            raise AuditWriteError(f"audit write failed for {tool}/{status}") from exc
        return False
