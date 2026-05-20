"""Tests for shared HTTP auth helpers."""

from __future__ import annotations

import hashlib
import hmac

import httpx
import pytest
from fastapi import Depends, FastAPI

from opspilot.entrypoints.auth import require_bearer, verify_alertmanager_signature


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_bearer)])
    async def protected() -> dict[str, str]:
        return {"ok": "yes"}

    return app


@pytest.fixture
def _clear_settings_cache():
    from opspilot.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_require_bearer_fail_closed_when_token_unconfigured(
    monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
) -> None:
    # 空 token → 503，避免"忘配 token 就裸奔"
    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", "")
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/protected", headers={"Authorization": "Bearer anything"})
        assert r.status_code == 503


@pytest.mark.anyio
async def test_require_bearer_rejects_missing_header(
    monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
) -> None:
    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", "secret123")
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/protected")
        assert r.status_code == 401


@pytest.mark.anyio
async def test_require_bearer_rejects_wrong_token(monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None) -> None:
    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", "secret123")
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/protected", headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401


@pytest.mark.anyio
async def test_require_bearer_accepts_correct_token(
    monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
) -> None:
    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", "secret123")
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/protected", headers={"Authorization": "Bearer secret123"})
        assert r.status_code == 200


def test_verify_alertmanager_signature_fail_closed_when_secret_unconfigured(
    monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
) -> None:
    from fastapi import HTTPException

    monkeypatch.setenv("OPSPILOT_ALERTMANAGER_HMAC_SECRET", "")
    with pytest.raises(HTTPException) as exc:
        verify_alertmanager_signature(b"body", "sig")
    assert exc.value.status_code == 503


def test_verify_alertmanager_signature_accepts_correct_hmac(
    monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
) -> None:
    monkeypatch.setenv("OPSPILOT_ALERTMANAGER_HMAC_SECRET", "shared")
    body = b'{"alerts":[]}'
    sig = hmac.new(b"shared", body, hashlib.sha256).hexdigest()
    # 不抛即通过
    verify_alertmanager_signature(body, sig)


def test_verify_alertmanager_signature_rejects_wrong_hmac(
    monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
) -> None:
    from fastapi import HTTPException

    monkeypatch.setenv("OPSPILOT_ALERTMANAGER_HMAC_SECRET", "shared")
    with pytest.raises(HTTPException) as exc:
        verify_alertmanager_signature(b'{"alerts":[]}', "forgedsig")
    assert exc.value.status_code == 401
