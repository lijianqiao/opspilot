"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_http_api.py
@DateTime: 2026-05-20
@Docs: Tests FastAPI /ask /alert /healthz with auth.
    测试 FastAPI /ask /alert /healthz 与鉴权。
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest

from opspilot.entrypoints.http_api import create_app


async def fake_agent(question: str) -> str:
    return f"answer: {question}"


@pytest.fixture
def auth_token(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Configure the server-side bearer token and yield it; clear cache around test."""
    from opspilot.config import get_settings

    token = "test-token-123"
    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", token)
    get_settings.cache_clear()
    try:
        yield token
    finally:
        get_settings.cache_clear()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_healthz() -> None:
    # /healthz 不鉴权
    """
    Verify healthz.

    验证：healthz。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_metrics_endpoint() -> None:
    # /metrics 不鉴权
    """
    Verify metrics endpoint.

    验证：metrics endpoint。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "opspilot_agent_requests_total" in resp.text


@pytest.mark.anyio
async def test_ask_delegates_to_agent(auth_token: str) -> None:
    """
    Verify ask delegates to agent.

    验证：ask delegates to agent。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "default 有哪些 pod 不正常"}, headers=_bearer(auth_token))
    assert resp.status_code == 200
    assert resp.json() == {"answer": "answer: default 有哪些 pod 不正常"}


@pytest.mark.anyio
async def test_ask_rejects_empty_question(auth_token: str) -> None:
    """
    Verify ask rejects empty question.

    验证：ask rejects empty question。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "   "}, headers=_bearer(auth_token))
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_ask_rejects_oversized_question(auth_token: str) -> None:
    """
    Verify ask rejects oversized question.

    验证：ask rejects oversized question。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "x" * 4001}, headers=_bearer(auth_token))
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_ask_rejects_oversized_body(auth_token: str) -> None:
    """
    Verify ask rejects oversized body.

    验证：ask rejects oversized body。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ask",
            content=b'{"question":"' + (b"x" * 600_000) + b'"}',
            headers={**_bearer(auth_token), "content-type": "application/json"},
        )
    assert resp.status_code == 413


@pytest.mark.anyio
async def test_ask_requires_bearer(auth_token: str) -> None:
    """
    Verify ask requires bearer.

    验证：ask requires bearer。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 无 header → 401
        r1 = await client.post("/ask", json={"question": "x"})
        assert r1.status_code == 401
        # 错 token → 401
        r2 = await client.post("/ask", json={"question": "x"}, headers={"Authorization": "Bearer wrong"})
        assert r2.status_code == 401


@pytest.mark.anyio
async def test_ask_plan_mode(monkeypatch: pytest.MonkeyPatch, auth_token: str) -> None:
    """
    Verify ask plan mode.

    验证：ask plan mode。
    """
    called: dict[str, bool] = {"plan": False}

    async def mock_run_agent(
        question: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        plan: bool = False,
        confirmed_request_id: str | None = None,
        confirmation_context: dict[str, str] | None = None,
    ) -> str:
        called["plan"] = plan
        return "planned"

    monkeypatch.setattr("opspilot.entrypoints.http_api._run_agent", mock_run_agent)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ask",
            json={"question": "重启服务", "plan": True},
            headers=_bearer(auth_token),
        )
    assert resp.status_code == 200
    assert resp.json()["answer"] == "planned"
    assert called["plan"] is True


@pytest.mark.anyio
async def test_ask_passes_confirmed_request_id_in_production_path(
    monkeypatch: pytest.MonkeyPatch, auth_token: str
) -> None:
    """
    Verify ask passes confirmed request id in production path.

    验证：ask passes confirmed request id in production path。
    """
    called: dict[str, object] = {"confirmed_request_id": None}

    async def mock_run_agent(
        question: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        plan: bool = False,
        confirmed_request_id: str | None = None,
        confirmation_context: dict[str, str] | None = None,
    ) -> str:
        called["confirmed_request_id"] = confirmed_request_id
        called["confirmation_context"] = confirmation_context
        return f"ok: {question}"

    monkeypatch.setattr("opspilot.entrypoints.http_api._run_agent", mock_run_agent)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ask",
            json={"question": "approve", "confirmed_request_id": "req-123"},
            headers=_bearer(auth_token),
        )
    assert resp.status_code == 200
    assert resp.json()["answer"] == "ok: approve"
    assert called["confirmed_request_id"] == "req-123"


@pytest.mark.anyio
async def test_ask_builds_confirmation_context_from_body(monkeypatch: pytest.MonkeyPatch, auth_token: str) -> None:
    """
    Verify /ask builds confirmation_context from channel/chat_id/requester body.

    验证：/ask 根据请求体中的 channel/chat_id/requester 构造 confirmation_context。
    """
    captured: dict[str, object] = {}

    async def mock_run_agent(
        question: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        plan: bool = False,
        confirmed_request_id: str | None = None,
        confirmation_context: dict[str, str] | None = None,
    ) -> str:
        captured["confirmation_context"] = confirmation_context
        return "ok"

    monkeypatch.setattr("opspilot.entrypoints.http_api._run_agent", mock_run_agent)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ask",
            json={
                "question": "restart payment",
                "channel": "feishu",
                "chat_id": "chat-a",
                "requester": "ou_1",
            },
            headers=_bearer(auth_token),
        )
    assert resp.status_code == 200
    assert captured["confirmation_context"] == {
        "channel": "feishu",
        "chat_id": "chat-a",
        "requester": "ou_1",
    }


@pytest.mark.anyio
async def test_ask_confirmation_context_is_none_when_no_channel_info(
    monkeypatch: pytest.MonkeyPatch, auth_token: str
) -> None:
    """
    Verify /ask passes None when no channel/chat/requester is supplied.

    验证：未携带渠道字段时 /ask 透传 confirmation_context=None，保持向后兼容。
    """
    captured: dict[str, object] = {"set": False}

    async def mock_run_agent(
        question: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        plan: bool = False,
        confirmed_request_id: str | None = None,
        confirmation_context: dict[str, str] | None = None,
    ) -> str:
        captured["set"] = True
        captured["confirmation_context"] = confirmation_context
        return "ok"

    monkeypatch.setattr("opspilot.entrypoints.http_api._run_agent", mock_run_agent)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ask",
            json={"question": "list pods"},
            headers=_bearer(auth_token),
        )
    assert resp.status_code == 200
    assert captured["set"] is True
    assert captured["confirmation_context"] is None


@pytest.fixture
def hmac_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Configure OPSPILOT_ALERTMANAGER_HMAC_SECRET for /alert tests."""
    from opspilot.config import get_settings

    secret = "shared-test-secret"
    monkeypatch.setenv("OPSPILOT_ALERTMANAGER_HMAC_SECRET", secret)
    get_settings.cache_clear()
    try:
        yield secret
    finally:
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_alert_rejects_non_object_payload(hmac_secret: str) -> None:
    """
    Verify alert rejects non object payload.

    验证：alert rejects non object payload。
    """
    app = create_app(agent=fake_agent)
    body = b"[]"
    sig = _hmac_sig(body, hmac_secret)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/alert",
            content=body,
            headers={"Content-Type": "application/json", "X-OpsPilot-Signature": sig},
        )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_alert_rejects_malformed_alerts_field(hmac_secret: str) -> None:
    """
    Verify alert rejects malformed alerts field.

    验证：alert rejects malformed alerts field。
    """
    app = create_app(agent=fake_agent)
    scalar_body = b'{"alerts":1}'
    item_body = b'{"alerts":["bad"]}'
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        scalar_resp = await client.post(
            "/alert",
            content=scalar_body,
            headers={
                "Content-Type": "application/json",
                "X-OpsPilot-Signature": _hmac_sig(scalar_body, hmac_secret),
            },
        )
        item_resp = await client.post(
            "/alert",
            content=item_body,
            headers={
                "Content-Type": "application/json",
                "X-OpsPilot-Signature": _hmac_sig(item_body, hmac_secret),
            },
        )
    assert scalar_resp.status_code == 422
    assert item_resp.status_code == 422


@pytest.mark.anyio
async def test_alert_normalizes_grafana_payload(monkeypatch: pytest.MonkeyPatch, hmac_secret: str) -> None:
    """
    Verify /alert routes Grafana payloads through the normalizer.

    验证：/alert 能识别 Grafana 载荷并归一化后再交给 handle_alert。
    """
    from opspilot.alerts.models import NormalizedAlertEvent

    captured: dict[str, NormalizedAlertEvent | None] = {"event": None}

    async def fake_handle(event, llm):  # type: ignore[no-untyped-def]
        captured["event"] = event
        return "grafana ok"

    monkeypatch.setattr("opspilot.entrypoints.http_api.handle_alert", fake_handle)
    app = create_app()
    body = json.dumps(
        {
            "title": "High memory",
            "state": "alerting",
            "ruleName": "MemoryHigh",
            "tags": {"service": "payment", "env": "prod"},
            "message": "memory over threshold",
        }
    ).encode("utf-8")
    sig = _hmac_sig(body, hmac_secret)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/alert",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-OpsPilot-Signature": sig,
                "X-OpsPilot-Alert-Source": "grafana",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["diagnosis"] == "grafana ok"
    event = captured["event"]
    assert event is not None
    assert event.source == "grafana"
    assert event.alerts[0].service == "payment"


@pytest.mark.anyio
async def test_ask_response_echoes_supplied_trace_id(auth_token: str) -> None:
    """
    /ask response echoes incoming X-OpsPilot-Trace-ID for client correlation.

    验证：/ask 在响应头中回显入站 X-OpsPilot-Trace-ID，便于客户端关联。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ask",
            json={"question": "x"},
            headers={**_bearer(auth_token), "X-OpsPilot-Trace-ID": "trace-echo-a"},
        )
    assert resp.status_code == 200
    assert resp.headers.get("x-opspilot-trace-id") == "trace-echo-a"


@pytest.mark.anyio
async def test_ask_response_mints_trace_id_when_missing(auth_token: str) -> None:
    """
    /ask still returns an X-OpsPilot-Trace-ID header even without incoming one.

    验证：未带入站 trace id 时，/ask 仍会生成并在响应头中返回一个 trace id。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ask", json={"question": "x"}, headers=_bearer(auth_token))
    assert resp.status_code == 200
    minted = resp.headers.get("x-opspilot-trace-id")
    assert minted and len(minted) > 0


@pytest.mark.anyio
async def test_ask_trace_id_reaches_audit_log_through_guarded_call_tool(auth_token: str, tmp_path) -> None:
    """
    Closed loop: trace id flows from /ask middleware → fake agent → guarded_call_tool → audit JSONL.

    闭环验证：trace id 从 /ask 中间件经过 agent → guarded_call_tool → 审计 JSONL 完整落盘。
    """
    from opspilot.agent.tool_exec import guarded_call_tool

    audit_path = tmp_path / "audit.jsonl"

    async def agent_runs_safe_tool(question: str) -> str:
        # Fake agent invokes a registered safe tool through the guarded chokepoint,
        # which writes an audit record. The ContextVar set by the trace middleware
        # must survive across this boundary.
        result = guarded_call_tool(
            "get_pod_status",
            "default",
            calls=1,
            max_calls=5,
            audit_path=str(audit_path),
        )
        return result.observation

    app = create_app(agent=agent_runs_safe_tool)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ask",
            json={"question": "list pods"},
            headers={**_bearer(auth_token), "X-OpsPilot-Trace-ID": "trace-tool-a"},
        )
    assert resp.status_code == 200
    assert resp.headers.get("x-opspilot-trace-id") == "trace-tool-a"
    content = audit_path.read_text(encoding="utf-8")
    assert '"trace_id": "trace-tool-a"' in content


def _hmac_sig(body: bytes, secret: str) -> str:
    import hashlib
    import hmac as _hmac

    return _hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.mark.anyio
async def test_alert_with_valid_hmac_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """/alert accepts a valid HMAC signature and returns the diagnosis.

    /alert 在 HMAC 签名有效时返回 200 与诊断结果。
    """
    from opspilot.config import get_settings

    monkeypatch.setenv("OPSPILOT_ALERTMANAGER_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", "ignored-when-hmac-present")
    get_settings.cache_clear()

    async def fake_handle(event, llm):  # type: ignore[no-untyped-def]
        return "diagnosis-stub"

    monkeypatch.setattr("opspilot.entrypoints.http_api.handle_alert", fake_handle)

    app = create_app(agent=fake_agent)
    body = b'{"alerts":[{"labels":{"alertname":"X"}}]}'
    sig = _hmac_sig(body, "test-secret")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/alert",
            content=body,
            headers={"Content-Type": "application/json", "X-OpsPilot-Signature": sig},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["diagnosis"] == "diagnosis-stub"
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_alert_rejects_bad_hmac(monkeypatch: pytest.MonkeyPatch) -> None:
    """/alert returns 401 on HMAC mismatch.

    /alert 在 HMAC 签名不匹配时返回 401。
    """
    from opspilot.config import get_settings

    monkeypatch.setenv("OPSPILOT_ALERTMANAGER_HMAC_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/alert",
            content=b'{"alerts":[]}',
            headers={"Content-Type": "application/json", "X-OpsPilot-Signature": "forgedsig"},
        )
    assert resp.status_code == 401
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_alert_fail_closed_when_hmac_secret_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """/alert returns 503 when OPSPILOT_ALERTMANAGER_HMAC_SECRET is empty.

    未配置 OPSPILOT_ALERTMANAGER_HMAC_SECRET 时 /alert 返回 503。
    """
    from opspilot.config import get_settings

    monkeypatch.setenv("OPSPILOT_ALERTMANAGER_HMAC_SECRET", "")
    get_settings.cache_clear()

    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/alert",
            content=b'{"alerts":[]}',
            headers={"Content-Type": "application/json", "X-OpsPilot-Signature": "anything"},
        )
    assert resp.status_code == 503
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_alert_rejects_oversized_body_under_hmac(monkeypatch: pytest.MonkeyPatch) -> None:
    """/alert returns 413 when the streamed body exceeds the size cap.

    /alert 在请求体超过限制时返回 413（流式校验，早拒）。
    """
    from opspilot.config import get_settings

    monkeypatch.setenv("OPSPILOT_ALERTMANAGER_HMAC_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app(agent=fake_agent)
    body = b'{"alerts":"' + (b"x" * 600_000) + b'"}'
    sig = _hmac_sig(body, "test-secret")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/alert",
            content=body,
            headers={"Content-Type": "application/json", "X-OpsPilot-Signature": sig},
        )
    assert resp.status_code == 413
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_http_client_is_reused_across_requests(auth_token: str) -> None:
    """The httpx client on app.state survives between requests (no recreation per call).

    验证：app.state 上的 httpx 客户端在多次请求间复用，避免每次 /ask 都重建。
    """
    app = create_app(agent=fake_agent)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/ask", headers=_bearer(auth_token), json={"question": "hi"})
        assert r1.status_code == 200
        first = app.state.http_client
        r2 = await client.post("/ask", headers=_bearer(auth_token), json={"question": "hi2"})
        assert r2.status_code == 200
        second = app.state.http_client
    assert first is not None
    assert first is second


@pytest.mark.anyio
async def test_ask_fail_closed_when_token_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify ask fail closed when token unconfigured.

    验证：ask fail closed when token unconfigured。
    """
    from opspilot.config import get_settings

    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", "")
    get_settings.cache_clear()
    try:
        app = create_app(agent=fake_agent)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post("/ask", json={"question": "x"}, headers={"Authorization": "Bearer anything"})
        # 服务端无 token 配置 → 503，避免裸奔
        assert r.status_code == 503
    finally:
        get_settings.cache_clear()
