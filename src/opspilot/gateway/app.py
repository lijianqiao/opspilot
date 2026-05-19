"""FastAPI application wiring for the LLM gateway."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Response

from opspilot.gateway.config import GatewayProvider, GatewaySettings
from opspilot.gateway.providers import ProviderRouter


async def _proxy_chat(provider: GatewayProvider, payload: dict[str, Any], timeout: float) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(
            f"{provider.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {provider.api_key}"},
            json=payload,
        )


def create_app(settings: GatewaySettings | None = None, limiter: Any | None = None) -> FastAPI:
    settings = settings or GatewaySettings()
    router = ProviderRouter(settings.providers)

    app = FastAPI(title="OpsPilot LLM Gateway")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        client_id = request.headers.get("x-opspilot-client", request.client.host if request.client else "unknown")
        if limiter is not None:
            limit = await limiter.check(client_id)
            if not limit.allowed:
                raise HTTPException(status_code=429, detail="rate limit exceeded")

        payload = await request.json()
        provider = router.select()
        upstream = await _proxy_chat(provider, payload, settings.provider_timeout_seconds)

        if upstream.status_code >= 500:
            fallback = router.fallback_after(provider)
            if fallback is not None:
                upstream = await _proxy_chat(fallback, payload, settings.provider_timeout_seconds)

        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    return app
