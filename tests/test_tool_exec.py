"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_tool_exec.py
@DateTime: 2026-05-20
@Docs: Tests unified guarded_call_tool chokepoint.
    测试统一 guarded_call_tool 受控执行。
"""

from opspilot.agent.confirmation import ConfirmationStore
from opspilot.agent.tool_exec import GuardedResult, guarded_call_tool


def test_safe_tool_executes_and_audits(tmp_path) -> None:
    audit = tmp_path / "a.jsonl"
    r = guarded_call_tool(
        "kubectl_get",
        "pods",
        calls=1,
        max_calls=8,
        store=ConfirmationStore(300),
        audit_path=str(audit),
    )
    assert isinstance(r, GuardedResult)
    assert r.blocked is False
    # mock kubectl_get returns either a pod table or "没有找到"
    assert "NAME" in r.observation or "没有找到" in r.observation
    # safe tool also audited
    assert audit.read_text(encoding="utf-8").strip()


def test_cap_exceeded_blocks() -> None:
    r = guarded_call_tool("kubectl_get", "pods", calls=9, max_calls=8, store=ConfirmationStore(300))
    assert r.blocked is True
    assert "上限" in r.observation


def test_dangerous_without_confirmation_blocked_and_audited(tmp_path) -> None:
    audit = tmp_path / "a.jsonl"
    store = ConfirmationStore(300)
    r = guarded_call_tool(
        "kubectl_scale",
        '{"deployment":"user-service","replicas":0}',
        calls=1,
        max_calls=8,
        store=store,
        audit_path=str(audit),
    )
    assert r.blocked is True
    assert r.request_id is not None  # pending 已登记，等待人工
    assert "scaled" not in r.observation  # 未执行
    # 审计已落 blocked 记录
    content = audit.read_text(encoding="utf-8")
    assert '"status": "blocked"' in content


def test_dangerous_with_human_confirmation_executes(tmp_path) -> None:
    audit = tmp_path / "a.jsonl"
    store = ConfirmationStore(300)
    raw = '{"deployment":"user-service","replicas":0}'
    pc = store.request("kubectl_scale", raw)
    assert store.confirm(pc.request_id, pc.token, actor="feishu:ou_42") is True

    r = guarded_call_tool(
        "kubectl_scale",
        raw,
        calls=1,
        max_calls=8,
        store=store,
        confirmed_request_id=pc.request_id,
        audit_path=str(audit),
    )
    assert r.blocked is False
    assert "scaled" in r.observation  # mock: "deployment.apps/x scaled: 3 -> 0"
    # confirmation 被消费，再次确认状态变 False
    assert store.is_confirmed(pc.request_id) is False
    # 审计 executed 含 confirmer
    content = audit.read_text(encoding="utf-8")
    assert '"status": "executed"' in content
    assert "feishu:ou_42" in content


def test_observation_redacted(tmp_path) -> None:
    from opspilot.tools.registry import register_tool

    @register_tool(name="leaky_for_tool_exec_test")
    def _leaky(x: str) -> str:
        """leak."""
        return "api_key=sk-DEADBEEF999999"

    r = guarded_call_tool(
        "leaky_for_tool_exec_test",
        "x",
        calls=1,
        max_calls=8,
        store=ConfirmationStore(300),
        audit_path=str(tmp_path / "a.jsonl"),
    )
    assert "sk-DEADBEEF999999" not in r.observation
