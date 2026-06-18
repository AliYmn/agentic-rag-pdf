"""Agent tools and their execution context.

Three tools give the orchestrator the three "moves" a human reader makes:

  * ``search``      — hybrid retrieval of relevant passages (with page citations),
  * ``view_page``   — render a page as an image (tables/figures the text misses),
  * ``get_outline`` — the document's section structure for navigation.

:class:`ToolContext` holds the per-question state (document, retriever, outline)
and accumulates the *evidence* the agent actually saw, so the verifier can later
grade the answer against exactly that evidence.

Tools return a :class:`ToolResult` (text, plus an optional rendered image).
OpenAI tool-result messages are text-only, so the agent loop attaches any image
as a follow-up user message — see ``agents/base.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..preprocessing.outline import OutlineNode, outline_to_text
from ..preprocessing.pdf_loader import PdfDocument
from ..retrieval.base import Retriever

# Tool schemas advertised to the model (OpenAI function-calling format).
# Descriptions are prescriptive about *when* to call each tool.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": (
                "Search the document for passages relevant to a query using hybrid "
                "lexical + semantic retrieval. Call this first for any factual "
                "question. Returns ranked snippets, each tagged with its page like "
                "[p.3] so you can cite it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to look for."},
                    "k": {
                        "type": "integer",
                        "description": "How many passages to return (default 8).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_page",
            "description": (
                "Render a page as an image and look at it. Call this when the answer "
                "likely lives in a table, chart, figure, or layout that plain text "
                "extraction would mangle — e.g. after search points you at a page "
                "that mentions a table, or for a document with no text layer."
            ),
            "parameters": {
                "type": "object",
                "properties": {"page_number": {"type": "integer", "description": "1-based page number."}},
                "required": ["page_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_outline",
            "description": (
                "Return the document's hierarchical section outline with page "
                "numbers. Call this to orient yourself in a long document before "
                "deciding where to search."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


@dataclass
class ToolResult:
    """Result of a tool call: text for the model, plus an optional image.

    ``image`` is ``(media_type, base64_data)`` when the tool produced a picture
    the model should look at (``view_page``); the loop renders it as an image
    block in a follow-up user message.
    """

    text: str
    image: tuple[str, str] | None = None


@dataclass
class ToolContext:
    """Per-question state shared across tool calls within one agent run."""

    doc: PdfDocument
    # None when the document has no extractable text layer (image-only PDF):
    # the agent then relies on view_page / get_outline instead of search.
    retriever: Retriever | None
    outline: list[OutlineNode]
    default_k: int = 8
    # Evidence the agent actually observed, for downstream verification.
    seen_chunks: dict[str, str] = field(default_factory=dict)  # "[p.N] text"
    viewed_pages: set[int] = field(default_factory=set)

    def evidence_text(self) -> str:
        """The evidence the agent observed, assembled for the verifier."""
        parts = list(self.seen_chunks.values())
        if self.viewed_pages:
            pages = ", ".join(f"p.{p}" for p in sorted(self.viewed_pages))
            parts.append(
                f"(The agent also visually inspected page(s) {pages} as images; "
                f"that visual content is not reproduced in this text evidence.)"
            )
        return "\n\n".join(parts) if parts else "(no evidence was gathered)"


def _run_search(ctx: ToolContext, tool_input: dict[str, Any]) -> ToolResult:
    if ctx.retriever is None:
        return ToolResult(
            "This document has no extractable text layer, so text search is "
            "unavailable. Use view_page to read pages as images, and get_outline "
            "to inspect the structure."
        )
    query = tool_input["query"]
    k = int(tool_input.get("k") or ctx.default_k)
    results = ctx.retriever.search(query, k=k)
    if not results:
        return ToolResult("No relevant passages found.")
    lines = []
    for r in results:
        snippet = f"[p.{r.chunk.page_number}] {r.chunk.text}"
        ctx.seen_chunks[r.chunk.id] = snippet
        lines.append(snippet)
    return ToolResult("\n\n".join(lines))


def _run_view_page(ctx: ToolContext, tool_input: dict[str, Any]) -> ToolResult:
    page_number = int(tool_input["page_number"])
    try:
        media_type, data = ctx.doc.render_page_base64(page_number)
    except IndexError as exc:
        return ToolResult(f"Error: {exc}")
    ctx.viewed_pages.add(page_number)
    return ToolResult(f"Rendered page {page_number} as an image (shown next).", image=(media_type, data))


def _run_get_outline(ctx: ToolContext, _tool_input: dict[str, Any]) -> ToolResult:
    return ToolResult(outline_to_text(ctx.outline) or "(no outline available)")


_DISPATCH = {
    "search": _run_search,
    "view_page": _run_view_page,
    "get_outline": _run_get_outline,
}


def execute_tool(ctx: ToolContext, name: str, tool_input: dict[str, Any]) -> ToolResult:
    """Execute a tool by name and return its :class:`ToolResult`."""
    handler = _DISPATCH.get(name)
    if handler is None:
        return ToolResult(f"Unknown tool: {name}")
    return handler(ctx, tool_input)
