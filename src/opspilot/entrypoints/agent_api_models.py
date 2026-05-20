"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: agent_api_models.py
@DateTime: 2026-05-20
@Docs: Pydantic models for channel-facing agent-core HTTP API.
    渠道侧调用 agent-core HTTP API 的 Pydantic 模型。
"""

from pydantic import BaseModel, Field

from opspilot.entrypoints.body_limits import MAX_AGENT_QUESTION_CHARS


class AskRequest(BaseModel):
    """Request body for POST /ask.

    POST /ask 请求体。

    Attributes:
        question: User question text (1..MAX_AGENT_QUESTION_CHARS).
            用户问题文本。
        plan: Use Plan-Execute when True.
            为 True 时使用 Plan-Execute。
        confirmed_request_id: Resume after HITL confirm when set.
            设置时在人工确认后继续执行。
        channel: Source channel label (e.g. "feishu") for HITL context binding.
            来源渠道标签（如 "feishu"），用于 HITL 上下文绑定。
        chat_id: Channel chat id where the question originated.
            问题发起的渠道会话 ID。
        requester: Identity of the human asker (e.g. Feishu open_id).
            提问人身份标识（如飞书 open_id）。
        trace_id: Optional caller-supplied trace id for cross-service correlation.
            可选，调用方提供的 trace id，用于跨服务关联。
    """

    question: str = Field(min_length=1, max_length=MAX_AGENT_QUESTION_CHARS)
    plan: bool = False
    confirmed_request_id: str | None = Field(default=None, max_length=128)
    channel: str | None = Field(default=None, max_length=64)
    chat_id: str | None = Field(default=None, max_length=128)
    requester: str | None = Field(default=None, max_length=128)
    trace_id: str | None = Field(default=None, max_length=128)


class AskResponse(BaseModel):
    """Response body for POST /ask.

    POST /ask 响应体。
    """

    answer: str


class PendingConfirmationView(BaseModel):
    """Pending HITL confirmation exposed to channel adapters (no token).

    暴露给渠道适配器的待确认危险操作视图（不含 token）。

    Attributes:
        request_id: Opaque confirmation id.
            不透明确认 ID。
        tool: Blocked tool name.
            被拦截的工具名。
        tool_input: Raw tool input snapshot.
            工具输入快照。
        context: Channel-bound context recorded when the pending was created
            (channel/chat_id/requester). Empty when legacy/unbound.
            登记 pending 时记录的渠道绑定上下文（channel/chat_id/requester），
            未绑定/旧记录时为空。
    """

    request_id: str
    tool: str
    tool_input: str
    context: dict[str, str] = Field(default_factory=dict)


class PendingConfirmationInternalView(PendingConfirmationView):
    """Internal pending HITL confirmation including the one-time token.

    内部待确认危险操作视图，包含一次性 token。
    """

    token: str


class CardActionRequest(BaseModel):
    """Feishu interactive card action callback payload.

    飞书交互卡片按钮回调载荷。
    """

    action: dict = Field(default_factory=dict)
    operator: dict | None = None
    chat_id: str | None = Field(default=None, max_length=128)


class CardActionResponse(BaseModel):
    """Feishu card action handler response (toast message).

    飞书卡片 action 处理结果（toast 文案）。
    """

    message: str
