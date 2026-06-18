# Agentic RAG over PDF

Multi-modal, agentic question answering over long PDF documents. An orchestrator
agent navigates a document with tools — **hybrid retrieval** (BM25 + dense OpenAI
embeddings), **multi-modal page viewing** (tables/figures as images), and
**structural outline** navigation — then an independent **verifier agent** checks
the answer against the retrieved evidence before it is returned.

Built on the OpenAI API (`gpt-4o`) with a small, framework-free agent loop — a
single provider powers both the agent and the embeddings. See
**[DESIGN.md](DESIGN.md)** for the architecture and the rationale behind each
design decision.

## Features

- **PDF ingestion** — text, per-page images, and metadata via PyMuPDF.
- **Hybrid retrieval** — BM25 (lexical) ⊕ OpenAI (dense) fused with Reciprocal
  Rank Fusion; results carry page citations.
- **Multi-modal** — the agent renders a page to an image when the answer lives in
  a table/figure the text layer can't capture.
- **Multi-agent** — orchestrator (tool-calling) + independent verifier (validation).
- **Structural navigation** — hierarchical JSON outline (embedded TOC or font
  heuristic).
- **Cross-task memory** — file-based recall of prior Q&A across runs.
- **CLI + evaluation harness** with a generated demo transcript.

## Requirements

- Python **3.10+** (developed on 3.12).
- A single **OpenAI API key** — https://platform.openai.com/api-keys
  (powers both the agent LLM and the dense embeddings).

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"          # or: pip install -r requirements.txt

cp .env.example .env             # then edit .env and add your API key
```

`.env` keys (see `.env.example` for the full list and defaults):

```
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o
EMBEDDING_MODEL=text-embedding-3-small
```

Sample PDFs live under `samples/`:

| File | Content | Exercises |
|------|---------|-----------|
| `samples-1.pdf` | 1-page press release (Yapı Kredi responsible-AI principles) | short text doc |
| `samples-2.pdf` | 1-page, **no text layer** (image only) | multi-modal `view_page` |
| `samples-3.pdf` | 18-page academic article (AI in banking) | retrieval + structural navigation |

## Usage

```bash
agentic-rag --pdf samples/samples-3.pdf \
            --question "Bu makalenin yazarı kimdir?"
```

Useful flags:

| Flag | Effect |
|------|--------|
| `-q, --question` | The question to answer (required). |
| `--pdf` | Path to the PDF (required). |
| `--show-trace` | Print the agent's tool-call trace. |
| `--json` | Emit a machine-readable JSON result. |
| `--no-memory` | Skip cross-task memory for this run. |

Example forcing the multi-modal path — `samples-2.pdf` has no text layer, so the
agent must render the page and read it as an image (`view_page`):

```bash
agentic-rag --pdf samples/samples-2.pdf --show-trace \
  -q "Bu sayfada hangi bilgiler yer alıyor?"
```

## Evaluation & demo

Run the harness over the bundled Q&A set; it prints a results table and writes a
transcript to `docs/demo_output.md`:

```bash
python scripts/evaluate.py
```

The four cases probe verifiable text facts in `samples-3.pdf` (author, journal,
affiliation, stated challenges). See `eval/questions.json` to add your own.

## Tests

24 unit tests run fully offline against the real PDFs in `samples/` (no API keys
needed):

```bash
pytest -q
```

They cover preprocessing (loading, chunking, outline, image-only PDFs), retrieval
(BM25, RRF fusion, hybrid), tools (search/`view_page`/outline), memory, and the
full pipeline wiring with a mocked LLM.

## Project layout

```
src/agentic_rag/
  config.py            # env-driven settings (pydantic)
  llm.py               # OpenAI client + request defaults
  preprocessing/       # pdf_loader, chunker, outline
  retrieval/           # bm25_index, dense_index (OpenAI+Chroma), hybrid (RRF)
  agents/              # base loop, tools, orchestrator, verifier, pipeline
  memory/              # file-based cross-task memory
  cli.py               # command-line entrypoint
samples/               # sample PDFs (samples-1/2/3.pdf)
scripts/evaluate.py    # evaluation harness
tests/                 # offline unit tests (run against samples/)
eval/questions.json    # evaluation Q&A set
DESIGN.md              # architecture & design rationale
```
