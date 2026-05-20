"""FastAPI application wiring for the LLM gateway."""

from __future__ import annotations

import secrets
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response

from opspilot.gateway.config import GatewayProvider, GatewaySettings
from opspilot.gateway.metrics import build_registry, render_metrics
from opspilot.gateway.providers import ProviderRouter


async def _proxy_chat(provider: GatewayProvider, payload: dict[str, Any], timeout: float) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(
            f"{provider.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {provider.api_key}"},
            json=payload,
        )


async def _proxy_or_none(provider: GatewayProvider, payload: dict[str, Any], timeout: float) -> httpx.Response | None:
    """Call _proxy_chat, return None on transport-level failure (caller falls back)."""
    try:
        return await _proxy_chat(provider, payload, timeout)
    except (httpx.TransportError, httpx.TimeoutException):
        return None


def _check_gateway_bearer(authorization: str, expected_token: str) -> None:
    """Gateway Bearer check (fail-closed when unconfigured)."""
    if not expected_token:
        raise HTTPException(status_code=503, detail="gateway auth not configured")
    if not secrets.compare_digest(authorization, f"Bearer {expected_token}"):
        raise HTTPException(status_code=401, detail="unauthorized")


def create_app(settings: GatewaySettings | None = None, limiter: Any | None = None) -> FastAPI:
    settings = settings or GatewaySettings()
    router = ProviderRouter(settings.providers)

    registry, request_counter, request_latency = build_registry()

    app = FastAPI(title="OpsPilot LLM Gateway")

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=render_metrics(registry), media_type="text/plain; version=0.0.4")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request, authorization: str = Header(default="")) -> Response:
        # 审查报告 #2：默认 limiter=None + 无鉴权 = 开放代理可盗刷上游 key
        # → 装 Bearer 鉴权（fail-closed），未配 token 直接 503
        _check_gateway_bearer(authorization, settings.auth_token)

        client_id = request.headers.get("x-opspilot-client", request.client.host if request.client else "unknown")
        if limiter is not None:
            limit = await limiter.check(client_id)
            if not limit.allowed:
                raise HTTPException(status_code=429, detail="rate limit exceeded")

        payload = await request.json()
        provider = router.select()
        with request_latency.labels(provider=provider.name).time():
            upstream = await _proxy_or_none(provider, payload, settings.provider_timeout_seconds)

        if upstream is not None:
            request_counter.labels(provider=provider.name, status=str(upstream.status_code)).inc()

        # 审查报告 fix：fallback 不仅在 5xx，transport error / timeout 也触发
        need_fallback = upstream is None or upstream.status_code >= 500
        if need_fallback:
            fallback = router.fallback_after(provider)
            if fallback is not None:
                with request_latency.labels(provider=fallback.name).time():
                    fb_resp = await _proxy_or_none(fallback, payload, settings.provider_timeout_seconds)
                if fb_resp is not None:
                    request_counter.labels(provider=fallback.name, status=str(fb_resp.status_code)).inc()
                    upstream = fb_resp

        if upstream is None:
            # 主备都 transport 失败 → 502 Bad Gateway
            raise HTTPException(status_code=502, detail="all providers unreachable")

        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    return app


app = create_app()
