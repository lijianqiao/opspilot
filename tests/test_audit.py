"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_audit.py
@DateTime: 2026-05-20
@Docs: Tests append-only JSONL operation audit log.
    测试 append-only JSONL 操作审计日志。
"""

import json

import pytest


def test_record_operation_appends_jsonl(tmp_path) -> None:
    """
    Verify record operation appends jsonl.

    验证：record operation appends jsonl。
    """
    from opspilot.observability.audit import record_operation

    log = tmp_path / "audit.jsonl"
    record_operation(
        tool="kubectl_scale",
        tool_input='{"deployment": "x", "replicas": 0}',
        actor="agent",
        confirmed_by=None,
        status="blocked",
        result="需人工确认",
        rollback=None,
        path=str(log),
    )
    record_operation(
        tool="kubectl_scale",
        tool_input="x",
        actor="agent",
        confirmed_by="feishu:ou_123",
        status="executed",
        result="scaled",
        rollback={"replicas": 3},
        path=str(log),
    )
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[1])
    assert rec["tool"] == "kubectl_scale"
    assert rec["confirmed_by"] == "feishu:ou_123"
    assert rec["rollback"] == {"replicas": 3}
    assert "ts" in rec and rec["status"] == "executed"


def test_record_operation_truncates_huge_result(tmp_path) -> None:
    """
    Verify record operation truncates huge result.

    验证：record operation truncates huge result。
    """
    from opspilot.observability.audit import record_operation

    log = tmp_path / "a.jsonl"
    record_operation(
        tool="t",
        tool_input="i",
        actor="agent",
        confirmed_by=None,
        status="executed",
        result="x" * 9000,
        rollback=None,
        path=str(log),
    )
    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert len(rec["result"]) <= 2000


def test_record_operation_redacts_and_truncates_input_and_result(tmp_path) -> None:
    """
    Verify record operation redacts and truncates input and result.

    验证：record operation redacts and truncates input and result。
    """
    from opspilot.observability.audit import record_operation

    log = tmp_path / "a.jsonl"
    record_operation(
        tool="t",
        tool_input=f'{{"api_key":"sk-INPUTSECRET999999","payload":"{"i" * 3000}"}}',
        actor="agent",
        confirmed_by=None,
        status="executed",
        result=f"password=hunter2 {'r' * 3000}",
        rollback=None,
        path=str(log),
    )

    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert "sk-INPUTSECRET999999" not in rec["tool_input"]
    assert "hunter2" not in rec["result"]
    assert len(rec["tool_input"]) <= 2000
    assert len(rec["result"]) <= 2000


def test_record_operation_includes_trace_id(tmp_path) -> None:
    """
    record_operation should embed the current trace id from ContextVar.

    验证：record_operation 应从 ContextVar 读取并写入当前 trace id。
    """
    from opspilot.observability.audit import record_operation
    from opspilot.observability.context import reset_trace_id, set_trace_id

    log = tmp_path / "audit.jsonl"
    token = set_trace_id("trace-a")
    try:
        record_operation(
            tool="kubectl_get",
            tool_input="pods",
            actor="agent",
            confirmed_by=None,
            status="executed",
            result="ok",
            rollback=None,
            path=str(log),
        )
    finally:
        reset_trace_id(token)
    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert rec["trace_id"] == "trace-a"


def test_record_operation_trace_id_none_when_unset(tmp_path) -> None:
    """
    record_operation should record trace_id=None when no ContextVar is set.

    验证：未设置 trace id 时，record_operation 写入 trace_id=None，向后兼容。
    """
    from opspilot.observability.audit import record_operation

    log = tmp_path / "audit.jsonl"
    record_operation(
        tool="kubectl_get",
        tool_input="pods",
        actor="agent",
        confirmed_by=None,
        status="executed",
        result="ok",
        rollback=None,
        path=str(log),
    )
    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert "trace_id" in rec
    assert rec["trace_id"] is None


def test_record_operation_returns_true_on_success(tmp_path) -> None:
    """
    record_operation returns True when the append succeeds.

    验证：成功写入时 record_operation 返回 True。
    """
    from opspilot.observability.audit import record_operation

    log = tmp_path / "audit.jsonl"
    ok = record_operation(
        tool="kubectl_get",
        tool_input="pods",
        actor="agent",
        confirmed_by=None,
        status="executed",
        result="ok",
        rollback=None,
        path=str(log),
    )
    assert ok is True


def test_record_operation_returns_false_when_best_effort_write_fails(tmp_path) -> None:
    """
    record_operation returns False on OSError when fail_closed is omitted.

    验证：默认模式下写失败（OSError）应返回 False 且不抛异常。
    """
    from opspilot.observability.audit import record_operation

    # Use a directory path as the audit "file" — open(..., "a") raises
    # IsADirectoryError (an OSError) on POSIX, PermissionError on Windows.
    # Both inherit from OSError and trigger the same branch.
    bad = tmp_path / "dir"
    bad.mkdir()

    ok = record_operation(
        tool="kubectl_get",
        tool_input="pods",
        actor="agent",
        confirmed_by=None,
        status="executed",
        result="ok",
        rollback=None,
        path=str(bad),
    )
    assert ok is False


def test_record_operation_raises_when_fail_closed_and_write_fails(tmp_path) -> None:
    """
    record_operation raises AuditWriteError when fail_closed=True and write fails.

    验证：fail_closed=True 时写失败应抛 AuditWriteError。
    """
    from opspilot.observability.audit import AuditWriteError, record_operation

    bad = tmp_path / "dir"
    bad.mkdir()

    with pytest.raises(AuditWriteError):
        record_operation(
            tool="kubectl_get",
            tool_input="pods",
            actor="agent",
            confirmed_by=None,
            status="approved",
            result="approved for execution",
            rollback=None,
            path=str(bad),
            fail_closed=True,
        )
