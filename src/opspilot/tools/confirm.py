"""Confirmation guidance tool.

注意：此工具**不再**自行放行任何操作（旧的静态 token=CONFIRM 设计可被 LLM 自确认）。
真正的放行只发生在 agent.confirmation.ConfirmationStore，经由人工通道（飞书卡片回调）。
本工具只负责告诉 LLM "该操作已进入待人工确认状态"。
"""

from __future__ import annotations

from opspilot.tools.registry import register_tool


@register_tool(name="confirm_dangerous_op", risk="low")
def confirm_dangerous_op(operation: str) -> str:
    """说明危险操作已转入人工确认流程（本工具不放行，仅提示）。"""
    return (
        f"操作「{operation}」已被安全网关拦截，正在等待人工审批。"
        "请勿尝试自行放行；审批由运维人员通过审批通道完成后会自动继续。"
    )
