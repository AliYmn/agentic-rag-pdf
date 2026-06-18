"""End-to-end question-answering pipeline.

Wires the pieces together for one document:

    recall memory -> orchestrator (draft + evidence) -> verifier -> persist

This is the object the CLI and the evaluation harness drive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

from ..config import Settings, get_settings
from ..memory.store import MemoryStore
from ..preprocessing.chunker import chunk_document
from ..preprocessing.outline import OutlineNode, extract_outline
from ..preprocessing.pdf_loader import PdfDocument
from ..retrieval.hybrid import HybridRetriever
from .base import ToolCall
from .orchestrator import Orchestrator
from .verifier import Verdict, verify

_PAGE_CITATION = re.compile(r"\[p\.(\d+)\]")


@dataclass
class AnswerResult:
    """Everything the pipeline produced for one question."""

    question: str
    answer: str
    verdict: Verdict
    draft_answer: str
    pages: list[int]
    trace: list[ToolCall] = field(default_factory=list)
    used_memory: bool = False


class Pipeline:
    """A reusable QA pipeline bound to a single open PDF document."""

    def __init__(
        self,
        doc: PdfDocument,
        retriever: HybridRetriever | None,
        outline: list[OutlineNode],
        memory: MemoryStore,
    ) -> None:
        self._doc = doc
        self._retriever = retriever
        self._outline = outline
        self._memory = memory

    @classmethod
    def from_pdf(cls, pdf_path: str | Path, *, settings: Settings | None = None) -> Pipeline:
        """Build a pipeline: load + chunk + index + outline + memory."""
        settings = settings or get_settings()
        doc = PdfDocument.open(pdf_path)
        chunks = chunk_document(doc)
        # Image-only PDFs (no text layer) yield no chunks: skip the text index
        # and let the agent rely on view_page + get_outline instead of failing.
        retriever = HybridRetriever.from_chunks(chunks) if chunks else None
        outline = extract_outline(doc)
        memory = MemoryStore(settings.memory_path)
        return cls(doc, retriever, outline, memory)

    def run(self, question: str, *, use_memory: bool = True) -> AnswerResult:
        """Answer ``question``: draft with tools, verify, and persist to memory."""
        recalled = self._memory.recall(question) if use_memory else []
        hint = MemoryStore.format_hint(recalled) if recalled else ""

        orchestrator = Orchestrator(self._doc, self._retriever, self._outline)
        draft = orchestrator.answer(question, memory_hint=hint)

        evidence = orchestrator.context.evidence_text()
        # Show the verifier the same page images the agent viewed, so it can
        # validate image-grounded answers (capped to bound cost).
        viewed = sorted(orchestrator.context.viewed_pages)[:3]
        images = [self._doc.render_page_base64(p) for p in viewed]
        verdict = verify(question, draft.answer, evidence, images=images)

        final_answer = verdict.revised_answer or draft.answer
        pages = self._collect_pages(final_answer, orchestrator)

        self._memory.add(
            question,
            final_answer,
            pages=pages,
            confidence=verdict.confidence,
            document=self._doc.path.name,
        )

        return AnswerResult(
            question=question,
            answer=final_answer,
            verdict=verdict,
            draft_answer=draft.answer,
            pages=pages,
            trace=draft.trace,
            used_memory=bool(recalled),
        )

    @staticmethod
    def _collect_pages(answer: str, orchestrator: Orchestrator) -> list[int]:
        """Pages cited in the answer, plus any pages the agent viewed."""
        cited = {int(m) for m in _PAGE_CITATION.findall(answer)}
        cited |= orchestrator.context.viewed_pages
        return sorted(cited)

    def close(self) -> None:
        self._doc.close()

    def __enter__(self) -> Pipeline:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
