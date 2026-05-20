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
