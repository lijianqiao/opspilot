"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_rag_retrieval.py
@DateTime: 2026-05-20
@Docs: Tests RetrievalService hybrid search formatting.
    测试 RetrievalService 混合检索与格式化。
"""

from opspilot.rag.embedding import EmbeddingService
from opspilot.rag.qdrant_store import QdrantStore
from opspilot.rag.retrieval import RetrievalService


def _build_service() -> RetrievalService:
    store = QdrantStore(url=":memory:")
    store.ensure_collection()
    emb_svc = EmbeddingService()
    return RetrievalService(store=store, embedding_service=emb_svc)


def _seed(store: QdrantStore, emb_svc: EmbeddingService) -> None:
    """Ingest a few test documents via the embedding service."""

    docs = [
        "# OOMKilled\n\n## 排查\n\n检查内存限制和日志。查看 memory limit 配置和 kubectl top，"
        "分析是否存在内存泄漏。常见原因包括 JVM heap 不足和并发请求突增。",
        "# CrashLoopBackOff\n\n## 排查\n\n查看 pod 事件和上次崩溃日志。"
        "使用 kubectl describe pod 检查退出码，确认启动命令和配置是否正确。",
        "# CPU 高负载\n\n## 排查\n\n使用 Prometheus 查 CPU 使用率。"
        "排查最近部署、检查是否存在死循环，使用 profile 工具定位热点函数。",
    ]
    dense = emb_svc.embed_documents(docs)
    sparse = emb_svc.embed_sparse(docs)
    store.upsert(
        ids=list(range(len(docs))),
        dense_vectors=[d.tolist() for d in dense],
        payloads=[{"content": c} for c in docs],
        sparse_vectors=sparse,
    )


def test_retrieve_returns_results():
    svc = _build_service()
    _seed(svc._store, svc._embedding_service)
    results = svc.retrieve("OOMKilled 怎么排查", top_k=2)
    assert len(results) == 2
    assert any("OOMKilled" in r for r in results)


def test_retrieve_handles_empty_collection():
    svc = _build_service()
    results = svc.retrieve("anything", top_k=3)
    assert results == []


def test_retrieve_formats_runbook_text():
    svc = _build_service()
    _seed(svc._store, svc._embedding_service)
    text = svc.retrieve_formatted("CPU 高负载")
    assert "CPU" in text


def test_retrieve_hybrid_respects_top_k():
    svc = _build_service()
    _seed(svc._store, svc._embedding_service)
    results = svc.retrieve("排查", top_k=1)
    assert len(results) == 1


def test_retrieve_formatted_empty_collection():
    svc = _build_service()
    text = svc.retrieve_formatted("anything")
    assert text  # returns fallback text, not empty
    assert "通用" in text or "故障" in text
