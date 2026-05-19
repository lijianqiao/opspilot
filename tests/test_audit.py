import json


def test_record_operation_appends_jsonl(tmp_path) -> None:
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
