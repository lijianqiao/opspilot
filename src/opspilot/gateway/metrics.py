from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest


def build_registry() -> tuple[CollectorRegistry, Counter, Histogram]:
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
    return generate_latest(registry)
