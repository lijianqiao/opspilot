"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_http_api_channels.py
@DateTime: 2026-05-20
@Docs: Tests channel routes pending lookup and feishu card-action.
    测试渠道路由：pending 查询与飞书卡片回调。
"""

import pytest
from fastapi.testclient import TestClient

from opspilot.agent.confirmation import ConfirmationStore
from opspilot.entrypoints.http_api import create_app


@pytest.fixture
def authed_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", "test-secret")
    from opspilot.config import get_settings

    get_settings.cache_clear()

    async def _ok(q: str) -> str:
        return "ok"

    return TestClient(create_app(agent=_ok))


def test_get_pending_returns_confirmation(authed_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request("kubectl_scale", '{"deployment":"x","replicas":0}')
    monkeypatch.setattr("opspilot.entrypoints.http_api.STORE", store)

    r = authed_client.get(
        f"/channels/pending/{pc.request_id}",
        headers={"Authorization": "Bearer test-secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["request_id"] == pc.request_id
    assert body["token"] == pc.token
    assert body["tool"] == "kubectl_scale"


def test_get_pending_missing_returns_404(authed_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "opspilot.entrypoints.http_api.STORE",
        ConfirmationStore(ttl_seconds=300),
    )
    r = authed_client.get(
        "/channels/pending/nonexistent",
        headers={"Authorization": "Bearer test-secret"},
    )
    assert r.status_code == 404


def test_feishu_card_action_confirm(authed_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request("kubectl_scale", "x")
    monkeypatch.setattr("opspilot.entrypoints.http_api.STORE", store)

    r = authed_client.post(
        "/channels/feishu/card-action",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "action": {"value": {"action": "confirm", "request_id": pc.request_id, "token": pc.token}},
            "operator": {"open_id": "ou_test"},
        },
    )
    assert r.status_code == 200
    assert "已确认" in r.json()["message"]
    assert store.is_confirmed(pc.request_id)
