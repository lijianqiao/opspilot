"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_cli.py
@DateTime: 2026-05-20
@Docs: Tests Typer CLI ask command with mocked agent.
    测试 Typer CLI ask 命令（mock 智能体）。
"""

import pytest
from typer.testing import CliRunner

from opspilot.entrypoints import cli

runner = CliRunner()


class _NoopLLM:
    def __init__(self, *args: object, **kwargs: object) -> None: ...

    async def aclose(self) -> None:
        return None


def test_cli_ask_outputs_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_react_graph(question: str, llm: object, max_steps: int = 5) -> str:
        return f"FAKE:{question}"

    monkeypatch.setattr(cli, "run_react_graph", fake_run_react_graph)
    monkeypatch.setattr(cli, "LLMClient", _NoopLLM)

    result = runner.invoke(cli.app, ["ask", "user-service 状态"])

    assert result.exit_code == 0
    assert "FAKE:user-service 状态" in result.stdout


def test_cli_ask_plan_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_plan_execute(question: str, llm: object, max_steps: int = 8) -> str:
        return f"PLAN:{question}"

    async def fake_run_react_graph(question: str, llm: object, max_steps: int = 5) -> str:
        return f"REACT:{question}"

    monkeypatch.setattr(cli, "run_plan_execute", fake_run_plan_execute)
    monkeypatch.setattr(cli, "run_react_graph", fake_run_react_graph)
    monkeypatch.setattr(cli, "LLMClient", _NoopLLM)

    result = runner.invoke(cli.app, ["ask", "--plan", "deploy check"])

    assert result.exit_code == 0
    assert "PLAN:deploy check" in result.stdout
