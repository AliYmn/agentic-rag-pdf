"""Evaluation harness: run a set of Q&A pairs and measure accuracy.

Scores each answer by exact-match substring (case-insensitive) against the
expected answer(s), prints a summary table, and writes a Markdown transcript to
``docs/demo_output.md`` for the demo deliverable.

Requires OPENAI_API_KEY (see .env.example).

Usage:
    python scripts/evaluate.py [--questions eval/questions.json] [--out docs/demo_output.md]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from agentic_rag.agents.pipeline import AnswerResult, Pipeline
from agentic_rag.config import get_settings

console = Console()


@dataclass
class CaseOutcome:
    question: str
    expected_any: list[str]
    probes: str
    result: AnswerResult
    passed: bool


def _score(answer: str, expected_any: list[str]) -> bool:
    low = answer.lower()
    return any(exp.lower() in low for exp in expected_any)


def run(questions_path: Path, out_path: Path) -> int:
    spec = json.loads(questions_path.read_text(encoding="utf-8"))
    pdf_path = Path(spec["pdf"])
    cases = spec["cases"]

    outcomes: list[CaseOutcome] = []
    with Pipeline.from_pdf(pdf_path) as pipeline:
        for case in cases:
            # Memory off so each case is scored independently.
            result = pipeline.run(case["question"], use_memory=False)
            passed = _score(result.answer, case["expected_any"])
            outcomes.append(
                CaseOutcome(
                    question=case["question"],
                    expected_any=case["expected_any"],
                    probes=case.get("probes", ""),
                    result=result,
                    passed=passed,
                )
            )

    _print_summary(outcomes)
    accuracy = sum(o.passed for o in outcomes) / len(outcomes)
    console.print(f"\n[bold]Accuracy: {accuracy:.0%} ({sum(o.passed for o in outcomes)}/{len(outcomes)})[/]")
    _write_transcript(outcomes, accuracy, pdf_path, out_path)
    console.print(f"[dim]Transcript written to {out_path}[/]")
    return 0 if accuracy == 1.0 else 1


def _print_summary(outcomes: list[CaseOutcome]) -> None:
    table = Table(title="Evaluation results")
    table.add_column("#", justify="right")
    table.add_column("Question", max_width=40)
    table.add_column("Probes")
    table.add_column("Pass")
    table.add_column("Conf", justify="right")
    table.add_column("Tools")
    for i, o in enumerate(outcomes, 1):
        tools = ",".join(sorted({c.name for c in o.result.trace})) or "-"
        table.add_row(
            str(i),
            o.question,
            o.probes,
            "[green]✓[/]" if o.passed else "[red]✗[/]",
            f"{o.result.verdict.confidence:.2f}",
            tools,
        )
    console.print(table)


def _write_transcript(outcomes: list[CaseOutcome], accuracy: float, pdf_path: Path, out_path: Path) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# Demo Output — Agentic RAG over PDF",
        "",
        f"- Document: `{pdf_path}`",
        f"- Generated: {now}",
        f"- Accuracy: **{accuracy:.0%}** ({sum(o.passed for o in outcomes)}/{len(outcomes)})",
        "",
        "Each case below shows the question, the verified answer, the verifier's "
        "judgment, the pages cited, and the tools the agent invoked.",
        "",
    ]
    for i, o in enumerate(outcomes, 1):
        v = o.result.verdict
        tools = ", ".join(f"`{c.name}`" for c in o.result.trace) or "—"
        pages = ", ".join(f"p.{p}" for p in o.result.pages) or "none"
        lines += [
            f"## {i}. {o.question}",
            "",
            f"- **Probes:** {o.probes}",
            f"- **Answer:** {o.result.answer}",
            f"- **Result:** {'✅ PASS' if o.passed else '❌ FAIL'} (expected one of: {', '.join(o.expected_any)})",
            f"- **Verifier:** supported={v.supported}, confidence={v.confidence:.2f}",
            f"- **Citations:** {pages}",
            f"- **Tools used:** {tools}",
        ]
        if v.issues:
            lines.append(f"- **Verifier notes:** {'; '.join(v.issues)}")
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the QA evaluation harness.")
    parser.add_argument("--questions", default="eval/questions.json", type=Path)
    parser.add_argument("--out", default="docs/demo_output.md", type=Path)
    args = parser.parse_args()

    try:
        get_settings().require_openai()
    except RuntimeError as exc:
        console.print(f"[bold red]{exc}[/]")
        return 2
    return run(args.questions, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
