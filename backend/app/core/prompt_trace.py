"""
Request-scoped LLM prompt tracing via contextvars.

When tracing is enabled (via `init_trace()`), every LLM call automatically
records the messages sent, parameters, response preview, token usage, and timing.
Traces are collected per-request and returned in the chat response when debug=true.

Usage:
    # At request start (only when debug=true):
    init_trace()

    # ... LLM calls happen, each calls record_trace() internally ...

    # At request end:
    traces = get_traces()   # list[dict] or None
    clear_trace()
"""

import time
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import Any

# Request-scoped trace storage. None = tracing disabled (zero overhead).
_trace_entries: ContextVar[list["TraceEntry"] | None] = ContextVar(
    "_trace_entries", default=None
)

# Stash last token usage from provider-specific functions
_last_token_usage: ContextVar[dict[str, int]] = ContextVar(
    "_last_token_usage", default={}
)

# Max chars to keep per message content in trace output
_MAX_MESSAGE_CONTENT = 2000
# Max chars for response preview
_MAX_RESPONSE_PREVIEW = 500


@dataclass
class TraceEntry:
    """A single LLM call trace."""

    step: str  # e.g. "intent_classification", "phase1_plan"
    provider: str  # "ollama", "anthropic", "openai"
    model: str
    temperature: float
    messages: list[dict[str, str]]  # The actual messages sent to LLM
    response_preview: str = ""  # First N chars of response
    token_usage: dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize with truncation for large prompts."""
        d = asdict(self)
        # Truncate message contents
        for msg in d["messages"]:
            content = msg.get("content", "")
            if len(content) > _MAX_MESSAGE_CONTENT:
                msg["content"] = (
                    content[:_MAX_MESSAGE_CONTENT]
                    + f"\n\n... [truncated, {len(content)} chars total]"
                )
        # Truncate response preview
        if len(d["response_preview"]) > _MAX_RESPONSE_PREVIEW:
            d["response_preview"] = d["response_preview"][:_MAX_RESPONSE_PREVIEW] + "..."
        return d


def init_trace():
    """Enable tracing for the current request. Call at request start."""
    _trace_entries.set([])


def record_trace(entry: TraceEntry):
    """Record a trace entry. No-op if tracing is not enabled."""
    entries = _trace_entries.get(None)
    if entries is not None:
        entries.append(entry)


def set_last_token_usage(usage: dict[str, int]):
    """Called by provider-specific LLM functions to stash token usage."""
    _last_token_usage.set(usage)


def get_last_token_usage() -> dict[str, int]:
    """Read the last stashed token usage."""
    return _last_token_usage.get({})


def get_traces() -> list[dict[str, Any]] | None:
    """Return collected traces, or None if tracing was not enabled."""
    entries = _trace_entries.get(None)
    if entries is None:
        return None
    return [e.to_dict() for e in entries]


def clear_trace():
    """Reset trace state. Call at request end."""
    _trace_entries.set(None)
    _last_token_usage.set({})
