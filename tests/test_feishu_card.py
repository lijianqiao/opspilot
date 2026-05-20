import json

from opspilot.entrypoints.feishu_card import build_confirm_card, confirm_from_card


def test_build_confirm_card_returns_valid_card_json() -> None:
    card = build_confirm_card("req_abc", "tok_xyz", "kubectl_scale", '{"deployment":"user-service","replicas":0}')
    data = json.loads(card)
    assert "elements" in data  # Feishu card message structure
    assert "kubectl_scale" in card


def test_build_confirm_card_buttons_carry_request_id_and_token() -> None:
    card = json.loads(build_confirm_card("req_abc", "tok_xyz", "kubectl_scale", "in"))
    actions = next(el for el in card["elements"] if el.get("tag") == "action")
    confirm_button = next(b for b in actions["actions"] if "primary" in b.get("type", ""))
    cancel_button = next(b for b in actions["actions"] if "danger" in b.get("type", ""))
    confirm_value = json.loads(confirm_button["value"])
    cancel_value = json.loads(cancel_button["value"])
    assert confirm_value["action"] == "confirm"
    assert confirm_value["request_id"] == "req_abc"
    assert confirm_value["token"] == "tok_xyz"  # required so callback can call STORE.confirm()
    assert cancel_value["action"] == "cancel"
    assert cancel_value["request_id"] == "req_abc"


def test_confirm_from_card_authorizes_via_store() -> None:
    from opspilot.agent.confirmation import ConfirmationStore

    store = ConfirmationStore(300)
    pc = store.request("kubectl_scale", "x")
    assert confirm_from_card(pc.request_id, pc.token, actor="feishu:ou_42", store=store) is True
    assert store.is_confirmed(pc.request_id) is True


def test_confirm_from_card_wrong_token_rejected() -> None:
    from opspilot.agent.confirmation import ConfirmationStore

    store = ConfirmationStore(300)
    pc = store.request("kubectl_scale", "x")
    assert confirm_from_card(pc.request_id, "wrong-token", actor="x", store=store) is False
    assert store.is_confirmed(pc.request_id) is False


def test_old_pending_api_removed() -> None:
    # 旧的进程内 _pending_confirmations / register_pending / consume_confirmation
    # 已迁到 ConfirmationStore（带 TTL + 一次性 + 防重放），不再暴露
    import opspilot.entrypoints.feishu_card as fc

    assert not hasattr(fc, "_pending_confirmations")
    assert not hasattr(fc, "register_pending")
    assert not hasattr(fc, "consume_confirmation")
