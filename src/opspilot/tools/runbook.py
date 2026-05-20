"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: runbook.py
@DateTime: 2026-05-20
@Docs: retrieve_runbook — Qdrant RAG with keyword-match fallback.
    retrieve_runbook：Qdrant RAG 检索，不可用时关键字回退。
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from opspilot.rag.retrieval import FALLBACK_RUNBOOK_TEXT
from opspilot.tools.registry import register_tool

if TYPE_CHECKING:
    from opspilot.rag.retrieval import RetrievalService

logger = logging.getLogger(__name__)

_FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures"

# ---------------------------------------------------------------------------
# Stub fallback (original Stage 3 keyword-match) — used when Qdrant is down
# ---------------------------------------------------------------------------

_RUNBOOKS: list[dict[str, object]] = []
_runbooks_lock = threading.Lock()

_retrieval_service: RetrievalService | None = None
_init_error: str | None = None
_retrieval_lock = threading.Lock()


def _load_runbooks() -> list[dict[str, object]]:
    """Load fixture runbooks once (thread-safe, idempotent)."""
    global _RUNBOOKS
    if _RUNBOOKS:
        return _RUNBOOKS
    with _runbooks_lock:
        if _RUNBOOKS:
            return _RUNBOOKS
        loaded: list[dict[str, object]] = []
        for path in sorted(_FIXTURES_DIR.glob("runbook_*.json")):
            loaded.append(json.loads(path.read_text(encoding="utf-8")))
        _RUNBOOKS = loaded
    return _RUNBOOKS


def _keyword_fallback(query: str) -> str:
    """Original keyword-match fallback (Stage 3 stub behavior)."""
    runbooks = _load_runbooks()
    query_lower = query.lower()
    best: dict[str, object] | None = None
    best_score = 0
    for rb in runbooks:
        keywords = rb.get("keywords", [])
        if not isinstance(keywords, list):
            continue
        score = sum(1 for kw in keywords if isinstance(kw, str) and kw.lower() in query_lower)
        if score > best_score:
            best_score = score
            best = rb
    if best and best_score > 0:
        name = str(best.get("name", "Runbook"))
        steps = best.get("steps", [])
        if isinstance(steps, list):
            step_lines = "\n".join(str(s) for s in steps)
            return f"=== {name} ===\n\n{step_lines}"
    return FALLBACK_RUNBOOK_TEXT


def _get_retrieval_service() -> RetrievalService | None:
    """Lazy-init RetrievalService. Returns None if Qdrant is unavailable."""
    global _retrieval_service, _init_error
    if _retrieval_service is not None:
        return _retrieval_service
    if _init_error is not None:
        return None

    with _retrieval_lock:
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
    """Retrieve runbook steps by fault keywords (RAG or keyword fallback).
    根据故障关键词检索相关 Runbook，返回排查步骤。

    Uses Qdrant RAG when available; otherwise keyword match on fixtures.

    Args:
        query: Fault description or alert keywords.
            故障描述或告警关键词。

    Returns:
        Formatted runbook steps or fallback guidance text.
            格式化的 Runbook 步骤或回退引导文本。
    """
    svc = _get_retrieval_service()
    if svc is not None:
        try:
            return svc.retrieve_formatted(query)
        except Exception:
            logger.exception("RAG retrieval failed, falling back to keyword match")

    return _keyword_fallback(query)
