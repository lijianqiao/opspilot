"""Feishu WS long-connection entrypoint.

Wires the Agent to Feishu via lark-oapi:
- 文本消息 → 运行 agent (Supervisor / Plan-Execute) → 回复文本
- 若 agent 输出中含 "request_id=XXX"（来自 guarded_call_tool 危险拦截），
  自动发交互卡片（按钮带 token），供运维人员人工放行
- 卡片按钮 click → register_p2_card_action_trigger 回调 → ConfirmationStore 放行
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

from opspilot.agent.confirmation import STORE
from opspilot.agent.guardrails import redact
from opspilot.agent.plan_execute import run_plan_execute
from opspilot.agent.supervisor import run_supervisor
from opspilot.config import get_settings
from opspilot.entrypoints.feishu_callback import handle_card_action
from opspilot.entrypoints.feishu_card import build_confirm_card
from opspilot.llm.client import LLMClient

logger = logging.getLogger(__name__)

AgentFn = Callable[[str], Awaitable[str]]


_FEISHU_MENTION_RE = re.compile(r"^@\S+\s*")
# guarded_call_tool 拦截消息形如 "...request_id=AbCdEf12..."
_REQUEST_ID_RE = re.compile(r"request_id=([A-Za-z0-9_\-]+)")

# 有界线程池：限制并发消息处理 worker，避免 thread-per-message 耗尽
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="opspilot-feishu")


def _select_agent(text: str) -> tuple[str, bool]:
    """Return (stripped_text, use_plan_execute).

    Strips Feishu mention prefix (e.g. ``@_user_1 ``) before matching.
    """
    cleaned = _FEISHU_MENTION_RE.sub("", text)
    for prefix in ("规划：", "规划:", "/plan "):
        if cleaned.startswith(prefix):
            return cleaned[len(prefix) :], True
    return cleaned, False


async def handle_question(text: str, agent: AgentFn) -> str:
    """Handle a Feishu message: strip, validate, delegate to agent.

    Exception path：固定脱敏文案给用户，原始异常详情仅写日志，
    避免 DSN/密钥/堆栈出现在用户视图（审查报告 feishu_ws:46-47）。
    """
    text = text.strip()
    if not text:
        return "Please enter your ops question."
    try:
        return await agent(text)
    except Exception:
        logger.exception("agent failed for feishu message")
        return redact("处理出错，请稍后重试或联系运维。")


def _run_blocking(text: str, agent: AgentFn) -> str:
    """Run handle_question in a fresh event loop on a new thread.

    lark-oapi WS callbacks run on a thread that already has an event
    loop, so anyio.run() raises RuntimeError. This helper spawns a
    clean thread with no running loop.
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
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("interactive")
            .content(card_json)
            .build()
        )
        .build()
    )


def _maybe_send_confirm_card(client: lark.Client, chat_id: str, answer: str) -> None:
    """If agent output mentions request_id=..., look up STORE and send a confirm card."""
    m = _REQUEST_ID_RE.search(answer)
    if m is None:
        return
    request_id = m.group(1)
    pc = STORE.get_pending(request_id)
    if pc is None:
        logger.info("request_id=%s not found in STORE (already consumed/expired)", request_id)
        return
    card = build_confirm_card(pc.request_id, pc.token, pc.tool, pc.tool_input)
    try:
        _send_card(client, chat_id, card)
        logger.info("sent confirm card for request_id=%s tool=%s", request_id, pc.tool)
    except Exception:
        logger.exception("failed to send confirm card for request_id=%s", request_id)


def _on_card_action(trigger: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    """lark-oapi card-action callback adapter — delegates to pure handle_card_action."""
    data = trigger.event
    if data is None:
        return P2CardActionTriggerResponse({"toast": {"type": "error", "content": "无效回调"}})
    op = data.operator
    payload = {
        "action": {"value": (data.action.value if data.action else {}) or {}},
        "operator": {"open_id": (op.open_id if op else None) or (op.user_id if op else None) or "unknown"},
    }
    msg = handle_card_action(payload)
    return P2CardActionTriggerResponse({"toast": {"type": "success", "content": msg}})


def run() -> None:  # manual verification only, not unit tested
    """Start Feishu WS long-connection bot. Requires OPSPILOT_FEISHU_APP_ID/SECRET."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = get_settings()
    client = _get_lark_client(settings.feishu_app_id, settings.feishu_app_secret)

    async def _agent(text: str) -> str:
        llm = LLMClient(settings)
        try:
            stripped, use_plan = _select_agent(text)
            if use_plan:
                logger.info("Agent mode: Plan-Execute (direct) | question: %s", stripped)
                return await run_plan_execute(stripped, llm)
            logger.info("Agent mode: Supervisor | question: %s", stripped)
            return await run_supervisor(stripped, llm)
        finally:
            await llm.aclose()

    def _handle_in_background(chat_id: str, question: str) -> None:
        """Run agent, send reply, and (if guarded) follow up with confirm card."""
        try:
            answer = _run_blocking(question, _agent)
            _send_reply(client, chat_id, answer)
            _maybe_send_confirm_card(client, chat_id, answer)
        except Exception:
            logger.exception("Failed to handle message for chat %s", chat_id)

    def _on_message(event: P2ImMessageReceiveV1) -> None:
        data = event.event
        if data is None or data.message is None or data.message.chat_id is None:
            return
        question = _extract_text(event)
        if not question:
            return
        # 有界执行：限制并发，避免不可控的 thread-per-message。
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
