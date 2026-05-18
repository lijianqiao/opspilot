import json

from opspilot.entrypoints.feishu_card import (
    _pending_confirmations,
    build_confirm_card,
    consume_confirmation,
    register_pending,
)


def test_build_confirm_card_returns_valid_card_json():
    card = build_confirm_card("kubectl_scale", '{"deployment":"user-service","replicas":0}')
    data = json.loads(card)
    assert "elements" in data  # Feishu card message structure
    assert "kubectl_scale" in card


def test_register_and_consume_confirmation():
    _pending_confirmations.clear()
    register_pending("chat_001", {"tool": "kubectl_scale", "input": "x", "confirmed": True})
    result = consume_confirmation("chat_001")
    assert result is True

    # Second call should return None (already consumed)
    result2 = consume_confirmation("chat_001")
    assert result2 is None


def test_consume_unknown_chat_returns_none():
    _pending_confirmations.clear()
    assert consume_confirmation("nonexistent") is None
