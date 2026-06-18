"""Shared pytest fixtures.

Tests run against the real PDFs in ``samples/`` (read-only). All tests are
offline — they never call the OpenAI API.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def _require(name: str) -> Path:
    path = _SAMPLES / name
    if not path.exists():
        pytest.skip(f"sample PDF missing: {path}")
    return path


@pytest.fixture(scope="session")
def rich_pdf() -> Path:
    """A long, text-rich academic article (18 pages, embedded figures)."""
    return _require("samples-3.pdf")


@pytest.fixture(scope="session")
def short_pdf() -> Path:
    """A single-page text document (press release)."""
    return _require("samples-1.pdf")


@pytest.fixture(scope="session")
def image_only_pdf() -> Path:
    """A single-page PDF with no extractable text layer (image only)."""
    return _require("samples-2.pdf")
