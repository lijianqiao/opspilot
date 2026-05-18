from __future__ import annotations

import inspect

import pytest

from opspilot.tools.registry import ToolInfo, get_registered_tools, register_tool, build_tools_prompt


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

    # cleanup
    from opspilot.tools.registry import _registry
    _registry.pop("my_tool", None)


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

    from opspilot.tools.registry import _registry
    _registry.pop("schema_tool", None)


def test_register_tool_custom_name() -> None:
    @register_tool(name="custom_name")
    def some_func(x: str) -> str:
        """Has custom name."""
        return x

    assert "custom_name" in get_registered_tools()
    assert "some_func" not in get_registered_tools()

    from opspilot.tools.registry import _registry
    _registry.pop("custom_name", None)


def test_build_tools_prompt_contains_tool_info() -> None:
    @register_tool
    def prompt_tool(namespace: str) -> str:
        """Check namespace status."""
        return namespace

    prompt = build_tools_prompt()
    assert "prompt_tool" in prompt
    assert "Check namespace status" in prompt
    assert "namespace" in prompt

    from opspilot.tools.registry import _registry
    _registry.pop("prompt_tool", None)


def test_get_registered_tools_returns_copy() -> None:
    """Returned dict should be a copy so callers can't mutate the registry."""
    tools = get_registered_tools()
    tools["should_not_exist"] = None  # type: ignore[assignment]
    assert "should_not_exist" not in get_registered_tools()
