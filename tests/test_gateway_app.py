"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_gateway_app.py
@DateTime: 2026-05-20
@Docs: Tests LLM Gateway auth, rate limit, and transport fallback.
    测试 LLM Gateway 鉴权、限流与传输层 fallback。
"""

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
    """
    Verify healthz returns ok.

    验证：healthz returns ok。
    """
    app = create_app(settings=_settings(), limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_metrics_endpoint_exposes_prometheus_text() -> None:
    # /metrics 公开不鉴权
    """
    Verify metrics endpoint exposes prometheus text.

    验证：metrics endpoint exposes prometheus text。
    """
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
    """
    Verify chat completions proxies to provider.

    验证：chat completions proxies to provider。
    """
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
    """
    Verify chat completions requires gateway bearer.

    验证：chat completions requires gateway bearer。
    """
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
    """
    Verify chat completions fail closed when auth unconfigured.

    验证：chat completions fail closed when auth unconfigured。
    """
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
    """
    Verify rate limit blocks request before provider call.

    验证：rate limit blocks request before provider call。
    """
    app = create_app(settings=_settings(), limiter=BlockAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json={"model": "x", "messages": []}, headers=_bearer())
    assert resp.status_code == 429
    assert "rate limit" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_chat_completions_rejects_large_message_content() -> None:
    """
    Verify chat completions rejects large message content.

    验证：chat completions rejects large message content。
    """
    app = create_app(settings=_settings(), limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": "x", "messages": [{"role": "user", "content": "x" * 200_001}]},
            headers=_bearer(),
        )
    assert resp.status_code == 413


@pytest.mark.anyio
async def test_chat_completions_rejects_non_object_payload() -> None:
    """
    Verify chat completions rejects non object payload.

    验证：chat completions rejects non object payload。
    """
    app = create_app(settings=_settings(), limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json=[], headers=_bearer())
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_chat_completions_rejects_non_list_messages() -> None:
    """
    Verify chat completions rejects non list messages.

    验证：chat completions rejects non list messages。
    """
    app = create_app(settings=_settings(), limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": "x", "messages": {"content": "x" * 200_001}},
            headers=_bearer(),
        )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_chat_completions_rejects_non_object_message_items() -> None:
    """
    Verify chat completions rejects non object message items.

    验证：chat completions rejects non object message items。
    """
    app = create_app(settings=_settings(), limiter=AllowAllLimiter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": "x", "messages": ["x" * 200_001]},
            headers=_bearer(),
        )
    assert resp.status_code == 422


@pytest.mark.anyio
@respx.mock
async def test_fallback_on_transport_error_not_only_5xx() -> None:
    # 审查报告：原 fallback 仅 status>=500；transport/timeout 错误直接 500 无降级。
    # 现在 transport 异常也应触发 fallback provider。
    """
    Verify fallback on transport error not only 5xx.

    验证：fallback on transport error not only 5xx。
    """
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
    """
    Verify all providers unreachable returns 502.

    验证：all providers unreachable returns 502。
    """
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
