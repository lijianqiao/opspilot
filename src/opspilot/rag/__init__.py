"""RAG knowledge base — vector search over runbook documents.

Stage 4 replaces the retrieve_runbook keyword-match stub with
real Qdrant-based hybrid retrieval (dense + BM25 → RRF → rerank).
"""
