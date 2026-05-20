"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_agent_client.py
@DateTime: 2026-05-20
@Docs: Tests AgentClient HTTP calls to agent-core.
    测试 AgentClient 对 agent-core 的 HTTP 调用。
"""

import httpx
import pytest
import respx

from opspilot.config import Settings
from opspilot.entrypoints.agent_client import AgentClient


@pytest.mark.anyio
@respx.mock
async def test_ask_posts_with_bearer() -> None:
    """
    AgentClient POST /ask sends Authorization Bearer header.

    AgentClient 调用 POST /ask 时应携带 Bearer 鉴权头。
    """
    route = respx.post("http://agent-core:8000/ask").mock(return_value=httpx.Response(200, json={"answer": "ok"}))
    settings = Settings(
        agent_core_url="http://agent-core:8000",
        api_auth_token="tok",
    )
    client = AgentClient(settings)
    answer = await client.ask("hello", plan=False)
    assert answer == "ok"
    assert route.calls[0].request.headers["authorization"] == "Bearer tok"
    await client.aclose()


@pytest.mark.anyio
@respx.mock
async def test_ask_propagates_channel_context() -> None:
    """
    AgentClient.ask sends channel/chat_id/requester/trace_id in payload.

    AgentClient.ask 应在请求体中透传 channel/chat_id/requester/trace_id。
    """
    import json as _json

    route = respx.post("http://agent-core:8000/ask").mock(return_value=httpx.Response(200, json={"answer": "ok"}))
    settings = Settings(agent_core_url="http://agent-core:8000", api_auth_token="tok")
    client = AgentClient(settings)
    answer = await client.ask(
        "restart payment",
        plan=True,
        channel="feishu",
        chat_id="chat-a",
        requester="ou_1",
        trace_id="trace-xyz",
    )
    assert answer == "ok"
    body = _json.loads(route.calls[0].request.content.decode("utf-8"))
    assert body["question"] == "restart payment"
    assert body["plan"] is True
    assert body["channel"] == "feishu"
    assert body["chat_id"] == "chat-a"
    assert body["requester"] == "ou_1"
    assert body["trace_id"] == "trace-xyz"
    await client.aclose()


@pytest.mark.anyio
@respx.mock
async def test_ask_omits_unset_context_fields() -> None:
    """
    AgentClient.ask should not include channel/chat_id/etc when not set.

    AgentClient.ask 未提供渠道字段时不应写入请求体，保持向后兼容。
    """
    import json as _json

    route = respx.post("http://agent-core:8000/ask").mock(return_value=httpx.Response(200, json={"answer": "ok"}))
    settings = Settings(agent_core_url="http://agent-core:8000", api_auth_token="tok")
    client = AgentClient(settings)
    await client.ask("ping")
    body = _json.loads(route.calls[0].request.content.decode("utf-8"))
    assert set(body.keys()) == {"question", "plan"}
    await client.aclose()


@pytest.mark.anyio
@respx.mock
async def test_ask_get_pending_card_action_share_trace_id_header() -> None:
    """
    ask/get_pending/feishu_card_action all forward x-opspilot-trace-id when given trace_id.

    AgentClient 的 ask/get_pending/feishu_card_action 在传入 trace_id 时
    都应通过 x-opspilot-trace-id 请求头透传同一个 trace id。
    """
    ask_route = respx.post("http://agent-core:8000/ask").mock(return_value=httpx.Response(200, json={"answer": "ok"}))
    pending_route = respx.get("http://agent-core:8000/internal/channels/pending/rid1").mock(
        return_value=httpx.Response(
            200,
            json={"request_id": "rid1", "tool": "t", "tool_input": "x", "token": "tk"},
        )
    )
    card_route = respx.post("http://agent-core:8000/channels/feishu/card-action").mock(
        return_value=httpx.Response(200, json={"message": "done"})
    )
    settings = Settings(
        agent_core_url="http://agent-core:8000",
        api_auth_token="tok",
        channel_internal_token="chan",
    )
    client = AgentClient(settings)
    trace_id = "trace-feishu-a"
    await client.ask("hello", trace_id=trace_id)
    await client.get_pending("rid1", trace_id=trace_id)
    await client.feishu_card_action({"action": {}, "operator": {}}, trace_id=trace_id)
    assert ask_route.calls[0].request.headers["x-opspilot-trace-id"] == trace_id
    assert pending_route.calls[0].request.headers["x-opspilot-trace-id"] == trace_id
    assert card_route.calls[0].request.headers["x-opspilot-trace-id"] == trace_id
    await client.aclose()


@pytest.mark.anyio
@respx.mock
async def test_ask_omits_trace_header_when_not_provided() -> None:
    """
    Without trace_id, AgentClient.ask must not send x-opspilot-trace-id.

    未提供 trace_id 时，AgentClient.ask 不应携带 x-opspilot-trace-id 头。
    """
    route = respx.post("http://agent-core:8000/ask").mock(return_value=httpx.Response(200, json={"answer": "ok"}))
    settings = Settings(agent_core_url="http://agent-core:8000", api_auth_token="tok")
    client = AgentClient(settings)
    await client.ask("hello")
    assert "x-opspilot-trace-id" not in route.calls[0].request.headers
    await client.aclose()


@pytest.mark.anyio
@respx.mock
async def test_get_pending() -> None:
    """
    AgentClient fetches internal pending confirmation including token.

    AgentClient 应能通过内部接口获取含 token 的待确认记录。
    """
    respx.get("http://agent-core:8000/internal/channels/pending/rid1").mock(
        return_value=httpx.Response(
            200,
            json={
                "request_id": "rid1",
                "tool": "kubectl_scale",
                "tool_input": "x",
                "token": "sec",
            },
        )
    )
    settings = Settings(agent_core_url="http://agent-core:8000", api_auth_token="tok", channel_internal_token="chan")
    client = AgentClient(settings)
    pc = await client.get_pending("rid1")
    assert pc is not None
    assert pc.token == "sec"
    assert respx.calls.last.request.headers["authorization"] == "Bearer chan"
    await client.aclose()
