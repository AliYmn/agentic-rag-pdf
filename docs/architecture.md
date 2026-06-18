# Architecture & Design Rationale

This document describes the architecture of the Agentic RAG over PDF prototype, the reasoning behind its component choices, and the main trade-offs accepted in the MVP.

The system is designed for question answering over long PDF documents where useful evidence may live in plain text, layout-heavy pages, tables, or scanned content. The core idea is simple: instead of treating the document as a flat text corpus, the system combines retrieval, structural navigation, and targeted page inspection inside an explicit agent loop, then validates the final answer in a separate pass.

## System overview

At a high level, the pipeline follows the same steps a careful human reader would use:

1. inspect the document structure
2. retrieve the most relevant passages
3. inspect the original page visually when text extraction is insufficient
4. draft an answer with citations
5. verify the answer against the gathered evidence

```text
┌─────────────────────────────────────────────────────────────────┐
│ PDF -> preprocessing (PyMuPDF)                                 │
│ pages, extracted text, optional page images, outline, chunks   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator agent (gpt-4o, tool-calling loop)                 │
│ tools: search | get_outline | view_page                        │
└───────────────┬───────────────────────┬─────────────────────────┘
                │                       │
                │                       └──────────────► page image rendering
                │
                └──────────────────────► hybrid retrieval
                                          BM25 + dense embeddings + RRF
                                │
                                ▼
                     cited draft answer + gathered evidence
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ Verifier agent (independent LLM pass)                          │
│ checks support, citations, issues, and revised answer          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                  final answer + confidence + cited pages

Memory store (JSONL) persists prior Q&A across runs and can surface
related prior answers as hints for future questions.
```

## Design goals

The MVP was shaped around four constraints:

- keep the system small enough to understand end-to-end
- make the answer path inspectable from the CLI
- support scanned or layout-heavy pages without building a full multimodal index
- keep the implementation modular enough for independent testing

Those goals explain most of the implementation choices in the repository.

## 1. Document preprocessing

The preprocessing layer is built around PyMuPDF. It was chosen because it covers the full minimum feature set with one dependency: text extraction, page metadata, table of contents access, and raster page rendering.

The preprocessing stage produces three artifacts:

- per-page text, preserved with 1-based page numbers
- a document outline, when one can be inferred
- retrieval chunks, each anchored to its source page

### Text extraction

Each page is loaded with `get_text("text")`. The pipeline keeps the original page number attached to every page and every chunk. That page-level provenance is essential because the final answer format relies on explicit citations such as `[p.12]`.

### Page rendering

When the agent decides that the answer depends on layout or image content, the page is rendered to PNG and passed back to the model as a base64 image block. Rendering is performed at 150 DPI, which keeps the image readable without inflating token and latency costs more than necessary.

### Chunking strategy

Chunking is paragraph-aware rather than tokenizer-aware. Chunks are assembled with a character budget and controlled overlap. This is a pragmatic choice for an MVP:

- it keeps adjacent evidence together
- it stays robust across different PDF text layouts
- it avoids additional tokenizer dependencies

Oversized paragraphs are split deterministically so chunk generation does not fail on unusually dense pages.

## 2. Structural navigation

Long-document QA degrades quickly when retrieval is the only navigation mechanism. To avoid that, the agent gets access to a structural outline through the `get_outline` tool.

The outline is represented as a small hierarchical tree of section nodes, each carrying:

- title
- nesting level
- page number
- child sections

Two extraction strategies are used:

1. embedded table of contents, if the PDF exposes one
2. a font-size heuristic fallback when there is no embedded TOC

The embedded TOC path is the most reliable because it reflects author-provided structure. The fallback is deliberately simple: it estimates body text size, then treats lines significantly larger than that baseline as section headings. This is not a full document-layout model, but it is enough to orient the agent inside long reports and papers.

## 3. Retrieval strategy

The system uses hybrid retrieval:

- lexical search with BM25
- dense semantic search with OpenAI embeddings
- Reciprocal Rank Fusion (RRF) to merge both rankings

### Why hybrid retrieval

BM25 remains strong on exact names, affiliations, numbers, and uncommon terminology. Dense retrieval is useful when the wording of the question differs from the wording in the source. The combined system is more stable than either method alone for mixed academic and report-style PDFs.

### BM25

The lexical index is built over the generated chunks. Tokenization is intentionally language-agnostic rather than tied to English stopword removal, because the bundled examples and evaluation prompts are in Turkish and the repository should not degrade simply because the source language changes.

### Dense retrieval

Dense retrieval uses `text-embedding-3-small` and stores vectors in an in-memory Chroma collection. The collection is ephemeral by design. That avoids stale cross-document state and keeps the implementation predictable: every run builds a document-specific dense index from scratch.

### Rank fusion

RRF is used because it combines rankings without assuming that the underlying score scales are directly comparable. That makes it a good fit for merging BM25 and cosine-similarity outputs. The result is a fused list that rewards agreement between retrieval strategies.

### Visual retrieval integration

The system does not maintain a separate visual vector index. Instead, text retrieval finds the relevant page, and the agent decides whether to inspect that page visually with `view_page`. This keeps the infrastructure small while still allowing multimodal reasoning when the text layer is incomplete or misleading.

## 4. Agent architecture

The runtime uses two specialized agents:

- an orchestrator that plans, calls tools, and drafts the answer
- a verifier that checks whether the draft is fully supported

### Orchestrator

The orchestrator runs in a manual tool-calling loop. It can:

- call `search` to retrieve passages
- call `get_outline` to inspect structure
- call `view_page` to inspect a specific page as an image

The loop is intentionally framework-free. That choice gives the implementation direct control over:

- trace collection
- iteration limits
- image attachment after tool calls
- the exact evidence passed into verification

This is a better fit for a small, inspectable MVP than introducing a heavier external agent framework.

### Verifier

The verifier is a second, independent LLM call. It does not reuse the orchestrator’s internal reasoning. Instead, it only receives:

- the original question
- the drafted answer
- the evidence gathered by the orchestrator
- any page images viewed during the run

It returns a structured JSON verdict:

- whether the answer is supported
- a confidence score
- any detected issues
- a revised answer when a correction is possible

That separation reduces confirmation bias and makes the validation layer explicit instead of implicit.

## 5. Reliability and answer quality

The system uses several safeguards against confident but weak answers.

### Evidence grounding

The orchestrator is instructed to answer only from retrieved or viewed evidence and to cite page numbers for each factual claim. If the document does not contain the answer, the preferred behavior is to say so directly.

### Independent verification

The verifier checks the answer against only the supplied evidence. It is not asked to use external knowledge. This matters because the goal is not general factual correctness in the abstract; it is document-grounded correctness.

### Traceability

The CLI can expose:

- cited pages
- verification confidence
- verifier issues
- the tool-call trace

That makes it easier to understand how the answer was assembled and whether the agent had to inspect pages visually.

### Error handling

The CLI handles missing API credentials, broken PDFs, invalid page requests, and OpenAI API failures with user-facing error messages rather than raw tracebacks. This keeps failure modes predictable for both manual use and demo sessions.

## 6. Memory

Cross-run memory is implemented as a JSONL store. Each completed answer can be written with:

- question
- answer
- cited pages
- confidence
- document name
- timestamp

On later runs, the store can recall the most lexically similar previous questions and present them to the orchestrator as hints. The important design point is that memory is advisory, not authoritative. Recalled items must still be revalidated against the current document context.

This is deliberately lightweight. A file-backed JSONL memory store is transparent, easy to inspect, and good enough for an MVP that needs to demonstrate the concept of cross-task learning without introducing a more complex persistence layer.

## Trade-offs and limitations

The implementation is intentionally conservative. The main trade-offs are:

- Dense embeddings are rebuilt per document and per session, which increases runtime cost but avoids stale indexing problems.
- Visual reasoning depends on the agent reaching the correct page before calling `view_page`; there is no fully independent image-retrieval subsystem.
- Verification adds an extra model call, which improves answer quality at the cost of latency and tokens.
- The outline fallback is heuristic, so structural quality depends on the typography of the source PDF.

These are reasonable trade-offs for a minimum viable prototype whose primary purpose is to demonstrate architecture, modularity, and agent behavior clearly.

## Key design decisions

### 1. Treat page viewing as a tool instead of building a separate multimodal index

The project needed a practical way to answer questions that depend on scanned text, tables, or figures. One option was to introduce a dedicated visual retrieval stack. The alternative was to let the agent retrieve likely pages from text and then inspect those pages directly as images.

The second option was chosen. It keeps the system architecture smaller, uses the multimodal capability already available in the chosen model, and makes the visual step explicit in the trace. The trade-off is that image-heavy documents still rely on the agent identifying the right page before inspection.

### 2. Separate drafting from verification

The project could have asked one model call to answer and self-check in the same context. Instead, it uses a second pass for verification with isolated inputs.

That separation is more defensible because it reduces the chance that the model simply reasserts its own earlier reasoning. It also gives the pipeline a structured verdict that can be surfaced to the user or consumed programmatically.

### 3. A framework-free agent loop instead of LangChain/LlamaIndex

The orchestration loop is written by hand rather than on top of an agent framework. The assignment explicitly accepts a custom framework alongside LangChain and LlamaIndex, and for this MVP the custom loop is the better fit.

It gives direct control over the parts that matter here — trace capture, the iteration cap, attaching rendered page images as follow-up turns, and passing exactly the observed evidence into verification — without hiding them behind framework abstractions. It also keeps the dependency surface small and the system readable end to end, which is the stated design goal.

The trade-off is scope-dependent: a larger system (many retrievers, built-in memory and agent types, streaming, observability integrations) would benefit from the scaffolding a framework provides. At this scope that scaffolding would add dependency weight and hidden behavior without a matching payoff.

## Conclusion

This repository favors explicit structure over hidden orchestration. The system is not trying to be the most feature-rich RAG stack possible. It is trying to be understandable, testable, and strong enough to show how retrieval, tool use, multimodal inspection, and verification can work together in a compact agentic PDF QA pipeline.
