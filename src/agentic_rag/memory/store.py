"""File-based cross-task memory.

Persists answered questions to a JSONL file and recalls the most lexically
similar prior entries for a new question. This lets the agent reuse earlier
findings (e.g. a fact established in a previous question) across separate CLI
invocations — simple, transparent, and dependency-free.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_TOKEN = re.compile(r"\w+")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text)}


@dataclass
class MemoryRecord:
    """One remembered question/answer with provenance."""

    question: str
    answer: str
    pages: list[int]
    confidence: float
    document: str
    timestamp: str


class MemoryStore:
    """Append-only JSONL memory with Jaccard-overlap recall."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def add(
        self,
        question: str,
        answer: str,
        *,
        pages: list[int],
        confidence: float,
        document: str,
    ) -> None:
        """Append a record to the memory file (creating it if needed)."""
        record = MemoryRecord(
            question=question,
            answer=answer,
            pages=sorted(set(pages)),
            confidence=round(confidence, 3),
            document=document,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def _all(self) -> list[MemoryRecord]:
        if not self._path.exists():
            return []
        records: list[MemoryRecord] = []
        for raw_line in self._path.read_text(encoding="utf-8").splitlines():
            if line := raw_line.strip():
                records.append(MemoryRecord(**json.loads(line)))
        return records

    def recall(self, question: str, *, k: int = 2, min_overlap: float = 0.1) -> list[MemoryRecord]:
        """Return up to ``k`` past records most similar to ``question``.

        Similarity is token-set Jaccard overlap; records below ``min_overlap``
        are dropped so unrelated history is never surfaced.
        """
        q_tokens = _tokens(question)
        if not q_tokens:
            return []
        scored: list[tuple[float, MemoryRecord]] = []
        for record in self._all():
            r_tokens = _tokens(record.question)
            if not r_tokens:
                continue
            jaccard = len(q_tokens & r_tokens) / len(q_tokens | r_tokens)
            if jaccard >= min_overlap:
                scored.append((jaccard, record))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [record for _, record in scored[:k]]

    @staticmethod
    def format_hint(records: list[MemoryRecord]) -> str:
        """Render recalled records as a compact hint string for the agent."""
        lines = []
        for r in records:
            pages = ", ".join(f"p.{p}" for p in r.pages) or "n/a"
            lines.append(f"- Q: {r.question}\n  A: {r.answer} ({pages})")
        return "\n".join(lines)
