"""Hierarchical document outline extraction (structural navigation).

Produces a nested JSON-able structure of sections so the agent can navigate a
long document by structure ("jump to the Methods section") instead of relying
on retrieval alone. Two strategies, in order of preference:

  1. The PDF's embedded table of contents (``doc.get_toc``) — accurate and free.
  2. A font-size heuristic: lines whose font is well above the body-text median
     are treated as headings. Used when no TOC is embedded.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field

from .pdf_loader import PdfDocument


@dataclass
class OutlineNode:
    """A section heading and its nested subsections."""

    title: str
    level: int
    page: int
    children: list[OutlineNode] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _nest(flat: list[OutlineNode]) -> list[OutlineNode]:
    """Turn a flat, level-tagged heading list into a nested tree."""
    roots: list[OutlineNode] = []
    stack: list[OutlineNode] = []
    for node in flat:
        while stack and stack[-1].level >= node.level:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots


def _from_toc(doc: PdfDocument) -> list[OutlineNode]:
    flat = [OutlineNode(title=title.strip(), level=lvl, page=page) for lvl, title, page in doc.toc]
    return _nest(flat)


def _from_font_heuristic(doc: PdfDocument, *, max_pages: int = 40) -> list[OutlineNode]:
    """Detect headings by font size relative to the body-text median.

    Heuristic: collect (size, text, page) for every line; the body font is the
    median size; lines >= 1.2x the body size and reasonably short are headings.
    Two heading tiers are assigned (large -> level 1, medium -> level 2).
    """
    if doc._doc is None:  # pragma: no cover - defensive
        return []

    spans: list[tuple[float, str, int]] = []
    sizes: list[float] = []
    for page_number in range(1, min(doc.page_count, max_pages) + 1):
        page = doc._doc[page_number - 1]
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                line_spans = line.get("spans", [])
                if not line_spans:
                    continue
                text = "".join(s["text"] for s in line_spans).strip()
                if not text:
                    continue
                size = max(s["size"] for s in line_spans)
                spans.append((size, text, page_number))
                sizes.append(size)

    if not sizes:
        return []

    body = statistics.median(sizes)
    large = body * 1.5
    medium = body * 1.2

    flat: list[OutlineNode] = []
    for size, text, page in spans:
        if len(text) > 120:  # long lines are body text, not headings
            continue
        if size >= large:
            flat.append(OutlineNode(title=text, level=1, page=page))
        elif size >= medium:
            flat.append(OutlineNode(title=text, level=2, page=page))
    return _nest(flat)


def extract_outline(doc: PdfDocument) -> list[OutlineNode]:
    """Return the document outline, preferring the embedded TOC."""
    if doc.toc:
        return _from_toc(doc)
    return _from_font_heuristic(doc)


def outline_to_text(nodes: list[OutlineNode], *, indent: int = 0) -> str:
    """Render an outline as an indented, human/LLM-readable tree with page refs."""
    lines: list[str] = []
    for node in nodes:
        lines.append(f"{'  ' * indent}- {node.title}  (p.{node.page})")
        if node.children:
            lines.append(outline_to_text(node.children, indent=indent + 1))
    return "\n".join(line for line in lines if line)
