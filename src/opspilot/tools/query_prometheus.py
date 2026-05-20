"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: query_prometheus.py
@DateTime: 2026-05-20
@Docs: Mock Prometheus metrics query tool using fixtures.
    模拟 Prometheus 指标查询工具，数据来自 fixture。
"""

from __future__ import annotations

from opspilot.tools.fixtures_path import read_fixture_json, use_mock_tools
from opspilot.tools.registry import register_tool


@register_tool
def query_prometheus(metric_name: str) -> str:
    """Query a Prometheus metric and return current sample values.
    查询 Prometheus 指标，返回指定指标的当前值。

    Args:
        metric_name: Metric name to look up in fixtures.
            要在 fixture 中查找的指标名称。

    Returns:
        Formatted metric values per pod/namespace, or not-found message.
            按 pod/namespace 格式化的指标值，未找到时返回提示。
    """
    if not use_mock_tools():
        return "真实集群模式下 query_prometheus 尚未实现，请设置 OPSPILOT_USE_MOCK_TOOLS=true 或接入 Prometheus API。"
    raw = read_fixture_json("prometheus_metrics.json")
    assert isinstance(raw, dict)
    for metric in raw["metrics"]:
        if metric["name"] == metric_name:
            lines = [f"Metric: {metric_name}"]
            for entry in metric["data"]:
                labels = entry["metric"]
                ts, val = entry["value"]
                pod = labels.get("pod", "unknown")
                ns = labels.get("namespace", "unknown")
                lines.append(f"  [{ns}/{pod}] {val}")
            return "\n".join(lines)
    return f"没有找到指标：{metric_name}"
