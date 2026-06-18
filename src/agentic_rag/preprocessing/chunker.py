"""Split extracted page text into retrieval chunks.

Each chunk keeps a back-reference to its source page so retrieved evidence can
be cited (``[p.12]``) and the agent can decide to view that page as an image.
Splitting is paragraph-aware with a character budget and overlap, which keeps
related sentences together without needing a tokenizer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .pdf_loader import PdfDocument

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_WHITESPACE = re.compile(r"[ \t]+")


@dataclass(frozen=True)
class Chunk:
    """A retrieval unit: a span of text anchored to a page."""

    id: str
    text: str
    page_number: int
    chunk_index: int  # position within the page


def _normalise(text: str) -> str:
    """Collapse intra-line whitespace; keep paragraph breaks."""
    lines = (_WHITESPACE.sub(" ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _pack_paragraphs(paragraphs: list[str], max_chars: int, overlap: int) -> list[str]:
    """Greedily pack paragraphs into windows, carrying a char overlap forward."""
    windows: list[str] = []
    current = ""
    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}"
        else:
            windows.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{para}" if tail else para
        # A single oversized paragraph: hard-split it.
        while len(current) > max_chars:
            windows.append(current[:max_chars])
            current = current[max_chars - overlap :] if overlap else current[max_chars:]
    if current.strip():
        windows.append(current)
    return windows


def chunk_document(doc: PdfDocument, *, max_chars: int = 1200, overlap: int = 200) -> list[Chunk]:
    """Chunk a whole document, one independent pass per page.

    Args:
        doc: a loaded :class:`PdfDocument`.
        max_chars: target maximum characters per chunk.
        overlap: characters of context carried between adjacent chunks.

    Returns:
        Chunks in reading order, each with a stable ``id`` of ``p{page}-c{idx}``.
    """
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")

    chunks: list[Chunk] = []
    for page in doc.pages:
        normalised = _normalise(page.text)
        if not normalised:
            continue
        paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(normalised) if p.strip()]
        for idx, window in enumerate(_pack_paragraphs(paragraphs, max_chars, overlap)):
            chunks.append(
                Chunk(
                    id=f"p{page.page_number}-c{idx}",
                    text=window,
                    page_number=page.page_number,
                    chunk_index=idx,
                )
            )
    return chunks
