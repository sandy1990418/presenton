OPENAI_URL = "https://api.openai.com/v1"

# Default models
DEFAULT_OPENAI_MODEL = "gpt-4.1"
DEFAULT_GOOGLE_MODEL = "models/gemini-2.5-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# Approximate context window sizes in characters (~4 chars/token).
# Used for dynamic prompt budgeting.  Override per-model via
# the LLM_CONTEXT_CHARS env var if needed.
MODEL_CONTEXT_CHARS: dict[str, int] = {
    # OpenAI
    "gpt-4.1": 4_000_000,
    "gpt-4.1-mini": 4_000_000,
    "gpt-4.1-nano": 4_000_000,
    "gpt-4o": 512_000,
    "gpt-4o-mini": 512_000,
    "o3": 800_000,
    "o3-mini": 800_000,
    "o4-mini": 800_000,
    # Google
    "models/gemini-2.5-flash": 4_000_000,
    "models/gemini-2.5-pro": 4_000_000,
    "models/gemini-2.0-flash": 4_000_000,
    # Anthropic
    "claude-sonnet-4-20250514": 800_000,
    "claude-opus-4-20250514": 800_000,
    "claude-haiku-4-5-20251001": 800_000,
    "claude-3-5-sonnet-20241022": 800_000,
}

# Conservative default for unknown / Ollama / custom models.
DEFAULT_CONTEXT_CHARS = 28_000  # ~7K tokens

# Reserve this portion of the context window for LLM output.
OUTPUT_BUFFER_CHARS = 4_000
