"""Embedding service — wraps FastEmbed for multilingual embeddings.

Produces dense vectors (1024-dim) and BM25 sparse vectors for
hybrid retrieval. Singleton pattern via module-level _INSTANCE.

Note: the planned BAAI/bge-m3 is not in fastembed 0.8.0's TextEmbedding
registry, so the closest supported multilingual 1024-dim model
(intfloat/multilingual-e5-large) is used as the dense backbone.
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
    """Generates dense and sparse embeddings for RAG pipeline."""

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
        """Generate dense embeddings for a list of documents."""
        if not documents:
            return []
        # fastembed 0.8.0 mean-pooling returns float64; cast to float32
        # for compact, Qdrant-compatible storage.
        return [emb.astype(np.float32) for emb in self.dense_model.passage_embed(documents)]

    def embed_query(self, query: str) -> np.ndarray:
        """Generate dense embedding for a search query."""
        embedding = next(iter(self.dense_model.query_embed([query])))
        return embedding.astype(np.float32)

    def embed_sparse(self, texts: list[str]) -> list[dict[str, object]]:
        """Generate BM25 sparse vectors.

        Returns list of dicts with 'indices' and 'values' keys,
        compatible with Qdrant's SparseVector.
        """
        if not texts:
            return []
        results = list(self.sparse_model.embed(texts))
        return [{"indices": r.indices.tolist(), "values": r.values.tolist()} for r in results]

    def token_count(self, texts: list[str]) -> int:
        """Return total token count for the given texts."""
        return self.dense_model.token_count(texts)

    @property
    def dimension(self) -> int:
        return _EMBEDDING_DIM
