"""FastAPI HTTP endpoint for Alertmanager webhooks.

Start with: uvicorn opspilot.entrypoints.alert_webhook:app --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request

from opspilot.agent.alert_handler import handle_alert
from opspilot.config import get_settings
from opspilot.llm.client import LLMClient

logger = logging.getLogger(__name__)
app = FastAPI(title="OpsPilot Alert Handler")


@app.post("/alert")
async def receive_alert(request: Request) -> dict[str, str]:
    """Receive Alertmanager webhook, return diagnosis."""
    payload = await request.json()
    logger.info("Alert webhook received: %s alert(s)", len(payload.get("alerts", [])))

    settings = get_settings()
    llm = LLMClient(settings)
    try:
        report = await handle_alert(payload, llm)
        return {"status": "ok", "diagnosis": report}
    except Exception:
        logger.exception("Alert handling failed")
        return {"status": "error", "diagnosis": "告警处理失败，请检查日志。"}
    finally:
        await llm.aclose()
