import anyio
import typer

from opspilot.agent.langgraph_agent import run_react_graph
from opspilot.agent.plan_execute import run_plan_execute
from opspilot.config import get_settings
from opspilot.llm.client import LLMClient

app = typer.Typer(help="OpsPilot 运维智能助手 CLI")


@app.callback()
def _root() -> None:
    """OpsPilot 运维智能助手 CLI。"""


@app.command()
def ask(question: str, plan: bool = typer.Option(False, "--plan", help="使用 Plan-Execute 架构")) -> None:
    """向 OpsPilot 提一个运维问题。"""

    async def _run() -> str:
        llm = LLMClient(get_settings())
        try:
            if plan:
                return await run_plan_execute(question, llm)
            return await run_react_graph(question, llm)
        finally:
            await llm.aclose()

    typer.echo(anyio.run(_run))


def main() -> None:
    app()
