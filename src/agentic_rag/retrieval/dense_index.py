"""Dense semantic retrieval with OpenAI embeddings + ChromaDB.

Captures meaning, not just surface words — strong for paraphrased questions
whose wording differs from the source text.

The collection is built in-memory per session: embeddings are specific to a
document, and an in-memory index sidesteps stale-cache bugs across documents.
"""

from __future__ import annotations

import chromadb

from ..config import get_settings
from ..llm import get_client
from ..preprocessing.chunker import Chunk
from .base import RetrievalResult

# OpenAI's embeddings endpoint accepts large batches; keep it modest for safety.
_EMBED_BATCH = 256


class OpenAIEmbeddingIndex:
    """In-memory dense index: OpenAI embeddings stored in a Chroma collection."""

    def __init__(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("cannot build a dense index over zero chunks")
        settings = get_settings()
        self._chunks_by_id = {c.id: c for c in chunks}
        self._client = get_client()
        self._model = settings.embedding_model

        embeddings = self._embed([c.text for c in chunks])

        client = chromadb.EphemeralClient()
        self._collection = client.create_collection(name="document", metadata={"hnsw:space": "cosine"})
        self._collection.add(
            ids=[c.id for c in chunks],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[{"page": c.page_number} for c in chunks],
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH):
            batch = texts[start : start + _EMBED_BATCH]
            response = self._client.embeddings.create(model=self._model, input=batch)
            vectors.extend(item.embedding for item in response.data)
        return vectors

    def search(self, query: str, k: int) -> list[RetrievalResult]:
        """Return up to ``k`` chunks ranked by cosine similarity (best first)."""
        k = min(k, len(self._chunks_by_id))
        query_vec = self._embed([query])[0]
        response = self._collection.query(query_embeddings=[query_vec], n_results=k)
        ids = response["ids"][0]
        distances = response["distances"][0]
        results: list[RetrievalResult] = []
        for chunk_id, distance in zip(ids, distances):
            # cosine distance -> similarity score (only ordering matters for RRF)
            results.append(RetrievalResult(chunk=self._chunks_by_id[chunk_id], score=1.0 - float(distance)))
        return results
