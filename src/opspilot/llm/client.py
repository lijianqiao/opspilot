"""Async LLM client (OpenAI-compatible /chat/completions).

容错（审查报告 🔴 llm/client.py 无重试/无熔断/单一 120s 超时）：
- 重试：tenacity 指数退避+抖动，仅瞬时故障（5xx / httpx.TransportError）；
  4xx 直接抛出（auth/permission/bad request 不应重试）。attempts=3。
- 超时：分层 httpx.Timeout(connect=5/read=60/write=10/pool=5)，取代裸 120s。
- 熔断：连续 N 次逻辑失败 → 打开冷却期，期间立即抛 CircuitOpenError，
  避免上游持续不可用时仍每次打满重试放大故障/成本。冷却到期后半开
  探测一次，成功则关闭、失败则再次打开。
- python-anti-patterns: Double Retry —— 网关层也有 fallback；这里只做 3 次，
  不在 agent 层再叠加。

测试钩子：_RETRY_WAIT / _RETRY_ATTEMPTS / _CB_THRESHOLD / _CB_COOLDOWN_SECONDS
都是 module 级常量，可被 monkeypatch 加速测试。
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

# 重试 / 熔断参数（module 级以便测试 monkeypatch）
_RETRY_ATTEMPTS = 3
_RETRY_WAIT = wait_random_exponential(multiplier=0.5, max=8)
_CB_THRESHOLD = 3
_CB_COOLDOWN_SECONDS = 30.0


class CircuitOpenError(RuntimeError):
    """Raised while the breaker is open: 快速失败，不再打网络。"""


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
        # 熔断器状态（进程内、单实例）
        self._consec_failures = 0
        self._open_until = 0.0

    async def chat(self, messages: Sequence[Message]) -> str:
        # 熔断器：打开期内快速失败
        now = time.monotonic()
        if now < self._open_until:
            raise CircuitOpenError(f"LLM circuit open for {self._open_until - now:.1f}s")

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
            self._consec_failures = 0
            self._open_until = 0.0
            return content
        except Exception:
            status = "error"
            self._consec_failures += 1
            if self._consec_failures >= _CB_THRESHOLD:
                self._open_until = time.monotonic() + _CB_COOLDOWN_SECONDS
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
        await self._client.aclose()
