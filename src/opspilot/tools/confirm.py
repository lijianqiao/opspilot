"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: confirm.py
@DateTime: 2026-05-20
@Docs: Confirmation guidance tool; does not approve ops itself.
    确认引导工具：仅提示流程，不自行放行操作。
"""

from __future__ import annotations

from opspilot.tools.registry import register_tool


@register_tool(name="confirm_dangerous_op", risk="low")
def confirm_dangerous_op(operation: str) -> str:
    """Explain that a dangerous op awaits human approval (does not approve).
    说明危险操作已转入人工确认流程（本工具不放行，仅提示）。

    Args:
        operation: Human-readable description of the blocked operation.
            被拦截操作的可读描述。

    Returns:
        Guidance message for the LLM and operator.
            面向 LLM 与运维人员的引导说明文本。
    """
    return (
        f"操作「{operation}」已被安全网关拦截，正在等待人工审批。"
        "请勿尝试自行放行；审批由运维人员通过审批通道完成后会自动继续。"
    )
