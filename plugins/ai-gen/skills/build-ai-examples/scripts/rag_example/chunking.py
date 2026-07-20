"""Document splitting -- pure logic, standard library only.

Deliberately free of LangChain/pgvector imports so it can be unit-tested with no
services, no API keys and no network (see plugins/ai-gen/tests/smoke_test.py).
The framework wiring lives in ingest.py and agent.py.

Word-based windowing stands in for a real tokenizer here so the example runs
with nothing installed. See "Production deltas" in
references/rag-example.md -- chunk sizes must be measured in the *embedding
model's* tokens, not whitespace words, or your chunks silently overflow its
max sequence length.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Chunk:
    """One retrievable unit, carrying the metadata a citation needs."""

    text: str
    index: int
    source: str
    # Metadata captured at load time; it cannot be reconstructed later.
    meta: dict[str, str] = field(default_factory=dict)


def split_words(words: list[str], chunk_size: int, overlap: int) -> list[list[str]]:
    """Window `words` into overlapping runs of at most `chunk_size`.

    Consecutive windows share exactly `overlap` words -- that overlap is the
    cheap insurance against an answer severed by a chunk boundary, and it costs
    index size. The final window is short rather than padded.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    stride = chunk_size - overlap
    windows: list[list[str]] = []
    start = 0
    while True:
        window = words[start : start + chunk_size]
        if not window:
            break
        windows.append(window)
        if start + chunk_size >= len(words):
            break
        start += stride
    return windows


def split_text(
    text: str,
    source: str,
    chunk_size: int = 120,
    overlap: int = 20,
    meta: dict[str, str] | None = None,
) -> list[Chunk]:
    """Split a document into overlapping chunks with citation metadata attached."""
    words = text.split()
    return [
        Chunk(text=" ".join(w), index=i, source=source, meta=dict(meta or {}))
        for i, w in enumerate(split_words(words, chunk_size, overlap))
    ]
