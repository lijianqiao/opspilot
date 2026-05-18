"""Human-in-the-loop confirmation tool for dangerous operations.

Stage 2 scope: text-based confirmation token. The full Feishu
interactive-card callback is Stage 3.
"""

from __future__ import annotations

from opspilot.tools.registry import register_tool

CONFIRM_TOKEN = "CONFIRM"


@register_tool(name="confirm_dangerous_op", risk="low")
def confirm_dangerous_op(operation: str, token: str = "") -> str:
    """对危险操作做人工二次确认。token 必须等于 CONFIRM 才放行。"""
    if token.strip() == CONFIRM_TOKEN:
        return f"已确认，可以执行：{operation}"
    return f"未确认。该操作被拦截，需人工确认：{operation}。回复包含 Action Input 的 token=CONFIRM 以放行。"
