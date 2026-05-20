"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: agent_client.py
@DateTime: 2026-05-20
@Docs: HTTP client for channel adapters to call agent-core.
    渠道适配器经 HTTP 调用 agent-core 的客户端。
"""

from dataclasses import dataclass, field

import httpx

from opspilot.config import Settings, get_settings
from opspilot.entrypoints.agent_api_models import PendingConfirmationInternalView


@dataclass(frozen=True)
class PendingConfirmation:
    """Pending HITL confirmation returned from agent-core.

    agent-core 返回的待确认危险操作记录。
    """

    request_id: str
    tool: str
    tool_input: str
    token: str
    context: dict[str, str] = field(default_factory=dict)


class AgentClient:
    """Async HTTP client for channel adapters (Feishu, future Slack, etc.).

    渠道适配器（飞书及未来 Slack 等）使用的异步 HTTP 客户端。
    """

    def __init__(self, settings: Settings | None = None, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize the HTTP client for agent-core.

        初始化连接 agent-core 的 HTTP 客户端。

        Args:
            settings: Optional settings; defaults to cached get_settings().
                可选配置；默认使用 get_settings() 缓存。
            http_client: Optional shared AsyncClient (for tests).
                可选共享 AsyncClient（测试注入用）。
        """
        self._settings = settings or get_settings()
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=self._settings.agent_core_url.rstrip("/"),
            timeout=httpx.Timeout(120.0),
        )

    def _auth_header(self) -> dict[str, str]:
        """Build Authorization header for public agent-core API.

        构建面向外部/渠道的 agent-core API 鉴权头。

        Returns:
            Header dict with Bearer OPSPILOT_API_AUTH_TOKEN.
                含 Bearer OPSPILOT_API_AUTH_TOKEN 的请求头字典。

        Raises:
            RuntimeError: When OPSPILOT_API_AUTH_TOKEN is empty.
                未配置 OPSPILOT_API_AUTH_TOKEN 时抛出。
        """
        token = self._settings.api_auth_token
        if not token:
            raise RuntimeError("OPSPILOT_API_AUTH_TOKEN 未配置，无法调用 agent-core")
        return {"Authorization": f"Bearer {token}"}

    def _channel_internal_auth_header(self) -> dict[str, str]:
        """Build Authorization header for internal channel-only endpoints.

        构建渠道内部接口（如 pending 含 token）的鉴权头。

        Returns:
            Header dict with Bearer OPSPILOT_CHANNEL_INTERNAL_TOKEN.
                含 Bearer OPSPILOT_CHANNEL_INTERNAL_TOKEN 的请求头字典。

        Raises:
            RuntimeError: When OPSPILOT_CHANNEL_INTERNAL_TOKEN is empty.
                未配置 OPSPILOT_CHANNEL_INTERNAL_TOKEN 时抛出。
        """
        token = self._settings.channel_internal_token
        if not token:
            raise RuntimeError("OPSPILOT_CHANNEL_INTERNAL_TOKEN 未配置，无法查询待确认操作")
        return {"Authorization": f"Bearer {token}"}

    async def ask(
        self,
        question: str,
        *,
        plan: bool = False,
        channel: str | None = None,
        chat_id: str | None = None,
        requester: str | None = None,
        trace_id: str | None = None,
    ) -> str:
        """POST /ask and return the answer text.

        调用 POST /ask 并返回回答文本。

        Args:
            question: User question.
                用户问题。
            plan: Use Plan-Execute when True.
                为 True 时使用 Plan-Execute。
            channel: Source channel label (e.g. "feishu") for HITL binding.
                来源渠道标签（如 "feishu"），用于 HITL 绑定。
            chat_id: Originating chat id for HITL binding.
                发起会话 ID，用于 HITL 绑定。
            requester: Identity of the asker (e.g. Feishu open_id).
                提问人身份标识（如飞书 open_id）。
            trace_id: Optional caller-supplied trace id.
                可选调用方提供的 trace id。

        Returns:
            Agent answer string.
                Agent 回答。
        """
        payload: dict[str, object] = {"question": question, "plan": plan}
        if channel:
            payload["channel"] = channel
        if chat_id:
            payload["chat_id"] = chat_id
        if requester:
            payload["requester"] = requester
        if trace_id:
            payload["trace_id"] = trace_id
        headers = self._auth_header()
        if trace_id:
            headers["x-opspilot-trace-id"] = trace_id
        r = await self._client.post(
            "/ask",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()
        return r.json()["answer"]

    async def get_pending(self, request_id: str, *, trace_id: str | None = None) -> PendingConfirmation | None:
        """GET /internal/channels/pending/{request_id}; None if 404.

        查询待确认记录；404 时返回 None。

        Args:
            request_id: Pending confirmation id from agent output.
                Agent 输出中的 request_id。
            trace_id: Optional trace id to propagate via X-OpsPilot-Trace-ID.
                可选 trace id，将通过 X-OpsPilot-Trace-ID 头透传。

        Returns:
            PendingConfirmation or None if missing/expired.
                待确认记录，或不存在/已过期时为 None。
        """
        headers = self._channel_internal_auth_header()
        if trace_id:
            headers["x-opspilot-trace-id"] = trace_id
        r = await self._client.get(
            f"/internal/channels/pending/{request_id}",
            headers=headers,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        view = PendingConfirmationInternalView.model_validate(r.json())
        return PendingConfirmation(
            request_id=view.request_id,
            tool=view.tool,
            tool_input=view.tool_input,
            token=view.token,
            context=dict(view.context),
        )

    async def feishu_card_action(self, payload: dict, *, trace_id: str | None = None) -> str:
        """POST /channels/feishu/card-action and return toast message.

        调用飞书卡片回调接口并返回 toast 文案。

        Args:
            payload: Feishu card action dict (action + operator).
                飞书卡片 action 字典。
            trace_id: Optional trace id to propagate via X-OpsPilot-Trace-ID.
                可选 trace id，将通过 X-OpsPilot-Trace-ID 头透传。

        Returns:
            Short message for the operator.
                给操作者的简短反馈。
        """
        headers = self._auth_header()
        if trace_id:
            headers["x-opspilot-trace-id"] = trace_id
        r = await self._client.post(
            "/channels/feishu/card-action",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()
        return r.json()["message"]

    async def aclose(self) -> None:
        """Close the underlying HTTP client if owned by this instance.

        关闭本实例拥有的底层 HTTP 客户端。
        """
        if self._owns_client:
            await self._client.aclose()
