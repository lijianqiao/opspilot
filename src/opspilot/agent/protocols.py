"""Shared agent protocols — single source of truth for the LLM chat interface."""

from __future__ import annotations

from typing import Protocol


class SupportsChat(Protocol):
    async def chat(self, messages: list[dict[str, str]]) -> str: ...
