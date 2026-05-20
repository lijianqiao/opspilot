"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_registry_risk.py
@DateTime: 2026-05-20
@Docs: Tests ToolInfo risk and reversible metadata.
    测试 ToolInfo 风险与可回滚元数据。
"""

from opspilot.tools.registry import (
    ToolInfo,
    get_registered_tools,
    register_tool,
)


def test_default_risk_is_low() -> None:
    @register_tool(name="t_low_demo")
    def t_low_demo(x: str) -> str:
        """demo low."""
        return x

    info = get_registered_tools()["t_low_demo"]
    assert isinstance(info, ToolInfo)
    assert info.risk == "low"


def test_explicit_high_risk() -> None:
    @register_tool(name="t_high_demo", risk="high")
    def t_high_demo(x: str) -> str:
        """demo high."""
        return x

    assert get_registered_tools()["t_high_demo"].risk == "high"
