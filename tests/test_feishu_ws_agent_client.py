"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_feishu_ws_agent_client.py
@DateTime: 2026-05-20
@Docs: Tests Feishu thin adapter path via AgentClient mock.
    测试飞书经 AgentClient 调用 agent-core 的薄适配器路径。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opspilot.entrypoints.feishu_ws import _handle_via_agent_core


@pytest.mark.anyio
async def test_handle_via_agent_core_sends_card_when_request_id_in_answer() -> None:
    """
    Feishu adapter sends confirm card when answer contains request_id.

    飞书适配器在回答含 request_id 时应发送确认卡片。
    """
    mock_client = AsyncMock()
    mock_client.ask.return_value = "blocked request_id=abc123xyz"
    mock_client.get_pending.return_value = MagicMock(
        request_id="abc123xyz",
        token="tok",
        tool="kubectl_scale",
        tool_input="x",
    )
    mock_lark = MagicMock()
    with (
        patch("opspilot.entrypoints.feishu_ws._send_reply"),
        patch("opspilot.entrypoints.feishu_ws._send_card") as send_card,
        patch("opspilot.entrypoints.feishu_ws.build_confirm_card", return_value="{}"),
    ):
        await _handle_via_agent_core(mock_lark, "chat1", "scale x", mock_client)
    mock_client.ask.assert_awaited_once()
    mock_client.get_pending.assert_awaited_once_with("abc123xyz")
    send_card.assert_called_once()
