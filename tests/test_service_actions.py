"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_service_actions.py
@DateTime: 2026-05-20
@Docs: Tests generic mock service action tools (restart/scale/remediation).
    测试通用 mock 服务动作工具（重启/扩缩容/补救动作）。
"""

from opspilot.tools.registry import get_registered_tools
from opspilot.tools.service_actions import restart_service, scale_service


def test_restart_service_is_high_risk_registered_tool() -> None:
    """Verify restart_service is registered as a high-risk tool with a rolling restart message.
    验证 restart_service 注册为高危工具且返回滚动重启提示。
    """
    tools = get_registered_tools()
    assert tools["restart_service"].risk == "high"
    assert "rolling restart" in restart_service("user-service", env="staging").lower()


def test_scale_service_returns_mock_result() -> None:
    """Verify scale_service returns a mock message containing service and replica count.
    验证 scale_service 返回包含服务名与目标副本数的 mock 提示。
    """
    result = scale_service("user-service", replicas=3, env="staging")
    assert "user-service" in result
    assert "3" in result
