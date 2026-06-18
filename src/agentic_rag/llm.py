"""Thin wrapper around the OpenAI Chat Completions API.

Centralises client construction and the request defaults we use everywhere.
The agent loop in ``agents/base.py`` builds on :func:`chat`; one-shot structured
calls (the verifier) use :func:`complete_json`.
"""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from .config import get_settings

_DEFAULT_MAX_TOKENS = 4000


@cache
def get_client() -> OpenAI:
    """Return a process-wide cached OpenAI client."""
    settings = get_settings()
    return OpenAI(api_key=settings.require_openai())


def chat(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> ChatCompletionMessage:
    """Call Chat Completions and return the assistant message.

    Args:
        messages: conversation in OpenAI message format.
        tools: optional tool (function) definitions for tool-calling turns.
        max_tokens: output ceiling.

    Returns:
        The assistant :class:`ChatCompletionMessage` (may carry ``tool_calls``).
    """
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    response = get_client().chat.completions.create(**kwargs)
    return response.choices[0].message


def complete_json(
    system: str,
    user: str,
    schema: dict[str, Any],
    *,
    images: list[tuple[str, str]] | None = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> Any:
    """One-shot call constrained to a JSON schema; returns parsed JSON.

    Uses OpenAI structured outputs (``response_format`` with a strict
    ``json_schema``) so the response is guaranteed to be schema-valid JSON.

    Args:
        images: optional ``(media_type, base64)`` page images to include as
            visual evidence (e.g. to verify image-grounded answers). Requires a
            vision-capable model.
    """
    settings = get_settings()
    if images:
        user_message: Any = [{"type": "text", "text": user}]
        for media_type, data in images:
            user_message.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}})
    else:
        user_message = user
    response = get_client().chat.completions.create(
        model=settings.openai_model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "result", "strict": True, "schema": schema},
        },
    )
    return json.loads(response.choices[0].message.content)
