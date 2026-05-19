from opspilot.agent.react_protocol import parse_react_output


def test_parse_action() -> None:
    p = parse_react_output('Thought: t\nAction: kubectl_get\nAction Input: {"resource": "pods"}')
    assert p.action == "kubectl_get"
    assert p.action_input == '{"resource": "pods"}'
    assert p.final is None


def test_parse_final() -> None:
    p = parse_react_output("Thought: done\nFinal Answer: 一切正常")
    assert p.final == "一切正常"
    assert p.action is None


def test_parse_plain_reply() -> None:
    p = parse_react_output("我不知道")
    assert p.action is None and p.final is None
