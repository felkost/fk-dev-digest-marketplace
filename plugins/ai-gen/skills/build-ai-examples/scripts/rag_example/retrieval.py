"""Ranking logic -- pure functions, standard library only.

Separated from the pgvector/LangGraph wiring on purpose: this is the part worth
unit-testing, and it tests offline against a stub embedder. In production the
ANN search happens inside Postgres (see ingest.py); this module is the
reference semantics that search must reproduce, and what the smoke test pins.
"""

from __future__ import annotations

import math
from typing import Protocol, Sequence


class Embedder(Protocol):
    """Anything that turns texts into vectors.

    Production: an API-backed embedding model. Tests: a deterministic stub.
    The seam exists so the test never needs a key or a network.
    """

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity; 0.0 for a zero vector rather than a ZeroDivisionError."""
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} != {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def rank(
    query_vec: Sequence[float],
    chunk_vecs: Sequence[Sequence[float]],
    top_k: int,
) -> list[tuple[int, float]]:
    """Return the top_k (chunk_index, score) pairs, best first.

    Ties break by original index so the output is deterministic -- an unstable
    ranking makes a retrieval eval unreproducible for no benefit.
    """
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    scored = [(i, cosine(query_vec, v)) for i, v in enumerate(chunk_vecs)]
    scored.sort(key=lambda p: (-p[1], p[0]))
    return scored[:top_k]


def recall_at_k(ranked_indices: Sequence[int], relevant: set[int]) -> float:
    """Fraction of the relevant chunks present in a ranked list.

    Here because it is the highest-value measurement in RAG work and belongs
    next to the ranking it measures -- not in a notebook nobody reruns. Metric
    definitions: evaluate-optimize-models/references/evaluation.md.
    """
    if not relevant:
        raise ValueError("relevant set must be non-empty")
    return len(set(ranked_indices) & relevant) / len(relevant)


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[int]],
    k: int = 60,
) -> list[tuple[int, float]]:
    """Fuse multiple ranked id lists into one, best first.

    Cormack, Clarke & Buttcher, "Reciprocal Rank Fusion Outperforms Condorcet
    and Individual Rank Learning Methods" (SIGIR 2009): each system
    contributes 1 / (k + rank) per id it ranked, rank counted from 1. An id
    absent from a given ranking simply gets nothing from that system -- no
    score normalization is needed between systems, which is what makes this
    usable when one ranking comes from cosine similarity and the other from a
    PostgreSQL ts_rank_cd score on a completely different scale (see
    agent.py's search_docs). k=60 is the paper's own near-optimal constant,
    found via a pilot sweep in which the choice was explicitly NOT critical
    (their table: MAP moved from .2138 to .2147 across k=40..90) -- so it is
    a reasonable default, not a tuned value to chase.

    Ties break by ascending id, the same determinism `rank()` above enforces
    by index: an unstable fusion makes a retrieval eval unreproducible.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    scores: dict[int, float] = {}
    for ranking in rankings:
        for position, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + position)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
