"""PDF loading and page rendering via PyMuPDF (fitz).

Responsibilities:
  * extract per-page text (for chunking + retrieval),
  * expose document metadata and any embedded table of contents,
  * render an arbitrary page to a base64 PNG on demand (for the multi-modal
    ``view_page`` agent tool — tables/figures/scanned content the text layer
    can't capture).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

import fitz  # PyMuPDF


@dataclass
class PageContent:
    """Extracted text and geometry for a single page (1-based number)."""

    page_number: int
    text: str
    width: float
    height: float


@dataclass
class PdfDocument:
    """An opened PDF: extracted text plus lazy page-image rendering.

    Use as a context manager so the underlying file handle is always released::

        with PdfDocument("paper.pdf") as doc:
            for page in doc.pages:
                ...
    """

    path: Path
    pages: list[PageContent] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    toc: list[tuple[int, str, int]] = field(default_factory=list)
    _doc: fitz.Document | None = field(default=None, repr=False)

    @classmethod
    def open(cls, path: str | Path) -> PdfDocument:
        """Open a PDF and eagerly extract text, metadata, and TOC.

        Raises:
            FileNotFoundError: if ``path`` does not exist.
            ValueError: if the file cannot be parsed as a PDF.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        try:
            raw = fitz.open(path)
        except Exception as exc:  # PyMuPDF raises a variety of low-level errors
            raise ValueError(f"Could not open '{path}' as a PDF: {exc}") from exc

        pages = [
            PageContent(
                page_number=i + 1,
                text=page.get_text("text"),
                width=page.rect.width,
                height=page.rect.height,
            )
            for i, page in enumerate(raw)
        ]
        metadata = {k: v for k, v in (raw.metadata or {}).items() if v}
        # get_toc -> [[level, title, page], ...]; normalise to tuples.
        toc = [(lvl, title, page) for lvl, title, page in raw.get_toc(simple=True)]

        return cls(path=path, pages=pages, metadata=metadata, toc=toc, _doc=raw)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def full_text(self) -> str:
        """All page text joined, with form-feed separators."""
        return "\f".join(p.text for p in self.pages)

    def render_page_base64(self, page_number: int, dpi: int = 150) -> tuple[str, str]:
        """Render a 1-based page to a base64-encoded PNG.

        Args:
            page_number: 1-based page index.
            dpi: render resolution; 150 balances legibility against token cost.

        Returns:
            ``(media_type, base64_data)`` ready for an OpenAI image block.

        Raises:
            IndexError: if ``page_number`` is out of range.
            RuntimeError: if the document was closed.
        """
        if self._doc is None:
            raise RuntimeError("PdfDocument is closed; reopen before rendering.")
        if not 1 <= page_number <= self.page_count:
            raise IndexError(f"page {page_number} out of range (1..{self.page_count})")
        page = self._doc[page_number - 1]
        pix = page.get_pixmap(dpi=dpi)
        data = base64.standard_b64encode(pix.tobytes("png")).decode("ascii")
        return "image/png", data

    def close(self) -> None:
        if self._doc is not None:
            self._doc.close()
            self._doc = None

    def __enter__(self) -> PdfDocument:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
