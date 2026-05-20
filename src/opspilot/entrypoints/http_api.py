"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: http_api.py
@DateTime: 2026-05-20
@Docs: FastAPI app exposing agent /ask, /alert, health, and metrics.
    FastAPI 应用：暴露 /ask、/alert、健康检查与指标端点。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel

from opspilot.agent.alert_handler import handle_alert
from opspilot.agent.supervisor import run_supervisor
from opspilot.config import get_settings
from opspilot.entrypoints.auth import require_bearer
from opspilot.llm.client import LLMClient
from opspilot.observability.metrics import record_agent_request, render_metrics

AgentFn = Callable[[str], Awaitable[str]]


class AskRequest(BaseModel):
    """Request body for POST /ask.

    POST /ask 请求体。
    """

    question: str


class AskResponse(BaseModel):
    """Response body for POST /ask.

    POST /ask 响应体。
    """

    answer: str


async def _default_agent(question: str) -> str:
    """Default agent implementation using Supervisor.

    默认 Agent 实现：通过 Supervisor 处理问题。
    """
    settings = get_settings()
    llm = LLMClient(settings)
    try:
        return await run_supervisor(question, llm)
    finally:
        await llm.aclose()


def create_app(agent: AgentFn | None = None) -> FastAPI:
    """Create the OpsPilot FastAPI application.

    创建 OpsPilot FastAPI 应用实例。

    Endpoints:
        GET /healthz — liveness check.
            存活探针。
        GET /metrics — Prometheus metrics.
            Prometheus 指标。
        POST /ask — natural-language question (Bearer auth).
            自然语言提问（需 Bearer 鉴权）。
        POST /alert — Alertmanager webhook payload (Bearer auth).
            Alertmanager 告警载荷（需 Bearer 鉴权）。

    Args:
        agent: Optional async callable(question) -> answer; defaults to Supervisor.
            可选的异步 agent(question) -> answer；默认使用 Supervisor。

    Returns:
        Configured FastAPI app.
            配置完成的 FastAPI 应用。
    """
    agent_fn = agent or _default_agent
    app = FastAPI(title="OpsPilot Agent Core")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")

    @app.post("/ask", response_model=AskResponse, dependencies=[Depends(require_bearer)])
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

    @app.post("/alert", dependencies=[Depends(require_bearer)])
    async def alert(payload: dict) -> dict[str, str]:
        settings = get_settings()
        llm = LLMClient(settings)
        try:
            diagnosis = await handle_alert(payload, llm)
            return {"status": "ok", "diagnosis": diagnosis}
        finally:
            await llm.aclose()

    return app


app = create_app()
