from __future__ import annotations

import pytest

from opspilot.tools.registry import (
    _registry,
    build_tools_prompt,
    call_tool,
    get_registered_tools,
    register_tool,
)


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Ensure each test starts and ends with an empty registry."""
    _registry.clear()
    yield
    _registry.clear()


def test_register_tool_adds_to_registry() -> None:
    @register_tool
    def my_tool(x: str) -> str:
        """A test tool."""
        return x

    tools = get_registered_tools()
    assert "my_tool" in tools
    info = tools["my_tool"]
    assert info.name == "my_tool"
    assert info.description == "A test tool."
    assert info.func is my_tool


def test_register_tool_infers_json_schema_from_signature() -> None:
    @register_tool
    def schema_tool(query: str, limit: int = 50) -> str:
        """Query with limit."""
        return f"{query}:{limit}"

    info = get_registered_tools()["schema_tool"]
    schema = info.parameters
    assert schema["type"] == "object"
    assert "query" in schema["properties"]
    assert "limit" in schema["properties"]
    assert schema["properties"]["query"]["type"] == "string"
    assert schema["properties"]["limit"]["type"] == "integer"
    assert schema["properties"]["limit"]["default"] == 50
    assert schema["required"] == ["query"]


def test_register_tool_custom_name() -> None:
    @register_tool(name="custom_name")
    def some_func(x: str) -> str:
        """Has custom name."""
        return x

    assert "custom_name" in get_registered_tools()
    assert "some_func" not in get_registered_tools()


def test_build_tools_prompt_contains_tool_info() -> None:
    @register_tool
    def prompt_tool(namespace: str) -> str:
        """Check namespace status."""
        return namespace

    prompt = build_tools_prompt()
    assert "prompt_tool" in prompt
    assert "Check namespace status" in prompt
    assert "namespace" in prompt


def test_get_registered_tools_returns_copy() -> None:
    """Returned dict should be a copy so callers can't mutate the registry."""
    tools = get_registered_tools()
    tools["should_not_exist"] = None  # type: ignore[assignment]
    assert "should_not_exist" not in get_registered_tools()


# ---------------------------------------------------------------------------
# call_tool tests
# ---------------------------------------------------------------------------


def test_call_tool_json_object_input() -> None:
    """JSON object with named kwargs should be unpacked correctly."""

    @register_tool
    def greet(name: str, greeting: str = "hi") -> str:
        return f"{greeting} {name}"

    result = call_tool("greet", '{"name": "Alice", "greeting": "hello"}')
    assert result == "hello Alice"


def test_call_tool_single_required_param_fallback() -> None:
    """Plain string input with one required param should pass as that param."""

    @register_tool
    def echo(message: str) -> str:
        return message

    result = call_tool("echo", "hello world")
    assert result == "hello world"


def test_call_tool_single_required_param_fallback_with_coercion() -> None:
    """Plain string input should be coerced to the required param's type."""

    @register_tool
    def double(n: int) -> str:
        return str(n * 2)

    result = call_tool("double", "21")
    assert result == "42"


def test_call_tool_first_positional_fallback() -> None:
    """When there are multiple required params, the first gets the value."""

    @register_tool
    def pair(a: str, b: str = "default") -> str:
        return f"{a}-{b}"

    result = call_tool("pair", "x")
    assert result == "x-default"


def test_call_tool_unknown_tool() -> None:
    """Unknown tool name should return an error message."""
    result = call_tool("nonexistent", "input")
    assert "nonexistent" in result
    assert "不存在" in result or "错误" in result


def test_call_tool_execution_error() -> None:
    """Tool that raises should return a formatted error string."""

    @register_tool
    def bad_tool(x: str) -> str:
        raise ValueError("something broke")

    result = call_tool("bad_tool", "test")
    assert "工具执行错误" in result
    assert "something broke" in result
