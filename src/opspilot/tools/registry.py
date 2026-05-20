"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: registry.py
@DateTime: 2026-05-20
@Docs: Tool registry: decorator registration with auto JSON Schema.
    工具注册表：装饰器注册并自动生成 JSON Schema。
"""

from __future__ import annotations

import inspect
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints, overload

from opspilot.observability.metrics import record_tool_call

# Module-level registry — populated by @register_tool
_registry: dict[str, ToolInfo] = {}


TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}

_SCHEMA_TYPE_TO_PYTHON: dict[str, type] = {v: k for k, v in TYPE_MAP.items()}


@dataclass(frozen=True)
class ToolInfo:
    """Metadata the agent needs for one registered tool.
    智能体所需的单个已注册工具元数据。

    Attributes:
        name: Tool name used in Action lines.
            Action 行中使用的工具名。
        description: First line of tool docstring (English for prompts).
            工具文档字符串首行（英文，用于提示）。
        func: Callable implementing the tool.
            实现该工具的可调用对象。
        parameters: JSON Schema for Action Input.
            Action Input 的 JSON Schema。
        risk: Risk level label (e.g. low, high).
            风险等级标签（如 low、high）。
        reversible: Whether the op supports rollback metadata.
            是否支持回滚元数据。
    """

    name: str
    description: str
    func: Callable[..., str]
    parameters: dict[str, Any] = field(default_factory=dict)
    risk: str = "low"
    reversible: bool = False


def _infer_json_schema(func: Callable[..., Any]) -> dict[str, Any]:
    """Build a JSON Schema object from a function's signature and type hints.

    Works for functions with simple typed parameters (str, int, float, bool)
    and optional defaults. No external schema libraries required.
    """
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        json_type = TYPE_MAP.get(hints.get(name, str), "string")
        prop: dict[str, Any] = {"type": json_type}
        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(name)
        properties[name] = prop

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


@overload
def register_tool(func: Callable[..., str], /) -> Callable[..., str]: ...


@overload
def register_tool(
    func: None = None, *, name: str | None = None, risk: str = "low", reversible: bool = False
) -> Callable[[Callable[..., str]], Callable[..., str]]: ...


def register_tool(
    func: Callable[..., str] | None = None, *, name: str | None = None, risk: str = "low", reversible: bool = False
) -> Callable[..., str] | Callable[[Callable[..., str]], Callable[..., str]]:
    """Decorator to register a function as an OpsPilot tool.
    将函数注册为 OpsPilot 工具的装饰器。

    Usage:
        @register_tool
        def my_tool(x: str) -> str: ...

        @register_tool(name="custom_name")
        def my_tool(x: str) -> str: ...

    Args:
        func: Function to register when used as @register_tool without parens.
            无参装饰时待注册的函数。
        name: Optional override for tool name.
            可选的工具名覆盖。
        risk: Risk level stored in ToolInfo.
            写入 ToolInfo 的风险等级。
        reversible: Reversible flag for rollback-aware tools.
            支持回滚的工具的可逆标志。

    Returns:
        Registered function unchanged, or partial decorator when func is None.
            原函数不变，或 func 为 None 时返回部分装饰器。
    """

    def _register(f: Callable[..., str]) -> Callable[..., str]:
        tool_name = name or f.__name__
        doc = inspect.getdoc(f) or ""
        info = ToolInfo(
            name=tool_name,
            description=doc.split("\n")[0],  # first line only
            func=f,
            parameters=_infer_json_schema(f),
            risk=risk,
            reversible=reversible,
        )
        _registry[tool_name] = info
        return f

    if func is not None:
        return _register(func)
    return _register


def get_registered_tools() -> dict[str, ToolInfo]:
    """Return a copy of the registry so callers cannot mutate it.
    返回注册表副本，防止调用方修改内部状态。

    Returns:
        Dict mapping tool name to ToolInfo.
            工具名到 ToolInfo 的字典。
    """
    return dict(_registry)


def build_tools_prompt(tool_filter: set[str] | None = None) -> str:
    """Auto-generate the tools section of the system prompt from registry.
    根据注册表自动生成系统提示中的工具说明段落。

    Args:
        tool_filter: Optional set of tool names to include; None means all.
            可选工具名集合；为 None 时包含全部已注册工具。

    Returns:
        Chinese-formatted tools prompt for the LLM.
            面向 LLM 的中文格式工具提示文本。
    """
    tools = get_registered_tools()

    # Filter: only include tools in tool_filter (if specified and non-empty)
    if tool_filter:
        tools = {k: v for k, v in tools.items() if k in tool_filter}

    if not tools:
        return "当前没有可用工具。"

    lines = ["可用工具：", ""]
    for info in tools.values():
        params = info.parameters.get("properties", {})
        required = info.parameters.get("required", [])
        param_parts = []
        for pname, pinfo in params.items():
            type_str = pinfo.get("type", "string")
            if pname in required:
                param_parts.append(f"{pname}: {type_str}")
            else:
                default = pinfo.get("default", "")
                param_parts.append(f"{pname}: {type_str} = {default}")
        param_str = ", ".join(param_parts)
        lines.append(f"工具：{info.name}({param_str})")
        lines.append(f"描述：{info.description}")
        lines.append("")

    lines.append("严格按格式逐步推理，每次只输出一步。需要调用工具时：")
    lines.append("")
    lines.append("Thought: <思考>")
    lines.append("Action: <工具名>")
    lines.append('Action Input: <参数 JSON，如 {"namespace": "default"} 或单个值如 default>')
    lines.append("")
    lines.append("拿到足够信息后：")
    lines.append("")
    lines.append("Thought: <总结>")
    lines.append("Final Answer: <给用户的最终回答>")

    return "\n".join(lines)


def call_tool(name: str, raw_input: str) -> str:
    """Look up a registered tool and call it, parsing raw_input intelligently.
    查找已注册工具并调用，智能解析 raw_input。

    Parsing: JSON object kwargs, single required param, or first positional.

    Args:
        name: Registered tool name.
            已注册的工具名称。
        raw_input: Action Input string (JSON or scalar).
            Action Input 字符串（JSON 或标量）。

    Returns:
        Tool result string, or Chinese error message on failure.
            工具结果字符串，失败时返回中文错误信息。
    """
    tools = get_registered_tools()
    if name not in tools:
        return f"错误：工具 {name} 不存在。可用工具：{list(tools)}"

    info = tools[name]
    started = time.perf_counter()
    status = "success"
    try:
        # Try JSON first
        try:
            args = json.loads(raw_input)
            if isinstance(args, dict):
                return info.func(**args)
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: coerce raw_input to the parameter's annotated type
        def _coerce(value: str, param_name: str) -> Any:
            props = info.parameters.get("properties", {})
            schema_type = props.get(param_name, {}).get("type", "string")
            python_type = _SCHEMA_TYPE_TO_PYTHON.get(schema_type, str)
            if python_type is bool:
                return value.lower() in ("true", "1", "yes")
            return python_type(value)

        # Fallback: single required param → pass as that param
        required = info.parameters.get("required", [])
        if len(required) == 1:
            return info.func(**{required[0]: _coerce(raw_input, required[0])})

        # Fallback: first positional arg
        params = list(info.parameters.get("properties", {}).keys())
        if params:
            return info.func(**{params[0]: _coerce(raw_input, params[0])})

        return info.func(raw_input)
    except Exception as e:
        status = "error"
        return f"工具执行错误：{e}"
    finally:
        record_tool_call(name, status, time.perf_counter() - started)
