"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_demo_smoke.py
@DateTime: 2026-05-20
@Docs: Tests demo_smoke script end-to-end smoke path.
    测试 demo_smoke 脚本端到端冒烟路径。
"""

from scripts.demo_smoke import build_demo_requests


def test_build_demo_requests_contains_core_scenarios() -> None:
    """
    Verify build demo requests contains core scenarios.

    验证：build demo requests contains core scenarios。
    """
    requests = build_demo_requests()
    questions = [item["question"] for item in requests]
    assert any("pod" in q for q in questions)
    assert any("日志" in q for q in questions)
    assert any("告警" in q for q in questions)
