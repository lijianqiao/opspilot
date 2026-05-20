"""Append-only operation audit log (JSONL).

每条写/危险操作都落一行：谁、何时、什么工具、参数、是否确认、结果、可回滚信息。
JSONL append 是进程内最简单的不可篡改近似；Stage 6 可换 Postgres append-only 表。
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


def _default_path() -> str:
    from opspilot.config import get_settings

    return get_settings().audit_log_path


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
    """Append one audit record. Never raises into the caller's hot path."""
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "tool": tool,
        "tool_input": tool_input,
        "actor": actor,
        "confirmed_by": confirmed_by,
        "status": status,
        "result": result[:2000],
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
