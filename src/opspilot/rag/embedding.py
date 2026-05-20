"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: embedding.py
@DateTime: 2026-05-20
@Docs: FastEmbed wrapper — dense and BM25 sparse embeddings for RAG.
    FastEmbed 封装：为 RAG 生成稠密向量与 BM25 稀疏向量。
"""

from __future__ import annotations

import logging
from threading import Lock

import numpy as np
from fastembed import SparseTextEmbedding, TextEmbedding

logger = logging.getLogger(__name__)

# multilingual-e5-large: 1024-dim dense, multilingual (Chinese + English).
# Used in place of BAAI/bge-m3, which fastembed 0.8.0 does not ship.
_DENSE_MODEL = "intfloat/multilingual-e5-large"
_SPARSE_MODEL = "Qdrant/bm25"

_EMBEDDING_DIM = 1024


class EmbeddingService:
    """Generates dense and sparse embeddings for the RAG pipeline.

    为 RAG 流水线生成稠密与稀疏嵌入向量。

    Uses intfloat/multilingual-e5-large (1024-dim) as dense backbone because
    BAAI/bge-m3 is not in fastembed 0.8.0's TextEmbedding registry.
    稠密模型使用 multilingual-e5-large（1024 维），因 fastembed 0.8.0 未内置 bge-m3。
    """

    def __init__(self) -> None:
        self._dense_model: TextEmbedding | None = None
        self._sparse_model: SparseTextEmbedding | None = None
        self._lock = Lock()

    @property
    def dense_model(self) -> TextEmbedding:
        if self._dense_model is None:
            with self._lock:
                if self._dense_model is None:
                    logger.info("Loading dense model: %s", _DENSE_MODEL)
                    self._dense_model = TextEmbedding(model_name=_DENSE_MODEL)
        return self._dense_model

    @property
    def sparse_model(self) -> SparseTextEmbedding:
        if self._sparse_model is None:
            with self._lock:
                if self._sparse_model is None:
                    logger.info("Loading sparse model: %s", _SPARSE_MODEL)
                    self._sparse_model = SparseTextEmbedding(model_name=_SPARSE_MODEL)
        return self._sparse_model

    def embed_documents(self, documents: list[str]) -> list[np.ndarray]:
        """Generate dense embeddings for a list of documents.

        为文档列表生成稠密嵌入向量。

        Args:
            documents: Document text strings.
                文档文本列表。

        Returns:
            List of float32 embedding arrays.
                float32 嵌入向量数组列表。
        """
        if not documents:
            return []
        # fastembed 0.8.0 mean-pooling returns float64; cast to float32
        # for compact, Qdrant-compatible storage.
        return [emb.astype(np.float32) for emb in self.dense_model.passage_embed(documents)]

    def embed_query(self, query: str) -> np.ndarray:
        """Generate dense embedding for a search query.

        为检索查询生成稠密嵌入向量。

        Args:
            query: Query text.
                查询文本。

        Returns:
            float32 embedding vector.
                float32 嵌入向量。
        """
        embedding = next(iter(self.dense_model.query_embed([query])))
        return embedding.astype(np.float32)

    def embed_sparse(self, texts: list[str]) -> list[dict[str, object]]:
        """Generate BM25 sparse vectors.

        生成 BM25 稀疏向量。

        Args:
            texts: Input text strings.
                输入文本列表。

        Returns:
            Dicts with 'indices' and 'values' keys (Qdrant SparseVector compatible).
                含 indices/values 的字典列表，兼容 Qdrant SparseVector。
        """
        if not texts:
            return []
        results = list(self.sparse_model.embed(texts))
        return [{"indices": r.indices.tolist(), "values": r.values.tolist()} for r in results]

    def token_count(self, texts: list[str]) -> int:
        """Return total token count for the given texts.

        返回给定文本的总 token 数。

        Args:
            texts: Input text strings.
                输入文本列表。

        Returns:
            Total token count.
                总 token 数。
        """
        return self.dense_model.token_count(texts)

    @property
    def dimension(self) -> int:
        """Dense embedding vector dimension.

        稠密嵌入向量维度。
        """
        return _EMBEDDING_DIM
