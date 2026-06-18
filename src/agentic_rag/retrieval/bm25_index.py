"""Lexical retrieval with BM25 (via the ``bm25s`` library).

Captures exact keyword overlap — strong for names, numbers, and rare terms that
dense embeddings tend to smear together.
"""

from __future__ import annotations

import bm25s

from ..preprocessing.chunker import Chunk
from .base import RetrievalResult


class BM25Index:
    """In-memory BM25 index over a fixed set of chunks."""

    def __init__(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("cannot build a BM25 index over zero chunks")
        self._chunks = chunks
        corpus = [c.text for c in chunks]
        # Keep tokenisation language-agnostic: the assignment samples/questions are
        # Turkish, and hard-coding English stopword removal weakens multilingual use.
        corpus_tokens = bm25s.tokenize(corpus, stopwords=[], show_progress=False)
        self._retriever = bm25s.BM25()
        self._retriever.index(corpus_tokens, show_progress=False)

    def search(self, query: str, k: int) -> list[RetrievalResult]:
        """Return up to ``k`` chunks ranked by BM25 score (best first)."""
        k = min(k, len(self._chunks))
        query_tokens = bm25s.tokenize(query, stopwords=[], show_progress=False)
        indices, scores = self._retriever.retrieve(query_tokens, k=k, show_progress=False)
        results: list[RetrievalResult] = []
        for idx, score in zip(indices[0], scores[0]):
            results.append(RetrievalResult(chunk=self._chunks[int(idx)], score=float(score)))
        return results
