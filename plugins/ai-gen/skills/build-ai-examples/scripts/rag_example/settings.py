"""Environment configuration -- standard library only, validated at startup.

Fails loudly and early when a variable is missing: a RAG service that boots
without DATABASE_URL and dies on the first question is strictly worse than one
that refuses to start. Every name read here must appear in .env.example --
plugins/ai-gen/tests/smoke_test.py fails the build when they drift apart.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Chat and embeddings come from DIFFERENT providers on purpose: OpenRouter's
    # API documents chat completions, not an /v1/embeddings endpoint, so it
    # cannot serve the retrieval half of RAG. Verify against OpenRouter's current
    # API reference before assuming otherwise.
    openrouter_api_key: str
    chat_model: str
    embedding_base_url: str
    embedding_api_key: str
    embedding_model: str
    database_url: str
    chunk_size: int
    chunk_overlap: int
    top_k: int


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in; "
            "never commit the filled-in file."
        )
    return value


def load_settings() -> Settings:
    """Read and validate configuration from the environment."""
    chunk_size = int(os.environ.get("CHUNK_SIZE", "120"))
    chunk_overlap = int(os.environ.get("CHUNK_OVERLAP", "20"))
    if not 0 <= chunk_overlap < chunk_size:
        raise RuntimeError(
            f"CHUNK_OVERLAP ({chunk_overlap}) must be >= 0 and < CHUNK_SIZE ({chunk_size})"
        )
    return Settings(
        openrouter_api_key=_require("OPENROUTER_API_KEY"),
        database_url=_require("DATABASE_URL"),
        # Pinned exact IDs, never "auto": an eval number without its model ID is
        # unreproducible. Verify both against the provider's current catalog.
        chat_model=os.environ.get("CHAT_MODEL", "openai/gpt-4o-mini"),
        # Defaults to a local OpenAI-compatible embeddings server (Ollama), so the
        # example needs exactly one paid key and the corpus never leaves the host.
        # Point these at any OpenAI-compatible embeddings endpoint to switch.
        embedding_base_url=os.environ.get("EMBEDDING_BASE_URL", "http://localhost:11434/v1"),
        # Local servers ignore the key; a hosted endpoint will not.
        embedding_api_key=os.environ.get("EMBEDDING_API_KEY", "not-needed-for-local"),
        embedding_model=os.environ.get("EMBEDDING_MODEL", "nomic-embed-text"),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        top_k=int(os.environ.get("TOP_K", "5")),
    )
