"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: protocols.py
@DateTime: 2026-05-20
@Docs: Shared agent protocols for the LLM chat interface.
    智能体共享协议：LLM 对话接口定义。
"""

from __future__ import annotations

from typing import Protocol


class SupportsChat(Protocol):
    """Protocol for LLM chat backends used by all agents.
    所有智能体共用的 LLM 对话后端协议。

    Methods:
        chat: Send messages and receive assistant text.
            发送消息列表并返回助手文本。
    """

    async def chat(self, messages: list[dict[str, str]]) -> str:
        """Send a message list to the LLM and return the reply text.
        向 LLM 发送消息列表并返回回复文本。

        Args:
            messages: OpenAI-style role/content dicts.
                OpenAI 风格的 role/content 消息字典列表。

        Returns:
            Assistant reply as plain text.
                助手回复的纯文本内容。
        """
        ...
