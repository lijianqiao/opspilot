from opspilot.tools.confirm import CONFIRM_TOKEN, confirm_dangerous_op
from opspilot.tools.registry import get_registered_tools


def test_confirm_requires_token() -> None:
    assert "未确认" in confirm_dangerous_op("kubectl_scale user-service 0", "")
    assert "未确认" in confirm_dangerous_op("kubectl_scale user-service 0", "wrong")


def test_confirm_with_token_acknowledges() -> None:
    out = confirm_dangerous_op("kubectl_scale user-service 0", CONFIRM_TOKEN)
    assert "已确认" in out
    assert "kubectl_scale user-service 0" in out


def test_confirm_registered_low_risk() -> None:
    # the confirmation tool itself must not be flagged dangerous
    assert get_registered_tools()["confirm_dangerous_op"].risk == "low"
