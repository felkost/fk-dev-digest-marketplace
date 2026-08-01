"""Pure-logic core of a metacognitive monitoring harness.

Implements the pieces `design-agent-architecture/references/agent-metacognition.md`
specifies as testable: a confidence gate that reads a tracked state object rather
than a verbal claim, a stagnation detector with two independent signals (content
repeating vs confidence flatlining), and a resolver that prefers a genuinely
implicit confidence signal (token logprobs) when one is available and degrades to
a declared, honestly-labelled fallback when it is not.

Everything here is stdlib-only and free of import-time side effects, so the smoke
test can import and exercise it offline. Model wiring lives in ``agent.py`` and is
never imported from here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Sequence


# --------------------------------------------------------------------------
# Confidence gate: a structural check against tracked state, not a verbal one
# --------------------------------------------------------------------------


class GateDecision(str, Enum):
    PRESENT = "present"
    GATHER_MORE = "gather_more"
    SIGNAL_UNCERTAINTY = "signal_uncertainty"


@dataclass
class ConfidenceState:
    """What the gate reads. ``trend`` is history strictly before ``value`` --
    the caller appends the previous reading to trend before updating value,
    so the trend check below never compares a reading against itself.
    """

    value: float
    trend: tuple[float, ...] = ()
    has_open_contradiction: bool = False
    retries_used: int = 0


def check_confidence_gate(
    state: ConfidenceState,
    *,
    floor: float = 0.3,
    ceiling: float = 0.6,
    max_retries: int = 3,
    trend_window: int = 3,
) -> GateDecision:
    """floor/ceiling/max_retries/trend_window are illustrative defaults, not
    tuned values -- calibrate against your own eval set before trusting them,
    the same caution agent-tdad.md states for rubric thresholds.
    """
    if state.value < floor:
        return GateDecision.SIGNAL_UNCERTAINTY

    if state.value < ceiling:
        if state.retries_used < max_retries:
            return GateDecision.GATHER_MORE
        return GateDecision.SIGNAL_UNCERTAINTY

    # Above the ceiling: confidence and consistency are independent axes, so
    # a high reading does not override an unresolved contradiction.
    if state.has_open_contradiction:
        return GateDecision.GATHER_MORE

    if len(state.trend) >= trend_window:
        recent = state.trend[-trend_window:]
        if all(recent[i] > recent[i + 1] for i in range(len(recent) - 1)):
            return GateDecision.GATHER_MORE

    return GateDecision.PRESENT


# --------------------------------------------------------------------------
# Stagnation detection: two independent signals, either one fires it
# --------------------------------------------------------------------------


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


@dataclass
class StagnationVerdict:
    stagnant: bool
    signal: str  # "" | "content_overlap" | "confidence_plateau"


def detect_content_stagnation(
    embeddings: Sequence[Sequence[float]], *, threshold: float = 0.92
) -> bool:
    """Embeddings are injected, not computed here -- real vectors in
    production, stub vectors in tests. Compares only the last two, matching
    the scope of agent-loop.md's word-overlap detector (consecutive
    summaries, not the whole history).
    """
    if len(embeddings) < 2:
        return False
    return cosine(embeddings[-1], embeddings[-2]) >= threshold


def detect_confidence_plateau(
    trend: Sequence[float], *, window: int = 3, spread: float = 0.05
) -> bool:
    """A flatlined trend: the last `window` readings span less than `spread`."""
    if len(trend) < window:
        return False
    recent = trend[-window:]
    return (max(recent) - min(recent)) < spread


def detect_stagnation(
    embeddings: Sequence[Sequence[float]],
    confidence_trend: Sequence[float],
    *,
    content_threshold: float = 0.92,
    plateau_window: int = 3,
    plateau_spread: float = 0.05,
) -> StagnationVerdict:
    """Either signal firing is stagnation. The two catch different failures --
    content repeating while confidence keeps moving, or confidence flatlining
    while content keeps (marginally) changing -- so both run on every check;
    content is checked first only because it is cheaper to explain, not
    because it takes priority.
    """
    if detect_content_stagnation(embeddings, threshold=content_threshold):
        return StagnationVerdict(True, "content_overlap")
    if detect_confidence_plateau(
        confidence_trend, window=plateau_window, spread=plateau_spread
    ):
        return StagnationVerdict(True, "confidence_plateau")
    return StagnationVerdict(False, "")


# --------------------------------------------------------------------------
# Implicit confidence from logprobs, with a labelled, honest fallback
# --------------------------------------------------------------------------


@dataclass
class ConfidenceEstimate:
    value: float
    source: str  # "implicit_logprob" | "fallback_declared"


def implicit_confidence_from_logprobs(
    token_logprobs: Sequence[float] | None,
) -> float | None:
    """Mean per-token log-probability, mapped through exp() into (0, 1].

    Returns None -- never a guessed number -- when no logprobs are available.
    OpenRouter documents `logprobs`/`top_logprobs` with no published
    per-model support matrix, so absence is an expected, ordinary case, not
    an error to work around.
    """
    if not token_logprobs:
        return None
    mean_logprob = sum(token_logprobs) / len(token_logprobs)
    return math.exp(mean_logprob)


def resolve_confidence(
    token_logprobs: Sequence[float] | None, *, fallback: float
) -> ConfidenceEstimate:
    """Never let a fallback quietly masquerade as the real signal -- the
    caller always learns which one it received.
    """
    implicit = implicit_confidence_from_logprobs(token_logprobs)
    if implicit is not None:
        return ConfidenceEstimate(implicit, "implicit_logprob")
    return ConfidenceEstimate(fallback, "fallback_declared")
