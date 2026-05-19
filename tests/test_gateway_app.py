"""Tests for the gateway FastAPI app."""

from __future__ import annotations

import httpx
import pytest
import respx

from opspilot.gateway.app import create_app
from opspilot.gateway.config import GatewayProvider, GatewaySettings
from opspilot.gateway.rate_limit import RateLimitResult


class AllowAllLimiter:
    async def check(self, client_id: str) -> RateLimitResult:
        return RateLimitResult(allowed=True, remaining=59)


class BlockAllLimiter:
    async def check(self, client_id: str) -> RateLimitResult:
        return RateLimitResult(allowed=False, remaining=0)


@pytest.mark.anyio
async def test_healthz_returns_ok() -> None:
    app = create_app(settings=GatewaySettings(), limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
@respx.mock
async def test_chat_completions_proxies_to_provider() -> None:
    settings = GatewaySettings(
        providers=[GatewayProvider(name="local", base_url="http://provider.test/v1", api_key="sk-provider")]
    )
    respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hello"}}]},
        )
    )
    app = create_app(settings=settings, limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json={"model": "qwen", "messages": []})
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "hello"
    request = respx.calls.last.request
    assert request.headers["authorization"] == "Bearer sk-provider"


@pytest.mark.anyio
async def test_rate_limit_blocks_request_before_provider_call() -> None:
    app = create_app(settings=GatewaySettings(), limiter=BlockAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json={"model": "qwen", "messages": []})
    assert resp.status_code == 429
    assert "rate limit" in resp.json()["detail"].lower()
