"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: feishu_card.py
@DateTime: 2026-05-20
@Docs: Feishu interactive cards for danger-op human confirmation flow.
    飞书交互卡片：危险操作人工确认流程。
"""

from __future__ import annotations

import json

from opspilot.agent.confirmation import STORE, ConfirmationStore


def build_confirm_card(request_id: str, token: str, tool_name: str, tool_input: str) -> str:
    """Build a Feishu interactive card asking for human confirmation.

    构建请求人工确认的飞书交互卡片 JSON。

    Button values carry request_id + token so the callback can call
    STORE.confirm(request_id, token, actor).
    按钮 value 携带 request_id 与 token，供回调调用 STORE.confirm。

    Args:
        request_id: Pending confirmation request ID.
            待确认请求 ID。
        token: One-time confirmation token.
            一次性确认令牌。
        tool_name: Name of the guarded tool.
            被拦截的工具名称。
        tool_input: Serialized tool input for display.
            用于展示的工具入参。

    Returns:
        JSON string of the interactive card payload.
            交互卡片载荷的 JSON 字符串。
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
                            "value": json.dumps({"action": "confirm", "request_id": request_id, "token": token}),
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


def confirm_from_card(request_id: str, token: str, actor: str, store: ConfirmationStore | None = None) -> bool:
    """Thin adapter: card callback (request_id, token, actor) → STORE.confirm.

    薄适配层：飞书卡片回调拿到 (request_id, token, actor) 后委托 STORE 放行。

    Args:
        request_id: Pending confirmation request ID.
            待确认请求 ID。
        token: One-time confirmation token from the card.
            卡片携带的一次性确认令牌。
        actor: Operator identity (e.g. feishu:open_id).
            操作者标识（如 feishu:open_id）。
        store: Optional ConfirmationStore; defaults to global STORE.
            可选确认存储；默认使用全局 STORE。

    Returns:
        True if confirmation succeeded.
            确认成功返回 True。
    """
    return (store if store is not None else STORE).confirm(request_id, token, actor)
