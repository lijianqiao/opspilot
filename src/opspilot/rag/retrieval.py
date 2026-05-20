"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: retrieval.py
@DateTime: 2026-05-20
@Docs: Hybrid retrieval — embed query, RRF search, return top-k runbooks.
    混合检索服务：查询嵌入、RRF 检索、返回 top-k Runbook 文本。
"""

from __future__ import annotations

import logging

from opspilot.rag.embedding import EmbeddingService
from opspilot.rag.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)

_DEFAULT_TOP_K = 3
_DENSE_PREFETCH_LIMIT = 50

# 单一来源：RAG 无命中与 runbook 关键词兜底共用同一通用排查文案
FALLBACK_RUNBOOK_TEXT = (
    "通用故障排查步骤：\n"
    "1. 确认故障影响范围（哪些服务/用户受影响）\n"
    "2. 查看最近部署和变更记录\n"
    "3. 检查服务日志（kubectl logs / Loki query）\n"
    "4. 检查资源使用（kubectl top / Prometheus）\n"
    "5. 检查依赖服务状态\n"
    "6. 如果无法定位，升级到 on-call"
)


class RetrievalService:
    """Orchestrates embedding + hybrid search + formatting.

    编排嵌入、混合检索与结果格式化。
    """

    def __init__(
        self,
        store: QdrantStore,
        embedding_service: EmbeddingService,
    ) -> None:
        """Initialize retrieval service.

        初始化检索服务。

        Args:
            store: Qdrant store for hybrid search.
                用于混合检索的 Qdrant 存储。
            embedding_service: Service for query/document embeddings.
                查询/文档嵌入服务。
        """
        self._store = store
        self._embedding_service = embedding_service

    def retrieve(self, query: str, top_k: int = _DEFAULT_TOP_K) -> list[str]:
        """Retrieve top-k runbook document texts for a query.

        为查询检索 top-k 条 Runbook 文档正文。

        Args:
            query: Natural-language search query.
                自然语言检索查询。
            top_k: Number of documents to return.
                返回文档数量。

        Returns:
            Document content strings, best match first; empty if collection empty.
                文档正文列表（最佳匹配在前）；集合为空时返回空列表。
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

        检索并格式化为单块 Runbook 文本。

        Compatible with legacy retrieve_runbook(query) -> str signature.
        与旧版 retrieve_runbook(query) -> str 签名兼容。

        Args:
            query: Natural-language search query.
                自然语言检索查询。
            top_k: Number of documents to include.
                纳入的文档数量。

        Returns:
            Formatted runbook text or FALLBACK_RUNBOOK_TEXT if no hits.
                格式化 Runbook 文本；无命中时返回通用兜底文案。
        """
        docs = self.retrieve(query, top_k=top_k)
        if not docs:
            return FALLBACK_RUNBOOK_TEXT

        parts: list[str] = []
        for i, doc in enumerate(docs, 1):
            parts.append(f"--- 相关 Runbook {i} ---\n\n{doc[:2000]}")
        return "\n\n".join(parts)
