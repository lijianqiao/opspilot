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

from opspilot.agent.alert_handler import handle_alert
from opspilot.agent.confirmation import STORE
from opspilot.agent.plan_execute import run_plan_execute
from opspilot.agent.supervisor import run_supervisor
from opspilot.config import get_settings
from opspilot.entrypoints.agent_api_models import (
    AskRequest,
    AskResponse,
    CardActionRequest,
    CardActionResponse,
    PendingConfirmationView,
)
from opspilot.entrypoints.auth import require_bearer
from opspilot.entrypoints.feishu_callback import handle_card_action
from opspilot.llm.client import LLMClient
from opspilot.observability.metrics import record_agent_request, render_metrics

AgentFn = Callable[[str], Awaitable[str]]


async def _run_agent(question: str, *, plan: bool = False) -> str:
    """Run Supervisor or Plan-Execute against agent-core LLM client.

    使用 agent-core 内 LLM 客户端运行 Supervisor 或 Plan-Execute。

    Args:
        question: User question after strip.
            去空白后的用户问题。
        plan: If True, use Plan-Execute instead of Supervisor.
            为 True 时使用 Plan-Execute，否则 Supervisor。

    Returns:
        Agent answer text.
            Agent 回答文本。
    """
    settings = get_settings()
    llm = LLMClient(settings)
    try:
        if plan:
            return await run_plan_execute(question, llm)
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
        GET /channels/pending/{request_id} — HITL pending lookup.
            待确认危险操作查询。
        POST /channels/feishu/card-action — Feishu confirm/cancel card.
            飞书确认/取消卡片回调。

    Args:
        agent: Optional async callable(question) -> answer for tests; production uses _run_agent.
            测试用可选 agent(question)；生产路径使用 _run_agent。

    Returns:
        Configured FastAPI app.
            配置完成的 FastAPI 应用。
    """
    use_injected_agent = agent is not None
    agent_fn = agent
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
            if use_injected_agent:
                assert agent_fn is not None
                answer = await agent_fn(question)
            else:
                answer = await _run_agent(question, plan=request.plan)
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

    @app.get(
        "/channels/pending/{request_id}",
        response_model=PendingConfirmationView,
        dependencies=[Depends(require_bearer)],
    )
    async def get_pending(request_id: str) -> PendingConfirmationView:
        pc = STORE.get_pending(request_id)
        if pc is None:
            raise HTTPException(status_code=404, detail="pending not found or expired")
        return PendingConfirmationView(
            request_id=pc.request_id,
            tool=pc.tool,
            tool_input=pc.tool_input,
            token=pc.token,
        )

    @app.post(
        "/channels/feishu/card-action",
        response_model=CardActionResponse,
        dependencies=[Depends(require_bearer)],
    )
    async def feishu_card_action(body: CardActionRequest) -> CardActionResponse:
        payload = {"action": body.action, "operator": body.operator or {}}
        msg = handle_card_action(payload, store=STORE)
        return CardActionResponse(message=msg)

    return app


app = create_app()
