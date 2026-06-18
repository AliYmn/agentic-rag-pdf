"""Shared retrieval types and rank-fusion.

A ``Retriever`` is anything that turns a query into a ranked list of
:class:`RetrievalResult`. Hybrid retrieval fuses several such lists with
Reciprocal Rank Fusion (RRF), which combines rankings without needing the
underlying score scales to be comparable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..preprocessing.chunker import Chunk


@dataclass
class RetrievalResult:
    """A retrieved chunk with a score and (optionally) per-source ranks."""

    chunk: Chunk
    score: float
    ranks: dict[str, int] = field(default_factory=dict)


class Retriever(Protocol):
    """Anything that can rank chunks for a query."""

    def search(self, query: str, k: int) -> list[RetrievalResult]: ...


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[RetrievalResult]], *, rrf_k: int = 60, top_k: int = 8
) -> list[RetrievalResult]:
    """Fuse several ranked lists into one with Reciprocal Rank Fusion.

    For each list, a document at 1-based rank ``r`` contributes ``1/(rrf_k + r)``
    to its fused score. Documents are de-duplicated by ``chunk.id``.

    Args:
        ranked_lists: mapping of source name -> ranked results (best first).
        rrf_k: RRF constant; larger values flatten the contribution of top ranks.
        top_k: how many fused results to return.

    Returns:
        Fused results sorted by descending score, length <= ``top_k``.
    """
    fused: dict[str, RetrievalResult] = {}
    for source, results in ranked_lists.items():
        for rank, result in enumerate(results, start=1):
            contribution = 1.0 / (rrf_k + rank)
            existing = fused.get(result.chunk.id)
            if existing is None:
                fused[result.chunk.id] = RetrievalResult(
                    chunk=result.chunk,
                    score=contribution,
                    ranks={source: rank},
                )
            else:
                existing.score += contribution
                existing.ranks[source] = rank

    ordered = sorted(fused.values(), key=lambda r: r.score, reverse=True)
    return ordered[:top_k]
