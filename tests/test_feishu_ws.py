import pytest

from opspilot.entrypoints.feishu_ws import handle_question


@pytest.mark.anyio
async def test_handle_question_delegates_and_trims() -> None:
    async def agent(text: str) -> str:
        return f"answered: {text}"

    assert await handle_question("  pod 状态  ", agent) == "answered: pod 状态"


@pytest.mark.anyio
async def test_handle_question_rejects_empty() -> None:
    async def agent(text: str) -> str:
        raise AssertionError("空输入不应调用 agent")

    assert "请输入" in await handle_question("   ", agent)
