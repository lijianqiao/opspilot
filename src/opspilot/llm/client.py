"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: client.py
@DateTime: 2026-05-20
@Docs: Async OpenAI-compatible LLM client with retry and circuit breaker.
    异步 OpenAI 兼容 LLM 客户端：重试与熔断保护。
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

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

# 重试 / 熔断参数（module 级以便测试 monkeypatch）
_RETRY_ATTEMPTS = 3
_RETRY_WAIT = wait_random_exponential(multiplier=0.5, max=8)
_CB_THRESHOLD = 3
_CB_COOLDOWN_SECONDS = 30.0


class CircuitOpenError(RuntimeError):
    """Raised while the breaker is open — fail fast without network I/O.

    熔断器打开时抛出：快速失败，不再发起网络请求。
    """


@dataclass
class CircuitBreakerState:
    """Shared circuit breaker state for one logical LLM provider.
    共享一个逻辑 LLM Provider 的熔断器状态。
    """

    consec_failures: int = 0
    open_until: float = 0.0


def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient failures (transport errors, 5xx).

    判定是否为可重试的瞬时故障（传输错误、5xx）。

    Args:
        exc: Exception to check.
            要检查的异常。

    Returns:
        True if the exception is retryable, False otherwise.
            如果异常可重试，返回 True，否则返回 False。

    4xx client errors are not retried.
    4xx 客户端错误不重试。
    """
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


class LLMClient:
    """Minimal async client for OpenAI-compatible /chat/completions.

    调用 OpenAI 兼容 /chat/completions 的最小异步客户端。

    Features retry with exponential backoff, layered timeouts, and a
    process-local circuit breaker. Module-level constants are monkeypatchable
    in tests.
    支持指数退避重试、分层超时与进程内熔断；模块级常量可在测试中 monkeypatch。
    """

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
        breaker: CircuitBreakerState | None = None,
    ) -> None:
        """Initialize LLM client.

        初始化 LLM 客户端。

        Args:
            settings: Application settings (base URL, model, API key).
                应用配置（基础 URL、模型、API 密钥）。
            http_client: Optional shared httpx.AsyncClient.
                可选的共享 httpx.AsyncClient。
            breaker: Optional shared circuit breaker state.
                可选的共享熔断器状态。
        """
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._breaker = breaker or CircuitBreakerState()

    async def chat(self, messages: Sequence[Message]) -> str:
        """Send chat completion request and return assistant content.

        发送对话补全请求并返回助手回复内容。

        Args:
            messages: OpenAI-style message list (role + content).
                OpenAI 风格消息列表（role + content）。

        Returns:
            Assistant message content string.
                助手回复文本。

        Raises:
            CircuitOpenError: When circuit breaker is open.
                熔断器打开时。
            httpx.HTTPStatusError: On non-retryable HTTP errors after retries.
                重试后仍失败的 HTTP 错误。
        """
        # 熔断器：打开期内快速失败
        now = time.monotonic()
        if now < self._breaker.open_until:
            raise CircuitOpenError(f"LLM circuit open for {self._breaker.open_until - now:.1f}s")

        started = time.perf_counter()
        status = "success"
        content = ""
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(_RETRY_ATTEMPTS),
                wait=_RETRY_WAIT,
                retry=retry_if_exception(_is_retryable),
                reraise=True,
            ):
                with attempt:
                    resp = await self._client.post(
                        f"{self._settings.llm_base_url}/chat/completions",
                        # OpenAI 兼容 API：Authorization: Bearer <api_key>
                        headers={"Authorization": f"Bearer {self._settings.llm_api_key}"},
                        json={
                            "model": self._settings.llm_model,
                            "messages": list(messages),
                            "temperature": 0.0,
                        },
                    )
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"]
            # 成功 → 重置（含半开探测成功）
            self._breaker.consec_failures = 0
            self._breaker.open_until = 0.0
            return content
        except Exception:
            status = "error"
            self._breaker.consec_failures += 1
            if self._breaker.consec_failures >= _CB_THRESHOLD:
                self._breaker.open_until = time.monotonic() + _CB_COOLDOWN_SECONDS
            raise
        finally:
            elapsed = time.perf_counter() - started
            text = "".join(msg.get("content", "") for msg in messages if isinstance(msg, dict))
            # // 4 ≈ 英文每 token 约 4 字符的粗略估算，仅用于指标，非计费
            token_estimate = max((len(text) + len(content)) // 4, 1)
            record_llm_call(
                provider=self._settings.llm_base_url,
                status=status,
                duration_seconds=elapsed,
                token_estimate=token_estimate,
            )

    async def aclose(self) -> None:
        """Close the underlying HTTP client.

        关闭底层 HTTP 客户端。
        """
        await self._client.aclose()
