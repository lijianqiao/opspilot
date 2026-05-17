import anyio
import typer

from opspilot.agent.react import run_react
from opspilot.config import get_settings
from opspilot.llm.client import LLMClient

app = typer.Typer(help="OpsPilot 运维智能助手 CLI")


@app.callback()
def _root() -> None:
    """OpsPilot 运维智能助手 CLI。"""


@app.command()
def ask(question: str) -> None:
    """向 OpsPilot 提一个运维问题。"""

    async def _run() -> str:
        llm = LLMClient(get_settings())
        try:
            return await run_react(question, llm)
        finally:
            await llm.aclose()

    typer.echo(anyio.run(_run))


def main() -> None:
    app()
