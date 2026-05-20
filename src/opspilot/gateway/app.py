"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: app.py
@DateTime: 2026-05-20
@Docs: FastAPI LLM gateway — proxy, Bearer auth, metrics, provider fallback.
    FastAPI LLM 网关：上游代理、Bearer 鉴权、指标与 Provider 故障转移。
"""

from __future__ import annotations

import secrets
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response

from opspilot.gateway.config import GatewayProvider, GatewaySettings
from opspilot.gateway.metrics import build_registry, render_metrics
from opspilot.gateway.providers import ProviderRouter


async def _proxy_chat(provider: GatewayProvider, payload: dict[str, Any], timeout: float) -> httpx.Response:
    """POST chat/completions to one upstream provider.

    向单个上游 Provider 转发 chat/completions 请求。

    Args:
        provider: Target upstream provider.
            目标上游 Provider。
        payload: OpenAI-compatible request JSON body.
            OpenAI 兼容的请求 JSON 体。
        timeout: HTTP client timeout in seconds.
            HTTP 客户端超时时间（秒）。

    Returns:
        Raw upstream HTTP response.
            上游原始 HTTP 响应。
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(
            f"{provider.base_url}/chat/completions",
            # OpenAI 兼容上游：Authorization: Bearer <api_key>
            headers={"Authorization": f"Bearer {provider.api_key}"},
            json=payload,
        )


async def _proxy_or_none(provider: GatewayProvider, payload: dict[str, Any], timeout: float) -> httpx.Response | None:
    """Call _proxy_chat; return None on transport-level failure (caller may fallback).

    调用 _proxy_chat；传输层失败时返回 None（由调用方触发降级）。

    Args:
        provider: Target upstream provider.
            目标上游 Provider。
        payload: OpenAI-compatible request JSON body.
            OpenAI 兼容的请求 JSON 体。
        timeout: HTTP client timeout in seconds.
            HTTP 客户端超时时间（秒）。

    Returns:
        Upstream response, or None on transport error/timeout.
            上游响应；传输错误或超时时为 None。
    """
    try:
        return await _proxy_chat(provider, payload, timeout)
    except (httpx.TransportError, httpx.TimeoutException):
        return None


def _check_gateway_bearer(authorization: str, expected_token: str) -> None:
    """Validate gateway Bearer token (fail-closed when unconfigured).

    校验网关 Bearer 令牌（未配置 expected_token 时 fail-closed）。

    Args:
        authorization: Raw Authorization header value.
            原始 Authorization 请求头值。
        expected_token: Configured bearer token (without "Bearer " prefix).
            已配置的 Bearer 令牌（不含 "Bearer " 前缀）。

    Raises:
        HTTPException: 503 when token not configured; 401 when mismatch.
            未配置令牌时 503；不匹配时 401。
    """
    if not expected_token:
        raise HTTPException(status_code=503, detail="gateway auth not configured")
    if not secrets.compare_digest(authorization, f"Bearer {expected_token}"):
        raise HTTPException(status_code=401, detail="unauthorized")


def create_app(settings: GatewaySettings | None = None, limiter: Any | None = None) -> FastAPI:
    """Build the FastAPI gateway application with routes and middleware wiring.

    构建 FastAPI 网关应用（注册路由、指标与可选限流）。

    Args:
        settings: Gateway settings; defaults to GatewaySettings() from env.
            网关配置；默认从环境变量加载 GatewaySettings()。
        limiter: Optional rate limiter with async check(client_id); None disables.
            可选限流器（需提供 async check(client_id)）；None 表示不限流。

    Returns:
        Configured FastAPI application.
            配置完成的 FastAPI 应用实例。
    """
    settings = settings or GatewaySettings()
    router = ProviderRouter(settings.providers)

    registry, request_counter, request_latency = build_registry()

    app = FastAPI(title="OpsPilot LLM Gateway")

    @app.get("/metrics")
    async def metrics() -> Response:
        """Expose Prometheus metrics for scraping.

        暴露 Prometheus 指标供抓取。
        """
        return Response(content=render_metrics(registry), media_type="text/plain; version=0.0.4")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe endpoint.

        存活探针端点。
        """
        return {"status": "ok"}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request, authorization: str = Header(default="")) -> Response:
        """OpenAI-compatible chat completions proxy with auth, limit, and fallback.

        OpenAI 兼容的对话补全代理（鉴权、限流、上游降级）。
        """
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
