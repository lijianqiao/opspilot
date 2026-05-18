from __future__ import annotations

from opspilot.tools.kubectl_ops import kubectl_describe, kubectl_get
from opspilot.tools.query_loki import query_loki
from opspilot.tools.query_prometheus import query_prometheus
from opspilot.tools.registry import get_registered_tools


class TestQueryLoki:
    def test_returns_matching_logs(self) -> None:
        result = query_loki("error")
        assert "ERROR" in result
        assert "order-service" in result

    def test_filters_by_namespace(self) -> None:
        result = query_loki("info", namespace="staging")
        assert "没有找到" in result

    def test_respects_limit(self) -> None:
        result = query_loki("error", limit=1)
        lines = [line for line in result.strip().split("\n") if "ERROR" in line]
        assert len(lines) <= 1


class TestKubectlOps:
    def test_kubectl_get_returns_table(self) -> None:
        result = kubectl_get("pods")
        assert "NAME" in result
        assert "order-service" in result
        assert "CrashLoopBackOff" in result

    def test_kubectl_get_filters_namespace(self) -> None:
        result = kubectl_get("pods", namespace="staging")
        assert "user-service-6a8e2f-pqrst" in result  # staging pod exists in fixture

    def test_kubectl_get_empty_namespace(self) -> None:
        result = kubectl_get("pods", namespace="nonexistent")
        assert "没有找到" in result

    def test_kubectl_describe_returns_events(self) -> None:
        result = kubectl_describe("pod", "order-service-5c7b9d-klmno")
        assert "OOMKilled" in result
        assert "BackOff" in result

    def test_kubectl_describe_unknown_pod(self) -> None:
        result = kubectl_describe("pod", "nonexistent")
        assert "没有找到" in result


class TestQueryPrometheus:
    def test_returns_metric_data(self) -> None:
        result = query_prometheus("container_cpu_usage_seconds_total")
        assert "order-service" in result
        assert "0.95" in result

    def test_unknown_metric(self) -> None:
        result = query_prometheus("nonexistent_metric")
        assert "没有找到" in result


class TestToolsRegistered:
    def test_all_new_tools_in_registry(self) -> None:
        tools = get_registered_tools()
        for name in ["query_loki", "kubectl_get", "kubectl_describe", "query_prometheus"]:
            assert name in tools, f"{name} not registered"
