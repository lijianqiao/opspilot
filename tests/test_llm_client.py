"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_llm_client.py
@DateTime: 2026-05-20
@Docs: Tests LLMClient retry, timeouts, and circuit breaker.
    测试 LLMClient 重试、超时与熔断。
"""

import httpx
import pytest
import respx
from tenacity import wait_none

from opspilot.config import Settings
from opspilot.llm.client import CircuitOpenError, LLMClient


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


@pytest.mark.anyio
@respx.mock
async def test_circuit_opens_after_consecutive_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    # 加速：测试用 wait_none() 跳过 tenacity 的 backoff
    monkeypatch.setattr("opspilot.llm.client._RETRY_WAIT", wait_none())
    route = respx.post("http://test/v1/chat/completions").mock(return_value=httpx.Response(500))
    settings = Settings(llm_base_url="http://test/v1", llm_model="m", llm_api_key="k")
    client = LLMClient(settings)

    # 3 次连续失败 → 熔断打开
    for _ in range(3):
        with pytest.raises(Exception):  # noqa: B017
            await client.chat([{"role": "user", "content": "x"}])

    calls_before_open = route.call_count
    # 熔断打开期间立即抛 CircuitOpenError，且不再打网络
    with pytest.raises(CircuitOpenError):
        await client.chat([{"role": "user", "content": "x"}])
    assert route.call_count == calls_before_open  # 无新增 HTTP 调用

    await client.aclose()


@pytest.mark.anyio
@respx.mock
async def test_circuit_half_open_probes_after_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    # 加速 + 短 cooldown
    monkeypatch.setattr("opspilot.llm.client._RETRY_WAIT", wait_none())
    monkeypatch.setattr("opspilot.llm.client._CB_COOLDOWN_SECONDS", 0.05)
    settings = Settings(llm_base_url="http://test/v1", llm_model="m", llm_api_key="k")
    client = LLMClient(settings)

    # 先用 500 触发熔断
    fail_route = respx.post("http://test/v1/chat/completions").mock(return_value=httpx.Response(500))
    for _ in range(3):
        with pytest.raises(Exception):  # noqa: B017
            await client.chat([{"role": "user", "content": "x"}])
    # 此时熔断打开
    with pytest.raises(CircuitOpenError):
        await client.chat([{"role": "user", "content": "x"}])

    # 等 cooldown 过去，切换上游响应 200
    import asyncio

    await asyncio.sleep(0.1)
    fail_route.mock(return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}))

    # 半开探测：放行一次；成功 → 熔断关闭
    reply = await client.chat([{"role": "user", "content": "x"}])
    assert reply == "ok"

    # 后续调用不再触发熔断
    reply2 = await client.chat([{"role": "user", "content": "x"}])
    assert reply2 == "ok"

    await client.aclose()
