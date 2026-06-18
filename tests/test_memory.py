"""Tests for the file-based cross-task memory store (offline)."""

from __future__ import annotations

from pathlib import Path

from agentic_rag.memory.store import MemoryStore


def test_add_and_recall_similar_question(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "mem.jsonl")
    store.add(
        "What accuracy did the agentic system reach?",
        "87 percent.",
        pages=[3],
        confidence=0.9,
        document="report.pdf",
    )
    store.add(
        "Who wrote the report?",
        "The Agentic Platform Team.",
        pages=[1],
        confidence=0.8,
        document="report.pdf",
    )

    hits = store.recall("What accuracy did the system achieve?", k=1)
    assert len(hits) == 1
    assert "87" in hits[0].answer


def test_recall_filters_unrelated(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "mem.jsonl")
    store.add("What is the capital of France?", "Paris.", pages=[], confidence=1.0, document="x")
    hits = store.recall("Describe the retrieval fusion algorithm", min_overlap=0.2)
    assert hits == []


def test_recall_on_empty_store(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "missing.jsonl")
    assert store.recall("anything") == []


def test_format_hint_includes_pages(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "mem.jsonl")
    store.add("Q1", "A1", pages=[2, 5], confidence=0.7, document="d")
    hint = MemoryStore.format_hint(store.recall("Q1"))
    assert "p.2" in hint and "p.5" in hint
