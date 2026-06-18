# Technical Note — Two Key Design Decisions

This note summarizes the two most consequential design decisions made while
building the Agentic RAG over PDF prototype, and the reasoning behind them. The
full architecture is documented in [docs/architecture.md](docs/architecture.md).

## 1. Page viewing as a tool, not a separate visual index

Multimodal questions — tables, figures, or scanned pages with no usable text
layer — were a core requirement. The conventional approach is a dedicated visual
retrieval stack (page-image embeddings, a vision index, separate ranking). I
chose instead to expose page inspection as a single agent tool, `view_page`:
text retrieval locates the likely page, and the orchestrator decides whether to
render that page and read it as an image.

The rationale is cost versus value for an MVP. A separate visual index roughly
doubles the indexing infrastructure and introduces fusion logic between two
embedding spaces, yet the chosen model is already vision-capable. Treating the
visual step as a tool reuses that capability, keeps the system small enough to
understand end-to-end, and makes every visual lookup explicit in the tool trace.
The accepted trade-off: image-heavy documents depend on the agent first reaching
the correct page from text. For documents with no text layer at all, the
pipeline degrades gracefully — it skips the text index and the agent relies on
`view_page` and `get_outline` instead of failing.

## 2. Separating drafting from verification

The pipeline could have answered and self-checked in one model call. Instead, a
second, independent verifier call grades the draft. Critically, the verifier
does **not** see the orchestrator's reasoning — only the question, the draft
answer, the evidence actually retrieved, and any page images viewed.

The reason is confirmation bias: a model asked to check its own chain of thought
tends to reassert it. Isolating the inputs forces the verifier to judge the
answer purely against gathered evidence, and it returns a structured verdict
(`supported`, `confidence`, `issues`, `revised_answer`) that the CLI surfaces and
other code can consume. The trade-off is one extra model call per question —
more latency and tokens — which is justified because document-grounded
correctness is the project's primary goal.
