"""FastAPI application exposing the OpsPilot agent via HTTP.

Endpoints:
  GET  /healthz  - Liveness/readiness check
  POST /ask      - Natural-language question, returns agent answer
  POST /alert    - Alertmanager webhook, returns diagnosis
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

from opspilot.observability.metrics import record_agent_request, render_metrics

from opspilot.agent.alert_handler import handle_alert
from opspilot.agent.supervisor import run_supervisor
from opspilot.config import get_settings
from opspilot.llm.client import LLMClient

AgentFn = Callable[[str], Awaitable[str]]


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


async def _default_agent(question: str) -> str:
    settings = get_settings()
    llm = LLMClient(settings)
    try:
        return await run_supervisor(question, llm)
    finally:
        await llm.aclose()


def create_app(agent: AgentFn | None = None) -> FastAPI:
    agent_fn = agent or _default_agent
    app = FastAPI(title="OpsPilot Agent Core")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")

    @app.post("/ask", response_model=AskResponse)
    async def ask(request: AskRequest) -> AskResponse:
        question = request.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="question is required")
        try:
            answer = await agent_fn(question)
        except Exception:
            record_agent_request(endpoint="/ask", status="error")
            raise
        record_agent_request(endpoint="/ask", status="success")
        return AskResponse(answer=answer)

    @app.post("/alert")
    async def alert(payload: dict) -> dict[str, str]:
        settings = get_settings()
        llm = LLMClient(settings)
        try:
            diagnosis = await handle_alert(payload, llm)
            return {"status": "ok", "diagnosis": diagnosis}
        finally:
            await llm.aclose()

    return app
