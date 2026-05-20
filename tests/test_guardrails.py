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


def test_dangerous_by_input_pattern_even_if_low_tool() -> None:
    """
    Verify dangerous by input pattern even if low tool.

    验证：dangerous by input pattern even if low tool。
    """
    assert is_dangerous("kubectl_get", "rm -rf /data") is True
    assert is_dangerous("kubectl_get", "drop table users") is True


def test_safe_low_tool_safe_input() -> None:
    """
    Verify safe low tool safe input.

    验证：safe low tool safe input。
    """
    assert is_dangerous("kubectl_get", "pods") is False


def test_unknown_tool_falls_back_to_input_pattern() -> None:
    """
    Verify unknown tool falls back to input pattern.

    验证：unknown tool falls back to input pattern。
    """
    assert is_dangerous("no_such_tool", "pods") is False
    assert is_dangerous("no_such_tool", "rm -rf /") is True


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
