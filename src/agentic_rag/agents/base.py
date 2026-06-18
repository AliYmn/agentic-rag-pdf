"""A minimal, framework-free tool-calling agent loop (OpenAI).

We run the loop manually (rather than any agent framework) because the pipeline
needs fine-grained control: capturing a tool-call trace, bounding iterations,
attaching rendered page images as follow-up user messages, and feeding the
observed evidence to a separate verifier.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..llm import chat
from .tools import ToolResult

# (name, input) -> ToolResult
ToolExecutor = Callable[[str, dict[str, Any]], ToolResult]


@dataclass
class ToolCall:
    """One tool invocation, for tracing/explainability."""

    name: str
    input: dict[str, Any]


@dataclass
class AgentRun:
    """Result of a completed agent loop."""

    answer: str
    trace: list[ToolCall] = field(default_factory=list)


def _image_message(images: list[tuple[str, str]]) -> dict[str, Any]:
    """Build a user message carrying rendered page images for the model to see."""
    content: list[dict[str, Any]] = [{"type": "text", "text": "Here are the page image(s) you requested:"}]
    for media_type, data in images:
        content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}})
    return {"role": "user", "content": content}


def run_tool_loop(
    *,
    system: str,
    user_content: str,
    tool_schemas: list[dict[str, Any]],
    execute: ToolExecutor,
    max_iterations: int = 6,
    max_tokens: int = 4000,
) -> AgentRun:
    """Drive a tool-calling conversation until the model stops calling tools.

    Args:
        system: system prompt.
        user_content: the initial user turn.
        tool_schemas: OpenAI tool (function) definitions.
        execute: callback that runs a tool and returns a :class:`ToolResult`.
        max_iterations: hard cap on tool-call rounds (prevents runaway loops).
        max_tokens: per-response output ceiling.

    Returns:
        An :class:`AgentRun` with the final text answer and a tool-call trace.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    trace: list[ToolCall] = []

    for _ in range(max_iterations):
        message = chat(messages=messages, tools=tool_schemas, max_tokens=max_tokens)

        if not message.tool_calls:
            return AgentRun(answer=message.content or "", trace=trace)

        # Echo the assistant's tool-call turn back verbatim.
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            }
        )

        pending_images: list[tuple[str, str]] = []
        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            trace.append(ToolCall(name=tc.function.name, input=args))
            result = execute(tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result.text})
            if result.image is not None:
                pending_images.append(result.image)

        # Images can't ride inside a tool message, so attach them as a user turn.
        if pending_images:
            messages.append(_image_message(pending_images))

    # Hit the iteration cap: ask once more for a final answer, no tools.
    messages.append({"role": "user", "content": "Stop searching and answer now with what you have."})
    final = chat(messages=messages, max_tokens=max_tokens)
    return AgentRun(answer=final.content or "", trace=trace)
