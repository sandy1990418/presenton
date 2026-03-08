"""
Dynamic context-window budgeting for LLM calls.

Calculates how many characters of source content can safely fit into a
prompt given the fixed parts (system prompt, schema, outline, etc.)
and the model's context window.
"""

import os
from typing import List, Optional

from constants.llm import (
    DEFAULT_CONTEXT_CHARS,
    MODEL_CONTEXT_CHARS,
    OUTPUT_BUFFER_CHARS,
)


def get_model_context_chars(model: str) -> int:
    """Return the context-window size (in chars) for *model*.

    Checks the ``LLM_CONTEXT_CHARS`` env var first (allows per-deploy
    override), then falls back to the built-in registry and finally to
    ``DEFAULT_CONTEXT_CHARS``.
    """
    override = os.getenv("LLM_CONTEXT_CHARS")
    if override:
        try:
            return int(override)
        except ValueError:
            pass
    return MODEL_CONTEXT_CHARS.get(model, DEFAULT_CONTEXT_CHARS)


def estimate_source_budget(
    model: str,
    fixed_parts: List[str],
    output_buffer: Optional[int] = None,
) -> int:
    """Calculate how many chars are left for source content.

    Args:
        model: Model identifier (e.g. "gpt-4.1").
        fixed_parts: All non-source parts of the prompt that are
            already known (system prompt text, schema JSON, user
            content, outline, etc.).
        output_buffer: Chars to reserve for the LLM's response.
            Defaults to ``OUTPUT_BUFFER_CHARS``.

    Returns:
        Available chars for source content (≥ 0).
    """
    context_chars = get_model_context_chars(model)
    buf = output_buffer if output_buffer is not None else OUTPUT_BUFFER_CHARS
    fixed_total = sum(len(p) for p in fixed_parts if p)
    budget = context_chars - fixed_total - buf
    return max(0, budget)
