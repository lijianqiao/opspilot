"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_log_tools.py
@DateTime: 2026-05-20
@Docs: Tests Loki/Prometheus mock log tools.
    测试 Loki/Prometheus mock 日志工具。
"""

from opspilot.tools.log_tools import aggregate_errors, tail_pod_logs


def test_aggregate_errors_returns_error_summary():
    result = aggregate_errors("order-service", "default")
    assert "order-service" in result
    assert "error" in result.lower() or "错误" in result


def test_aggregate_errors_handles_empty():
    result = aggregate_errors("nonexistent", "default")
    assert result  # should return something, not raise


def test_tail_pod_logs_returns_log_content():
    result = tail_pod_logs("order-service-5c7b9d-klmno", "default", tail_lines=10)
    assert "order-service" in result


def test_tail_pod_logs_default_tail():
    result = tail_pod_logs("order-service-5c7b9d-klmno")
    assert result  # default namespace + tail_lines
