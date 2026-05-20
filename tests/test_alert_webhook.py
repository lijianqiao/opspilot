"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_alert_webhook.py
@DateTime: 2026-05-20
@Docs: Tests Alertmanager webhook HMAC and error sanitization.
    测试 Alertmanager Webhook HMAC 与错误脱敏。
"""

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
    """
    Verify alert accepted with valid signature.

    验证：alert accepted with valid signature。
    """
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
    """
    Verify alert rejects bad signature.

    验证：alert rejects bad signature。
    """
    body = b'{"alerts":[]}'
    response = client.post(
        "/alert",
        content=body,
        headers={"Content-Type": "application/json", "X-Opspilot-Signature": "forgedsig"},
    )
    assert response.status_code == 401


def test_alert_rejects_oversized_body(client: TestClient, hmac_secret: str) -> None:
    """
    Verify alert rejects oversized body.

    验证：alert rejects oversized body。
    """
    body = b'{"alerts":"' + (b"x" * 600_000) + b'"}'
    response = client.post(
        "/alert",
        content=body,
        headers={"Content-Type": "application/json", "X-Opspilot-Signature": _sign(body, hmac_secret)},
    )
    assert response.status_code == 413


def test_alert_rejects_invalid_json(client: TestClient, hmac_secret: str) -> None:
    """
    Verify alert rejects invalid json.

    验证：alert rejects invalid json。
    """
    body = b'{"alerts":'
    response = client.post(
        "/alert",
        content=body,
        headers={"Content-Type": "application/json", "X-Opspilot-Signature": _sign(body, hmac_secret)},
    )
    assert response.status_code == 400


def test_alert_rejects_non_object_json(client: TestClient, hmac_secret: str) -> None:
    """
    Verify alert rejects non object json.

    验证：alert rejects non object json。
    """
    body = b"[]"
    response = client.post(
        "/alert",
        content=body,
        headers={"Content-Type": "application/json", "X-Opspilot-Signature": _sign(body, hmac_secret)},
    )
    assert response.status_code == 422


def test_alert_rejects_malformed_alerts_field(client: TestClient, hmac_secret: str) -> None:
    """
    Verify alert rejects malformed alerts field.

    验证：alert rejects malformed alerts field。
    """
    scalar_body = b'{"alerts":1}'
    scalar_response = client.post(
        "/alert",
        content=scalar_body,
        headers={
            "Content-Type": "application/json",
            "X-Opspilot-Signature": _sign(scalar_body, hmac_secret),
        },
    )
    item_body = b'{"alerts":["bad"]}'
    item_response = client.post(
        "/alert",
        content=item_body,
        headers={
            "Content-Type": "application/json",
            "X-Opspilot-Signature": _sign(item_body, hmac_secret),
        },
    )
    assert scalar_response.status_code == 422
    assert item_response.status_code == 422


def test_alert_fail_closed_when_secret_unconfigured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify alert fail closed when secret unconfigured.

    验证：alert fail closed when secret unconfigured。
    """
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


def test_alert_normalizes_zabbix_payload(client: TestClient, hmac_secret: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify Zabbix-sourced webhooks bypass alertmanager validation and normalize correctly.

    验证：Zabbix 来源的载荷跳过 alertmanager 校验，并按 zabbix 适配器归一化。
    """
    from opspilot.alerts.models import NormalizedAlertEvent

    captured: dict[str, NormalizedAlertEvent | None] = {"event": None}

    async def fake_handle(event, llm):  # type: ignore[no-untyped-def]
        captured["event"] = event
        return "zabbix ok"

    monkeypatch.setattr("opspilot.entrypoints.alert_webhook.handle_alert", fake_handle)
    body = json.dumps(
        {
            "trigger": "CPU high",
            "host": "api-01",
            "severity": "High",
            "service": "api",
            "env": "prod",
        }
    ).encode("utf-8")
    response = client.post(
        "/alert",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Opspilot-Signature": _sign(body, hmac_secret),
            "X-OpsPilot-Alert-Source": "zabbix",
        },
    )
    assert response.status_code == 200
    assert response.json()["diagnosis"] == "zabbix ok"
    event = captured["event"]
    assert event is not None
    assert event.source == "zabbix"
    assert event.alerts[0].source_entity == "api-01"
    assert event.alerts[0].severity == "high"


def test_alert_response_echoes_trace_id(client: TestClient, hmac_secret: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify /alert echoes incoming X-OpsPilot-Trace-ID in the response.

    验证：/alert 在响应头中回显入站 X-OpsPilot-Trace-ID。
    """

    async def fake_handle(payload, llm):  # type: ignore[no-untyped-def]
        return "ok"

    monkeypatch.setattr("opspilot.entrypoints.alert_webhook.handle_alert", fake_handle)
    body = b'{"alerts":[]}'
    response = client.post(
        "/alert",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Opspilot-Signature": _sign(body, hmac_secret),
            "X-OpsPilot-Trace-ID": "trace-z",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("x-opspilot-trace-id") == "trace-z"


def test_alert_handles_error_with_redaction(
    client: TestClient, hmac_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Verify alert handles error with redaction.

    验证：alert handles error with redaction。
    """

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
