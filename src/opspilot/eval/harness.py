"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: harness.py
@DateTime: 2026-05-20
@Docs: Offline eval harness — run scripted cases via ReAct graph and score.
    离线评测 harness：经 ReAct 图执行脚本用例并输出三维评分表。
"""

from __future__ import annotations

from dataclasses import dataclass

from opspilot.agent.context import use_llm
from opspilot.agent.langgraph_agent import _FINAL_RE, _compiled_graph, run_react_graph
from opspilot.config import get_settings
from opspilot.eval.cases import CASES, EvalCase
from opspilot.tools.registry import build_tools_prompt


class _ScriptedLLM:
    """Fake LLM that pops canned replies and records Action tool names.

    脚本化假 LLM：按序弹出预设回复并记录 Action 行中的工具名。

    Args:
        replies: Canned assistant outputs consumed in order.
            按顺序消费的预设助手输出列表。
    """

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.seen_tools: list[str] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        """Return next scripted reply and append any Action tool to seen_tools.

        返回下一条脚本回复，并将 Action 行中的工具名追加到 seen_tools。

        Args:
            messages: Conversation history (ignored except for interface compat).
                对话历史（仅为接口兼容，内容未使用）。

        Returns:
            Next canned reply or a default Final Answer when exhausted.
                下一条脚本回复；用尽时返回默认 Final Answer。
        """
        reply = self._replies.pop(0) if self._replies else "Final Answer: (脚本结束)"
        for line in reply.splitlines():
            line = line.strip()
            if line.startswith("Action:"):
                self.seen_tools.append(line.split(":", 1)[1].strip())
        return reply


@dataclass(frozen=True)
class EvalResult:
    """Per-case scoring breakdown for the eval table.

    单条用例的评分拆解（用于评测表格）。

    Attributes:
        name: Case name label.
            用例名称。
        tool_sequence_ok: Whether observed tools match expected sequence.
            观测工具序列是否与期望一致。
        danger_blocked_ok: Whether dangerous ops were blocked as expected.
            危险操作是否按期望被拦截。
        answer_keywords_ok: Whether answer (and trace) contain required keywords.
            答案（及轨迹）是否包含必需关键词。
    """

    name: str
    tool_sequence_ok: bool
    danger_blocked_ok: bool
    answer_keywords_ok: bool

    @property
    def passed(self) -> bool:
        """True when all three dimension checks succeed.

        当三个维度检查均通过时返回 True。
        """
        return self.tool_sequence_ok and self.danger_blocked_ok and self.answer_keywords_ok


async def _run_with_trace(case: EvalCase, llm: _ScriptedLLM) -> tuple[str, str]:
    """Run graph and return (final_answer, full_message_text_for_trace_checks).

    执行图并返回 (最终答案, 完整消息文本) 供轨迹关键词检查。

    Args:
        case: Eval case definition.
            评测用例定义。
        llm: Scripted LLM instance bound into graph context.
            注入图上下文的脚本化 LLM 实例。

    Returns:
        Tuple of final answer string and concatenated trace text.
            (最终答案字符串, 拼接后的轨迹文本) 元组。
    """
    initial_state: dict[str, object] = {
        "messages": [
            {"role": "system", "content": f"你是运维助手 OpsPilot。\n\n{build_tools_prompt()}"},
            {"role": "user", "content": case.question},
        ],
        "question": case.question,
        "steps_taken": 0,
        "max_steps": case.max_steps,
        "tool_calls": 0,
    }
    with use_llm(llm):
        result = await _compiled_graph.ainvoke(initial_state)
    messages = result.get("messages", [])
    trace = "\n".join(str(m.get("content", "")) for m in messages if isinstance(m, dict))

    if result.get("tool_calls", 0) > get_settings().agent_max_tool_calls:
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                if final := _FINAL_RE.search(str(msg.get("content", ""))):
                    return final.group(1).strip(), trace
        return "工具调用次数已达上限，已停止。", trace

    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            content = str(msg.get("content", ""))
            if final := _FINAL_RE.search(content):
                return final.group(1).strip(), trace
            return content.strip(), trace
    return "未能得到最终答案。", trace


async def run_case(case: EvalCase) -> EvalResult:
    """Execute one eval case and compute three metric dimensions.

    执行单条评测用例并计算三个评分维度。

    Args:
        case: Eval case to run.
            待运行的评测用例。

    Returns:
        EvalResult with per-dimension pass/fail flags.
            包含各维度通过/失败标志的 EvalResult。
    """
    llm = _ScriptedLLM(case.scripted_replies)
    if case.trace_keywords:
        answer, trace = await _run_with_trace(case, llm)
    else:
        answer = await run_react_graph(case.question, llm, max_steps=case.max_steps)
        trace = answer

    tool_ok = llm.seen_tools == case.expected_tool_sequence

    if case.expect_danger_blocked:
        # blocked => the mock write success string must NOT be in the answer
        danger_ok = "scaled" not in answer and "已触发滚动重启" not in answer
    else:
        danger_ok = True

    kw_ok = all(k in answer for k in case.answer_keywords)
    if case.trace_keywords:
        kw_ok = kw_ok and all(k in trace for k in case.trace_keywords)

    return EvalResult(case.name, tool_ok, danger_ok, kw_ok)


async def run_all() -> list[EvalResult]:
    """Run every case in CASES sequentially.

    顺序执行 CASES 中的全部用例。

    Returns:
        List of EvalResult in case order.
            按用例顺序排列的 EvalResult 列表。
    """
    return [await run_case(c) for c in CASES]


def format_table(results: list[EvalResult]) -> str:
    """Format eval results as a fixed-width ASCII score table.

    将评测结果格式化为固定宽度的 ASCII 评分表。

    Args:
        results: Outcomes from run_all or run_case.
            run_all 或 run_case 产生的结果列表。

    Returns:
        Multi-line table string with per-case PASS/FAIL and total.
            含逐行 PASS/FAIL 与汇总的多行表格字符串。
    """
    rows = [
        "name                | tools | danger | answer | PASS",
        "--------------------+-------+--------+--------+-----",
    ]
    for r in results:
        rows.append(
            f"{r.name:<20}|  {'Y' if r.tool_sequence_ok else 'N':<4}|  "
            f"{'Y' if r.danger_blocked_ok else 'N':<5}|  "
            f"{'Y' if r.answer_keywords_ok else 'N':<5}| {'PASS' if r.passed else 'FAIL'}"
        )
    passed = sum(1 for r in results if r.passed)
    rows.append(f"\nTOTAL: {passed}/{len(results)} passed")
    return "\n".join(rows)
