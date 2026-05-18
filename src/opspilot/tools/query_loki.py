"""Mock Loki log query tool — reads from fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from opspilot.tools.registry import register_tool

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


@register_tool
def query_loki(query: str, namespace: str = "default", limit: int = 100) -> str:
    """查询 Loki 日志，支持关键字搜索和 namespace 过滤。"""
    raw = json.loads((_FIXTURES_DIR / "loki_logs.json").read_text(encoding="utf-8"))
    results: list[str] = []
    for stream in raw["streams"]:
        ns = stream["stream"].get("namespace", "")
        if ns != namespace:
            continue
        pod = stream["stream"].get("pod", "unknown")
        for ts, line in stream["values"]:
            if query.lower() in line.lower():
                results.append(f"[{pod}] {line}")
    if not results:
        return f"namespace {namespace} 下没有找到匹配 '{query}' 的日志。"
    return "\n".join(results[:limit])
