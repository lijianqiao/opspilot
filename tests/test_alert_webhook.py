import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from opspilot.entrypoints.alert_webhook import app


@pytest.fixture
def client():
    return TestClient(app)


def test_alert_endpoint_returns_diagnosis(client, monkeypatch):
    fixture = json.loads(Path("fixtures/alertmanager_webhook.json").read_text("utf-8"))

    # We don't want to call a real LLM — monkeypatch handle_alert
    async def fake_handle(payload, llm):
        return "诊断结果：测试告警已处理。"

    monkeypatch.setattr(
        "opspilot.entrypoints.alert_webhook.handle_alert", fake_handle
    )

    response = client.post("/alert", json=fixture)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "测试告警" in data["diagnosis"]


def test_alert_endpoint_handles_error(client, monkeypatch):
    async def fake_handle(payload, llm):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(
        "opspilot.entrypoints.alert_webhook.handle_alert", fake_handle
    )

    response = client.post("/alert", json={"alerts": []})
    assert response.status_code == 200
    assert response.json()["status"] == "error"
