"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: agent_api_models.py
@DateTime: 2026-05-20
@Docs: Pydantic models for channel-facing agent-core HTTP API.
    渠道侧调用 agent-core HTTP API 的 Pydantic 模型。
"""

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Request body for POST /ask.

    POST /ask 请求体。
    """

    question: str
    plan: bool = False


class AskResponse(BaseModel):
    """Response body for POST /ask.

    POST /ask 响应体。
    """

    answer: str


class PendingConfirmationView(BaseModel):
    """Pending HITL confirmation exposed to channel adapters.

    暴露给渠道适配器的待确认危险操作视图。
    """

    request_id: str
    tool: str
    tool_input: str
    token: str


class CardActionRequest(BaseModel):
    """Feishu interactive card action callback payload.

    飞书交互卡片按钮回调载荷。
    """

    action: dict = Field(default_factory=dict)
    operator: dict | None = None


class CardActionResponse(BaseModel):
    """Feishu card action handler response (toast message).

    飞书卡片 action 处理结果（toast 文案）。
    """

    message: str
