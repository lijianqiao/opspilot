"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: query_loki.py
@DateTime: 2026-05-20
@Docs: Mock Loki log query tool with keyword and namespace filter.
    模拟 Loki 日志查询工具，支持关键字与 namespace 过滤。
"""

from __future__ import annotations

import json
from pathlib import Path

from opspilot.tools.registry import register_tool

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


@register_tool
def query_loki(query: str, namespace: str = "default", limit: int = 100) -> str:
    """Query Loki logs with keyword search and namespace filter.
    查询 Loki 日志，支持关键字搜索和 namespace 过滤。

    Args:
        query: Substring to match in log lines (case-insensitive).
            日志行匹配子串（不区分大小写）。
        namespace: Namespace label filter.
            namespace 标签过滤条件。
        limit: Maximum number of log lines to return.
            返回日志行的最大条数。

    Returns:
        Matching log lines or not-found message.
            匹配的日志行文本，无匹配时返回提示。
    """
    raw = json.loads((_FIXTURES_DIR / "loki_logs.json").read_text(encoding="utf-8"))
    results: list[str] = []
    for stream in raw["streams"]:
        ns = stream["stream"].get("namespace", "")
        if ns != namespace:
            continue
        pod = stream["stream"].get("pod", "unknown")
        for _ts, line in stream["values"]:
            if query.lower() in line.lower():
                results.append(f"[{pod}] {line}")
    if not results:
        return f"namespace {namespace} 下没有找到匹配 '{query}' 的日志。"
    return "\n".join(results[:limit])
