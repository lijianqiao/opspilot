"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: feishu_ws.py
@DateTime: 2026-05-20
@Docs: Feishu WS bot — thin adapter calling agent-core via AgentClient.
    飞书 WS 薄适配器：经 AgentClient 调用 agent-core，不进程内跑 Agent。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import anyio
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger,
    P2CardActionTriggerResponse,
)

from opspilot.agent.guardrails import redact
from opspilot.config import get_settings
from opspilot.entrypoints.agent_client import AgentClient
from opspilot.entrypoints.feishu_card import build_confirm_card

logger = logging.getLogger(__name__)

AgentFn = Callable[[str], Awaitable[str]]

_FEISHU_MENTION_RE = re.compile(r"^@\S+\s*")
_REQUEST_ID_RE = re.compile(r"request_id=([A-Za-z0-9_\-]+)")

_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="opspilot-feishu")


def _select_agent(text: str) -> tuple[str, bool]:
    """Return (stripped_text, use_plan_execute).

    返回 (去前缀后的文本, 是否使用 Plan-Execute)。
    """
    cleaned = _FEISHU_MENTION_RE.sub("", text)
    for prefix in ("规划：", "规划:", "/plan "):
        if cleaned.startswith(prefix):
            return cleaned[len(prefix) :], True
    return cleaned, False


async def handle_question(text: str, agent: AgentFn) -> str:
    """Handle a Feishu message: strip, validate, delegate to agent.

    处理飞书消息：去空白、校验后委托 agent 回答。
    """
    text = text.strip()
    if not text:
        return "Please enter your ops question."
    try:
        return await agent(text)
    except Exception:
        logger.exception("agent failed for feishu message")
        return redact("处理出错，请稍后重试或联系运维。")


def _run_blocking(coro_factory: Callable[[], Awaitable[object]]) -> object:
    """Run an async coroutine factory in a fresh thread event loop.

    在无运行中事件循环的新线程中执行异步协程工厂。
    """
    box: dict[str, object] = {}
    error: dict[str, Exception] = {}

    def _worker() -> None:
        try:
            box["result"] = anyio.run(coro_factory)
        except Exception as exc:
            error["exc"] = exc

    thread = threading.Thread(target=_worker, name="opspilot-feishu-async")
    thread.start()
    thread.join()
    if "exc" in error:
        raise error["exc"]
    return box["result"]


def _run_blocking_question(text: str, agent: AgentFn) -> str:
    """Run handle_question in a fresh event loop on a new thread."""
    return str(_run_blocking(lambda: handle_question(text, agent)))


async def _handle_via_agent_core(
    lark_client: lark.Client,
    chat_id: str,
    question: str,
    agent_client: AgentClient,
) -> None:
    """Handle one Feishu message via agent-core HTTP API.

    经 agent-core HTTP 处理一条飞书消息：回复文本并在需要时发确认卡片。
    """
    stripped, use_plan = _select_agent(question)

    async def _ask(text: str) -> str:
        return await agent_client.ask(text, plan=use_plan)

    answer = await handle_question(stripped, _ask)
    _send_reply(lark_client, chat_id, answer)
    await _maybe_send_confirm_card(lark_client, chat_id, answer, agent_client)


async def _maybe_send_confirm_card(
    lark_client: lark.Client,
    chat_id: str,
    answer: str,
    agent_client: AgentClient,
) -> None:
    """If answer mentions request_id=..., fetch pending from agent-core and send card."""
    m = _REQUEST_ID_RE.search(answer)
    if m is None:
        return
    request_id = m.group(1)
    pc = await agent_client.get_pending(request_id)
    if pc is None:
        logger.info("request_id=%s not found in agent-core (consumed/expired)", request_id)
        return
    card = build_confirm_card(pc.request_id, pc.token, pc.tool, pc.tool_input)
    try:
        _send_card(lark_client, chat_id, card)
        logger.info("sent confirm card for request_id=%s tool=%s", request_id, pc.tool)
    except Exception:
        logger.exception("failed to send confirm card for request_id=%s", request_id)


def _extract_text(event: P2ImMessageReceiveV1) -> str:
    data = event.event
    if data is None or data.message is None:
        return ""
    content = data.message.content or "{}"
    return json.loads(content).get("text", "")


@lru_cache(maxsize=4)
def _get_lark_client(app_id: str, app_secret: str) -> lark.Client:
    """Cached lark.Client (审查报告：避免每次回复都 builder())。"""
    return lark.Client.builder().app_id(app_id).app_secret(app_secret).build()


def _send_reply(client: lark.Client, chat_id: str, answer: str) -> None:
    """Send a text reply to a Feishu chat."""
    assert client.im is not None
    client.im.v1.message.create(
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(lark.JSON.marshal({"text": answer}) or "{}")
            .build()
        )
        .build()
    )


def _send_card(client: lark.Client, chat_id: str, card_json: str) -> None:
    """Send a Feishu interactive card (危险操作确认卡片)。"""
    assert client.im is not None
    client.im.v1.message.create(
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder().receive_id(chat_id).msg_type("interactive").content(card_json).build()
        )
        .build()
    )


def run() -> None:  # manual verification only, not unit tested
    """Start Feishu WS long-connection bot (thin adapter to agent-core).

    启动飞书 WS 长连接机器人（薄适配器，Agent 运行在 agent-core）。
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = get_settings()
    lark_client = _get_lark_client(settings.feishu_app_id, settings.feishu_app_secret)
    agent_client = AgentClient(settings)

    def _handle_in_background(chat_id: str, question: str) -> None:
        try:
            _run_blocking(lambda: _handle_via_agent_core(lark_client, chat_id, question, agent_client))
        except Exception:
            logger.exception("Failed to handle message for chat %s", chat_id)

    def _on_card_action(trigger: P2CardActionTrigger) -> P2CardActionTriggerResponse:
        data = trigger.event
        if data is None:
            return P2CardActionTriggerResponse({"toast": {"type": "error", "content": "无效回调"}})
        op = data.operator
        payload = {
            "action": {"value": (data.action.value if data.action else {}) or {}},
            "operator": {"open_id": (op.open_id if op else None) or (op.user_id if op else None) or "unknown"},
        }
        try:
            msg = str(_run_blocking(lambda: agent_client.feishu_card_action(payload)))
        except Exception:
            logger.exception("feishu card-action via agent-core failed")
            return P2CardActionTriggerResponse({"toast": {"type": "error", "content": "处理失败，请稍后重试"}})
        return P2CardActionTriggerResponse({"toast": {"type": "success", "content": msg}})

    def _on_message(event: P2ImMessageReceiveV1) -> None:
        data = event.event
        if data is None or data.message is None or data.message.chat_id is None:
            return
        question = _extract_text(event)
        if not question:
            return
        _EXECUTOR.submit(_handle_in_background, data.message.chat_id, question)

    handler = (
        lark.EventDispatcherHandler.builder(
            settings.feishu_verification_token,
            settings.feishu_encrypt_key,
        )
        .register_p2_im_message_receive_v1(_on_message)
        .register_p2_card_action_trigger(_on_card_action)
        .build()
    )
    ws = lark.ws.Client(settings.feishu_app_id, settings.feishu_app_secret, event_handler=handler)
    ws.start()


if __name__ == "__main__":
    run()
