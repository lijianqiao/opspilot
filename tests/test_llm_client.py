import httpx
import pytest
import respx

from opspilot.config import Settings
from opspilot.llm.client import LLMClient


@pytest.mark.anyio
@respx.mock
async def test_chat_posts_openai_payload_and_parses_reply() -> None:
    settings = Settings(llm_base_url="http://test/v1", llm_model="m", llm_api_key="k")
    route = respx.post("http://test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})
    )
    client = LLMClient(settings)
    try:
        reply = await client.chat([{"role": "user", "content": "hi"}])
    finally:
        await client.aclose()

    assert reply == "hello"
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer k"
    body = httpx.Response(200, content=sent.content).json()
    assert body["model"] == "m"
    assert body["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.anyio
@respx.mock
async def test_chat_retries_transient_5xx_then_succeeds() -> None:
    settings = Settings(llm_base_url="http://test/v1", llm_model="m", llm_api_key="k")
    route = respx.post("http://test/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    client = LLMClient(settings)
    try:
        reply = await client.chat([{"role": "user", "content": "hi"}])
    finally:
        await client.aclose()
    assert reply == "ok"
    assert route.call_count == 3


@pytest.mark.anyio
@respx.mock
async def test_chat_does_not_retry_on_4xx() -> None:
    # python-anti-patterns: 4xx 是客户端错误，不应重试（auth/permission/bad request）
    settings = Settings(llm_base_url="http://test/v1", llm_model="m", llm_api_key="k")
    route = respx.post("http://test/v1/chat/completions").mock(return_value=httpx.Response(401))
    client = LLMClient(settings)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await client.chat([{"role": "user", "content": "x"}])
    finally:
        await client.aclose()
    assert route.call_count == 1


@pytest.mark.anyio
@respx.mock
async def test_chat_retries_transport_error_then_succeeds() -> None:
    settings = Settings(llm_base_url="http://test/v1", llm_model="m", llm_api_key="k")
    route = respx.post("http://test/v1/chat/completions").mock(
        side_effect=[
            httpx.ConnectError("boom"),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    client = LLMClient(settings)
    try:
        reply = await client.chat([{"role": "user", "content": "hi"}])
    finally:
        await client.aclose()
    assert reply == "ok"
    assert route.call_count == 2
