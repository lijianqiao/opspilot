"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_kubectl_write.py
@DateTime: 2026-05-20
@Docs: Tests mock kubectl write tools and rollback_info_for.
    测试 mock 写工具与 rollback_info_for。
"""

from opspilot.tools.kubectl_write import kubectl_rollout_restart, kubectl_scale, rollback_info_for
from opspilot.tools.registry import get_registered_tools


def test_scale_returns_mock_success() -> None:
    """
    Verify scale returns mock success.

    验证：scale returns mock success。
    """
    out = kubectl_scale("user-service", 5, "default")
    assert "user-service" in out
    assert "5" in out


def test_scale_unknown_deployment() -> None:
    """
    Verify scale unknown deployment.

    验证：scale unknown deployment。
    """
    assert "没有找到" in kubectl_scale("nope", 1, "default")


def test_rollout_restart_returns_mock_success() -> None:
    """
    Verify rollout restart returns mock success.

    验证：rollout restart returns mock success。
    """
    out = kubectl_rollout_restart("order-service", "default")
    assert "order-service" in out
    assert "重启" in out


def test_write_tools_registered_as_high_risk() -> None:
    """
    Verify write tools registered as high risk.

    验证：write tools registered as high risk。
    """
    tools = get_registered_tools()
    assert tools["kubectl_scale"].risk == "high"
    assert tools["kubectl_rollout_restart"].risk == "high"


def test_scale_exposes_rollback_prev_replicas() -> None:
    """
    Verify scale exposes rollback prev replicas.

    验证：scale exposes rollback prev replicas。
    """
    info = rollback_info_for("kubectl_scale", '{"deployment": "user-service", "replicas": 0, "namespace": "default"}')
    assert info == {"deployment": "user-service", "replicas": 3, "namespace": "default"}


def test_rollout_restart_exposes_rollback_revision() -> None:
    """
    Verify rollout restart exposes rollback revision.

    验证：rollout restart exposes rollback revision。
    """
    info = rollback_info_for("kubectl_rollout_restart", '{"deployment": "order-service"}')
    assert info == {"deployment": "order-service", "revision": "unknown", "namespace": "default"}


def test_rollback_info_none_for_bad_input_or_unknown() -> None:
    """
    Verify rollback info none for bad input or unknown.

    验证：rollback info none for bad input or unknown。
    """
    assert rollback_info_for("kubectl_scale", "not json") is None
    assert rollback_info_for("kubectl_scale", '{"deployment": "ghost", "replicas": 0}') is None
    assert rollback_info_for("query_loki", '{"query": "x"}') is None


def test_tool_info_has_reversible_default_false() -> None:
    """
    Verify tool info has reversible default false.

    验证：tool info has reversible default false。
    """
    assert get_registered_tools()["kubectl_scale"].reversible is False
