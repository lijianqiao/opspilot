def test_supports_chat_is_single_source() -> None:
    from opspilot.agent import alert_handler, langgraph_agent, plan_execute, react, supervisor
    from opspilot.agent.protocols import SupportsChat

    for mod in (react, langgraph_agent, plan_execute, supervisor, alert_handler):
        assert mod.SupportsChat is SupportsChat, f"{mod.__name__} 未复用共享 Protocol"
