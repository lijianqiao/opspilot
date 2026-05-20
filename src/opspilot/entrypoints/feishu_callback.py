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

    # Rebuild the current context from the Feishu event payload — the
    # authoritative trust boundary is the operator open_id and event chat_id.
    # The context embedded in the card `value` is NOT trusted as a security
    # signal: an attacker who forwards the card would still carry the
    # original value but click from a different chat / open_id.
    value_context_raw = value.get("context")
    value_context: dict[str, str] = value_context_raw if isinstance(value_context_raw, dict) else {}
    event_chat_id = payload.get("chat_id") or payload.get("open_chat_id")
    current_context: dict[str, str] = {"channel": "feishu"}
    if open_id and open_id != "unknown":
        current_context["requester"] = str(open_id)
    if event_chat_id:
        current_context["chat_id"] = str(event_chat_id)
    elif "chat_id" in value_context:
        # Compatibility fallback only: some lark-oapi callback model versions
        # do not surface chat_id on card-action events. requester (open_id)
        # remains the authoritative binding in that case.
        current_context["chat_id"] = str(value_context["chat_id"])

    if value.get("action") == "confirm":
        token: str = value.get("token", "")
        ok = store.confirm(request_id, token, actor=actor, context=current_context)
        if ok:
            logger.info("card confirm OK: request_id=%s actor=%s", request_id, actor)
            return f"已确认（{actor}），操作将继续执行。"
        logger.warning(
            "card confirm FAILED: request_id=%s actor=%s (expired/invalid/context mismatch)",
            request_id,
            actor,
        )
        return "确认失败：请求已过期、无效或上下文不匹配。"

    # cancel / unknown action
    logger.info("card cancel: request_id=%s actor=%s", request_id, actor)
    return "已取消，操作不会执行。"
