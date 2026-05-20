import hashlib
import hmac
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from opspilot.entrypoints.alert_webhook import app

_SECRET = "shared-test-secret"


@pytest.fixture
def hmac_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Configure HMAC secret for tests; clear settings cache around test."""
    from opspilot.config import get_settings

    monkeypatch.setenv("OPSPILOT_ALERTMANAGER_HMAC_SECRET", _SECRET)
    get_settings.cache_clear()
    try:
        yield _SECRET
    finally:
        get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_alert_accepted_with_valid_signature(
    client: TestClient, hmac_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = json.loads(Path("fixtures/alertmanager_webhook.json").read_text("utf-8"))
    body = json.dumps(fixture).encode("utf-8")

    async def fake_handle(payload, llm):
        return "诊断结果：测试告警已处理。"

    monkeypatch.setattr("opspilot.entrypoints.alert_webhook.handle_alert", fake_handle)
    response = client.post(
        "/alert",
        content=body,
        headers={"Content-Type": "application/json", "X-Opspilot-Signature": _sign(body, hmac_secret)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "测试告警" in data["diagnosis"]


def test_alert_rejects_bad_signature(client: TestClient, hmac_secret: str) -> None:
    body = b'{"alerts":[]}'
    response = client.post(
        "/alert",
        content=body,
        headers={"Content-Type": "application/json", "X-Opspilot-Signature": "forgedsig"},
    )
    assert response.status_code == 401


def test_alert_fail_closed_when_secret_unconfigured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from opspilot.config import get_settings

    monkeypatch.setenv("OPSPILOT_ALERTMANAGER_HMAC_SECRET", "")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/alert",
            content=b'{"alerts":[]}',
            headers={"Content-Type": "application/json", "X-Opspilot-Signature": "anything"},
        )
        assert response.status_code == 503
    finally:
        get_settings.cache_clear()


def test_alert_handles_error_with_redaction(
    client: TestClient, hmac_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(payload, llm):
        raise RuntimeError("LLM down with token=sk-LEAK and pg pwd=p@ss")

    monkeypatch.setattr("opspilot.entrypoints.alert_webhook.handle_alert", boom)
    body = b'{"alerts":[]}'
    response = client.post(
        "/alert",
        content=body,
        headers={"Content-Type": "application/json", "X-Opspilot-Signature": _sign(body, hmac_secret)},
    )
    assert response.status_code == 200
    body_out = response.json()
    assert body_out["status"] == "error"
    # 异常详情不应外泄
    assert "sk-LEAK" not in body_out["diagnosis"]
    assert "p@ss" not in body_out["diagnosis"]
