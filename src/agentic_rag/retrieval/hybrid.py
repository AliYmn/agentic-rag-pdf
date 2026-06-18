"""Hybrid retrieval: fuse BM25 (lexical) and OpenAI (dense) with RRF."""

from __future__ import annotations

import logging

from ..config import get_settings
from ..preprocessing.chunker import Chunk
from .base import RetrievalResult, Retriever, reciprocal_rank_fusion
from .bm25_index import BM25Index
from .dense_index import OpenAIEmbeddingIndex

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Combine several named retrievers into one RRF-fused ranking.

    Each component retriever is queried for a slightly larger candidate pool
    than the final ``top_k`` so fusion has room to promote items that rank
    moderately well in both lists over those that spike in only one.
    """

    def __init__(self, retrievers: dict[str, Retriever], *, rrf_k: int | None = None) -> None:
        if not retrievers:
            raise ValueError("HybridRetriever needs at least one component retriever")
        self._retrievers = retrievers
        settings = get_settings()
        self._rrf_k = rrf_k if rrf_k is not None else settings.rrf_k

    @property
    def components(self) -> list[str]:
        """Names of the active component retrievers (e.g. ``["bm25", "dense"]``)."""
        return list(self._retrievers)

    @classmethod
    def from_chunks(cls, chunks: list[Chunk]) -> HybridRetriever:
        """Build BM25 + OpenAI dense indexes; degrade to BM25-only if needed.

        Dense retrieval requires the API key to have embedding-model access. If
        building the embedding index fails (e.g. the key/project can't reach the
        embedding model), we log a warning and fall back to lexical-only
        retrieval rather than failing the whole run.
        """
        retrievers: dict[str, Retriever] = {"bm25": BM25Index(chunks)}
        try:
            retrievers["dense"] = OpenAIEmbeddingIndex(chunks)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully on any embed failure
            logger.warning("Dense retrieval unavailable (%s); falling back to BM25-only.", exc)
        return cls(retrievers)

    def search(self, query: str, k: int = 8) -> list[RetrievalResult]:
        """Query every component and return the RRF-fused top ``k`` results."""
        candidate_k = max(k, k * 2)
        ranked_lists = {name: retriever.search(query, candidate_k) for name, retriever in self._retrievers.items()}
        return reciprocal_rank_fusion(ranked_lists, rrf_k=self._rrf_k, top_k=k)
