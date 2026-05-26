"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_feishu_ws.py
@DateTime: 2026-05-20
@Docs: Tests Feishu WS error redaction and bounded threading.
    测试飞书 WS 错误脱敏与有界线程池。
"""

import anyio
import pytest

from opspilot.entrypoints.feishu_ws import (
    _select_agent,
    handle_question,
)


@pytest.mark.anyio
async def test_handle_question_delegates_and_trims() -> None:
    """
    Verify handle question delegates and trims.

    验证：handle question delegates and trims。
    """

    async def agent(text: str) -> str:
        return f"answered: {text}"

    assert await handle_question("  pod 状态  ", agent) == "answered: pod 状态"


@pytest.mark.anyio
async def test_handle_question_rejects_empty() -> None:
    """
    Verify handle question rejects empty.

    验证：handle question rejects empty。
    """

    async def agent(text: str) -> str:
        raise AssertionError("空输入不应调用 agent")

    assert "Please enter" in await handle_question("   ", agent)


@pytest.mark.anyio
async def test_handle_question_redacts_agent_failure_detail() -> None:
    # 审查报告 feishu_ws:46-47：原实现 f"Error: {exc}" 把异常字符串直传给用户，
    # 泄露 DSN/堆栈/密钥。新实现：固定脱敏文案，详情仅写日志。
    """
    Verify handle question redacts agent failure detail.

    验证：handle question redacts agent failure detail。
    """

    async def boom(text: str) -> str:
        raise RuntimeError("LLM connection refused")

    result = await handle_question("pod 状态", boom)
    assert "LLM connection refused" not in result
    assert "出错" in result


@pytest.mark.anyio
async def test_handle_question_does_not_leak_dsn_or_secrets() -> None:
    """
    Verify handle question does not leak dsn or secrets.

    验证：handle question does not leak dsn or secrets。
    """

    async def boom(text: str) -> str:
        raise RuntimeError("postgresql://opspilot:opspilot@db:5432 connect failed; api_key=sk-LEAK")

    result = await handle_question("hi", boom)
    assert "postgresql://" not in result
    assert "opspilot:opspilot" not in result
    assert "sk-LEAK" not in result
    assert "api_key" not in result.lower()


@pytest.mark.anyio
async def test_bare_anyio_run_fails_inside_running_loop() -> None:
    # Reproduce root cause: lark WS callback runs on a thread with an
    # existing event loop, so anyio.run() raises RuntimeError.
    """
    Verify bare anyio run fails inside running loop.

    验证：bare anyio run fails inside running loop。
    """

    async def agent(text: str) -> str:
        return text

    with pytest.raises(RuntimeError, match="Already running"):
        anyio.run(handle_question, "x", agent)


def test_executor_uses_configured_worker_count(monkeypatch: pytest.MonkeyPatch) -> None:
    # 校验 _get_executor 用 settings.feishu_workers 创建线程池；
    # 移除旧 _run_blocking 后这是验证新线程模型可配置性的最小契约。
    """
    Verify executor uses configured worker count.

    验证：executor uses configured worker count。
    """
    import opspilot.entrypoints.feishu_ws as ws
    from opspilot.config import get_settings

    monkeypatch.setenv("OPSPILOT_FEISHU_WORKERS", "3")
    get_settings.cache_clear()
    monkeypatch.setattr(ws, "_executor", None)
    executor = ws._get_executor()
    try:
        assert executor._max_workers == 3
        # Second call returns the same cached instance.
        assert ws._get_executor() is executor
    finally:
        executor.shutdown(wait=False)
        monkeypatch.setattr(ws, "_executor", None)
        get_settings.cache_clear()


def test_select_agent_plan_prefix():
    """
    Verify select agent plan prefix.

    验证：select agent plan prefix。
    """
    text, use_plan = _select_agent("规划：查看 pod")
    assert use_plan is True
    assert text == "查看 pod"


def test_select_agent_plan_prefix_half_width():
    """
    Verify select agent plan prefix half width.

    验证：select agent plan prefix half width。
    """
    text, use_plan = _select_agent("规划:查看 pod")
    assert use_plan is True
    assert text == "查看 pod"


def test_select_agent_slash_plan():
    """
    Verify select agent slash plan.

    验证：select agent slash plan。
    """
    text, use_plan = _select_agent("/plan 查看 pod")
    assert use_plan is True
    assert text == "查看 pod"


def test_select_agent_no_prefix():
    """
    Verify select agent no prefix.

    验证：select agent no prefix。
    """
    text, use_plan = _select_agent("查看 pod")
    assert use_plan is False
    assert text == "查看 pod"


def test_select_agent_strips_feishu_mention():
    """
    Verify select agent strips feishu mention.

    验证：select agent strips feishu mention。
    """
    text, use_plan = _select_agent("@_user_1 规划：查看 pod")
    assert use_plan is True
    assert text == "查看 pod"


def test_select_agent_strips_mention_no_plan():
    """
    Verify select agent strips mention no plan.

    验证：select agent strips mention no plan。
    """
    text, use_plan = _select_agent("@_user_1 查看 pod")
    assert use_plan is False
    assert text == "查看 pod"


def test_select_agent_routes_normal_message_to_default():
    """
    Verify select agent routes normal message to default.

    验证：select agent routes normal message to default。
    """
    text, use_plan = _select_agent("查看 pod 状态")
    assert use_plan is False
    assert text == "查看 pod 状态"


def test_select_agent_preserves_plan_prefix_behavior():
    """
    Verify select agent preserves plan prefix behavior.

    验证：select agent preserves plan prefix behavior。
    """
    text, use_plan = _select_agent("规划：重启 order-service")
    assert use_plan is True
    assert text == "重启 order-service"
