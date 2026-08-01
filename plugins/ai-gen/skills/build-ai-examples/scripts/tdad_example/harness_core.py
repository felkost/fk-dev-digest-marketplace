"""Pure-logic core of a Test-Driven Agent Development (TDAD) harness.

Implements the pieces `evaluate-optimize-models/references/agent-tdad.md`
specifies: a normalizing evaluator, a grounding check that takes context as
an explicit argument (the structural fix to the shared-mutable-state bug the
reference documents), N-repeat benchmark running, defect-localization
classification, the minimum-change ladder as an escalate-only-on-failure
sequence, and a named retry-ceiling policy.

Everything here is stdlib-only and free of import-time side effects, so the
smoke test can import and exercise it offline. Model wiring lives in
``agent.py`` and is never imported from here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# --------------------------------------------------------------------------
# Normalizing evaluator
# --------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Lowercase, strip surrounding whitespace and trailing punctuation.

    "Photons." and "photons" must compare equal -- a strict string compare
    is exactly the evaluator bug this file exists to catch.
    """
    return text.strip().rstrip(".!?,;:").strip().lower()


def exact_match(expected: str, actual: str) -> bool:
    return normalize(expected) == normalize(actual)


# --------------------------------------------------------------------------
# Grounding: context is an explicit argument, never a module global
# --------------------------------------------------------------------------


_TERM_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9]{3,}")


def _key_terms(text: str) -> set[str]:
    return {w.lower() for w in _TERM_RE.findall(text)}


@dataclass
class AccumulatingContext:
    """Evidence gathered across multiple search steps for ONE request.

    Each request builds its own instance; nothing here is shared across
    requests, which is what makes interleaving safe by construction rather
    than by discipline.
    """

    _pieces: list[str] = field(default_factory=list)

    def add(self, piece: str) -> None:
        self._pieces.append(piece)

    def snapshot(self) -> tuple[str, ...]:
        """An immutable copy -- callers can check against it without racing
        a future ``add()``."""
        return tuple(self._pieces)

    def __len__(self) -> int:
        return len(self._pieces)


def is_grounded(answer: str, context: tuple[str, ...], threshold: float = 0.6) -> bool:
    """Does ``answer`` trace to ``context``? Context is ALWAYS an explicit
    argument -- this is the entire fix for the module-level-global bug
    agent-tdad.md documents. Call this against ``AccumulatingContext.
    snapshot()``, and pass the FULL snapshot when evidence accumulated
    across steps, not just the most recently added piece.
    """
    terms = _key_terms(answer)
    if not terms:
        return True
    combined = " ".join(context).lower()
    covered = sum(1 for t in terms if t in combined)
    return (covered / len(terms)) >= threshold


# --------------------------------------------------------------------------
# N-repeat benchmarking: a single pass on a stochastic task proves nothing
# --------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    pass_rate: float
    passes: int
    n: int
    results: tuple[bool, ...]


def run_benchmark(task_fn, n: int = 5) -> BenchmarkResult:
    """Run ``task_fn()`` (returns truthy/falsy) ``n`` times and report the
    pass RATE, not a single boolean -- a case that is right 3 times out of 5
    hands a one-shot harness a pass 3 times out of 5, indistinguishable from
    reliable until repeated.
    """
    results = tuple(bool(task_fn()) for _ in range(n))
    passes = sum(results)
    return BenchmarkResult(pass_rate=passes / n, passes=passes, n=n, results=results)


# --------------------------------------------------------------------------
# Defect localization: evaluator bug vs instruction bug vs capability gap
# --------------------------------------------------------------------------


def classify_failure(
    *,
    expected: str,
    raw_output: str,
    evaluator_verdict: bool,
    tool_calls: list[str],
    required_tool: str,
) -> str:
    """Given a case the evaluator marked failed, name which component broke.

    Order matters: check the evaluator's own correctness FIRST, because a
    wrong verdict on a right answer means nothing downstream (including a
    trajectory check) can be trusted until the evaluator itself is fixed.
    """
    if not evaluator_verdict and exact_match(expected, raw_output):
        return "evaluator_bug"
    if required_tool not in tool_calls:
        return "instruction_bug"
    return "capability_gap"


# --------------------------------------------------------------------------
# Minimum-change ladder: escalate only on failure of the cheaper level
# --------------------------------------------------------------------------

LADDER: tuple[str, ...] = ("word", "clause", "sentence", "section", "tool", "model")


def escalate_fix_tier(current: str) -> str:
    """The next, more expensive tier -- callers must have already tried
    ``current`` and confirmed it failed before calling this."""
    try:
        idx = LADDER.index(current)
    except ValueError:
        raise ValueError(f"unknown ladder tier: {current!r}; must be one of {LADDER}") from None
    if idx + 1 >= len(LADDER):
        raise ValueError(f"already at the most expensive tier: {current!r}")
    return LADDER[idx + 1]


# --------------------------------------------------------------------------
# Retry ceiling: a named decision, not a silent fall-through
# --------------------------------------------------------------------------

RETRY_POLICIES: tuple[str, ...] = ("escalate_human", "escalate_model", "partial_with_flag", "fail")


def retry_ceiling_action(attempts: int, max_attempts: int, policy: str = "escalate_human") -> str:
    """"retry" while under the cap `autonomy-contracts.md` owns; once the
    cap fires, return the NAMED policy outcome -- never a silent retry loop
    and never an unnamed fall-through.
    """
    if attempts < max_attempts:
        return "retry"
    if policy not in RETRY_POLICIES:
        raise ValueError(f"unknown retry policy: {policy!r}; must be one of {RETRY_POLICIES}")
    return policy
