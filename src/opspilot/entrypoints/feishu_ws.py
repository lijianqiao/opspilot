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

    Args:
        text: Raw Feishu message text (may include @mention or plan prefix).
            原始飞书消息（可能含 @ 提及或规划前缀）。

    Returns:
        Tuple of stripped question and whether to use Plan-Execute.
            (去前缀后的问题, 是否走 Plan-Execute)。
    """
    cleaned = _FEISHU_MENTION_RE.sub("", text)
    for prefix in ("规划：", "规划:", "/plan "):
        if cleaned.startswith(prefix):
            return cleaned[len(prefix) :], True
    return cleaned, False


async def handle_question(text: str, agent: AgentFn) -> str:
    """Handle a Feishu message: strip, validate, delegate to agent.

    处理飞书消息：去空白、校验后委托 agent 回答。

    Args:
        text: Incoming message text.
            入站消息文本。
        agent: Async callable(question) -> answer.
            异步 agent(question) -> answer。

    Returns:
        Agent answer or user-safe error message.
            Agent 回答或对用户安全的错误提示。
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

    Args:
        coro_factory: Zero-arg callable returning an awaitable.
            无参可调用对象，返回 awaitable。

    Returns:
        Coroutine result.
            协程执行结果。

    Raises:
        Exception: Re-raises any exception from the worker thread.
            工作线程中的异常会原样抛出。
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
    """Run handle_question in a fresh event loop on a new thread.

    在新线程的独立事件循环中运行 handle_question。

    Args:
        text: Incoming message text.
            入站消息文本。
        agent: Async agent callable.
            异步 agent 可调用对象。

    Returns:
        Answer string from handle_question.
            handle_question 返回的回答字符串。
    """
    return str(_run_blocking(lambda: handle_question(text, agent)))


async def _handle_via_agent_core(
    lark_client: lark.Client,
    chat_id: str,
    question: str,
    agent_client: AgentClient,
    requester: str | None = None,
) -> None:
    """Handle one Feishu message via agent-core HTTP API.

    经 agent-core HTTP 处理一条飞书消息：回复文本并在需要时发确认卡片。

    Args:
        lark_client: Lark SDK client for sending messages.
            用于发消息的 Lark 客户端。
        chat_id: Feishu chat id to reply in.
            要回复的飞书会话 ID。
        question: Raw user message text.
            用户原始消息文本。
        agent_client: HTTP client to agent-core.
            调用 agent-core 的 HTTP 客户端。
        requester: Optional Feishu open_id of the sender for HITL binding.
            可选，发送者的飞书 open_id，用于 HITL 绑定。
    """
    stripped, use_plan = _select_agent(question)

    async def _ask(text: str) -> str:
        return await agent_client.ask(
            text,
            plan=use_plan,
            channel="feishu",
            chat_id=chat_id,
            requester=requester,
        )

    answer = await handle_question(stripped, _ask)
    _send_reply(lark_client, chat_id, answer)
    await _maybe_send_confirm_card(lark_client, chat_id, answer, agent_client)


async def _maybe_send_confirm_card(
    lark_client: lark.Client,
    chat_id: str,
    answer: str,
    agent_client: AgentClient,
) -> None:
    """If answer mentions request_id=..., fetch pending from agent-core and send card.

    若回答含 request_id=...，从 agent-core 拉取 pending 并发送确认卡片。

    Args:
        lark_client: Lark SDK client.
            Lark 客户端。
        chat_id: Target chat id.
            目标会话 ID。
        answer: Agent reply text possibly containing request_id.
            可能含 request_id 的 Agent 回复。
        agent_client: HTTP client for internal pending lookup.
            用于内部 pending 查询的 HTTP 客户端。
    """
    m = _REQUEST_ID_RE.search(answer)
    if m is None:
        return
    request_id = m.group(1)
    pc = await agent_client.get_pending(request_id)
    if pc is None:
        logger.info("request_id=%s not found in agent-core (consumed/expired)", request_id)
        return
    card = build_confirm_card(pc.request_id, pc.token, pc.tool, pc.tool_input, context=pc.context)
    try:
        _send_card(lark_client, chat_id, card)
        logger.info("sent confirm card for request_id=%s tool=%s", request_id, pc.tool)
    except Exception:
        logger.exception("failed to send confirm card for request_id=%s", request_id)


def _extract_text(event: P2ImMessageReceiveV1) -> str:
    """Extract plain text from a Feishu IM message receive event.

    从飞书 IM 收消息事件中解析纯文本。

    Args:
        event: Lark P2ImMessageReceiveV1 event.
            Lark 收消息事件对象。

    Returns:
        Message text or empty string if unavailable.
            消息文本；无法解析时返回空字符串。
    """
    data = event.event
    if data is None or data.message is None:
        return ""
    content = data.message.content or "{}"
    return json.loads(content).get("text", "")


@lru_cache(maxsize=4)
def _get_lark_client(app_id: str, app_secret: str) -> lark.Client:
    """Return a cached lark.Client for the given app credentials.

    返回给定应用凭证的缓存 lark.Client（避免每次回复都 builder）。

    Args:
        app_id: Feishu application id.
            飞书应用 App ID。
        app_secret: Feishu application secret.
            飞书应用密钥。

    Returns:
        Configured Lark client.
            配置完成的 Lark 客户端。
    """
    return lark.Client.builder().app_id(app_id).app_secret(app_secret).build()


def _send_reply(client: lark.Client, chat_id: str, answer: str) -> None:
    """Send a text reply to a Feishu chat.

    向飞书会话发送文本回复。

    Args:
        client: Lark SDK client.
            Lark 客户端。
        chat_id: Target chat id.
            目标会话 ID。
        answer: Reply body text.
            回复正文。
    """
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
    """Send a Feishu interactive card (HITL confirm card).

    发送飞书交互卡片（危险操作确认卡片）。

    Args:
        client: Lark SDK client.
            Lark 客户端。
        chat_id: Target chat id.
            目标会话 ID。
        card_json: Serialized interactive card JSON.
            序列化后的交互卡片 JSON。
    """
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

    def _handle_in_background(chat_id: str, question: str, requester: str | None) -> None:
        try:
            _run_blocking(
                lambda: _handle_via_agent_core(lark_client, chat_id, question, agent_client, requester=requester)
            )
        except Exception:
            logger.exception("Failed to handle message for chat %s", chat_id)

    def _on_card_action(trigger: P2CardActionTrigger) -> P2CardActionTriggerResponse:
        data = trigger.event
        if data is None:
            return P2CardActionTriggerResponse({"toast": {"type": "error", "content": "无效回调"}})
        op = data.operator
        # chat_id may or may not be exposed on card-action events depending on
        # lark-oapi version; pass it through when available so the callback can
        # bind to the real (event-supplied) chat context, not the card value.
        event_chat_id = getattr(data, "open_chat_id", None) or getattr(data, "chat_id", None)
        payload: dict[str, object] = {
            "action": {"value": (data.action.value if data.action else {}) or {}},
            "operator": {"open_id": (op.open_id if op else None) or (op.user_id if op else None) or "unknown"},
        }
        if event_chat_id:
            payload["chat_id"] = str(event_chat_id)
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
        sender = data.sender
        requester = (sender.sender_id.open_id if sender and sender.sender_id else None) or None
        _EXECUTOR.submit(_handle_in_background, data.message.chat_id, question, requester)

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
