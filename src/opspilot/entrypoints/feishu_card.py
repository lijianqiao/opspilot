"""Feishu interactive card: danger-op confirmation flow.

When the K8s Operator wants to execute a dangerous operation, the
Supervisor sends a card to the user. The user clicks confirm/cancel,
and the card callback triggers the actual execution (or abort).

State is stored in _pending_confirmations (process-in-memory).
Stage 3 keeps it in-process; Stage 6 can migrate to Postgres.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# chat_id → {tool, input, timestamp}
_pending_confirmations: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def build_confirm_card(tool_name: str, tool_input: str) -> str:
    """Build a Feishu interactive card asking for confirmation."""
    return json.dumps(
        {
            "header": {
                "title": {"tag": "plain_text", "content": "危险操作确认"},
                "template": "red",
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"**操作：** {tool_name}\n**参数：** `{tool_input}`\n\n此操作存在风险，请确认是否执行。",
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "确认执行"},
                            "type": "primary",
                            "value": json.dumps({"action": "confirm", "tool": tool_name, "input": tool_input}),
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "取消"},
                            "type": "danger",
                            "value": json.dumps({"action": "cancel"}),
                        },
                    ],
                },
            ],
        },
        ensure_ascii=False,
    )


def register_pending(chat_id: str, context: dict[str, Any]) -> None:
    """Register a pending confirmation for a chat."""
    with _lock:
        _pending_confirmations[chat_id] = context
    logger.info("Pending confirmation registered for chat %s: %s", chat_id, context.get("tool"))


def consume_confirmation(chat_id: str) -> bool | None:
    """Consume a pending confirmation. Returns True=confirmed, False=cancelled, None=not found."""
    with _lock:
        context = _pending_confirmations.pop(chat_id, None)
    if context is None:
        return None
    return context.get("confirmed", False)
