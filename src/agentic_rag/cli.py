"""Command-line interface.

    agentic-rag --pdf paper.pdf --question "What accuracy did the system reach?"

Loads the PDF, runs the agentic pipeline, and prints the verified answer with
citations, a confidence score, and (optionally) the tool-call trace.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Sequence

import openai
from rich.console import Console
from rich.panel import Panel

from .agents.pipeline import AnswerResult, Pipeline
from .config import get_settings

console = Console()
err_console = Console(stderr=True, style="bold red")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-rag",
        description="Agentic, multimodal RAG question answering over a PDF.",
    )
    parser.add_argument("--pdf", required=True, help="Path to the PDF document.")
    parser.add_argument("--question", "-q", required=True, help="Question to answer.")
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Do not recall or store cross-task memory.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON instead of prose.")
    parser.add_argument(
        "--show-trace",
        action="store_true",
        help="Print the agent's tool-call trace.",
    )
    return parser


def _render_human(result: AnswerResult, *, show_trace: bool) -> None:
    console.print(Panel(result.answer, title="Answer", border_style="green"))

    citations = ", ".join(f"p.{p}" for p in result.pages) or "none"
    verdict = result.verdict
    status = "[green]supported[/]" if verdict.supported else "[yellow]needs review[/]"
    console.print(
        f"Verification: {status}  "
        f"confidence={verdict.confidence:.2f}  citations={citations}"
        + ("  (used memory)" if result.used_memory else "")
    )
    if verdict.issues:
        console.print("[yellow]Verifier notes:[/]")
        for issue in verdict.issues:
            console.print(f"  • {issue}")

    if show_trace and result.trace:
        console.print("\n[dim]Tool trace:[/]")
        for i, call in enumerate(result.trace, 1):
            console.print(f"  [dim]{i}. {call.name}({json.dumps(call.input, ensure_ascii=False)})[/]")


def _render_json(result: AnswerResult) -> None:
    payload = {
        "question": result.question,
        "answer": result.answer,
        "pages": result.pages,
        "supported": result.verdict.supported,
        "confidence": result.verdict.confidence,
        "issues": result.verdict.issues,
        "used_memory": result.used_memory,
        "trace": [dataclasses.asdict(c) for c in result.trace],
    }
    console.print_json(json.dumps(payload, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()

    # Fail fast with a clear message if the API key is missing.
    try:
        settings.require_openai()
    except RuntimeError as exc:
        err_console.print(str(exc))
        return 2

    try:
        with Pipeline.from_pdf(args.pdf, settings=settings) as pipeline:
            result = pipeline.run(args.question, use_memory=not args.no_memory)
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"Document error: {exc}")
        return 2
    except openai.APIError as exc:
        err_console.print(f"OpenAI API error: {exc}")
        return 3
    except Exception as exc:  # last-resort guard so the CLI never dumps a traceback
        err_console.print(f"Unexpected error: {exc}")
        return 1

    if args.json:
        _render_json(result)
    else:
        _render_human(result, show_trace=args.show_trace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
