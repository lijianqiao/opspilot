"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_confirmation.py
@DateTime: 2026-05-20
@Docs: Tests HITL ConfirmationStore TTL and one-time tokens.
    测试人工确认 ConfirmationStore（TTL、一次性 token）。
"""

import dataclasses
import time

from opspilot.agent.confirmation import ConfirmationStore


def test_request_creates_unpredictable_token() -> None:
    """
    Verify request creates unpredictable token.

    验证：request creates unpredictable token。
    """
    store = ConfirmationStore(ttl_seconds=300)
    a = store.request("kubectl_scale", '{"deployment":"x","replicas":0}')
    b = store.request("kubectl_scale", '{"deployment":"x","replicas":0}')
    assert a.token != b.token
    assert a.request_id != b.request_id
    # 一次性随机 token 必须足够长 (LLM 不可预测)
    assert len(a.token) >= 32


def test_confirm_then_consume_allows_once() -> None:
    """
    Verify confirm then consume allows once.

    验证：confirm then consume allows once。
    """
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request("kubectl_scale", "x")
    assert store.is_confirmed(pc.request_id) is False
    assert store.confirm(pc.request_id, pc.token, actor="feishu:ou_1") is True
    assert store.is_confirmed(pc.request_id) is True
    # 一次性：consume 后失效，防重放
    assert store.consume(pc.request_id) == "feishu:ou_1"
    assert store.is_confirmed(pc.request_id) is False
    # 再 consume 返回 None
    assert store.consume(pc.request_id) is None


def test_consume_if_matches_requires_original_tool_and_input() -> None:
    """
    Verify consume if matches requires original tool and input.

    验证：consume if matches requires original tool and input。
    """
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request("kubectl_scale", '{"deployment":"x","replicas":0}')
    assert store.confirm(pc.request_id, pc.token, actor="feishu:ou_1") is True

    assert store.consume_if_matches(pc.request_id, "kubectl_rollout_restart", '{"deployment":"x"}') is None
    assert store.is_confirmed(pc.request_id) is True

    assert store.consume_if_matches(pc.request_id, "kubectl_scale", '{"deployment":"x","replicas":0}') == "feishu:ou_1"
    assert store.consume_if_matches(pc.request_id, "kubectl_scale", '{"deployment":"x","replicas":0}') is None


def test_consume_if_matches_rejects_expired_confirmation() -> None:
    """
    Verify consume if matches rejects expired confirmation.

    验证：consume if matches rejects expired confirmation。
    """
    # 用充足 TTL 让 confirm() 必定成功（CI 慢 runner 上 ttl_seconds=0 会触发
    # request→confirm 间的 monotonic 时钟竞态）。confirm 成功后用 dataclasses.replace
    # 把 expires_at 强制改成过去时刻，确定性触发过期路径，无 sleep 时序假设。
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request("kubectl_scale", "x")
    assert store.confirm(pc.request_id, pc.token, actor="feishu:ou_1") is True

    # 直接将 pending 的 expires_at 改到 1 秒前 → consume_if_matches 走过期分支
    with store._lock:
        store._pending[pc.request_id] = dataclasses.replace(
            store._pending[pc.request_id], expires_at=time.monotonic() - 1.0
        )

    assert store.consume_if_matches(pc.request_id, "kubectl_scale", "x") is None
    assert store.is_confirmed(pc.request_id) is False


def test_wrong_token_rejected() -> None:
    """
    Verify wrong token rejected.

    验证：wrong token rejected。
    """
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request("kubectl_scale", "x")
    # LLM 猜测 token 必须失败
    assert store.confirm(pc.request_id, "guessed-by-llm", actor="agent") is False
    assert store.is_confirmed(pc.request_id) is False


def test_unknown_request_id_rejected() -> None:
    """
    Verify unknown request id rejected.

    验证：unknown request id rejected。
    """
    store = ConfirmationStore(ttl_seconds=300)
    assert store.confirm("nonexistent", "anytoken", actor="x") is False


def test_expired_request_rejected() -> None:
    """
    Verify expired request rejected.

    验证：expired request rejected。
    """
    store = ConfirmationStore(ttl_seconds=0)
    pc = store.request("kubectl_scale", "x")
    time.sleep(0.05)
    assert store.confirm(pc.request_id, pc.token, actor="x") is False
    assert store.is_confirmed(pc.request_id) is False


def test_consume_if_matches_requires_same_channel_context() -> None:
    """
    Verify HITL approvals are bound to the channel/chat/requester context.

    验证：HITL 审批必须绑定渠道/会话/请求人上下文，跨会话重放应被拒绝。
    """
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request(
        "restart_service",
        '{"service":"user-service"}',
        context={"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
    )
    # 同一 token + 不同 chat 应被拒：攻击者把卡片转发到其他群也无法通过
    assert (
        store.confirm(
            pc.request_id,
            pc.token,
            actor="feishu:ou_1",
            context={"channel": "feishu", "chat_id": "chat-b", "requester": "ou_1"},
        )
        is False
    )
    # 同一 context 才能确认
    assert (
        store.confirm(
            pc.request_id,
            pc.token,
            actor="feishu:ou_1",
            context={"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
        )
        is True
    )
    # consume_if_matches 同样需要 context 匹配
    assert (
        store.consume_if_matches(
            pc.request_id,
            "restart_service",
            '{"service":"user-service"}',
            context={"channel": "feishu", "chat_id": "chat-b", "requester": "ou_1"},
        )
        is None
    )
    # 正确 context 下应成功消费
    assert (
        store.consume_if_matches(
            pc.request_id,
            "restart_service",
            '{"service":"user-service"}',
            context={"channel": "feishu", "chat_id": "chat-a", "requester": "ou_1"},
        )
        == "feishu:ou_1"
    )


def test_legacy_pending_with_empty_context_matches_any_context() -> None:
    """
    Backwards compat: pending without context (legacy / API caller without
    channel info) must still be confirmable with any or no context.

    向后兼容：登记时未带 context 的旧 pending，确认/消费时传任意 context 都应通过。
    """
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request("kubectl_scale", "x")
    assert store.confirm(pc.request_id, pc.token, actor="cli:tester") is True
    # 即使提供 context 也不应被拒（pending 上下文为空）
    pc2 = store.request("kubectl_scale", "y")
    assert (
        store.confirm(
            pc2.request_id,
            pc2.token,
            actor="cli:tester",
            context={"channel": "feishu", "chat_id": "c", "requester": "ou_x"},
        )
        is True
    )


def test_get_pending_returns_record_without_consuming() -> None:
    # 飞书 entrypoint 收到 guarded_call_tool 返回的 request_id 后，需要
    # 取出 token + tool + input 构造确认卡片；只读，不消费、不放行。
    """
    Verify get pending returns record without consuming.

    验证：get pending returns record without consuming。
    """
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request("kubectl_scale", "x")
    fetched = store.get_pending(pc.request_id)
    assert fetched is not None
    assert fetched.token == pc.token
    assert fetched.tool == "kubectl_scale"
    # 仍 pending，未确认
    assert store.is_confirmed(pc.request_id) is False
    # 未知 request_id 返回 None
    assert store.get_pending("nope") is None
