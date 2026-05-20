"""Shared HTTP auth: Bearer token + Alertmanager HMAC signature.

设计原则：fail-closed —— 若服务侧未配置密钥/秘密，直接 503
（"unconfigured" 状态比"裸奔"安全得多）。常量时间比较防时序侧信道。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Header, HTTPException

from opspilot.config import get_settings


async def require_bearer(authorization: str = Header(default="")) -> None:
    """FastAPI dependency：校验 Authorization: Bearer <token>。

    服务侧 OPSPILOT_API_AUTH_TOKEN 为空 → 503（fail-closed）。
    Header 缺失/格式错/值不匹配 → 401。
    """
    token = get_settings().api_auth_token
    if not token:
        raise HTTPException(status_code=503, detail="server auth not configured")
    expected = f"Bearer {token}"
    if not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def verify_alertmanager_signature(raw_body: bytes, signature: str) -> None:
    """校验 Alertmanager webhook HMAC-SHA256(body, secret) 签名。

    服务侧 OPSPILOT_ALERTMANAGER_HMAC_SECRET 为空 → 503。
    签名不匹配 → 401。
    """
    secret = get_settings().alertmanager_hmac_secret
    if not secret:
        raise HTTPException(status_code=503, detail="alertmanager hmac not configured")
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="invalid signature")
