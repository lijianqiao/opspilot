import pytest

from opspilot.rag.ingestion import MarkdownChunk, chunk_markdown


def test_chunk_markdown_splits_by_headings():
    doc = """# Title

Overview text introducing the runbook purpose and scope.

## Section 1

Content one with enough text to exceed min chunk threshold.
This section contains detailed troubleshooting steps that span
multiple lines and provide substantial information.

## Section 2

Content two with enough text to stand alone as a chunk.
This section covers alternative approaches and edge cases
that the operator should be aware of during diagnosis.
"""
    chunks = chunk_markdown(doc, source="test.md")
    assert len(chunks) >= 2
    for ch in chunks:
        assert ch.source == "test.md"
        assert ch.title
        assert ch.content


def test_chunk_markdown_single_section():
    doc = "# Title\n\nJust one section."
    chunks = chunk_markdown(doc, source="single.md")
    assert len(chunks) == 1
    assert chunks[0].title == "Title"


def test_chunk_markdown_handles_code_blocks():
    doc = """# Debug Guide

This guide covers common debugging techniques for Kubernetes workloads.

## Step 1

First gather diagnostic information from the cluster:
```bash
kubectl get pods
kubectl describe pod xyz
```
This gives you the current state and recent events for the affected pod.

## Step 2

Next check the application logs to identify error patterns.
Use Loki queries or kubectl logs to inspect recent output.
Look for stack traces and error messages that indicate root cause.
"""
    chunks = chunk_markdown(doc, source="debug.md")
    assert len(chunks) >= 2
    # Code block should be preserved in content
    content_text = " ".join(ch.content for ch in chunks)
    assert "kubectl get pods" in content_text


def test_chunk_markdown_empty_doc():
    chunks = chunk_markdown("", source="empty.md")
    assert chunks == []


def test_chunk_markdown_whitespace_only():
    chunks = chunk_markdown("\n\n  \n", source="blank.md")
    assert chunks == []
