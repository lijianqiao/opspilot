"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-05-20
@Docs: RAG knowledge base — Qdrant hybrid retrieval over runbooks.
    RAG 知识库：基于 Qdrant 混合检索的 Runbook 文档检索。
"""

"""RAG knowledge base — vector search over runbook documents.

RAG 知识库：对 Runbook 文档进行向量检索。

Stage 4 replaces the retrieve_runbook keyword-match stub with
real Qdrant-based hybrid retrieval (dense + BM25 → RRF → rerank).

阶段 4 以 Qdrant 混合检索（稠密 + BM25 → RRF）替代关键词匹配桩实现。
"""
