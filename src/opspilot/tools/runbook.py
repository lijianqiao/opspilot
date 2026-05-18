"""retrieve_runbook stub — keyword match against fixture runbooks.

Stage 3 uses stub runbooks. Stage 4 will replace with real Qdrant
RAG while keeping the function signature unchanged.
"""

import json
from pathlib import Path

from opspilot.tools.registry import register_tool

_FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures"

_RUNBOOKS: list[dict] = []


def _load_runbooks() -> list[dict]:
    global _RUNBOOKS
    if _RUNBOOKS:
        return _RUNBOOKS
    for path in sorted(_FIXTURES_DIR.glob("runbook_*.json")):
        _RUNBOOKS.append(json.loads(path.read_text(encoding="utf-8")))
    return _RUNBOOKS


@register_tool
def retrieve_runbook(query: str) -> str:
    """根据故障关键词检索相关 Runbook，返回排查步骤。"""
    runbooks = _load_runbooks()
    query_lower = query.lower()

    # Simple keyword match
    best = None
    best_score = 0
    for rb in runbooks:
        score = sum(1 for kw in rb["keywords"] if kw.lower() in query_lower)
        if score > best_score:
            best_score = score
            best = rb

    if best and best_score > 0:
        return f"=== {best['name']} ===\n\n" + "\n".join(best["steps"])

    return (
        "通用故障排查步骤：\n"
        "1. 确认故障影响范围（哪些服务/用户受影响）\n"
        "2. 查看最近部署和变更记录\n"
        "3. 检查服务日志（kubectl logs / Loki query）\n"
        "4. 检查资源使用（kubectl top / Prometheus）\n"
        "5. 检查依赖服务状态\n"
        "6. 如果无法定位，升级到 on-call"
    )
