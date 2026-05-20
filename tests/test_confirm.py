"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_confirm.py
@DateTime: 2026-05-20
@Docs: Tests confirm_dangerous_op guidance tool (no self-auth).
    测试 confirm_dangerous_op 提示工具（不可自放行）。
"""

from opspilot.tools.confirm import confirm_dangerous_op
from opspilot.tools.registry import get_registered_tools


def test_confirm_tool_no_longer_self_authorizes() -> None:
    # 工具自身不再放行任何东西；它只产出"去人工通道确认"的指引
    out = confirm_dangerous_op("kubectl_scale user-service 0")
    assert "已确认" not in out
    # 应说明该操作进入待人工确认流程
    assert "kubectl_scale user-service 0" in out
    assert "人工" in out or "审批" in out


def test_confirm_no_longer_accepts_token_param() -> None:
    # 旧 token 参数已删除：传入额外位置参数应 TypeError
    import pytest

    with pytest.raises(TypeError):
        confirm_dangerous_op("op", "CONFIRM")  # type: ignore[call-arg]


def test_confirm_token_constant_removed() -> None:
    # 静态明文 token 不再导出
    import opspilot.tools.confirm as confirm_mod

    assert not hasattr(confirm_mod, "CONFIRM_TOKEN")


def test_confirm_registered_low_risk() -> None:
    # the confirmation tool itself must not be flagged dangerous
    assert get_registered_tools()["confirm_dangerous_op"].risk == "low"
