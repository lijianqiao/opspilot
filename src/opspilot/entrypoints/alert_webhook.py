"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: alert_webhook.py
@DateTime: 2026-05-20
@Docs: FastAPI Alertmanager webhook — HMAC verify and alert diagnosis.
    Alertmanager Webhook 端点：HMAC 校验与告警诊断。
"""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, Header, HTTPException, Request

from opspilot.agent.alert_handler import handle_alert
from opspilot.agent.guardrails import redact
from opspilot.config import get_settings
from opspilot.entrypoints.auth import verify_alertmanager_signature
from opspilot.entrypoints.body_limits import (
    MAX_ALERT_BODY_BYTES,
    content_length_exceeds,
    read_limited_body,
    require_alertmanager_payload,
    require_json_object,
    too_large_response,
)
from opspilot.llm.client import CircuitBreakerState, LLMClient

logger = logging.getLogger(__name__)
_LLM_BREAKER = CircuitBreakerState()
app = FastAPI(title="OpsPilot Alert Handler")


@app.middleware("http")
async def reject_large_bodies(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Reject requests with overly large bodies.
    拒绝请求体过大的请求。
    """
    if request.url.path == "/alert" and content_length_exceeds(request, MAX_ALERT_BODY_BYTES):
        return too_large_response()
    return await call_next(request)


@app.post("/alert")
async def receive_alert(request: Request, x_opspilot_signature: str = Header(default="")) -> dict[str, str]:
    """Receive Alertmanager webhook, verify HMAC, return diagnosis.

    接收 Alertmanager Webhook，校验 HMAC 签名并返回诊断结果。

    Security: unconfigured OPSPILOT_ALERTMANAGER_HMAC_SECRET → 503 fail-closed;
    error responses use fixed redacted text to avoid leaking secrets/stack traces.
    安全：未配置密钥时 503；异常响应使用固定脱敏文案，避免泄露密钥或堆栈。

    Args:
        request: Incoming HTTP request (body read for HMAC).
            入站 HTTP 请求（读取 body 用于 HMAC）。
        x_opspilot_signature: Hex HMAC digest header.
            X-OpsPilot-Signature 十六进制摘要头。

    Returns:
        Dict with status and diagnosis fields.
            含 status 与 diagnosis 字段的字典。
    """
    raw_body = await read_limited_body(request, MAX_ALERT_BODY_BYTES)
    # Fail-closed on unconfigured secret; raises HTTPException(401) on bad sig.
    verify_alertmanager_signature(raw_body, x_opspilot_signature)

    try:
        payload = require_alertmanager_payload(require_json_object(json.loads(raw_body)))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc
    logger.info("Alert webhook received: %s alert(s)", len(payload.get("alerts", [])))

    settings = get_settings()
    llm = LLMClient(settings, breaker=_LLM_BREAKER)
    try:
        report = await handle_alert(payload, llm)
        return {"status": "ok", "diagnosis": report}
    except Exception:
        logger.exception("Alert handling failed")
        return {"status": "error", "diagnosis": redact("告警处理失败，请检查日志。")}
    finally:
        await llm.aclose()
