"""Feishu interactive-card action callback — pure handler.

lark-oapi WS 的 card-action 事件 (`p2.card.action.trigger`) 在 feishu_ws.run()
里用 EventDispatcherHandler.builder().register_p2_card_action_trigger(...) 注册；
那一层只做薄适配 (P2CardActionTrigger → dict)，真正逻辑在本文件的纯函数，
便于单测且与 lark-oapi 版本解耦。
"""

from __future__ import annotations

import logging
from typing import Any

from opspilot.agent.confirmation import STORE, ConfirmationStore

logger = logging.getLogger(__name__)


def handle_card_action(payload: dict[str, Any], store: ConfirmationStore | None = None) -> str:
    """处理飞书卡片按钮 action 回调。

    payload 形如 lark P2CardActionTriggerData 的 dict：
      {"action": {"value": {"action": "confirm"|"cancel", "request_id":..., "token":...}},
       "operator": {"open_id": "ou_xxx"}}

    返回值是给操作者显示的简短反馈文案（toast）。
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
