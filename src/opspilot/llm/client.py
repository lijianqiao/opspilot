from collections.abc import Sequence

import httpx

from opspilot.config import Settings

Message = dict[str, str]


class LLMClient:
    """调用 OpenAI 兼容 /chat/completions 的最小异步客户端。"""

    def __init__(
        self, settings: Settings, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(timeout=120.0)

    async def chat(self, messages: Sequence[Message]) -> str:
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
        return resp.json()["choices"][0]["message"]["content"]

    async def aclose(self) -> None:
        await self._client.aclose()
