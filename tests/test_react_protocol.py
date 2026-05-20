"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_react_protocol.py
@DateTime: 2026-05-20
@Docs: Tests shared ReAct parse_react_output parser.
    测试共享 ReAct parse_react_output 解析器。
"""

from opspilot.agent.react_protocol import parse_react_output


def test_parse_action() -> None:
    """
    Verify parse action.

    验证：parse action。
    """
    p = parse_react_output('Thought: t\nAction: kubectl_get\nAction Input: {"resource": "pods"}')
    assert p.action == "kubectl_get"
    assert p.action_input == '{"resource": "pods"}'
    assert p.final is None


def test_parse_final() -> None:
    """
    Verify parse final.

    验证：parse final。
    """
    p = parse_react_output("Thought: done\nFinal Answer: 一切正常")
    assert p.final == "一切正常"
    assert p.action is None


def test_parse_plain_reply() -> None:
    """
    Verify parse plain reply.

    验证：parse plain reply。
    """
    p = parse_react_output("我不知道")
    assert p.action is None and p.final is None
