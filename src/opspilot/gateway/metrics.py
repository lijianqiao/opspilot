"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: metrics.py
@DateTime: 2026-05-20
@Docs: Prometheus metrics registry for gateway upstream requests.
    网关 Prometheus 指标注册与导出（请求计数、上游延迟）。
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest


def build_registry() -> tuple[CollectorRegistry, Counter, Histogram]:
    """Create an isolated Prometheus registry with gateway counters/histograms.

    创建独立的 Prometheus 注册表，并注册网关请求计数与延迟直方图。

    Returns:
        Tuple of (registry, request_counter, request_latency_histogram).
            三元组：(注册表, 请求计数器, 请求延迟直方图)。
    """
    registry = CollectorRegistry()
    requests = Counter(
        "opspilot_gateway_requests_total",
        "Total gateway requests",
        ["provider", "status"],
        registry=registry,
    )
    latency = Histogram(
        "opspilot_gateway_request_seconds",
        "Gateway upstream request latency",
        ["provider"],
        registry=registry,
    )
    return registry, requests, latency


def render_metrics(registry: CollectorRegistry) -> bytes:
    """Serialize Prometheus metrics from the given registry.

    将指定注册表中的指标序列化为 Prometheus 文本格式。

    Args:
        registry: Collector registry to export.
            待导出的 Collector 注册表。

    Returns:
        Prometheus exposition format bytes.
            Prometheus 文本 exposition 格式字节串。
    """
    return generate_latest(registry)
