# CLI Demo

This page presents representative CLI runs from the repository. The goal is not only to show that the commands execute, but also to make the behavior of the system visible: grounded answers, verification output, tool traces, multimodal fallback, and evaluation results.

For the generated benchmark transcript, see [demo_output.md](./demo_output.md).

## 1. Standard cited answer

This run shows the default question-answering flow on a text-rich academic PDF. The key behavior to notice is that the answer is returned together with verification status and page-level grounding.

```bash
agentic-rag --pdf samples/samples-3.pdf \
  --question "Bu makalenin yazarı kimdir?"
```

![Standard CLI answer](../images/01-basic-answer.png)

## 2. Tool trace and agent workflow

The next run enables `--show-trace` so the repository can demonstrate that the answer is not produced as an opaque single call. Instead, the orchestrator actively queries the document with tools before returning a final response.

```bash
agentic-rag --pdf samples/samples-3.pdf --show-trace \
  --question "Yazar hangi üniversitede görev yapmaktadır?"
```

![Tool trace output](../images/02-tool-trace.png)

## 3. Multimodal fallback on an image-only PDF

This example is the clearest demonstration of why the project is agentic rather than text-only. The PDF has no usable text layer, so the system must inspect the page visually instead of relying on text retrieval alone.

```bash
agentic-rag --pdf samples/samples-2.pdf --show-trace \
  --question "Bu sayfada hangi bilgiler yer alıyor?"
```

![Image-only PDF run](../images/03-multimodal-image-only.png)

## 4. Structured JSON output

The CLI can also emit a machine-readable result. This is useful when the pipeline is consumed by another script or when the answer, citations, and verification state need to be parsed programmatically.

```bash
agentic-rag --pdf samples/samples-3.pdf --json \
  --question "Makale hangi dergide yayımlanmıştır?"
```

![JSON output mode](../images/04-json-output.png)

## 5. Evaluation harness

Finally, the bundled evaluation script runs a small benchmark over the sample question set and writes a transcript to `docs/demo_output.md`. This is the fastest way to show end-to-end behavior across multiple prompts.

```bash
python scripts/evaluate.py
```

![Evaluation summary](../images/05-evaluation-summary.png)

## What this demo shows

Taken together, the screenshots illustrate the project’s main claims:

- the system answers from document evidence rather than free-form recall
- the orchestrator can expose its tool usage
- multimodal page inspection works when plain text extraction is insufficient
- the output can be consumed as either human-readable prose or structured JSON
- the repository includes a repeatable evaluation path rather than only ad hoc examples
