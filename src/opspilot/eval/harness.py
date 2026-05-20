"""Offline eval harness: run each scripted case through the real
ReAct graph and score 3 metrics. One command -> a score table.
"""

from __future__ import annotations

from dataclasses import dataclass

from opspilot.agent.langgraph_agent import _FINAL_RE, _compiled_graph, _current_llm, run_react_graph
from opspilot.config import get_settings
from opspilot.eval.cases import CASES, EvalCase
from opspilot.tools.registry import build_tools_prompt


class _ScriptedLLM:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.seen_tools: list[str] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        reply = self._replies.pop(0) if self._replies else "Final Answer: (脚本结束)"
        for line in reply.splitlines():
            line = line.strip()
            if line.startswith("Action:"):
                self.seen_tools.append(line.split(":", 1)[1].strip())
        return reply


@dataclass(frozen=True)
class EvalResult:
    name: str
    tool_sequence_ok: bool
    danger_blocked_ok: bool
    answer_keywords_ok: bool

    @property
    def passed(self) -> bool:
        return self.tool_sequence_ok and self.danger_blocked_ok and self.answer_keywords_ok


async def _run_with_trace(case: EvalCase, llm: _ScriptedLLM) -> tuple[str, str]:
    """Run graph and return (final_answer, full_message_text_for_trace_checks)."""
    _current_llm.set(llm)
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
    return [await run_case(c) for c in CASES]


def format_table(results: list[EvalResult]) -> str:
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
