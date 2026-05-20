"""FastAPI HTTP endpoint for Alertmanager webhooks.

Start with: uvicorn opspilot.entrypoints.alert_webhook:app --port 8000

安全：
- HMAC-SHA256 verify_alertmanager_signature(body, sig) 校验 X-OpsPilot-Signature 头；
  未配置 OPSPILOT_ALERTMANAGER_HMAC_SECRET → 503 fail-closed，避免裸奔。
- 异常响应固定文案，避免堆栈/DSN/密钥泄露（审查报告）。
"""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, Header, Request

from opspilot.agent.alert_handler import handle_alert
from opspilot.agent.guardrails import redact
from opspilot.config import get_settings
from opspilot.entrypoints.auth import verify_alertmanager_signature
from opspilot.llm.client import LLMClient

logger = logging.getLogger(__name__)
app = FastAPI(title="OpsPilot Alert Handler")


@app.post("/alert")
async def receive_alert(
    request: Request, x_opspilot_signature: str = Header(default="")
) -> dict[str, str]:
    """Receive Alertmanager webhook, verify HMAC signature, return diagnosis."""
    raw_body = await request.body()
    # Fail-closed on unconfigured secret; raises HTTPException(401) on bad sig.
    verify_alertmanager_signature(raw_body, x_opspilot_signature)

    payload = json.loads(raw_body)
    logger.info("Alert webhook received: %s alert(s)", len(payload.get("alerts", [])))

    settings = get_settings()
    llm = LLMClient(settings)
    try:
        report = await handle_alert(payload, llm)
        return {"status": "ok", "diagnosis": report}
    except Exception:
        logger.exception("Alert handling failed")
        return {"status": "error", "diagnosis": redact("告警处理失败，请检查日志。")}
    finally:
        await llm.aclose()
