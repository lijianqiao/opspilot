"""Qdrant collection manager — collection CRUD, upsert, search.

Supports local mode (:memory: or path) for dev/test and remote
mode (Docker Qdrant server) for production.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

COLLECTION_NAME = "runbooks"
_VECTOR_SIZE = 1024  # multilingual-e5-large dimension


class QdrantStore:
    """Manages a Qdrant collection for runbook document retrieval."""

    def __init__(self, url: str = "http://localhost:6333") -> None:
        if url == ":memory:":
            self._client = QdrantClient(":memory:")
        else:
            self._client = QdrantClient(url=url)
        self._closed = False

    @property
    def client(self) -> QdrantClient:
        if self._closed:
            raise RuntimeError("QdrantStore is closed")
        return self._client

    def ensure_collection(self) -> bool:
        """Create collection if it doesn't exist. Idempotent."""
        if self.client.collection_exists(COLLECTION_NAME):
            return True
        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=_VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(),
            },
        )
        logger.info("Collection %s created (dim=%d)", COLLECTION_NAME, _VECTOR_SIZE)
        return True

    def upsert(
        self,
        ids: Sequence[int],
        dense_vectors: Sequence[list[float]],
        payloads: Sequence[dict[str, object]],
        sparse_vectors: Sequence[dict[str, object]] | None = None,
    ) -> None:
        """Upsert a batch of points into the collection."""
        if not ids:
            return

        points = []
        for i, point_id in enumerate(ids):
            vector: dict[str, object] = {"": dense_vectors[i]}
            if sparse_vectors:
                sv = sparse_vectors[i]
                vector["sparse"] = models.SparseVector(
                    indices=sv["indices"],  # type: ignore[arg-type]
                    values=sv["values"],  # type: ignore[arg-type]
                )
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payloads[i],
                )
            )

        self.client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
        logger.info("Upserted %d points into %s", len(points), COLLECTION_NAME)

    def search_dense(
        self,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[models.ScoredPoint]:
        """Dense vector search."""
        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )
        return results.points

    def search_sparse(
        self,
        indices: list[int],
        values: list[float],
        limit: int = 10,
    ) -> list[models.ScoredPoint]:
        """Sparse (BM25) vector search."""
        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=models.SparseVector(indices=indices, values=values),
            using="sparse",
            limit=limit,
            with_payload=True,
        )
        return results.points

    def search_hybrid(
        self,
        query_dense: list[float],
        query_sparse_indices: list[int],
        query_sparse_values: list[float],
        limit: int = 10,
        dense_limit: int = 50,
    ) -> list[models.ScoredPoint]:
        """Hybrid search with RRF fusion of dense and sparse results."""
        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(query=query_dense, using="", limit=dense_limit),
                models.Prefetch(
                    query=models.SparseVector(indices=query_sparse_indices, values=query_sparse_values),
                    using="sparse",
                    limit=dense_limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return results.points

    def point_count(self) -> int:
        """Return the number of points in the collection."""
        if not self.client.collection_exists(COLLECTION_NAME):
            return 0
        info = self.client.get_collection(COLLECTION_NAME)
        return info.points_count or 0

    def close(self) -> None:
        if not self._closed:
            self.client.close()
            self._closed = True
