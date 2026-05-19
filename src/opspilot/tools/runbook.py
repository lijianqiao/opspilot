"""retrieve_runbook — hybrid RAG retrieval over Qdrant.

When Qdrant is unavailable, falls back to the original keyword-match
stub for graceful degradation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from opspilot.tools.registry import register_tool

logger = logging.getLogger(__name__)

_FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures"

# ---------------------------------------------------------------------------
# Stub fallback (original Stage 3 keyword-match) — used when Qdrant is down
# ---------------------------------------------------------------------------

_RUNBOOKS: list[dict] = []


def _load_runbooks() -> list[dict]:
    global _RUNBOOKS
    if _RUNBOOKS:
        return _RUNBOOKS
    for path in sorted(_FIXTURES_DIR.glob("runbook_*.json")):
        _RUNBOOKS.append(json.loads(path.read_text(encoding="utf-8")))
    return _RUNBOOKS


def _keyword_fallback(query: str) -> str:
    """Original keyword-match fallback (Stage 3 stub behavior)."""
    runbooks = _load_runbooks()
    query_lower = query.lower()
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


# ---------------------------------------------------------------------------
# RAG retrieval — used when Qdrant is available
# ---------------------------------------------------------------------------

_retrieval_service = None
_init_error: str | None = None


def _get_retrieval_service():
    """Lazy-init RetrievalService. Returns None if Qdrant is unavailable."""
    global _retrieval_service, _init_error
    if _retrieval_service is not None:
        return _retrieval_service
    if _init_error is not None:
        return None

    try:
        from opspilot.rag.embedding import EmbeddingService
        from opspilot.rag.qdrant_store import QdrantStore
        from opspilot.rag.retrieval import RetrievalService

        store = QdrantStore()
        if store.point_count() == 0:
            logger.warning("Qdrant collection is empty, falling back to keyword match")
            store.close()
            _init_error = "empty collection"
            return None

        emb_svc = EmbeddingService()
        _retrieval_service = RetrievalService(store=store, embedding_service=emb_svc)
        logger.info("RAG retrieval service initialized (%d docs)", store.point_count())
        return _retrieval_service
    except Exception as exc:
        _init_error = str(exc)
        logger.warning("Qdrant unavailable (%s), falling back to keyword match", exc)
        return None


@register_tool
def retrieve_runbook(query: str) -> str:
    """根据故障关键词检索相关 Runbook，返回排查步骤。

    Uses Qdrant RAG when available, falls back to keyword match otherwise.
    """
    svc = _get_retrieval_service()
    if svc is not None:
        try:
            return svc.retrieve_formatted(query)
        except Exception:
            logger.exception("RAG retrieval failed, falling back to keyword match")

    return _keyword_fallback(query)
