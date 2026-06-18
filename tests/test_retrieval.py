"""Tests for lexical retrieval and RRF fusion (offline; dense needs a key)."""

from __future__ import annotations

from pathlib import Path

from agentic_rag.preprocessing.chunker import Chunk, chunk_document
from agentic_rag.preprocessing.pdf_loader import PdfDocument
from agentic_rag.retrieval.base import RetrievalResult, reciprocal_rank_fusion
from agentic_rag.retrieval.bm25_index import BM25Index
from agentic_rag.retrieval.hybrid import HybridRetriever


def _chunk(cid: str, text: str = "x", page: int = 1) -> Chunk:
    return Chunk(id=cid, text=text, page_number=page, chunk_index=0)


def test_bm25_retrieves_keyword_match(rich_pdf: Path) -> None:
    with PdfDocument.open(rich_pdf) as doc:
        chunks = chunk_document(doc, max_chars=600, overlap=100)
    results = BM25Index(chunks).search("Ostim Teknik Üniversitesi", k=5)
    assert results
    # The author's affiliation should surface somewhere in the top results.
    assert any("Ostim" in r.chunk.text for r in results)


def test_rrf_rewards_agreement_across_lists() -> None:
    a, b, c = _chunk("a"), _chunk("b"), _chunk("c")
    lists = {
        "bm25": [RetrievalResult(a, 9.0), RetrievalResult(b, 8.0)],
        "dense": [RetrievalResult(b, 0.9), RetrievalResult(c, 0.8)],
    }
    fused = reciprocal_rank_fusion(lists, rrf_k=60, top_k=3)
    ids = [r.chunk.id for r in fused]
    # b appears in both lists -> should outrank a and c (each in one list)
    assert ids[0] == "b"
    assert set(ids) == {"a", "b", "c"}
    assert fused[0].ranks == {"bm25": 2, "dense": 1}


def test_rrf_respects_top_k() -> None:
    lists = {"only": [RetrievalResult(_chunk(str(i)), float(i)) for i in range(10)]}
    fused = reciprocal_rank_fusion(lists, top_k=4)
    assert len(fused) == 4


def test_hybrid_fuses_component_retrievers() -> None:
    a, b, c = _chunk("a"), _chunk("b"), _chunk("c")

    class Fake:
        def __init__(self, results: list[RetrievalResult]) -> None:
            self._results = results

        def search(self, query: str, k: int) -> list[RetrievalResult]:
            return self._results[:k]

    hybrid = HybridRetriever(
        {
            "bm25": Fake([RetrievalResult(a, 1.0), RetrievalResult(b, 0.5)]),
            "dense": Fake([RetrievalResult(b, 1.0), RetrievalResult(c, 0.5)]),
        },
        rrf_k=60,
    )
    fused = hybrid.search("q", k=3)
    assert fused[0].chunk.id == "b"  # the only id in both lists
