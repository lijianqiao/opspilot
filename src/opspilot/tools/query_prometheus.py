"""Mock Prometheus metrics query tool — reads from fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from opspilot.tools.registry import register_tool

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


@register_tool
def query_prometheus(metric_name: str) -> str:
    """查询 Prometheus 指标，返回指定指标的当前值。"""
    raw = json.loads(
        (_FIXTURES_DIR / "prometheus_metrics.json").read_text(encoding="utf-8")
    )
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
