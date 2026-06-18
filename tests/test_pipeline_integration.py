"""End-to-end pipeline wiring tests with a mocked LLM (offline, no API keys).

Exercises the full control flow — orchestrator tool loop -> tool execution ->
verifier -> page extraction -> memory persistence — without calling OpenAI. Also
checks that an image-only PDF builds a pipeline (no text index) instead of failing.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agentic_rag.agents import base as base_mod
from agentic_rag.agents import verifier as verifier_mod
from agentic_rag.agents.pipeline import Pipeline
from agentic_rag.memory.store import MemoryStore
from agentic_rag.preprocessing.chunker import Chunk
from agentic_rag.preprocessing.outline import extract_outline
from agentic_rag.preprocessing.pdf_loader import PdfDocument
from agentic_rag.retrieval.base import RetrievalResult


class _FakeRetriever:
    def __init__(self) -> None:
        self.last_k: int | None = None

    def search(self, query: str, k: int) -> list[RetrievalResult]:
        self.last_k = k
        chunk = Chunk(
            id="p5-c0",
            text="Yapay zeka bankacılıkta dolandırıcılık tespitinde kullanılır.",
            page_number=5,
            chunk_index=0,
        )
        return [RetrievalResult(chunk, 1.0)]


def _tool_call(name: str, arguments: str) -> SimpleNamespace:
    return SimpleNamespace(id="call_1", type="function", function=SimpleNamespace(name=name, arguments=arguments))


def _message(content: str | None, tool_calls: list | None) -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=tool_calls)


@pytest.fixture
def mocked_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the orchestrator's chat() and the verifier's complete_json()."""
    responses = iter(
        [
            _message(None, [_tool_call("search", '{"query": "dolandırıcılık"}')]),
            _message("Yapay zeka dolandırıcılık tespitinde kullanılır [p.5].", None),
        ]
    )

    def fake_chat(**kwargs: object) -> SimpleNamespace:
        return next(responses)

    def fake_complete_json(system: str, user: str, schema: dict, **kwargs: object) -> dict:
        return {
            "supported": True,
            "confidence": 0.9,
            "issues": [],
            "revised_answer": "Yapay zeka dolandırıcılık tespitinde kullanılır [p.5].",
        }

    monkeypatch.setattr(base_mod, "chat", fake_chat)
    monkeypatch.setattr(verifier_mod, "complete_json", fake_complete_json)


def test_pipeline_runs_end_to_end(rich_pdf: Path, tmp_path: Path, mocked_llm: None) -> None:
    retriever = _FakeRetriever()
    with PdfDocument.open(rich_pdf) as doc:
        pipeline = Pipeline(
            doc=doc,
            retriever=retriever,
            outline=extract_outline(doc),
            memory=MemoryStore(tmp_path / "mem.jsonl"),
            retrieval_top_k=2,
        )
        result = pipeline.run("Yapay zeka bankacılıkta nasıl kullanılır?")

    assert "dolandırıcılık" in result.answer
    assert result.pages == [5]  # extracted from the [p.5] citation
    assert result.verdict.supported is True
    assert retriever.last_k == 2
    assert [c.name for c in result.trace] == ["search"]
    assert (tmp_path / "mem.jsonl").exists()
    # recall matches on the stored *question*, so query with overlapping terms
    assert MemoryStore(tmp_path / "mem.jsonl").recall("Yapay zeka bankacılıkta kullanımı")


def test_pipeline_does_not_persist_memory_when_disabled(
    rich_pdf: Path,
    tmp_path: Path,
    mocked_llm: None,
) -> None:
    memory_path = tmp_path / "mem.jsonl"
    with PdfDocument.open(rich_pdf) as doc:
        pipeline = Pipeline(
            doc=doc,
            retriever=_FakeRetriever(),
            outline=extract_outline(doc),
            memory=MemoryStore(memory_path),
        )
        result = pipeline.run("Yapay zeka bankacılıkta nasıl kullanılır?", use_memory=False)

    assert "dolandırıcılık" in result.answer
    assert not memory_path.exists()


def test_from_pdf_handles_image_only_document(image_only_pdf: Path) -> None:
    """An image-only PDF builds a pipeline with no text retriever (no API call)."""
    pipeline = Pipeline.from_pdf(image_only_pdf)
    try:
        assert pipeline._retriever is None
    finally:
        pipeline.close()
