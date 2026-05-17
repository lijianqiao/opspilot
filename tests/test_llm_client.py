import httpx
import pytest
import respx

from opspilot.config import Settings
from opspilot.llm.client import LLMClient


@pytest.mark.anyio
@respx.mock
async def test_chat_posts_openai_payload_and_parses_reply() -> None:
    settings = Settings(
        llm_base_url="http://test/v1", llm_model="m", llm_api_key="k"
    )
    route = respx.post("http://test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "hello"}}]}
        )
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
