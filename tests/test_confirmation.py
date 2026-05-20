import time

from opspilot.agent.confirmation import ConfirmationStore


def test_request_creates_unpredictable_token() -> None:
    store = ConfirmationStore(ttl_seconds=300)
    a = store.request("kubectl_scale", '{"deployment":"x","replicas":0}')
    b = store.request("kubectl_scale", '{"deployment":"x","replicas":0}')
    assert a.token != b.token
    assert a.request_id != b.request_id
    # 一次性随机 token 必须足够长 (LLM 不可预测)
    assert len(a.token) >= 32


def test_confirm_then_consume_allows_once() -> None:
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


def test_wrong_token_rejected() -> None:
    store = ConfirmationStore(ttl_seconds=300)
    pc = store.request("kubectl_scale", "x")
    # LLM 猜测 token 必须失败
    assert store.confirm(pc.request_id, "guessed-by-llm", actor="agent") is False
    assert store.is_confirmed(pc.request_id) is False


def test_unknown_request_id_rejected() -> None:
    store = ConfirmationStore(ttl_seconds=300)
    assert store.confirm("nonexistent", "anytoken", actor="x") is False


def test_expired_request_rejected() -> None:
    store = ConfirmationStore(ttl_seconds=0)
    pc = store.request("kubectl_scale", "x")
    time.sleep(0.05)
    assert store.confirm(pc.request_id, pc.token, actor="x") is False
    assert store.is_confirmed(pc.request_id) is False


def test_get_pending_returns_record_without_consuming() -> None:
    # 飞书 entrypoint 收到 guarded_call_tool 返回的 request_id 后，需要
    # 取出 token + tool + input 构造确认卡片；只读，不消费、不放行。
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
