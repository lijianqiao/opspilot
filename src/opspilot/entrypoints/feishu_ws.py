import logging
import re
import threading
from collections.abc import Awaitable, Callable

import anyio
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)

from opspilot.agent.plan_execute import run_plan_execute
from opspilot.agent.supervisor import run_supervisor
from opspilot.config import Settings, get_settings
from opspilot.llm.client import LLMClient

logger = logging.getLogger(__name__)

AgentFn = Callable[[str], Awaitable[str]]


_FEISHU_MENTION_RE = re.compile(r"^@\S+\s*")


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
    """Handle a Feishu message: strip, validate, delegate to agent."""
    text = text.strip()
    if not text:
        return "Please enter your ops question."
    try:
        return await agent(text)
    except Exception as exc:
        return f"Error: {exc}"


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
    import json

    data = event.event
    if data is None or data.message is None:
        return ""
    content = data.message.content or "{}"
    return json.loads(content).get("text", "")


def _send_reply(chat_id: str, answer: str, settings: Settings) -> None:
    """Send a text reply to a Feishu chat. Runs in a background thread."""
    client = lark.Client.builder().app_id(settings.feishu_app_id).app_secret(settings.feishu_app_secret).build()
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


def run() -> None:  # manual verification only, not unit tested
    """Start Feishu WS long-connection bot. Requires OPSPILOT_FEISHU_APP_ID/SECRET."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = get_settings()

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
        """Run agent and send reply in a background thread (fire-and-forget).

        The WS callback thread returns immediately so lark-oapi can
        process ping/pong heartbeats without timeout.
        """
        try:
            answer = _run_blocking(question, _agent)
            _send_reply(chat_id, answer, settings)
        except Exception:
            logger.exception("Failed to handle message for chat %s", chat_id)

    def _on_message(event: P2ImMessageReceiveV1) -> None:
        data = event.event
        if data is None or data.message is None or data.message.chat_id is None:
            return
        question = _extract_text(event)
        if not question:
            return
        # Fire-and-forget: dispatch to background thread and return immediately
        # so the WS callback thread can keep processing heartbeats.
        threading.Thread(
            target=_handle_in_background,
            args=(data.message.chat_id, question),
            name="opspilot-feishu-agent",
            daemon=True,
        ).start()

    handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(_on_message).build()
    ws = lark.ws.Client(settings.feishu_app_id, settings.feishu_app_secret, event_handler=handler)
    ws.start()


if __name__ == "__main__":
    run()
