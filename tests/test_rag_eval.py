"""Test that RAGAS evaluation pipeline validates correctly."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def qa_dataset():
    path = Path("fixtures/rag_eval_qa.json")
    assert path.exists(), f"QA dataset not found: {path}"
    data = json.loads(path.read_text("utf-8"))
    assert len(data) == 30
    return data


def test_qa_dataset_has_all_required_fields(qa_dataset):
    for item in qa_dataset:
        assert "question" in item
        assert "reference" in item
        assert isinstance(item["question"], str) and len(item["question"]) > 0
        assert isinstance(item["reference"], str) and len(item["reference"]) > 0


def test_qa_dataset_questions_are_unique(qa_dataset):
    questions = [item["question"] for item in qa_dataset]
    assert len(questions) == len(set(questions))


@pytest.mark.anyio
async def test_rag_eval_pipeline_runs():
    """Verify the RAG eval pipeline structure with in-memory Qdrant."""
    from ragas import EvaluationDataset, SingleTurnSample

    from opspilot.rag.embedding import EmbeddingService
    from opspilot.rag.qdrant_store import QdrantStore
    from opspilot.rag.retrieval import RetrievalService

    store = QdrantStore(url=":memory:")
    store.ensure_collection()
    emb = EmbeddingService()
    docs = [
        "# OOMKilled 排查\n\n## 步骤\n\n检查 memory limit 和 kubectl logs --previous。"
        "使用 kubectl top 查看实际内存使用，分析是否存在内存泄漏。",
        "# CrashLoopBackOff 排查\n\n## 步骤\n\n查看 pod 事件和上次崩溃日志。"
        "使用 kubectl describe pod 检查退出码，确认启动命令是否正确。",
    ]
    dense = emb.embed_documents(docs)
    sparse = emb.embed_sparse(docs)
    store.upsert(
        ids=[0, 1],
        dense_vectors=[d.tolist() for d in dense],
        payloads=[{"content": d} for d in docs],
        sparse_vectors=sparse,
    )
    svc = RetrievalService(store=store, embedding_service=emb)

    samples = [
        SingleTurnSample(
            user_input="OOMKilled 怎么排查",
            retrieved_contexts=svc.retrieve("OOMKilled 怎么排查"),
            reference="检查 memory limit 和日志",
        ),
        SingleTurnSample(
            user_input="pod 反复重启",
            retrieved_contexts=svc.retrieve("pod 反复重启"),
            reference="查看 pod 事件和崩溃日志",
        ),
    ]
    dataset = EvaluationDataset(samples=samples)
    assert len(dataset) == 2
    store.close()
