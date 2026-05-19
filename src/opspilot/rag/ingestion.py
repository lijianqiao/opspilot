"""Ingestion pipeline: parse Markdown → chunk → embed → upsert into Qdrant.

Ingestion flow:
  1. Walk fixtures/runbook_docs/ for *.md files
  2. Chunk each doc by headings (## / ### level)
  3. Generate dense + sparse embeddings via EmbeddingService
  4. Upsert into QdrantStore
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from opspilot.rag.embedding import EmbeddingService
from opspilot.rag.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)

# Split on ## or ### headings
_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

_MIN_CHUNK_CHARS = 50
_BATCH_SIZE = 32


@dataclass(frozen=True)
class MarkdownChunk:
    """A chunk of a Markdown document, split by section headings."""

    source: str  # filename
    title: str  # document title (first # heading)
    section: str  # section heading text
    content: str  # full text of this chunk (heading + body)


def chunk_markdown(text: str, source: str = "") -> list[MarkdownChunk]:
    """Split a Markdown document into chunks by ## / ### headings.

    Each chunk = heading line + body text until the next heading.
    Chunks below _MIN_CHUNK_CHARS are merged with the previous chunk.
    """
    if not text.strip():
        return []

    # Extract document title from first # heading
    title_match = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
    doc_title = title_match.group(1).strip() if title_match else source

    # Find all heading positions
    positions: list[tuple[int, str]] = []
    for m in _HEADING_RE.finditer(text):
        positions.append((m.start(), m.group(0)))

    if not positions:
        # No sub-headings — whole document is one chunk
        return [MarkdownChunk(source=source, title=doc_title, section="", content=text.strip())]

    chunks: list[MarkdownChunk] = []
    for i, (pos, heading_line) in enumerate(positions):
        next_pos = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        content = text[pos:next_pos].strip()

        section_text = _HEADING_RE.match(heading_line)
        section = section_text.group(2).strip() if section_text else ""

        # Skip chunks that are too small — merge with previous
        if i > 0 and len(content) < _MIN_CHUNK_CHARS and chunks:
            chunks[-1] = MarkdownChunk(
                source=source,
                title=doc_title,
                section=chunks[-1].section,
                content=chunks[-1].content + "\n\n" + content,
            )
            continue

        if len(content) >= _MIN_CHUNK_CHARS or i == 0:
            chunks.append(
                MarkdownChunk(
                    source=source,
                    title=doc_title,
                    section=section,
                    content=content,
                )
            )

    return chunks


def _load_documents(docs_dir: Path) -> list[tuple[str, str]]:
    """Load all Markdown files from docs_dir. Returns [(filename, content), ...]."""
    docs: list[tuple[str, str]] = []
    for path in sorted(docs_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        docs.append((path.name, content))
    return docs


def ingest_all(
    store: QdrantStore,
    embedding_service: EmbeddingService,
    docs_dir: Path,
) -> int:
    """Ingest all Markdown docs from docs_dir into Qdrant.

    Returns total number of chunks ingested.
    """
    store.ensure_collection()
    docs = _load_documents(docs_dir)
    logger.info("Loaded %d documents from %s", len(docs), docs_dir)

    # Full re-ingestion: drop and recreate collection
    if store.point_count() > 0:
        store.client.delete_collection("runbooks")
        store.ensure_collection()

    next_id = 0
    all_dense: list[list[float]] = []
    all_sparse: list[dict[str, object]] = []
    all_payloads: list[dict[str, object]] = []
    all_ids: list[int] = []

    for filename, content in docs:
        chunks = chunk_markdown(content, source=filename)
        if not chunks:
            continue

        chunk_texts = [c.content for c in chunks]
        dense_embeddings = embedding_service.embed_documents(chunk_texts)
        sparse_embeddings = embedding_service.embed_sparse(chunk_texts)

        for i, chunk in enumerate(chunks):
            all_dense.append(dense_embeddings[i].tolist())
            all_sparse.append(sparse_embeddings[i])
            all_payloads.append(
                {
                    "source": chunk.source,
                    "title": chunk.title,
                    "section": chunk.section,
                    "content": chunk.content,
                }
            )
            all_ids.append(next_id)
            next_id += 1

        # Upsert in batches
        if len(all_ids) >= _BATCH_SIZE:
            store.upsert(
                ids=all_ids,
                dense_vectors=all_dense,
                payloads=all_payloads,
                sparse_vectors=all_sparse,
            )
            all_dense.clear()
            all_sparse.clear()
            all_payloads.clear()
            all_ids.clear()

    # Final batch
    if all_ids:
        store.upsert(
            ids=all_ids,
            dense_vectors=all_dense,
            payloads=all_payloads,
            sparse_vectors=all_sparse,
        )

    total = store.point_count()
    logger.info("Ingestion complete: %d chunks in collection", total)
    return total
