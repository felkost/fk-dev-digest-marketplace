"""Pure logic for a deterministic pass-off guardrail -- no agent framework,
no third-party imports. Kept separate from agent.py so tests/smoke_test.py
can exercise the guardrail and the decision point with a bare interpreter,
the same split every example in this plugin uses.

Anti-pattern this module exists to not repeat: the companion book's
`chapter_04/09_agent_passoff_guardrails.py` sets
`tripwire_triggered=result.final_output.is_sufficiently_detailed` -- no
negation -- so the guardrail trips (blocks the handoff) on a GOOD,
sufficiently-detailed plan and lets a thin one through. Its sibling,
`chapter_04/08_agent_guardrails.py`, has the same field with the required
`is False`, and the book's own prose matches `08`, not `09`. Two files in
one repo disagree about the polarity of the same field, and the wrong one
runs -- a demo where an inverted guardrail looks like it works, because the
flow just takes the fallback branch.

The structural fix below is not "remember the `is False`": it is not
exposing a positive-sense field (`is_sufficiently_detailed`) that a caller
must remember to negate at all. `PlanReview.should_block` is already
phrased as what it does to the flow -- block or not -- so there is nothing
left to invert.
"""

from __future__ import annotations

from dataclasses import dataclass

# Illustrative thresholds for this demo, not tuned values -- a real system
# calibrates these against labeled examples and the rubric/human agreement
# point where they peak (evaluate-optimize-models/references/evaluation.md),
# not a number picked once and trusted forever.
MIN_DETAIL_CHARS = 400
REQUIRED_SECTIONS = ("objective", "steps", "success criteria")


@dataclass(frozen=True)
class PlanReview:
    plan: str
    detail_chars: int
    missing_sections: tuple[str, ...]

    @property
    def should_block(self) -> bool:
        """True = block the handoff. Named for what it does to the flow, not
        for a positive-sense property a caller has to remember to negate --
        see the module docstring for the exact bug class that avoids.
        """
        return self.detail_chars < MIN_DETAIL_CHARS or bool(self.missing_sections)

    @property
    def reason(self) -> str:
        if not self.should_block:
            return "Plan is sufficiently detailed; handoff approved."
        problems = []
        if self.detail_chars < MIN_DETAIL_CHARS:
            problems.append(f"only {self.detail_chars} chars, need {MIN_DETAIL_CHARS}")
        if self.missing_sections:
            problems.append(f"missing section(s): {', '.join(self.missing_sections)}")
        return "Blocked: " + "; ".join(problems)


def review_plan(plan: str) -> PlanReview:
    """The guardrail. Deterministic: no model call, so it cannot be talked
    out of a verdict, and it needs nothing but the plan text itself -- no
    module-level state a concurrent call could contaminate (see
    `chapter_07/06_RAG_grounding_with_guardrails.py`'s `_last_context`
    global for the failure shape this design has no room for: it is
    overwritten by every search, so a multi-search answer grounds against
    only the last one).
    """
    lowered = plan.lower()
    missing = tuple(s for s in REQUIRED_SECTIONS if s not in lowered)
    return PlanReview(plan=plan, detail_chars=len(plan), missing_sections=missing)


@dataclass(frozen=True)
class PassoffOutcome:
    approved: bool
    review: PlanReview
    next_stage_input: str | None  # set only when approved -- never leaks a blocked plan forward


def attempt_passoff(plan: str) -> PassoffOutcome:
    """The one deterministic decision point: review, then gate. Nothing here
    is an LLM call -- see agent.py for where the two real agent calls
    (draft, then execute) sit around this function.
    """
    review = review_plan(plan)
    if review.should_block:
        return PassoffOutcome(approved=False, review=review, next_stage_input=None)
    return PassoffOutcome(approved=True, review=review, next_stage_input=plan)
