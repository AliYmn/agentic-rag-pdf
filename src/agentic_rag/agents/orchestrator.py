"""The orchestrator agent: plans, calls tools, and drafts a cited answer."""

from __future__ import annotations

from ..preprocessing.outline import OutlineNode
from ..preprocessing.pdf_loader import PdfDocument
from ..retrieval.base import Retriever
from .base import AgentRun, run_tool_loop
from .tools import TOOL_SCHEMAS, ToolContext, execute_tool

ORCHESTRATOR_SYSTEM = """\
You are a meticulous document-analysis agent. Answer the user's question using \
ONLY the provided PDF, which you access through tools.

How to work:
- Use `get_outline` to orient yourself in long documents.
- Use `search` to find relevant passages. Search more than once with different \
wording if the first results are weak.
- When the answer likely lives in a table, chart, or figure, use `view_page` to \
look at that page as an image — do not guess from the surrounding text.
- Ground every claim in retrieved evidence. Cite the page for each fact like \
[p.3]. If the document does not contain the answer, say so plainly instead of \
inventing one.

Keep the final answer concise and lead with the direct answer, then briefly \
support it with cited evidence."""


class Orchestrator:
    """Runs the tool-calling loop for a single question over one document."""

    def __init__(
        self,
        doc: PdfDocument,
        retriever: Retriever | None,
        outline: list[OutlineNode],
        *,
        default_k: int = 6,
    ) -> None:
        self._ctx = ToolContext(
            doc=doc,
            retriever=retriever,
            outline=outline,
            default_k=default_k,
        )

    @property
    def context(self) -> ToolContext:
        """The tool context (carries the evidence the agent observed)."""
        return self._ctx

    def answer(self, question: str, *, memory_hint: str = "") -> AgentRun:
        """Produce a drafted, cited answer to ``question``."""
        user = question
        if memory_hint:
            user = (
                f"{question}\n\n(Context from earlier related questions — verify before relying on it:\n{memory_hint})"
            )
        return run_tool_loop(
            system=ORCHESTRATOR_SYSTEM,
            user_content=user,
            tool_schemas=TOOL_SCHEMAS,
            execute=lambda name, tool_input: execute_tool(self._ctx, name, tool_input),
        )
