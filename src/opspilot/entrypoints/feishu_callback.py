"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: feishu_callback.py
@DateTime: 2026-05-20
@Docs: Pure handler for Feishu interactive card action callbacks.
    飞书交互卡片按钮回调的纯函数处理器（与 lark-oapi 解耦）。
"""

from __future__ import annotations

import logging
from typing import Any

from opspilot.agent.confirmation import STORE, ConfirmationStore

logger = logging.getLogger(__name__)


def handle_card_action(payload: dict[str, Any], store: ConfirmationStore | None = None) -> str:
    """Handle Feishu card button action callback.

    处理飞书卡片按钮 action 回调。

    Payload shape (lark P2CardActionTriggerData dict):
      {"action": {"value": {"action": "confirm"|"cancel", "request_id":..., "token":...}},
       "operator": {"open_id": "ou_xxx"}}

    payload 形如 lark P2CardActionTriggerData 的 dict（见上）。

    Args:
        payload: Card action event dict from Feishu.
            飞书卡片 action 事件字典。
        store: Optional ConfirmationStore; defaults to global STORE.
            可选确认存储；默认使用全局 STORE。

    Returns:
        Short toast message for the operator.
            给操作者显示的简短反馈文案（toast）。
    """
    store = store if store is not None else STORE
    action_obj = payload.get("action") or {}
    value = action_obj.get("value") or {}
    request_id: str = value.get("request_id", "")
    operator = payload.get("operator") or {}
    open_id = operator.get("open_id") or operator.get("user_id") or "unknown"
    actor = f"feishu:{open_id}"

    if value.get("action") == "confirm":
        token: str = value.get("token", "")
        ok = store.confirm(request_id, token, actor=actor)
        if ok:
            logger.info("card confirm OK: request_id=%s actor=%s", request_id, actor)
            return f"已确认（{actor}），操作将继续执行。"
        logger.warning("card confirm FAILED: request_id=%s actor=%s (expired/invalid)", request_id, actor)
        return "确认失败：请求已过期或无效。"

    # cancel / unknown action
    logger.info("card cancel: request_id=%s actor=%s", request_id, actor)
    return "已取消，操作不会执行。"
