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

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import ValidationError

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
    PendingConfirmationInternalView,
    PendingConfirmationView,
)
from opspilot.entrypoints.auth import require_bearer, require_channel_internal_bearer
from opspilot.entrypoints.body_limits import (
    MAX_AGENT_BODY_BYTES,
    MAX_ALERT_BODY_BYTES,
    content_length_exceeds,
    read_limited_json,
    require_alertmanager_payload,
    require_json_object,
    too_large_response,
)
from opspilot.entrypoints.feishu_callback import handle_card_action
from opspilot.llm.client import CircuitBreakerState, LLMClient
from opspilot.observability.metrics import record_agent_request, render_metrics

AgentFn = Callable[[str], Awaitable[str]]
_LLM_BREAKER = CircuitBreakerState()


async def _run_agent(question: str, *, plan: bool = False, confirmed_request_id: str | None = None) -> str:
    """Run Supervisor or Plan-Execute against agent-core LLM client.

    使用 agent-core 内 LLM 客户端运行 Supervisor 或 Plan-Execute。

    Args:
        question: User question after strip.
            去空白后的用户问题。
        plan: If True, use Plan-Execute instead of Supervisor.
            为 True 时使用 Plan-Execute，否则 Supervisor。
        confirmed_request_id: Optional id to resume after HITL approval.
            可选，人工确认后继续执行时传入的 request_id。

    Returns:
        Agent answer text.
            Agent 回答文本。
    """
    settings = get_settings()
    llm = LLMClient(settings, breaker=_LLM_BREAKER)
    try:
        if plan:
            return await run_plan_execute(question, llm, confirmed_request_id=confirmed_request_id)
        return await run_supervisor(question, llm, confirmed_request_id=confirmed_request_id)
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

    @app.middleware("http")
    async def reject_large_bodies(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Reject requests with overly large bodies.
        拒绝请求体过大的请求。
        """
        limit = None
        if request.url.path == "/ask":
            limit = MAX_AGENT_BODY_BYTES
        elif request.url.path == "/alert":
            limit = MAX_ALERT_BODY_BYTES
        if limit is not None and content_length_exceeds(request, limit):
            return too_large_response()
        return await call_next(request)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe endpoint.
        存活探针端点。
        """
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics() -> Response:
        """Expose Prometheus metrics for scraping.
        暴露 Prometheus 指标供抓取。
        """
        return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")

    @app.post("/ask", response_model=AskResponse, dependencies=[Depends(require_bearer)])
    async def ask(request: Request) -> AskResponse:
        """POST /ask and return the answer text.
        调用 POST /ask 并返回回答文本。

        Args:
            request: Incoming HTTP request.
                入站 HTTP 请求。

        Returns:
            AskResponse with answer text.
                含回答文本的 AskResponse。

        Raises:
            HTTPException: 422 if validation fails, 413 if body too large.
                验证失败时 422，请求体过大时 413。
        """
        payload = require_json_object(await read_limited_json(request, MAX_AGENT_BODY_BYTES))
        try:
            body = AskRequest.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        question = body.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="question is required")
        try:
            if use_injected_agent:
                assert agent_fn is not None
                answer = await agent_fn(question)
            elif body.confirmed_request_id is None:
                answer = await _run_agent(question, plan=body.plan)
            else:
                answer = await _run_agent(question, plan=body.plan, confirmed_request_id=body.confirmed_request_id)
        except Exception:
            record_agent_request(endpoint="/ask", status="error")
            raise
        record_agent_request(endpoint="/ask", status="success")
        return AskResponse(answer=answer)

    @app.post("/alert", dependencies=[Depends(require_bearer)])
    async def alert(request: Request) -> dict[str, str]:
        """POST /alert and return the diagnosis.
        调用 POST /alert 并返回诊断结果。

        Args:
            request: Incoming HTTP request.
                入站 HTTP 请求。

        Returns:
            Dict with status and diagnosis fields.
                含 status 与 diagnosis 字段的字典。
        """
        payload = require_alertmanager_payload(
            require_json_object(await read_limited_json(request, MAX_ALERT_BODY_BYTES))
        )
        settings = get_settings()
        llm = LLMClient(settings, breaker=_LLM_BREAKER)
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
        """GET /channels/pending/{request_id} and return the pending confirmation.
        调用 GET /channels/pending/{request_id} 并返回待确认操作。

        Args:
            request_id: Pending confirmation id.
                待确认操作 ID。

        Returns:
            PendingConfirmationView with request_id, tool, and tool_input.
                含 request_id、tool 和 tool_input 的 PendingConfirmationView。
        """
        pc = STORE.get_pending(request_id)
        if pc is None:
            raise HTTPException(status_code=404, detail="pending not found or expired")
        return PendingConfirmationView(
            request_id=pc.request_id,
            tool=pc.tool,
            tool_input=pc.tool_input,
        )

    @app.get(
        "/internal/channels/pending/{request_id}",
        response_model=PendingConfirmationInternalView,
        dependencies=[Depends(require_channel_internal_bearer)],
    )
    async def get_pending_internal(request_id: str) -> PendingConfirmationInternalView:
        """GET /internal/channels/pending/{request_id} and return the pending confirmation.
        调用 GET /internal/channels/pending/{request_id} 并返回待确认操作。

        Args:
            request_id: Pending confirmation id.
                待确认操作 ID。

        Returns:
            PendingConfirmationInternalView with request_id, tool, tool_input, and token.
                含 request_id、tool、tool_input 和 token 的 PendingConfirmationInternalView。
        """
        pc = STORE.get_pending(request_id)
        if pc is None:
            raise HTTPException(status_code=404, detail="pending not found or expired")
        return PendingConfirmationInternalView(
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
        """POST /channels/feishu/card-action and return the message.
        调用 POST /channels/feishu/card-action 并返回消息。

        Args:
            body: CardActionRequest payload.
                卡片操作请求载荷。

        Returns:
            CardActionResponse with message.
                含消息的 CardActionResponse。
        """
        payload = {"action": body.action, "operator": body.operator or {}}
        msg = handle_card_action(payload, store=STORE)
        return CardActionResponse(message=msg)

    return app


app = create_app()
