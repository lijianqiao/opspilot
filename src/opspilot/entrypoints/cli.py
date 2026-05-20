"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: cli.py
@DateTime: 2026-05-20
@Docs: Typer CLI — ask ops questions via ReAct or Plan-Execute agent.
    Typer CLI：通过 ReAct 或 Plan-Execute Agent 提问运维问题。
"""

import anyio
import typer

from opspilot.agent.langgraph_agent import run_react_graph
from opspilot.agent.plan_execute import run_plan_execute
from opspilot.config import get_settings
from opspilot.llm.client import LLMClient

app = typer.Typer(help="OpsPilot 运维智能助手 CLI")


@app.callback()
def _root() -> None:
    """OpsPilot ops assistant CLI root callback.

    OpsPilot 运维智能助手 CLI 根回调。
    """


@app.command()
def ask(question: str, plan: bool = typer.Option(False, "--plan", help="使用 Plan-Execute 架构")) -> None:
    """Ask OpsPilot an ops question via the agent.

    向 OpsPilot 提一个运维问题。

    Args:
        question: Natural-language ops question.
            自然语言运维问题。
        plan: Use Plan-Execute architecture instead of ReAct.
            为 True 时使用 Plan-Execute 架构而非 ReAct。
    """

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
    """CLI entrypoint invoked by the opspilot console script.

    由 opspilot 控制台脚本调用的 CLI 入口。
    """
    app()
