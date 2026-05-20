"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_feishu_callback.py
@DateTime: 2026-05-20
@Docs: Tests Feishu card action confirm/cancel handler.
    测试飞书卡片确认/取消回调处理。
"""

from opspilot.agent.confirmation import ConfirmationStore
from opspilot.entrypoints.feishu_callback import handle_card_action


def test_card_confirm_authorizes_via_store() -> None:
    """
    Verify card confirm authorizes via store.

    验证：card confirm authorizes via store。
    """
    store = ConfirmationStore(300)
    pc = store.request("kubectl_scale", "x")
    payload = {
        "action": {"value": {"action": "confirm", "request_id": pc.request_id, "token": pc.token}},
        "operator": {"open_id": "ou_user_1"},
    }
    msg = handle_card_action(payload, store=store)
    assert store.is_confirmed(pc.request_id) is True
    assert "已确认" in msg
    assert "feishu:ou_user_1" in msg


def test_card_cancel_does_not_authorize() -> None:
    """
    Verify card cancel does not authorize.

    验证：card cancel does not authorize。
    """
    store = ConfirmationStore(300)
    pc = store.request("kubectl_scale", "x")
    payload = {
        "action": {"value": {"action": "cancel", "request_id": pc.request_id}},
        "operator": {"open_id": "ou_2"},
    }
    msg = handle_card_action(payload, store=store)
    assert store.is_confirmed(pc.request_id) is False
    assert "已取消" in msg


def test_card_wrong_token_rejected() -> None:
    """
    Verify card wrong token rejected.

    验证：card wrong token rejected。
    """
    store = ConfirmationStore(300)
    pc = store.request("kubectl_scale", "x")
    payload = {
        "action": {"value": {"action": "confirm", "request_id": pc.request_id, "token": "forged"}},
        "operator": {"open_id": "ou_3"},
    }
    msg = handle_card_action(payload, store=store)
    assert store.is_confirmed(pc.request_id) is False
    assert "失败" in msg or "无效" in msg


def test_card_confirm_fails_when_event_requester_does_not_match() -> None:
    """
    Verify card confirmation fails when the clicker's open_id differs from the
    pending requester, even if the forwarded card carries the original value.

    验证：即使攻击者拿到原卡片 value，但事件中的点击人 open_id 与待确认请求人不匹配时，
    应被拒绝（requester 是权威绑定，不信任 card value 中的 context）。
    """
    store = ConfirmationStore(300)
    pc = store.request(
        "restart_service",
        '{"service":"user-service"}',
        context={"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
    )
    # 攻击者点击同一张卡片，但事件 open_id 是另一人
    payload = {
        "action": {
            "value": {
                "action": "confirm",
                "request_id": pc.request_id,
                "token": pc.token,
                "context": {"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
            }
        },
        "operator": {"open_id": "ou_attacker"},
        "chat_id": "chat-a",
    }
    msg = handle_card_action(payload, store=store)
    assert store.is_confirmed(pc.request_id) is False
    assert "失败" in msg or "不匹配" in msg


def test_card_confirm_fails_when_event_chat_does_not_match() -> None:
    """
    Verify card confirmation fails when event chat_id differs from pending chat
    (attacker forwards card to a different chat).

    验证：攻击者将卡片转发到其它会话点击时，事件 chat_id 不匹配，应被拒绝。
    """
    store = ConfirmationStore(300)
    pc = store.request(
        "restart_service",
        '{"service":"user-service"}',
        context={"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
    )
    payload = {
        "action": {
            "value": {
                "action": "confirm",
                "request_id": pc.request_id,
                "token": pc.token,
                # value 中仍是原 context，但事件 chat_id 是攻击者会话
                "context": {"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
            }
        },
        "operator": {"open_id": "ou_1"},
        "chat_id": "chat-b",
    }
    msg = handle_card_action(payload, store=store)
    assert store.is_confirmed(pc.request_id) is False
    assert "失败" in msg or "不匹配" in msg


def test_card_confirm_succeeds_when_event_context_matches_pending() -> None:
    """
    Verify card confirmation succeeds when event context matches pending.

    验证：事件上下文（open_id + chat_id）与 pending 一致时确认成功。
    """
    store = ConfirmationStore(300)
    pc = store.request(
        "restart_service",
        '{"service":"user-service"}',
        context={"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
    )
    payload = {
        "action": {
            "value": {
                "action": "confirm",
                "request_id": pc.request_id,
                "token": pc.token,
                "context": {"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
            }
        },
        "operator": {"open_id": "ou_1"},
        "chat_id": "chat-a",
    }
    msg = handle_card_action(payload, store=store)
    assert store.is_confirmed(pc.request_id) is True
    assert "已确认" in msg


def test_card_confirm_chat_id_compat_fallback_from_value() -> None:
    """
    When event chat_id is unavailable, callback falls back to value.context
    chat_id (compat mode); requester from event remains authoritative.

    事件未提供 chat_id 时，回调以 value.context 中的 chat_id 作为兼容回退；
    requester 仍以事件 open_id 为权威绑定。
    """
    store = ConfirmationStore(300)
    pc = store.request(
        "restart_service",
        '{"service":"user-service"}',
        context={"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
    )
    payload = {
        "action": {
            "value": {
                "action": "confirm",
                "request_id": pc.request_id,
                "token": pc.token,
                "context": {"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
            }
        },
        "operator": {"open_id": "ou_1"},
        # no top-level chat_id from event
    }
    msg = handle_card_action(payload, store=store)
    assert store.is_confirmed(pc.request_id) is True
    assert "已确认" in msg


def test_card_missing_operator_falls_back_to_unknown() -> None:
    # 防御性：payload 可能字段不全
    """
    Verify card missing operator falls back to unknown.

    验证：card missing operator falls back to unknown。
    """
    store = ConfirmationStore(300)
    pc = store.request("kubectl_scale", "x")
    payload = {"action": {"value": {"action": "confirm", "request_id": pc.request_id, "token": pc.token}}}
    msg = handle_card_action(payload, store=store)
    assert store.is_confirmed(pc.request_id) is True
    assert "feishu:unknown" in msg
