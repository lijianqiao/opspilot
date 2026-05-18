from opspilot.tools.kubectl_write import kubectl_rollout_restart, kubectl_scale
from opspilot.tools.registry import get_registered_tools


def test_scale_returns_mock_success() -> None:
    out = kubectl_scale("user-service", 5, "default")
    assert "user-service" in out
    assert "5" in out


def test_scale_unknown_deployment() -> None:
    assert "没有找到" in kubectl_scale("nope", 1, "default")


def test_rollout_restart_returns_mock_success() -> None:
    out = kubectl_rollout_restart("order-service", "default")
    assert "order-service" in out
    assert "重启" in out


def test_write_tools_registered_as_high_risk() -> None:
    tools = get_registered_tools()
    assert tools["kubectl_scale"].risk == "high"
    assert tools["kubectl_rollout_restart"].risk == "high"
