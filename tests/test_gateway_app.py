"""Tests for the gateway FastAPI app."""

from __future__ import annotations

import httpx
import pytest
import respx

from opspilot.gateway.app import create_app
from opspilot.gateway.config import GatewayProvider, GatewaySettings
from opspilot.gateway.rate_limit import RateLimitResult

_TOKEN = "gw-test-token-456"


def _settings(providers: list[GatewayProvider] | None = None) -> GatewaySettings:
    return GatewaySettings(
        providers=providers
        or [GatewayProvider(name="local", base_url="http://provider.test/v1", api_key="sk-provider")],
        auth_token=_TOKEN,
    )


def _bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TOKEN}"}


class AllowAllLimiter:
    async def check(self, client_id: str) -> RateLimitResult:
        return RateLimitResult(allowed=True, remaining=59)


class BlockAllLimiter:
    async def check(self, client_id: str) -> RateLimitResult:
        return RateLimitResult(allowed=False, remaining=0)


@pytest.mark.anyio
async def test_healthz_returns_ok() -> None:
    # /healthz 公开不鉴权
    app = create_app(settings=_settings(), limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_metrics_endpoint_exposes_prometheus_text() -> None:
    # /metrics 公开不鉴权
    app = create_app(settings=_settings(), limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "opspilot_gateway_requests_total" in resp.text


@pytest.mark.anyio
@respx.mock
async def test_chat_completions_proxies_to_provider() -> None:
    respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})
    )
    app = create_app(settings=_settings(), limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json={"model": "qwen", "messages": []}, headers=_bearer())
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "hello"
    request = respx.calls.last.request
    assert request.headers["authorization"] == "Bearer sk-provider"


@pytest.mark.anyio
async def test_chat_completions_requires_gateway_bearer() -> None:
    app = create_app(settings=_settings(), limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 无 header → 401
        r1 = await client.post("/v1/chat/completions", json={"model": "x", "messages": []})
        assert r1.status_code == 401
        # 错 token → 401
        r2 = await client.post(
            "/v1/chat/completions",
            json={"model": "x", "messages": []},
            headers={"Authorization": "Bearer wrong"},
        )
        assert r2.status_code == 401


@pytest.mark.anyio
async def test_chat_completions_fail_closed_when_auth_unconfigured() -> None:
    # 服务端 auth_token 为空 → 503 fail-closed
    app = create_app(
        settings=GatewaySettings(
            providers=[GatewayProvider(name="local", base_url="http://x", api_key="k")],
            auth_token="",
        ),
        limiter=AllowAllLimiter(),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "x", "messages": []},
            headers={"Authorization": "Bearer anything"},
        )
        assert r.status_code == 503


@pytest.mark.anyio
async def test_rate_limit_blocks_request_before_provider_call() -> None:
    app = create_app(settings=_settings(), limiter=BlockAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json={"model": "x", "messages": []}, headers=_bearer())
    assert resp.status_code == 429
    assert "rate limit" in resp.json()["detail"].lower()


@pytest.mark.anyio
@respx.mock
async def test_fallback_on_transport_error_not_only_5xx() -> None:
    # 审查报告：原 fallback 仅 status>=500；transport/timeout 错误直接 500 无降级。
    # 现在 transport 异常也应触发 fallback provider。
    settings = GatewaySettings(
        providers=[
            GatewayProvider(name="primary", base_url="http://primary.test/v1", api_key="kp"),
            GatewayProvider(name="backup", base_url="http://backup.test/v1", api_key="kb"),
        ],
        auth_token=_TOKEN,
    )
    respx.post("http://primary.test/v1/chat/completions").mock(side_effect=httpx.ConnectError("primary down"))
    respx.post("http://backup.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "from backup"}}]})
    )
    app = create_app(settings=settings, limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json={"model": "x", "messages": []}, headers=_bearer())
    assert resp.status_code == 200
    assert "from backup" in resp.text


@pytest.mark.anyio
@respx.mock
async def test_all_providers_unreachable_returns_502() -> None:
    settings = GatewaySettings(
        providers=[
            GatewayProvider(name="primary", base_url="http://primary.test/v1", api_key="kp"),
            GatewayProvider(name="backup", base_url="http://backup.test/v1", api_key="kb"),
        ],
        auth_token=_TOKEN,
    )
    respx.post("http://primary.test/v1/chat/completions").mock(side_effect=httpx.ConnectError("down"))
    respx.post("http://backup.test/v1/chat/completions").mock(side_effect=httpx.ConnectError("down"))
    app = create_app(settings=settings, limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json={"model": "x", "messages": []}, headers=_bearer())
    assert resp.status_code == 502
