"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: auth.py
@DateTime: 2026-05-20
@Docs: Shared HTTP auth — Bearer token and Alertmanager HMAC verification.
    共享 HTTP 鉴权：Bearer 令牌与 Alertmanager HMAC 签名校验。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Header, HTTPException

from opspilot.config import get_settings


async def require_bearer(authorization: str = Header(default="")) -> None:
    """FastAPI dependency: validate Authorization Bearer token.

    FastAPI 依赖：校验 Authorization: Bearer 令牌。

    Fail-closed: empty OPSPILOT_API_AUTH_TOKEN → 503; bad/missing header → 401.
    未配置 OPSPILOT_API_AUTH_TOKEN 时返回 503；缺失或错误令牌返回 401。

    Args:
        authorization: Raw Authorization header value.
            Authorization 请求头原始值。

    Raises:
        HTTPException: 503 if auth not configured, 401 if unauthorized.
            未配置鉴权时 503，未授权时 401。
    """
    token = get_settings().api_auth_token
    if not token:
        raise HTTPException(status_code=503, detail="server auth not configured")
    expected = f"Bearer {token}"
    if not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


async def require_channel_internal_bearer(authorization: str = Header(default="")) -> None:
    """Validate the internal channel-adapter Bearer token.
    校验渠道内部认证的 Bearer 令牌。

    Fail-closed: empty OPSPILOT_CHANNEL_INTERNAL_TOKEN → 503; bad/missing header → 401.
    未配置 OPSPILOT_CHANNEL_INTERNAL_TOKEN 时返回 503；缺失或错误令牌返回 401。

    Args:
        authorization: Raw Authorization header value.
            Authorization 请求头原始值。

    Raises:
        HTTPException: 503 if auth not configured, 401 if unauthorized.
            未配置鉴权时 503，未授权时 401。
    """
    token = get_settings().channel_internal_token
    if not token:
        raise HTTPException(status_code=503, detail="channel internal auth not configured")
    expected = f"Bearer {token}"
    if not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def verify_alertmanager_signature(raw_body: bytes, signature: str) -> None:
    """Verify Alertmanager webhook HMAC-SHA256(body, secret) signature.

    校验 Alertmanager Webhook 的 HMAC-SHA256(body, secret) 签名。

    Fail-closed: empty OPSPILOT_ALERTMANAGER_HMAC_SECRET → 503; mismatch → 401.
    未配置密钥时 503；签名不匹配时 401。

    Args:
        raw_body: Raw request body bytes.
            请求体原始字节。
        signature: Hex digest from X-OpsPilot-Signature header.
            X-OpsPilot-Signature 头中的十六进制摘要。

    Raises:
        HTTPException: 503 if secret not configured, 401 if signature invalid.
            未配置密钥时 503，签名无效时 401。
    """
    secret = get_settings().alertmanager_hmac_secret
    if not secret:
        raise HTTPException(status_code=503, detail="alertmanager hmac not configured")
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="invalid signature")
