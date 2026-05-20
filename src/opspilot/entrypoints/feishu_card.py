"""Feishu interactive card: danger-op confirmation flow.

危险操作拦截时由 supervisor/agent 发送确认卡片给运维人员；
点击"确认执行"按钮 → Feishu callback 调用 confirm_from_card()
→ 委托 agent.confirmation.STORE 状态机放行。

旧的进程内 _pending_confirmations dict 已删除——状态机统一在
ConfirmationStore（带 TTL + 一次性 + actor 记录 + 常量时间比较）。
"""

from __future__ import annotations

import json

from opspilot.agent.confirmation import STORE, ConfirmationStore


def build_confirm_card(request_id: str, token: str, tool_name: str, tool_input: str) -> str:
    """Build a Feishu interactive card asking for human confirmation.

    按钮 value 携带 request_id + token，使卡片回调能调用 STORE.confirm(request_id, token, actor)。
    """
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
                            "value": json.dumps(
                                {"action": "confirm", "request_id": request_id, "token": token}
                            ),
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "取消"},
                            "type": "danger",
                            "value": json.dumps({"action": "cancel", "request_id": request_id}),
                        },
                    ],
                },
            ],
        },
        ensure_ascii=False,
    )


def confirm_from_card(
    request_id: str, token: str, actor: str, store: ConfirmationStore | None = None
) -> bool:
    """Thin adapter: 飞书卡片回调拿到 (request_id, token, actor) → 委托 STORE 放行。"""
    return (store if store is not None else STORE).confirm(request_id, token, actor)
