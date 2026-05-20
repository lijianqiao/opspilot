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
    """
    Verify safe tool executes and audits.

    验证：safe tool executes and audits。
    """
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
    """
    Verify cap exceeded blocks.

    验证：cap exceeded blocks。
    """
    r = guarded_call_tool("kubectl_get", "pods", calls=9, max_calls=8, store=ConfirmationStore(300))
    assert r.blocked is True
    assert "上限" in r.observation


def test_dangerous_without_confirmation_blocked_and_audited(tmp_path) -> None:
    """
    Verify dangerous without confirmation blocked and audited.

    验证：dangerous without confirmation blocked and audited。
    """
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
    """
    Verify dangerous with human confirmation executes.

    验证：dangerous with human confirmation executes。
    """
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


def test_confirmed_request_is_bound_to_original_tool_and_input(tmp_path) -> None:
    """
    Verify confirmed request is bound to original tool and input.

    验证：confirmed request is bound to original tool and input。
    """
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request("kubectl_scale", '{"deployment":"user-service","replicas":0}')
    assert store.confirm(pc.request_id, pc.token, actor="feishu:ou_1") is True

    result = guarded_call_tool(
        "kubectl_rollout_restart",
        '{"deployment":"user-service"}',
        calls=1,
        max_calls=8,
        store=store,
        confirmed_request_id=pc.request_id,
        audit_path=str(tmp_path / "audit.jsonl"),
    )

    assert result.blocked is True
    assert "request_id=" in result.observation
    assert store.is_confirmed(pc.request_id) is True


def test_guarded_call_rejects_tool_not_in_allowed_set(tmp_path) -> None:
    """
    Verify a tool outside the allowlist is hard-blocked at execution.

    验证：不在 allowlist 内的工具会在执行入口被硬拦截。
    """
    result = guarded_call_tool(
        "kubectl_scale",
        '{"deployment":"user-service","replicas":0}',
        calls=1,
        max_calls=8,
        store=ConfirmationStore(300),
        allowed_tools={"kubectl_get"},
        audit_path=str(tmp_path / "audit.jsonl"),
    )
    assert result.blocked is True
    assert "not allowed" in result.observation.lower()


def test_observation_redacted(tmp_path) -> None:
    """
    Verify observation redacted.

    验证：observation redacted。
    """
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
