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


def test_generic_restart_service_requires_confirmation(tmp_path) -> None:
    """
    Verify the generic high-risk restart_service tool is blocked pending HITL.

    验证：通用高危 restart_service 工具会被拦截并登记人工确认。
    """
    result = guarded_call_tool(
        "restart_service",
        '{"service":"user-service","env":"staging"}',
        calls=1,
        max_calls=8,
        store=ConfirmationStore(300),
        audit_path=str(tmp_path / "audit.jsonl"),
    )
    assert result.blocked is True
    assert result.request_id


def test_confirmation_context_recorded_on_block(tmp_path) -> None:
    """
    Verify guarded_call_tool stores the channel-bound context on new pending.

    验证：guarded_call_tool 在登记 pending 时记录渠道绑定上下文。
    """
    store = ConfirmationStore(300)
    result = guarded_call_tool(
        "restart_service",
        '{"service":"user-service"}',
        calls=1,
        max_calls=8,
        store=store,
        confirmation_context={"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
        audit_path=str(tmp_path / "audit.jsonl"),
    )
    assert result.blocked is True
    assert result.request_id is not None
    pending = store.get_pending(result.request_id)
    assert pending is not None
    assert pending.context == {"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"}


def test_confirmation_context_mismatch_blocks_execution(tmp_path) -> None:
    """
    Verify a confirmed pending cannot be consumed from a different context.

    验证：已确认的 pending 在不同渠道/会话上下文中不可被消费。
    """
    store = ConfirmationStore(300)
    raw = '{"deployment":"user-service","replicas":0}'
    pc = store.request(
        "kubectl_scale",
        raw,
        context={"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
    )
    assert (
        store.confirm(
            pc.request_id,
            pc.token,
            actor="feishu:ou_1",
            context={"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
        )
        is True
    )

    result = guarded_call_tool(
        "kubectl_scale",
        raw,
        calls=1,
        max_calls=8,
        store=store,
        confirmed_request_id=pc.request_id,
        confirmation_context={"channel": "feishu", "chat_id": "chat-b", "requester": "ou_1"},
        audit_path=str(tmp_path / "audit.jsonl"),
    )
    # 上下文不匹配 → 视为未确认 → 重新登记 pending
    assert result.blocked is True
    # confirmation should still be intact on the original pending
    assert store.is_confirmed(pc.request_id) is True


def test_confirmation_context_match_executes(tmp_path) -> None:
    """
    Verify a confirmed pending with matching context executes successfully.

    验证：上下文匹配的已确认 pending 能够成功执行。
    """
    store = ConfirmationStore(300)
    raw = '{"deployment":"user-service","replicas":0}'
    ctx = {"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"}
    pc = store.request("kubectl_scale", raw, context=ctx)
    assert store.confirm(pc.request_id, pc.token, actor="feishu:ou_1", context=ctx) is True

    result = guarded_call_tool(
        "kubectl_scale",
        raw,
        calls=1,
        max_calls=8,
        store=store,
        confirmed_request_id=pc.request_id,
        confirmation_context=ctx,
        audit_path=str(tmp_path / "audit.jsonl"),
    )
    assert result.blocked is False
    assert "scaled" in result.observation


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


def test_tool_error_recorded_with_tool_error_status(tmp_path) -> None:
    """A call_tool failure should audit status='tool_error', not 'executed'.

    工具执行失败应以 status='tool_error' 审计，与正常执行区分。
    """
    audit = tmp_path / "a.jsonl"
    r = guarded_call_tool(
        "no_such_tool",
        "x",
        calls=1,
        max_calls=8,
        store=ConfirmationStore(300),
        audit_path=str(audit),
    )
    # Tool failure is not a guardrail block — agent gets the observation back.
    assert r.blocked is False
    assert "工具执行错误" in r.observation
    content = audit.read_text(encoding="utf-8")
    assert '"status": "tool_error"' in content


def test_confirmed_high_risk_tool_does_not_execute_when_audit_fails(monkeypatch, tmp_path) -> None:
    """
    When approved-audit write fails, the high-risk op must NOT run and the
    confirmation must remain intact so the operator can retry.

    验证：approved 审计写失败时高危操作不执行，且确认未被消费，可直接重试。
    """
    import opspilot.tools.service_actions  # noqa: F401 - ensure restart_service registered

    store = ConfirmationStore(300)
    raw = '{"service":"user-service","env":"staging"}'
    pc = store.request("restart_service", raw)
    assert store.confirm(pc.request_id, pc.token, actor="feishu:ou_42") is True

    def boom(**_kwargs) -> bool:
        raise RuntimeError("audit down")

    monkeypatch.setattr("opspilot.agent.tool_exec.record_operation", boom)

    result = guarded_call_tool(
        "restart_service",
        raw,
        calls=1,
        max_calls=8,
        store=store,
        confirmed_request_id=pc.request_id,
        audit_path=str(tmp_path / "audit.jsonl"),
    )

    assert result.blocked is True
    assert "audit" in result.observation.lower()
    # Confirmation must survive so the operator can retry without re-issuing a card.
    assert store.is_confirmed(pc.request_id) is True
