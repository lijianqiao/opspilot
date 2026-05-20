"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_pod_status.py
@DateTime: 2026-05-20
@Docs: Tests get_pod_status fixture-based kubectl mock.
    测试 get_pod_status fixture 模拟 kubectl。
"""

from opspilot.tools.pod_status import get_pod_status


def test_get_pod_status_default_namespace_lists_pods() -> None:
    out = get_pod_status("default")
    assert "user-service-7d9f8c-abcde" in out
    assert "CrashLoopBackOff" in out
    assert "order-service-5c7b9d-klmno" in out


def test_get_pod_status_filters_by_namespace() -> None:
    out = get_pod_status("staging")
    assert "user-service-6a8e2f-pqrst" in out
    assert "order-service-5c7b9d-klmno" not in out


def test_get_pod_status_unknown_namespace() -> None:
    assert "没有找到 pod" in get_pod_status("does-not-exist")
