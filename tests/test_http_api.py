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
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_metrics_endpoint() -> None:
    # /metrics 不鉴权
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "opspilot_agent_requests_total" in resp.text


@pytest.mark.anyio
async def test_ask_delegates_to_agent(auth_token: str) -> None:
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "default 有哪些 pod 不正常"}, headers=_bearer(auth_token))
    assert resp.status_code == 200
    assert resp.json() == {"answer": "answer: default 有哪些 pod 不正常"}


@pytest.mark.anyio
async def test_ask_rejects_empty_question(auth_token: str) -> None:
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "   "}, headers=_bearer(auth_token))
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_ask_requires_bearer(auth_token: str) -> None:
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
    called: dict[str, bool] = {"plan": False}

    async def mock_run_agent(question: str, *, plan: bool = False) -> str:
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
async def test_ask_fail_closed_when_token_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
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
