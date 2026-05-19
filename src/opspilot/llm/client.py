import time
from collections.abc import Sequence

import httpx

from opspilot.config import Settings
from opspilot.observability.metrics import record_llm_call

Message = dict[str, str]


class LLMClient:
    """调用 OpenAI 兼容 /chat/completions 的最小异步客户端。"""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(timeout=120.0)

    async def chat(self, messages: Sequence[Message]) -> str:
        started = time.perf_counter()
        status = "success"
        content = ""
        try:
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
