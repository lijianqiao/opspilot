"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_http_api.py
@DateTime: 2026-05-20
@Docs: Tests FastAPI /ask /alert /healthz with auth.
    测试 FastAPI /ask /alert /healthz 与鉴权。
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from opspilot.entrypoints.http_api import create_app


async def fake_agent(question: str) -> str:
    return f"answer: {question}"


@pytest.fixture
def auth_token(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Configure the server-side bearer token and yield it; clear cache around test."""
    from opspilot.config import get_settings

    token = "test-token-123"
    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", token)
    get_settings.cache_clear()
    try:
        yield token
    finally:
        get_settings.cache_clear()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_healthz() -> None:
    # /healthz 不鉴权
    """
    Verify healthz.

    验证：healthz。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_metrics_endpoint() -> None:
    # /metrics 不鉴权
    """
    Verify metrics endpoint.

    验证：metrics endpoint。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "opspilot_agent_requests_total" in resp.text


@pytest.mark.anyio
async def test_ask_delegates_to_agent(auth_token: str) -> None:
    """
    Verify ask delegates to agent.

    验证：ask delegates to agent。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "default 有哪些 pod 不正常"}, headers=_bearer(auth_token))
    assert resp.status_code == 200
    assert resp.json() == {"answer": "answer: default 有哪些 pod 不正常"}


@pytest.mark.anyio
async def test_ask_rejects_empty_question(auth_token: str) -> None:
    """
    Verify ask rejects empty question.

    验证：ask rejects empty question。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "   "}, headers=_bearer(auth_token))
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_ask_rejects_oversized_question(auth_token: str) -> None:
    """
    Verify ask rejects oversized question.

    验证：ask rejects oversized question。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "x" * 4001}, headers=_bearer(auth_token))
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_ask_rejects_oversized_body(auth_token: str) -> None:
    """
    Verify ask rejects oversized body.

    验证：ask rejects oversized body。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ask",
            content=b'{"question":"' + (b"x" * 600_000) + b'"}',
            headers={**_bearer(auth_token), "content-type": "application/json"},
        )
    assert resp.status_code == 413


@pytest.mark.anyio
async def test_ask_requires_bearer(auth_token: str) -> None:
    """
    Verify ask requires bearer.

    验证：ask requires bearer。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 无 header → 401
        r1 = await client.post("/ask", json={"question": "x"})
        assert r1.status_code == 401
        # 错 token → 401
        r2 = await client.post("/ask", json={"question": "x"}, headers={"Authorization": "Bearer wrong"})
        assert r2.status_code == 401


@pytest.mark.anyio
async def test_ask_plan_mode(monkeypatch: pytest.MonkeyPatch, auth_token: str) -> None:
    """
    Verify ask plan mode.

    验证：ask plan mode。
    """
    called: dict[str, bool] = {"plan": False}

    async def mock_run_agent(question: str, *, plan: bool = False, confirmed_request_id: str | None = None) -> str:
        called["plan"] = plan
        return "planned"

    monkeypatch.setattr("opspilot.entrypoints.http_api._run_agent", mock_run_agent)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ask",
            json={"question": "重启服务", "plan": True},
            headers=_bearer(auth_token),
        )
    assert resp.status_code == 200
    assert resp.json()["answer"] == "planned"
    assert called["plan"] is True


@pytest.mark.anyio
async def test_ask_passes_confirmed_request_id_in_production_path(
    monkeypatch: pytest.MonkeyPatch, auth_token: str
) -> None:
    """
    Verify ask passes confirmed request id in production path.

    验证：ask passes confirmed request id in production path。
    """
    called: dict[str, str | None] = {"confirmed_request_id": None}

    async def mock_run_agent(question: str, *, plan: bool = False, confirmed_request_id: str | None = None) -> str:
        called["confirmed_request_id"] = confirmed_request_id
        return f"ok: {question}"

    monkeypatch.setattr("opspilot.entrypoints.http_api._run_agent", mock_run_agent)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ask",
            json={"question": "approve", "confirmed_request_id": "req-123"},
            headers=_bearer(auth_token),
        )
    assert resp.status_code == 200
    assert resp.json()["answer"] == "ok: approve"
    assert called["confirmed_request_id"] == "req-123"


@pytest.mark.anyio
async def test_alert_rejects_non_object_payload(auth_token: str) -> None:
    """
    Verify alert rejects non object payload.

    验证：alert rejects non object payload。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/alert", json=[], headers=_bearer(auth_token))
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_alert_rejects_malformed_alerts_field(auth_token: str) -> None:
    """
    Verify alert rejects malformed alerts field.

    验证：alert rejects malformed alerts field。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        scalar_resp = await client.post("/alert", json={"alerts": 1}, headers=_bearer(auth_token))
        item_resp = await client.post("/alert", json={"alerts": ["bad"]}, headers=_bearer(auth_token))
    assert scalar_resp.status_code == 422
    assert item_resp.status_code == 422


@pytest.mark.anyio
async def test_ask_fail_closed_when_token_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify ask fail closed when token unconfigured.

    验证：ask fail closed when token unconfigured。
    """
    from opspilot.config import get_settings

    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", "")
    get_settings.cache_clear()
    try:
        app = create_app(agent=fake_agent)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post("/ask", json={"question": "x"}, headers={"Authorization": "Bearer anything"})
        # 服务端无 token 配置 → 503，避免裸奔
        assert r.status_code == 503
    finally:
        get_settings.cache_clear()
