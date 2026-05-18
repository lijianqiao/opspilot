# pyright: reportMissingTypeStubs=false
import threading
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


def _run_blocking(text: str, agent: AgentFn) -> str:
    """在独立线程里用全新事件循环执行 handle_question。

    lark-oapi 的 WS 客户端在“已运行事件循环”的线程里同步回调，
    此处直接 anyio.run() 会触发 RuntimeError: Already running asyncio
    in this thread。放进一个没有运行中循环的新线程即可安全执行并取回结果。
    """
    box: dict[str, str] = {}
    error: dict[str, Exception] = {}

    def _worker() -> None:
        try:
            box["answer"] = anyio.run(handle_question, text, agent)
        except Exception as exc:
            error["exc"] = exc

    thread = threading.Thread(target=_worker, name="opspilot-feishu-agent")
    thread.start()
    thread.join()
    if "exc" in error:
        raise error["exc"]
    return box["answer"]


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
        answer = _run_blocking(question, _agent)
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
