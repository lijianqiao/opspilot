"""Hybrid retrieval service — dense + BM25 → RRF fusion → rerank → top-k.

Pipeline:
  1. Embed query (dense + sparse)
  2. Hybrid search via Qdrant RRF
  3. Return top-k document texts (bge-reranker deferred to Stage 4.1)
"""

from __future__ import annotations

import logging

from opspilot.rag.embedding import EmbeddingService
from opspilot.rag.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)

_DEFAULT_TOP_K = 3
_DENSE_PREFETCH_LIMIT = 50
_FALLBACK_TEXT = (
    "通用故障排查步骤：\n"
    "1. 确认故障影响范围（哪些服务/用户受影响）\n"
    "2. 查看最近部署和变更记录\n"
    "3. 检查服务日志（kubectl logs / Loki query）\n"
    "4. 检查资源使用（kubectl top / Prometheus）\n"
    "5. 检查依赖服务状态\n"
    "6. 如果无法定位，升级到 on-call"
)


class RetrievalService:
    """Orchestrates embedding + hybrid search + formatting."""

    def __init__(
        self,
        store: QdrantStore,
        embedding_service: EmbeddingService,
    ) -> None:
        self._store = store
        self._embedding_service = embedding_service

    def retrieve(self, query: str, top_k: int = _DEFAULT_TOP_K) -> list[str]:
        """Retrieve top-k runbook document texts for a query.

        Returns list of document content strings, best match first.
        """
        if self._store.point_count() == 0:
            return []

        # 1. Embed query
        dense_vec = self._embedding_service.embed_query(query)
        sparse_list = self._embedding_service.embed_sparse([query])
        if not sparse_list:
            return []
        sparse_vec = sparse_list[0]

        # 2. Hybrid search
        results = self._store.search_hybrid(
            query_dense=dense_vec.tolist(),
            query_sparse_indices=sparse_vec["indices"],  # type: ignore[arg-type]
            query_sparse_values=sparse_vec["values"],  # type: ignore[arg-type]
            limit=top_k,
            dense_limit=_DENSE_PREFETCH_LIMIT,
        )

        # 3. Extract content
        docs: list[str] = []
        for point in results:
            if point.payload and "content" in point.payload:
                docs.append(str(point.payload["content"]))
        return docs

    def retrieve_formatted(self, query: str, top_k: int = _DEFAULT_TOP_K) -> str:
        """Retrieve and format as a single runbook text block.

        Signature-compatible with the original retrieve_runbook(query) -> str.
        """
        docs = self.retrieve(query, top_k=top_k)
        if not docs:
            return _FALLBACK_TEXT

        parts: list[str] = []
        for i, doc in enumerate(docs, 1):
            parts.append(f"--- 相关 Runbook {i} ---\n\n{doc[:2000]}")
        return "\n\n".join(parts)
