"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: alert_handler.py
@DateTime: 2026-05-20
@Docs: Alert Handler: webhook ingest, diagnose, return report.
    告警处理智能体：接收 Webhook、诊断并返回报告。
"""

from __future__ import annotations

import logging
from typing import Any

from opspilot.agent.protocols import SupportsChat
from opspilot.alerts.adapters import normalize_alert_payload
from opspilot.alerts.models import NormalizedAlertEvent
from opspilot.tools.log_tools import aggregate_errors
from opspilot.tools.runbook import retrieve_runbook

logger = logging.getLogger(__name__)


def _coerce_event(payload: NormalizedAlertEvent | dict[str, Any]) -> NormalizedAlertEvent:
    """Accept either a NormalizedAlertEvent or a raw dict for backwards compatibility.

    兼容旧调用方：dict 通过适配器归一化，NormalizedAlertEvent 直接返回。
    """
    if isinstance(payload, NormalizedAlertEvent):
        return payload
    source = str(payload.get("source") or "alertmanager")
    return normalize_alert_payload(payload, source=source)


def _extract_context(payload: NormalizedAlertEvent | dict[str, Any]) -> dict[str, str]:
    """Extract key fields from a normalized alert event (or legacy Alertmanager dict).

    从归一化告警事件（或旧版 Alertmanager dict）中提取关键字段。
    """
    event = _coerce_event(payload)
    alert = event.alerts[0]
    return {
        "service": alert.service,
        "namespace": alert.environment,
        "alertname": alert.alertname,
        "severity": alert.severity,
        "summary": alert.summary,
        "description": alert.description,
    }


async def handle_alert(payload: NormalizedAlertEvent | dict[str, Any], llm: SupportsChat) -> str:
    """Main entry: receive normalized (or raw) alert event, diagnose, return report.
    主入口：接收归一化（或原始）告警事件、综合诊断并返回报告。

    Pipeline: parse alert → gather logs/runbook → LLM synthesis.

    Args:
        payload: NormalizedAlertEvent or raw Alertmanager-shaped dict.
            归一化告警事件，或与 Alertmanager 兼容的原始 dict。
        llm: Chat backend for diagnosis synthesis.
            用于综合诊断的对话后端。

    Returns:
        Formatted diagnosis report string for operators.
            面向运维人员的格式化诊断报告文本。
    """
    ctx = _extract_context(payload)
    logger.info(
        "Alert received: %s/%s severity=%s",
        ctx["alertname"],
        ctx["service"],
        ctx["severity"],
    )

    # 1. Gather evidence: logs + runbook
    logs = aggregate_errors(ctx["service"], ctx["namespace"])
    runbook = retrieve_runbook(ctx["description"] or ctx["alertname"])

    # 2. Synthesize diagnosis via LLM
    diagnosis_prompt = (
        f"你是运维专家。收到以下告警，请综合分析并给出诊断结论和行动建议。\n\n"
        f"告警名称：{ctx['alertname']}\n"
        f"影响服务：{ctx['service']}（namespace: {ctx['namespace']}）\n"
        f"严重级别：{ctx['severity']}\n"
        f"告警摘要：{ctx['summary']}\n"
        f"告警详情：{ctx['description']}\n\n"
        f"=== 日志分析结果 ===\n{logs}\n\n"
        f"=== 相关 Runbook ===\n{runbook}\n\n"
        f"请用 Final Answer: 开头给出诊断结论，包括：\n"
        f"1. 根因分析\n2. 建议操作（区分紧急/长期）\n3. 是否需要升级"
    )
    diagnosis = await llm.chat([{"role": "user", "content": diagnosis_prompt}])

    # 3. Assemble final report
    return (
        f"【OpsPilot 告警诊断报告】\n"
        f"告警：{ctx['alertname']} | 服务：{ctx['service']} | 级别：{ctx['severity']}\n\n"
        f"{diagnosis}"
    )
