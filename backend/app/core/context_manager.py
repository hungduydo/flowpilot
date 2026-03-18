"""Context window manager — keeps conversation within token limits for LLM calls."""

import structlog

from app.config import settings
from app.db.models import Message

logger = structlog.get_logger()


def estimate_tokens(text: str) -> int:
    """Estimate token count. ~4 chars per token for English, ~2 for CJK."""
    return max(1, len(text) // 3)


class ContextWindowManager:
    """Builds a bounded message list that fits within the LLM's context window."""

    def __init__(
        self,
        max_tokens: int | None = None,
        reserved_for_output: int | None = None,
    ):
        self.max_tokens = max_tokens or settings.max_context_tokens
        self.reserved_for_output = reserved_for_output or settings.max_output_tokens

    @property
    def available_tokens(self) -> int:
        return self.max_tokens - self.reserved_for_output

    def build_context(
        self,
        system_prompt: str,
        messages: list[Message],
        max_messages: int = 50,
    ) -> list[dict[str, str]]:
        """
        Build a token-bounded message list from conversation history.

        Strategy: sliding window with recency bias.
        1. Always include system prompt.
        2. Always include the latest user message.
        3. Fill remaining budget from most recent backward.
        """
        budget = self.available_tokens
        system_tokens = estimate_tokens(system_prompt)
        budget -= system_tokens

        if budget <= 0:
            logger.warning("System prompt exceeds token budget", system_tokens=system_tokens)
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": messages[-1].content if messages else ""},
            ]

        # Convert Message models → dicts, most recent first
        candidates = [
            {"role": m.role, "content": m.content, "tokens": estimate_tokens(m.content)}
            for m in messages[-max_messages:]
        ]

        # Always include the last message (latest user input)
        if not candidates:
            return [{"role": "system", "content": system_prompt}]

        selected: list[dict] = []
        used_tokens = 0

        # Walk from most recent backward
        for msg in reversed(candidates):
            if used_tokens + msg["tokens"] > budget:
                break
            selected.insert(0, msg)
            used_tokens += msg["tokens"]

        # Ensure first selected message is a user message for coherence
        if selected and selected[0]["role"] == "assistant":
            # Find the user message before it in candidates
            idx = candidates.index(selected[0])
            if idx > 0:
                prev = candidates[idx - 1]
                if used_tokens + prev["tokens"] <= budget:
                    selected.insert(0, prev)
                    used_tokens += prev["tokens"]

        # Build final list
        result = [{"role": "system", "content": system_prompt}]
        result.extend({"role": m["role"], "content": m["content"]} for m in selected)

        logger.debug(
            "Context window built",
            total_messages=len(messages),
            included_messages=len(selected),
            estimated_tokens=system_tokens + used_tokens,
            budget=self.available_tokens,
        )
        return result
