"""Tool registry: decorator-based registration with auto JSON Schema generation."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints, overload

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
    """All metadata the agent needs about a registered tool."""

    name: str
    description: str
    func: Callable[..., str]
    parameters: dict[str, Any] = field(default_factory=dict)
    risk: str = "low"


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
    func: None = None, *, name: str | None = None, risk: str = "low"
) -> Callable[[Callable[..., str]], Callable[..., str]]: ...


def register_tool(
    func: Callable[..., str] | None = None, *, name: str | None = None, risk: str = "low"
) -> Callable[..., str] | Callable[[Callable[..., str]], Callable[..., str]]:
    """Decorator to register a function as an OpsPilot tool.

    Usage:
        @register_tool
        def my_tool(x: str) -> str: ...

        @register_tool(name="custom_name")
        def my_tool(x: str) -> str: ...
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
        )
        _registry[tool_name] = info
        return f

    if func is not None:
        return _register(func)
    return _register


def get_registered_tools() -> dict[str, ToolInfo]:
    """Return a copy of the registry so callers can't mutate it."""
    return dict(_registry)


def build_tools_prompt() -> str:
    """Auto-generate the tools section of the system prompt from registry.

    Produces a description block for each registered tool so the LLM
    knows what's available, what arguments to pass, and in what format.
    """
    tools = get_registered_tools()
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

    Parsing strategy:
    1. If raw_input is valid JSON object → use as keyword args
    2. If tool has exactly one required param → pass raw_input as that param
    3. Otherwise → pass raw_input as first positional arg
    """
    tools = get_registered_tools()
    if name not in tools:
        return f"错误：工具 {name} 不存在。可用工具：{list(tools)}"

    info = tools[name]
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
        return f"工具执行错误：{e}"
