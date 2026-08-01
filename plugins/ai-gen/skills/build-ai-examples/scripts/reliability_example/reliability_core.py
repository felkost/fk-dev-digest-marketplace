"""Pure-logic core of a serving-reliability harness.

Implements the pieces `deploy-ai-environments/references/serving-release.md`
specifies: a time-budget + fallback + circuit-breaker ladder as a state
machine, and an idempotency cache keyed by an explicit operation id --
contrasted against the argument-hash-only cache from
`chapter_08/06_idempotent_key_example.py`, which silently collapses two
distinct operations that happen to share arguments into one execution.

Everything here is stdlib-only and free of import-time side effects, so the
smoke test can import and exercise it offline. Model wiring lives in
``agent.py`` and is never imported from here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum


# --------------------------------------------------------------------------
# Circuit breaker
# --------------------------------------------------------------------------


class BreakerState(Enum):
    CLOSED = "closed"       # normal: calls pass through
    OPEN = "open"            # tripped: calls are shed without trying
    HALF_OPEN = "half_open"  # cooldown elapsed: one probe call allowed


@dataclass
class CircuitBreaker:
    """Trips after ``failure_threshold`` consecutive failures; sheds load
    while open; allows exactly one probe after ``cooldown`` ticks.

    ``now`` is an injectable clock (a plain counter by default) so tests are
    deterministic -- the same pattern `agent-loop.md`'s injectable clock
    uses, for the same reason.
    """

    failure_threshold: int = 3
    cooldown: int = 5
    state: BreakerState = BreakerState.CLOSED
    _consecutive_failures: int = 0
    _opened_at: int | None = None

    def allow(self, now: int) -> bool:
        if self.state == BreakerState.OPEN:
            if self._opened_at is not None and now - self._opened_at >= self.cooldown:
                self.state = BreakerState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self.state = BreakerState.CLOSED
        self._opened_at = None

    def record_failure(self, now: int) -> None:
        self._consecutive_failures += 1
        if self.state == BreakerState.HALF_OPEN:
            # the probe failed -- reopen immediately, don't wait to re-count
            self.state = BreakerState.OPEN
            self._opened_at = now
            return
        if self._consecutive_failures >= self.failure_threshold:
            self.state = BreakerState.OPEN
            self._opened_at = now


# --------------------------------------------------------------------------
# The reliability ladder: budget -> fallback -> circuit breaker -> degrade
# --------------------------------------------------------------------------


@dataclass
class LadderResult:
    outcome: str          # "primary" | "fallback:<name>" | "degraded" | "circuit_open"
    value: object
    attempts: tuple[str, ...]


def run_ladder(
    primary,
    fallbacks: list[tuple[str, object]],
    *,
    breaker: CircuitBreaker,
    time_budget: float,
    now: float,
    degraded_value: object = None,
) -> LadderResult:
    """Try ``primary`` under the breaker and time budget; on failure, walk
    ``fallbacks`` in order; if every rung fails, return ``degraded_value``
    with outcome "degraded" -- the ladder always returns SOMETHING usable,
    never a raw exception surfaced to a caller.

    ``primary`` and each fallback callable take no arguments and return
    ``(elapsed: float, value)`` or raise. ``now`` is a starting tick used
    only to evaluate the breaker's cooldown, not wall-clock time.
    """
    attempts: list[str] = []

    if not breaker.allow(now):
        return LadderResult(outcome="circuit_open", value=degraded_value, attempts=("circuit_open",))

    attempts.append("primary")
    try:
        elapsed, value = primary()
        if elapsed > time_budget:
            raise TimeoutError(f"primary exceeded budget: {elapsed} > {time_budget}")
        breaker.record_success()
        return LadderResult(outcome="primary", value=value, attempts=tuple(attempts))
    except Exception:
        breaker.record_failure(now)

    for name, fallback in fallbacks:
        attempts.append(f"fallback:{name}")
        try:
            elapsed, value = fallback()
            if elapsed > time_budget:
                raise TimeoutError(f"{name} exceeded budget: {elapsed} > {time_budget}")
            return LadderResult(outcome=f"fallback:{name}", value=value, attempts=tuple(attempts))
        except Exception:
            continue

    attempts.append("degraded")
    return LadderResult(outcome="degraded", value=degraded_value, attempts=tuple(attempts))


# --------------------------------------------------------------------------
# Idempotency: correct (operation id) vs the argument-hash anti-pattern
# --------------------------------------------------------------------------


def _canonical(name: str, args: dict) -> str:
    return json.dumps({"name": name, "args": args}, sort_keys=True, separators=(",", ":"))


@dataclass
class IdempotencyCache:
    """Correct: keyed by a caller-supplied ``operation_id``. Two calls with
    the SAME operation_id return the cached result without re-executing;
    two calls with DIFFERENT operation_ids always both execute, even if
    their arguments are identical.
    """

    _store: dict[str, object] = field(default_factory=dict)

    def call(self, operation_id: str, execute_fn) -> tuple[object, bool]:
        """Returns (result, was_cached)."""
        if operation_id in self._store:
            return self._store[operation_id], True
        result = execute_fn()
        self._store[operation_id] = result
        return result, False


@dataclass
class ArgHashCache:
    """The chapter_08/06_idempotent_key_example.py anti-pattern, reproduced
    on purpose: the key is sha256(name + args) with NO operation id. Two
    distinct operations that happen to share arguments collide -- the
    second call silently returns the first's result instead of executing.
    Kept here only so the harness can demonstrate the contrast; do not use
    this shape in real code (see serving-release.md).
    """

    _store: dict[str, object] = field(default_factory=dict)

    def call(self, name: str, args: dict, execute_fn) -> tuple[object, bool]:
        key = hashlib.sha256(_canonical(name, args).encode("utf-8")).hexdigest()
        if key in self._store:
            return self._store[key], True
        result = execute_fn()
        self._store[key] = result
        return result, False
