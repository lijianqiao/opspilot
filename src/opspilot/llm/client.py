"""Async LLM client (OpenAI-compatible /chat/completions).

容错（审查报告 🔴 llm/client.py 无重试/无熔断/单一 120s 超时）：
- 重试：tenacity 指数退避+抖动，仅瞬时故障（5xx / httpx.TransportError）；
  4xx 直接抛出（auth/permission/bad request 不应重试）。attempts=3。
- 超时：分层 httpx.Timeout(connect=5/read=60/write=10/pool=5)，取代裸 120s。
- python-anti-patterns: Double Retry —— 网关层也有 fallback；这里只做 3 次，
  不在 agent 层再叠加，避免重试放大。
"""

from __future__ import annotations

import time
from collections.abc import Sequence

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from opspilot.config import Settings
from opspilot.observability.metrics import record_llm_call

Message = dict[str, str]

_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)


def _is_retryable(exc: BaseException) -> bool:
    """瞬时故障判定：连接/超时 + 上游 5xx。4xx 是客户端错误，不重试。"""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


class LLMClient:
    """调用 OpenAI 兼容 /chat/completions 的最小异步客户端。"""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)

    async def chat(self, messages: Sequence[Message]) -> str:
        started = time.perf_counter()
        status = "success"
        content = ""
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_random_exponential(multiplier=0.5, max=8),
                retry=retry_if_exception(_is_retryable),
                reraise=True,
            ):
                with attempt:
                    resp = await self._client.post(
                        f"{self._settings.llm_base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self._settings.llm_api_key}"},
                        json={
                            "model": self._settings.llm_model,
                            "messages": list(messages),
                            "temperature": 0.0,
                        },
                    )
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"]
            return content
        except Exception:
            status = "error"
            raise
        finally:
            elapsed = time.perf_counter() - started
            text = "".join(msg.get("content", "") for msg in messages if isinstance(msg, dict))
            token_estimate = max((len(text) + len(content)) // 4, 1)
            record_llm_call(
                provider=self._settings.llm_base_url,
                status=status,
                duration_seconds=elapsed,
                token_estimate=token_estimate,
            )

    async def aclose(self) -> None:
        await self._client.aclose()
