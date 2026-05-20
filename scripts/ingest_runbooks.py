"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: ingest_runbooks.py
@DateTime: 2026-05-20
@Docs: CLI: ingest runbook Markdown into Qdrant.
    CLI：将 Runbook Markdown 导入 Qdrant。

Usage:
    uv run python scripts/ingest_runbooks.py
    uv run python scripts/ingest_runbooks.py --docs-dir fixtures/runbook_docs
    uv run python scripts/ingest_runbooks.py --url :memory:  # dry-run in memory
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from opspilot.rag.embedding import EmbeddingService
from opspilot.rag.ingestion import ingest_all
from opspilot.rag.qdrant_store import QdrantStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest runbook docs into Qdrant")
    parser.add_argument(
        "--docs-dir",
        default="fixtures/runbook_docs",
        help="Directory containing runbook Markdown files",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:6333",
        help="Qdrant server URL or :memory: for in-memory mode",
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.is_dir():
        raise SystemExit(f"Docs directory not found: {docs_dir}")

    print(f"Ingesting docs from {docs_dir} into Qdrant at {args.url}")
    store = QdrantStore(url=args.url)
    embedding_service = EmbeddingService()
    count = ingest_all(store, embedding_service, docs_dir)
    store.close()
    print(f"Done: {count} chunks ingested")


if __name__ == "__main__":
    main()
