"""Tests for agent tools (offline: no API calls, fake retriever)."""

from __future__ import annotations

from pathlib import Path

from agentic_rag.agents.tools import ToolContext, execute_tool
from agentic_rag.preprocessing.chunker import Chunk
from agentic_rag.preprocessing.outline import extract_outline
from agentic_rag.preprocessing.pdf_loader import PdfDocument
from agentic_rag.retrieval.base import RetrievalResult


class _FakeRetriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks

    def search(self, query: str, k: int) -> list[RetrievalResult]:
        return [RetrievalResult(c, 1.0) for c in self._chunks[:k]]


def _context(doc: PdfDocument, *, retriever: object | None = ...) -> ToolContext:
    chunks = [
        Chunk(id="p2-c0", text="Yapay zeka bankacılıkta kullanılır.", page_number=2, chunk_index=0),
        Chunk(id="p3-c0", text="Dolandırıcılık tespiti bir uygulamadır.", page_number=3, chunk_index=0),
    ]
    if retriever is ...:
        retriever = _FakeRetriever(chunks)
    return ToolContext(doc=doc, retriever=retriever, outline=extract_outline(doc))


def test_search_tags_pages_and_records_evidence(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc:
        ctx = _context(doc)
        result = execute_tool(ctx, "search", {"query": "yapay zeka", "k": 2})
    assert "[p.2]" in result.text and "[p.3]" in result.text
    assert result.image is None
    assert len(ctx.seen_chunks) == 2  # evidence accumulated for the verifier


def test_search_without_text_layer_guides_to_view_page(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc:
        ctx = _context(doc, retriever=None)  # image-only document
        result = execute_tool(ctx, "search", {"query": "anything"})
    assert "view_page" in result.text


def test_view_page_returns_image(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc:
        ctx = _context(doc)
        result = execute_tool(ctx, "view_page", {"page_number": 1})
    assert result.image is not None
    media_type, data = result.image
    assert media_type == "image/png" and len(data) > 100
    assert 1 in ctx.viewed_pages


def test_view_page_out_of_range_is_handled(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc:
        result = execute_tool(_context(doc), "view_page", {"page_number": 999})
    assert result.image is None and "Error" in result.text


def test_get_outline_returns_text(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc:
        result = execute_tool(_context(doc), "get_outline", {})
    assert result.text


def test_unknown_tool_is_handled(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc:
        result = execute_tool(_context(doc), "nope", {})
    assert "Unknown tool" in result.text
