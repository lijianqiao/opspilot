"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_rag_embedding.py
@DateTime: 2026-05-20
@Docs: Tests EmbeddingService dense/sparse vectors.
    测试 EmbeddingService 稠密/稀疏向量。
"""

import numpy as np

from opspilot.rag.embedding import EmbeddingService


def test_embed_documents_returns_2d_numpy_arrays():
    """
    Verify embed documents returns 2d numpy arrays.

    验证：embed documents returns 2d numpy arrays。
    """
    svc = EmbeddingService()
    docs = ["CrashLoopBackOff 故障排查", "OOMKilled 内存溢出"]
    embeddings = svc.embed_documents(docs)
    assert len(embeddings) == 2
    assert isinstance(embeddings[0], np.ndarray)
    assert embeddings[0].ndim == 1
    assert embeddings[0].dtype == np.float32


def test_embed_query_returns_1d_vector():
    """
    Verify embed query returns 1d vector.

    验证：embed query returns 1d vector。
    """
    svc = EmbeddingService()
    query = "pod 反复重启怎么排查"
    embedding = svc.embed_query(query)
    assert isinstance(embedding, np.ndarray)
    assert embedding.ndim == 1


def test_embedding_dimension_matches_bge_m3():
    """
    Verify embedding dimension matches bge m3.

    验证：embedding dimension matches bge m3。
    """
    svc = EmbeddingService()
    embeddings = svc.embed_documents(["test document"])
    assert embeddings[0].shape[0] == 1024  # bge-m3 dimension


def test_embed_empty_list_returns_empty():
    """
    Verify embed empty list returns empty.

    验证：embed empty list returns empty。
    """
    svc = EmbeddingService()
    result = svc.embed_documents([])
    assert result == []


def test_token_count_returns_positive_integer():
    """
    Verify token count returns positive integer.

    验证：token count returns positive integer。
    """
    svc = EmbeddingService()
    count = svc.token_count(["hello world", "foo bar"])
    assert isinstance(count, int)
    assert count > 0
