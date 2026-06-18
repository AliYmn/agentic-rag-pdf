"""The verifier agent: an independent check of the drafted answer.

Runs in a *separate* LLM call with its own context — it sees the question, the
drafted answer, and the evidence the orchestrator actually retrieved, but not
the orchestrator's reasoning. Its job is to catch unsupported claims and, when
possible, propose a corrected answer. This is the validation layer that guards
against confident-but-wrong responses.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..llm import complete_json

VERIFIER_SYSTEM = """\
You are an independent fact-checking verifier. You are given a QUESTION, a \
proposed ANSWER, and the EVIDENCE passages that were retrieved from a document \
(each tagged with its page, e.g. [p.3]). You may ALSO be shown page images the \
agent viewed — treat anything clearly visible in those images as valid evidence \
too (tables, figures, scanned text).

Check whether every factual claim in the ANSWER is supported by the EVIDENCE:
- "supported" is true only if all claims are backed by the evidence and any \
page citations are consistent with it.
- List specific problems in "issues" (unsupported claims, wrong citations, \
hallucinated details). Use an empty list if there are none.
- If the answer is wrong or unsupported but the evidence does contain the \
answer, put a corrected, cited answer in "revised_answer". Otherwise repeat the \
original answer there.
- "confidence" is your confidence (0..1) that the (possibly revised) answer is \
correct and grounded.

Judge only against the supplied evidence — do not use outside knowledge."""

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "confidence": {"type": "number"},
        "issues": {"type": "array", "items": {"type": "string"}},
        "revised_answer": {"type": "string"},
    },
    "required": ["supported", "confidence", "issues", "revised_answer"],
    "additionalProperties": False,
}


@dataclass
class Verdict:
    """The verifier's structured judgment."""

    supported: bool
    confidence: float
    issues: list[str]
    revised_answer: str


def verify(
    question: str,
    answer: str,
    evidence: str,
    *,
    images: list[tuple[str, str]] | None = None,
) -> Verdict:
    """Grade ``answer`` against ``evidence`` (and any page images) -> verdict.

    Args:
        images: ``(media_type, base64)`` page images the agent viewed, so the
            verifier can validate image-grounded claims it otherwise couldn't.
    """
    user = f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\nEVIDENCE:\n{evidence}"
    data = complete_json(VERIFIER_SYSTEM, user, _VERDICT_SCHEMA, images=images)
    return Verdict(
        supported=bool(data["supported"]),
        confidence=float(data["confidence"]),
        issues=list(data["issues"]),
        revised_answer=str(data["revised_answer"]).strip(),
    )
