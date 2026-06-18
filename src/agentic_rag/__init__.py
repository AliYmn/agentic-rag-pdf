"""Agentic RAG over multimodal PDF documents.

A small, framework-free prototype that combines hybrid retrieval (BM25 + dense
OpenAI embeddings) with a tool-calling agent loop on top of the OpenAI API,
plus an independent verifier agent for answer validation.
"""

__version__ = "0.1.0"
