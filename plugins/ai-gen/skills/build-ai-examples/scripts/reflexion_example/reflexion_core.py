"""Pure logic for a solver-critic Reflexion loop -- no `langgraph`, no model
client, no third-party imports. Kept separate from agent.py so
tests/smoke_test.py can exercise the loop's control flow (stopping, hint
accumulation, attempt cap) and the anti-oracle checker with a bare
interpreter, the same split rag_example and mcp_example use.

Anti-pattern this module exists to not repeat: the companion book's
`chapter_05/03_reflexion_agents.py` sets a module-level `TARGET_DAYS = "26"`
and checks `TARGET_DAYS in answer` -- a substring test a longer number like
"126" satisfies by accident, and a global the code itself leaves stale when
`problem` is reassigned to a different puzzle before running (the second
condition, `"correct" in answer.lower()`, is left over from the first
puzzle and is satisfied by the word "incorrect"). Both bugs share one root
cause: the check was not derived from the task it was meant to grade.
`Task` below makes that class of bug structurally harder to write, not just
easier to avoid -- the prompt and its checker are bound in one constructor
call, so there is no second global for a later task to inherit by accident.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

# --------------------------------------------------------------------------- #
# A task carries its own checker -- never a shared/global predicate.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    feedback: str


@dataclass(frozen=True)
class Task:
    """A checkable task. `check` is bound at construction, together with the
    prompt it grades -- see the module docstring for why that binding is the
    point, not an implementation detail."""

    prompt: str
    check: Callable[[str], CheckResult]


def _extract_last_int(text: str) -> int | None:
    """Pull the last standalone integer out of free text.

    `re.findall(r"-?\\d+", ...)` matches whole digit runs: inside "126" it
    matches "126", never "26". That is the fix for `TARGET_DAYS in answer` --
    comparing extracted *numbers*, not testing string containment, is what
    stops a longer number from satisfying a shorter one by accident.
    """
    matches = re.findall(r"-?\d+", text)
    return int(matches[-1]) if matches else None


def make_arithmetic_task(prompt: str, expected: int) -> Task:
    """Build a Task whose checker is derived from `expected` in this same
    call -- the fix for the book's demo, where `TARGET_DAYS` is a
    module-level constant checked against by whichever `problem` happens to
    be assigned when the script runs, including one it already overwrote.
    Two calls to this function produce two independently-checkable tasks;
    see smoke_test.py's "predicate does not leak across tasks" check.
    """

    def check(answer: str) -> CheckResult:
        found = _extract_last_int(answer)
        if found is None:
            return CheckResult(
                False, "No number found in the answer. State the final count explicitly."
            )
        if found == expected:
            return CheckResult(True, "Correct.")
        direction = "too high" if found > expected else "too low"
        return CheckResult(False, f"{found} is {direction}. Recompute from the stated quantities.")

    return Task(prompt=prompt, check=check)


# --------------------------------------------------------------------------- #
# The loop itself.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Attempt:
    number: int
    answer: str
    passed: bool
    feedback: str


@dataclass(frozen=True)
class ReflexionOutcome:
    attempts: tuple[Attempt, ...]
    succeeded: bool
    stop_reason: str  # "solved" | "attempt_cap"

    @property
    def final_answer(self) -> str | None:
        return self.attempts[-1].answer if self.attempts else None


def should_stop(*, passed: bool, attempt_number: int, max_attempts: int) -> bool:
    """The loop's one stopping rule. Shared by run_reflexion's own loop below
    AND by agent.py's LangGraph conditional edge, so the graph's routing and
    the pure loop can never quietly disagree about when to stop -- one
    decision function, not two copies that drift apart.
    """
    return passed or attempt_number >= max_attempts


def run_reflexion(
    task: Task,
    solve: Callable[[str, tuple[str, ...]], str],
    max_attempts: int = 3,
) -> ReflexionOutcome:
    """Run the solver-critic loop as a pure state machine.

    `solve` is injected -- `(prompt, accumulated_hints) -> answer` -- so this
    function runs identically against a scripted stub in tests and against a
    real model call in agent.py. `task.check` is the critic: deterministic,
    not an LLM asked to remember a target it was handed directly. Nothing
    here imports a model client or langgraph; this is the part smoke_test.py
    can run with a bare interpreter.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    hints: list[str] = []
    attempts: list[Attempt] = []
    number = 0
    while True:
        number += 1
        answer = solve(task.prompt, tuple(hints))
        result = task.check(answer)
        attempts.append(Attempt(number, answer, result.passed, result.feedback))
        if should_stop(passed=result.passed, attempt_number=number, max_attempts=max_attempts):
            stop_reason = "solved" if result.passed else "attempt_cap"
            return ReflexionOutcome(tuple(attempts), result.passed, stop_reason)
        # Hint accumulation: exactly one new item per failed attempt, fed to
        # the next solve() call as the growing tail of `hints`.
        hints.append(result.feedback)
