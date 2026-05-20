from opspilot.agent.confirmation import ConfirmationStore
from opspilot.entrypoints.feishu_callback import handle_card_action


def test_card_confirm_authorizes_via_store() -> None:
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
    store = ConfirmationStore(300)
    pc = store.request("kubectl_scale", "x")
    payload = {
        "action": {"value": {"action": "confirm", "request_id": pc.request_id, "token": "forged"}},
        "operator": {"open_id": "ou_3"},
    }
    msg = handle_card_action(payload, store=store)
    assert store.is_confirmed(pc.request_id) is False
    assert "失败" in msg or "无效" in msg


def test_card_missing_operator_falls_back_to_unknown() -> None:
    # 防御性：payload 可能字段不全
    store = ConfirmationStore(300)
    pc = store.request("kubectl_scale", "x")
    payload = {"action": {"value": {"action": "confirm", "request_id": pc.request_id, "token": pc.token}}}
    msg = handle_card_action(payload, store=store)
    assert store.is_confirmed(pc.request_id) is True
    assert "feishu:unknown" in msg
