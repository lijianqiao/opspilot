"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_guardrails.py
@DateTime: 2026-05-20
@Docs: Tests is_dangerous detection and output redaction.
    测试危险操作判定与输出脱敏。
"""

from opspilot.agent.guardrails import is_dangerous, redact


def test_dangerous_by_registry_risk() -> None:
    # kubectl_scale is registered risk="high" (Task 2)
    """
    Verify dangerous by registry risk.

    验证：dangerous by registry risk。
    """
    assert is_dangerous("kubectl_scale", '{"deployment": "x", "replicas": 0}') is True


def test_low_risk_tool_with_destructive_text_no_longer_blocked() -> None:
    """raw_input text scanning was removed; only registry risk='high' triggers HITL.

    验证：低风险工具携带破坏性文本不再触发 HITL（仅以注册表 risk='high' 为准）。
    """
    # A 'low' tool receiving destructive-looking text should NOT be flagged —
    # the text is just data, not an executed command.
    assert is_dangerous("kubectl_get", "rm -rf /data") is False
    assert is_dangerous("kubectl_get", "drop table users") is False
    assert is_dangerous("kubectl_get", '{"query": "drop table x"}') is False


def test_safe_low_tool_safe_input() -> None:
    """
    Verify safe low tool safe input.

    验证：safe low tool safe input。
    """
    assert is_dangerous("kubectl_get", "pods") is False


def test_unknown_tool_with_dangerous_text_no_longer_blocked() -> None:
    """Unknown tools fall through to safe-by-default (was: regex-flagged).

    验证：未知工具不再因输入文本触发 HITL，安全降级为 False。
    """
    assert is_dangerous("no_such_tool", "pods") is False
    assert is_dangerous("no_such_tool", "rm -rf /") is False


def test_redact_masks_api_key() -> None:
    """
    Verify redact masks api key.

    验证：redact masks api key。
    """
    out = redact("here is sk-abcdef123456 and Bearer tok_SECRET99")
    assert "sk-abcdef123456" not in out
    assert "tok_SECRET99" not in out
    assert "***" in out


def test_redact_masks_password_assignment() -> None:
    """
    Verify redact masks password assignment.

    验证：redact masks password assignment。
    """
    assert "hunter2" not in redact("password=hunter2 next")


def test_redact_keeps_normal_text() -> None:
    """
    Verify redact keeps normal text.

    验证：redact keeps normal text。
    """
    assert redact("default 下 3 个 pod 正常") == "default 下 3 个 pod 正常"
