# pyright: reportMissingTypeStubs=false
from collections.abc import Awaitable, Callable

import anyio
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)

from opspilot.agent.react import run_react
from opspilot.config import get_settings
from opspilot.llm.client import LLMClient

AgentFn = Callable[[str], Awaitable[str]]


async def handle_question(text: str, agent: AgentFn) -> str:
    """飞书消息处理核心：纯函数，便于单测。"""
    text = text.strip()
    if not text:
        return "请输入你的运维问题。"
    return await agent(text)


def _extract_text(event: P2ImMessageReceiveV1) -> str:
    import json

    data = event.event
    if data is None or data.message is None:
        return ""
    content = data.message.content or "{}"
    return json.loads(content).get("text", "")


def run() -> None:  # 手动验证，不进单测
    """启动飞书 WS 长连接 bot。需要 OPSPILOT_FEISHU_APP_ID/SECRET。"""
    settings = get_settings()

    async def _agent(text: str) -> str:
        llm = LLMClient(settings)
        try:
            return await run_react(text, llm)
        finally:
            await llm.aclose()

    def _on_message(event: P2ImMessageReceiveV1) -> None:
        data = event.event
        if data is None or data.message is None or data.message.chat_id is None:
            return
        question = _extract_text(event)
        answer = anyio.run(handle_question, question, _agent)
        client = lark.Client.builder().app_id(settings.feishu_app_id).app_secret(settings.feishu_app_secret).build()
        assert client.im is not None
        client.im.v1.message.create(
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(data.message.chat_id)
                .msg_type("text")
                .content(lark.JSON.marshal({"text": answer}) or "{}")
                .build()
            )
            .build()
        )

    handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(_on_message).build()
    ws = lark.ws.Client(settings.feishu_app_id, settings.feishu_app_secret, event_handler=handler)
    ws.start()


if __name__ == "__main__":
    run()
