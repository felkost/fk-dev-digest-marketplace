"""Pure-logic core of a Layer-2 agent loop harness.

Implements the layered stop gate that `design-agent-architecture/references/
agent-loop.md` specifies — iteration cap AND cost cap AND wall-clock cap AND a
stagnation detector — plus a de-duplicated follow-up queue with an explicit
breadth/depth parameter, tool-output offloading to an id-keyed log, and an
explorer/writer separation enforced by the harness rather than the prompt.

Everything here is stdlib-only and free of import-time side effects, so the
smoke test can import and exercise it offline. Model wiring lives in
``agent.py`` and is never imported from here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# --------------------------------------------------------------------------
# Stagnation detection
# --------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-zа-яіїєґ0-9']+", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def summary_overlap(a: str, b: str) -> float:
    """Jaccard overlap of the word sets of two iteration summaries, in [0, 1].

    A deliberate simplification: the production upgrade is embedding cosine
    (semantic overlap), but the *mechanism* — compare consecutive summaries,
    stop above a threshold — is identical, and the word-set version is
    computable offline. The reference documents why the two mechanisms and
    their thresholds must not be mixed up.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0  # two empty summaries are maximally stagnant, not novel
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class StagnationDetector:
    """Fires when consecutive summaries overlap above ``threshold``."""

    threshold: float = 0.8
    last_summary: str | None = None
    fired: bool = False

    def observe(self, summary: str) -> bool:
        """Record an iteration summary; return True if stagnation fired."""
        if self.last_summary is not None:
            if summary_overlap(self.last_summary, summary) >= self.threshold:
                self.fired = True
        self.last_summary = summary
        return self.fired


# --------------------------------------------------------------------------
# Follow-up queue: de-duplicated, with an explicit breadth/depth parameter
# --------------------------------------------------------------------------


def _normalize_question(q: str) -> str:
    return " ".join(_WORD_RE.findall(q.lower()))


@dataclass
class FollowUpQueue:
    """A queue that refuses re-entry of anything it has ever held.

    ``order`` is the named breadth/depth switch from agent-loop.md:
    ``"breadth"`` pops from the front (FIFO — explore the original question's
    facets), ``"depth"`` pops from the back (LIFO — drill into the most
    recently opened thread). It is a constructor argument precisely so the
    choice is a recorded decision, not an accident of ``list.pop()``.
    """

    order: str = "breadth"
    _items: list[str] = field(default_factory=list)
    _seen: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.order not in ("breadth", "depth"):
            raise ValueError(f"order must be 'breadth' or 'depth', got {self.order!r}")

    def push(self, question: str) -> bool:
        """Add a question unless an equivalent one was ever queued before."""
        key = _normalize_question(question)
        if not key or key in self._seen:
            return False
        self._seen.add(key)
        self._items.append(question)
        return True

    def pop(self) -> str | None:
        if not self._items:
            return None
        return self._items.pop(0) if self.order == "breadth" else self._items.pop()

    def __len__(self) -> int:
        return len(self._items)


# --------------------------------------------------------------------------
# Tool-output offloading
# --------------------------------------------------------------------------


@dataclass
class OffloadLog:
    """Stores raw tool output; the context gets back only an id + digest."""

    digest_chars: int = 160
    _records: dict[str, str] = field(default_factory=dict)

    def store(self, raw: str) -> tuple[str, str]:
        rec_id = f"obs-{len(self._records) + 1:04d}"
        self._records[rec_id] = raw
        digest = " ".join(raw.split())[: self.digest_chars]
        return rec_id, digest

    def fetch(self, rec_id: str) -> str:
        """Originals stay addressable — compaction must not orphan them."""
        return self._records[rec_id]

    def __len__(self) -> int:
        return len(self._records)


# --------------------------------------------------------------------------
# The layered stop gate
# --------------------------------------------------------------------------


@dataclass
class LoopBudget:
    max_iterations: int = 8
    max_cost: float = 1.0
    max_wall_clock_s: float = 300.0


@dataclass
class LoopState:
    iteration: int = 0
    cost_spent: float = 0.0
    elapsed_s: float = 0.0
    goal_satisfied: bool = False


def stop_reason(
    state: LoopState,
    budget: LoopBudget,
    queue: FollowUpQueue,
    stagnation: StagnationDetector,
) -> str | None:
    """The conjunction-of-families gate from agent-loop.md.

    Returns the *name* of the first stop family that fires, or None to
    continue — because "why did it stop" is the first debugging question,
    the reason is data, not a boolean.
    """
    if state.goal_satisfied:
        return "goal_predicate"
    if state.iteration >= budget.max_iterations:
        return "iteration_cap"
    if state.cost_spent >= budget.max_cost:
        return "cost_cap"
    if state.elapsed_s >= budget.max_wall_clock_s:
        return "wall_clock_cap"
    if stagnation.fired:
        return "stagnation"
    if len(queue) == 0:
        return "queue_exhausted"
    return None


# --------------------------------------------------------------------------
# The loop: explorer and writer are separate callables by construction
# --------------------------------------------------------------------------


@dataclass
class LoopResult:
    report: str
    stop: str
    iterations: int
    cost_spent: float
    findings: list[tuple[str, str, str]]  # (question, obs_id, summary)


def run_loop(
    seed_questions: list[str],
    explore_fn,
    write_fn,
    *,
    budget: LoopBudget | None = None,
    order: str = "breadth",
    stagnation_threshold: float = 0.8,
    goal_predicate=None,
    clock=None,
) -> LoopResult:
    """Run the Layer-2 loop.

    ``explore_fn(question) -> (raw_observation, summary, follow_ups, cost)``
    gathers; ``write_fn(findings) -> str`` synthesizes. The explorer never
    sees the report and the writer never sees a raw observation that was not
    accumulated into findings — the state store is the only interface between
    the two roles. ``clock`` is injectable so wall-clock tests are
    deterministic; it defaults to a counter that never fires the cap.
    """
    budget = budget or LoopBudget()
    queue = FollowUpQueue(order=order)
    stagnation = StagnationDetector(threshold=stagnation_threshold)
    log = OffloadLog()
    state = LoopState()
    findings: list[tuple[str, str, str]] = []

    for q in seed_questions:
        queue.push(q)

    t0 = clock() if clock else 0.0
    while True:
        reason = stop_reason(state, budget, queue, stagnation)
        if reason is not None:
            break
        question = queue.pop()
        raw, summary, follow_ups, cost = explore_fn(question)
        rec_id, _digest = log.store(raw)
        findings.append((question, rec_id, summary))
        state.iteration += 1
        state.cost_spent += cost
        state.elapsed_s = (clock() - t0) if clock else 0.0
        stagnation.observe(summary)
        for fu in follow_ups:
            queue.push(fu)
        if goal_predicate is not None and goal_predicate(findings):
            state.goal_satisfied = True

    report = write_fn(findings)
    return LoopResult(
        report=report,
        stop=reason,
        iterations=state.iteration,
        cost_spent=round(state.cost_spent, 6),
        findings=findings,
    )
