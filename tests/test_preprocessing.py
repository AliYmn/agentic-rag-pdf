"""Tests for PDF loading, chunking, and outline extraction (offline; no API keys)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_rag.preprocessing.chunker import chunk_document
from agentic_rag.preprocessing.outline import extract_outline, outline_to_text
from agentic_rag.preprocessing.pdf_loader import PdfDocument


def test_load_pdf_extracts_pages_and_text(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc:
        assert doc.page_count == 18
        assert "Bankacılıkta Yapay Zeka" in doc.full_text
        assert "Sultan" in doc.full_text


def test_load_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        PdfDocument.open("does-not-exist.pdf")


def test_render_page_returns_png_base64(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc:
        media_type, data = doc.render_page_base64(1)
        assert media_type == "image/png"
        assert len(data) > 100  # non-trivial image payload
        with pytest.raises(IndexError):
            doc.render_page_base64(999)


def test_image_only_pdf_has_no_text(image_only_pdf: Path) -> None:
    """An image-only page yields no chunks — the pipeline must tolerate this."""
    with PdfDocument.open(image_only_pdf) as doc:
        assert doc.page_count == 1
        assert chunk_document(doc) == []
        # ...but it can still be rendered as an image for the agent to view.
        media_type, _ = doc.render_page_base64(1)
        assert media_type == "image/png"


def test_chunking_preserves_page_refs_and_budget(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc:
        chunks = chunk_document(doc, max_chars=600, overlap=100)
    assert chunks
    assert all(1 <= c.page_number <= doc.page_count for c in chunks)
    assert all(len(c.text) <= 600 for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)  # unique ids
    assert all(c.id.startswith(f"p{c.page_number}-") for c in chunks)


def test_chunk_overlap_validation(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc, pytest.raises(ValueError):
        chunk_document(doc, max_chars=100, overlap=100)


def test_outline_is_jsonable_list(rich_pdf: Path) -> None:
    """These PDFs have no embedded TOC, so the font heuristic is exercised."""
    with PdfDocument.open(rich_pdf) as doc:
        outline = extract_outline(doc)
    assert isinstance(outline, list)
    for node in outline:
        d = node.to_dict()
        assert {"title", "level", "page", "children"} <= d.keys()
    assert isinstance(outline_to_text(outline), str)


def test_outline_nests_embedded_toc() -> None:
    """Unit-test the TOC -> tree nesting logic deterministically (no file)."""
    doc = PdfDocument(
        path=Path("synthetic.pdf"),
        pages=[],
        metadata={},
        toc=[(1, "A", 1), (2, "A.1", 1), (2, "A.2", 2), (1, "B", 3)],
    )
    outline = extract_outline(doc)
    assert [n.title for n in outline] == ["A", "B"]
    assert [c.title for c in outline[0].children] == ["A.1", "A.2"]
    assert "p.3" in outline_to_text(outline)
