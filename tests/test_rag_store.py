"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_rag_store.py
@DateTime: 2026-05-20
@Docs: Tests QdrantStore CRUD and hybrid search.
    测试 QdrantStore 增删查与混合搜索。
"""

import pytest

from opspilot.rag.qdrant_store import COLLECTION_NAME, QdrantStore


@pytest.fixture
def store():
    """In-memory Qdrant store for isolated tests."""
    store = QdrantStore(url=":memory:")
    yield store
    store.close()


@pytest.fixture
def store_with_collection(store):
    store.ensure_collection()
    return store


def test_ensure_collection_creates_collection(store):
    assert store.ensure_collection() is True
    # Second call should be idempotent
    assert store.ensure_collection() is True


def test_collection_exists_after_creation(store_with_collection):
    assert store_with_collection.client.collection_exists(COLLECTION_NAME)


def test_upsert_points_and_search(store_with_collection):
    v1 = [0.1] * 1024
    v2 = [-0.9] * 1024  # opposite direction to v1
    store_with_collection.upsert(
        ids=[1, 2],
        dense_vectors=[v1, v2],
        payloads=[{"text": "CrashLoopBackOff"}, {"text": "OOMKilled"}],
    )
    # Query with v1 → id=1 should be ranked first (same direction)
    results = store_with_collection.search_dense(query_vector=v1, limit=2)
    assert len(results) == 2
    assert results[0].id == 1


def test_upsert_with_sparse_vectors(store_with_collection):
    store_with_collection.upsert(
        ids=[1],
        dense_vectors=[[0.5] * 1024],
        payloads=[{"text": "test"}],
        sparse_vectors=[{"indices": [1, 2, 3], "values": [0.5, 0.3, 0.2]}],
    )
    results = store_with_collection.search_dense(query_vector=[0.5] * 1024, limit=1)
    assert len(results) == 1


def test_search_returns_empty_on_empty_collection(store_with_collection):
    results = store_with_collection.search_dense(query_vector=[0.5] * 1024, limit=5)
    assert results == []


def test_upsert_skips_empty_batch(store_with_collection):
    # Should not raise
    store_with_collection.upsert(ids=[], dense_vectors=[], payloads=[])
