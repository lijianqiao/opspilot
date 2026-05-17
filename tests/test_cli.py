import pytest
from typer.testing import CliRunner

from opspilot.entrypoints import cli

runner = CliRunner()


class _NoopLLM:
    def __init__(self, *args: object, **kwargs: object) -> None: ...

    async def aclose(self) -> None:
        return None


def test_cli_ask_outputs_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_react(question: str, llm: object, max_steps: int = 5) -> str:
        return f"FAKE:{question}"

    monkeypatch.setattr(cli, "run_react", fake_run_react)
    monkeypatch.setattr(cli, "LLMClient", _NoopLLM)

    result = runner.invoke(cli.app, ["ask", "user-service 状态"])

    assert result.exit_code == 0
    assert "FAKE:user-service 状态" in result.stdout
