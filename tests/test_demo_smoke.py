from scripts.demo_smoke import build_demo_requests


def test_build_demo_requests_contains_core_scenarios() -> None:
    requests = build_demo_requests()
    questions = [item["question"] for item in requests]
    assert any("pod" in q for q in questions)
    assert any("日志" in q for q in questions)
    assert any("告警" in q for q in questions)
