"""Tests for the OpsPilot agent HTTP API."""

from __future__ import annotations

import httpx
import pytest

from opspilot.entrypoints.http_api import create_app


async def fake_agent(question: str) -> str:
    return f"answer: {question}"


@pytest.mark.anyio
async def test_healthz() -> None:
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_ask_delegates_to_agent() -> None:
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "default 有哪些 pod 不正常"})
    assert resp.status_code == 200
    assert resp.json() == {"answer": "answer: default 有哪些 pod 不正常"}


@pytest.mark.anyio
async def test_ask_rejects_empty_question() -> None:
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "   "})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_metrics_endpoint() -> None:
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "opspilot_agent_requests_total" in resp.text
