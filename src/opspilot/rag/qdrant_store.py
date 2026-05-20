"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: qdrant_store.py
@DateTime: 2026-05-20
@Docs: Qdrant collection manager — CRUD, upsert, dense/sparse/hybrid search.
    Qdrant 集合管理：建库、写入与稠密/稀疏/混合检索。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

COLLECTION_NAME = "runbooks"
_VECTOR_SIZE = 1024  # multilingual-e5-large dimension


class QdrantStore:
    """Manages a Qdrant collection for runbook document retrieval.

    管理用于 Runbook 文档检索的 Qdrant 集合。

    Supports :memory: for dev/test and remote URL for production.
    支持 :memory: 本地模式与远程 URL 生产模式。
    """

    def __init__(self, url: str = "http://localhost:6333") -> None:
        """Initialize Qdrant client for the given URL.

        按 URL 初始化 Qdrant 客户端。

        Args:
            url: Qdrant server URL or ':memory:' for in-memory mode.
                Qdrant 服务地址，或 ':memory:' 内存模式。
        """
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
        """Create collection if it doesn't exist (idempotent).

        若集合不存在则创建（幂等）。

        Returns:
            True if collection exists or was created.
                集合已存在或已创建时返回 True。
        """
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
        """Upsert a batch of points into the collection.

        批量 upsert 点到集合中。

        Args:
            ids: Point IDs.
                点 ID 列表。
            dense_vectors: Dense embedding vectors.
                稠密嵌入向量列表。
            payloads: Per-point metadata payloads.
                每点元数据载荷。
            sparse_vectors: Optional BM25 sparse vectors.
                可选 BM25 稀疏向量列表。
        """
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
                    vector=vector,  # type: ignore[arg-type]
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
        """Dense vector search.

        稠密向量检索。

        Args:
            query_vector: Query dense embedding.
                查询稠密向量。
            limit: Maximum results to return.
                返回结果数量上限。

        Returns:
            Scored points with payloads.
                带载荷的打分点列表。
        """
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
        """Sparse (BM25) vector search.

        稀疏（BM25）向量检索。

        Args:
            indices: Sparse vector dimension indices.
                稀疏向量维度索引。
            values: Sparse vector values.
                稀疏向量值。
            limit: Maximum results to return.
                返回结果数量上限。

        Returns:
            Scored points with payloads.
                带载荷的打分点列表。
        """
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
        """Hybrid search with RRF fusion of dense and sparse results.

        稠密与稀疏结果经 RRF 融合的混合检索。

        Args:
            query_dense: Query dense embedding.
                查询稠密向量。
            query_sparse_indices: Query sparse indices.
                查询稀疏索引。
            query_sparse_values: Query sparse values.
                查询稀疏值。
            limit: Final fused result limit.
                融合后返回数量上限。
            dense_limit: Prefetch limit per channel.
                每路预取数量上限。

        Returns:
            Fused scored points with payloads.
                融合后的带载荷打分点列表。
        """
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
        """Return the number of points in the collection.

        返回集合中的点数量。
        """
        if not self.client.collection_exists(COLLECTION_NAME):
            return 0
        info = self.client.get_collection(COLLECTION_NAME)
        return info.points_count or 0

    def close(self) -> None:
        """Close the underlying Qdrant client.

        关闭底层 Qdrant 客户端。
        """
        if not self._closed:
            self.client.close()
            self._closed = True
