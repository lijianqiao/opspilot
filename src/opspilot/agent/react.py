import re
from collections.abc import Callable
from typing import Protocol

from opspilot.tools.pod_status import get_pod_status

Tool = Callable[[str], str]

TOOLS: dict[str, Tool] = {"get_pod_status": get_pod_status}

SYSTEM_PROMPT = """你是运维助手 OpsPilot。可用工具：

工具：get_pod_status(namespace)
描述：查询指定 namespace 下的 pod 状态。

严格按格式逐步推理，每次只输出一步。需要调用工具时：

Thought: <思考>
Action: get_pod_status
Action Input: <namespace，如 default>

拿到足够信息后：

Thought: <总结>
Final Answer: <给用户的最终回答>
"""

_ACTION_RE = re.compile(r"Action:\s*(\w+)")
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.*)")
_FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)


class SupportsChat(Protocol):
    async def chat(self, messages: list[dict[str, str]]) -> str: ...


async def run_react(
    question: str, llm: SupportsChat, max_steps: int = 5
) -> str:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    for _ in range(max_steps):
        reply = await llm.chat(messages)
        messages.append({"role": "assistant", "content": reply})

        if final := _FINAL_RE.search(reply):
            return final.group(1).strip()

        action = _ACTION_RE.search(reply)
        if action is None:
            return reply.strip()

        tool_name = action.group(1)
        tool = TOOLS.get(tool_name)
        if tool is None:
            observation = (
                f"错误：工具 {tool_name} 不存在。可用工具：{list(TOOLS)}"
            )
        else:
            arg = _ACTION_INPUT_RE.search(reply)
            namespace = (arg.group(1).strip() if arg else "default") or "default"
            observation = tool(namespace)

        messages.append(
            {"role": "user", "content": f"Observation: {observation}"}
        )

    return "达到最大推理步数，未能得到最终答案。"
