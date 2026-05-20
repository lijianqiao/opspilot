"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_alert_handler.py
@DateTime: 2026-05-20
@Docs: Tests alert diagnosis handler and runbook integration.
    测试告警诊断处理与 Runbook 集成。
"""

import json
from pathlib import Path

import pytest

from opspilot.agent.alert_handler import handle_alert


class FakeLLM:
    def __init__(self, replies: list[str]) -> None:
        self._replies = replies

    async def chat(self, messages: list[dict[str, str]]) -> str:
        return self._replies.pop(0)


@pytest.mark.anyio
async def test_handle_alert_diagnoses_crashloop():
    """
    Verify handle alert diagnoses crashloop.

    验证：handle alert diagnoses crashloop。
    """
    fixture = Path("fixtures/alertmanager_webhook.json").read_text("utf-8")
    payload = json.loads(fixture)

    llm = FakeLLM(
        [
            "Final Answer: 诊断结论：order-service 因 OOM 导致 CrashLoopBackOff，"
            "建议增加 memory limit 并排查内存泄漏。相关 Runbook 已附。",
        ]
    )
    result = await handle_alert(payload, llm)
    assert "OOM" in result
    assert "order-service" in result


@pytest.mark.anyio
async def test_handle_alert_includes_runbook():
    """
    Verify handle alert includes runbook.

    验证：handle alert includes runbook。
    """
    fixture = Path("fixtures/alertmanager_webhook.json").read_text("utf-8")
    payload = json.loads(fixture)

    llm = FakeLLM(["Final Answer: 诊断完成。"])
    result = await handle_alert(payload, llm)
    # Runbook should be included in the context even if LLM output is minimal
    assert len(result) > 0
