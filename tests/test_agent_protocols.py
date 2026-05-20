"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_agent_protocols.py
@DateTime: 2026-05-20
@Docs: Tests shared SupportsChat protocol single source.
    测试 SupportsChat 协议单一来源。
"""


def test_supports_chat_is_single_source() -> None:
    from opspilot.agent import alert_handler, langgraph_agent, plan_execute, react, supervisor
    from opspilot.agent.protocols import SupportsChat

    for mod in (react, langgraph_agent, plan_execute, supervisor, alert_handler):
        assert mod.SupportsChat is SupportsChat, f"{mod.__name__} 未复用共享 Protocol"
