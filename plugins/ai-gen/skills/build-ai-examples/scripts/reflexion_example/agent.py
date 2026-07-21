"""Serving: the solver-critic Reflexion loop as a real LangGraph graph.

Spends the user's OpenRouter credit when run -- the solver node is a model
call. The loop's control flow (stopping, hint accumulation, attempt cap) is
tested for free and offline against reflexion_core.py directly; this file
only adds the one thing that cannot be tested offline, an actual model.

Run:  python agent.py
"""

from __future__ import annotations

import os
import pathlib
from typing import TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from reflexion_core import Attempt, Task, make_arithmetic_task, should_stop

# Anchored to this file's directory, not CWD, so `python agent.py` works from
# anywhere. Must run before the os.environ read in _require() below.
load_dotenv(pathlib.Path(__file__).parent / ".env")

SOLVER_PROMPT = """Solve the word problem below. Show your work briefly, then
state the final answer as a single number on its own, e.g. "Final answer: 42".

Problem:
{prompt}

{hint_block}"""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in; "
            "never commit the filled-in file."
        )
    return value


class GraphState(TypedDict):
    task: Task
    hints: tuple[str, ...]
    attempts: list[Attempt]
    pending_answer: str
    max_attempts: int


def _format_hints(hints: tuple[str, ...]) -> str:
    if not hints:
        return ""
    body = "\n".join(f"- {h}" for h in hints)
    return f"Feedback on previous attempts (use it -- do not repeat the same mistake):\n{body}"


def solve_node(state: GraphState, model: ChatOpenAI) -> dict:
    """The solver. A real model call -- the only node that spends money."""
    message = SOLVER_PROMPT.format(
        prompt=state["task"].prompt, hint_block=_format_hints(state["hints"])
    )
    response = model.invoke(message)
    return {"pending_answer": response.content}


def check_node(state: GraphState) -> dict:
    """The critic. Deterministic on purpose -- see reflexion-example.md for
    why an external, checkable verifier is the stronger design, not a
    compromise: it cannot be talked out of a wrong answer, and it needs no
    memorized target the way the book's demo hands its critic one directly.
    """
    result = state["task"].check(state["pending_answer"])
    number = len(state["attempts"]) + 1
    attempt = Attempt(number, state["pending_answer"], result.passed, result.feedback)
    new_hints = state["hints"] if result.passed else state["hints"] + (result.feedback,)
    return {"attempts": [*state["attempts"], attempt], "hints": new_hints}


def route_after_check(state: GraphState) -> str:
    """Reuses should_stop from reflexion_core -- the same predicate
    run_reflexion's own offline loop uses -- so the graph's routing and the
    tested pure loop cannot silently disagree about when to stop.
    """
    last = state["attempts"][-1]
    if should_stop(passed=last.passed, attempt_number=last.number, max_attempts=state["max_attempts"]):
        return END
    return "solve"


def build_model() -> ChatOpenAI:
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=_require("OPENROUTER_API_KEY"),
        model=os.environ.get("CHAT_MODEL", "openai/gpt-4o-mini"),
        temperature=0,
        timeout=30,
    )


def build_graph(model: ChatOpenAI):
    builder = StateGraph(GraphState)
    builder.add_node("solve", lambda s: solve_node(s, model))
    builder.add_node("check", check_node)
    builder.add_edge(START, "solve")
    builder.add_edge("solve", "check")
    builder.add_conditional_edges("check", route_after_check)
    return builder.compile()


def main(task: Task, max_attempts: int = 3) -> None:
    model = build_model()
    app = build_graph(model)
    result = app.invoke(
        {"task": task, "hints": (), "attempts": [], "pending_answer": "", "max_attempts": max_attempts},
        # Belt-and-braces cap on top of should_stop -- an agent that can loop
        # can loop past a logic bug too.
        config={"recursion_limit": max_attempts * 2 + 2},
    )
    attempts: list[Attempt] = result["attempts"]
    for a in attempts:
        print(f"[attempt {a.number}] {a.answer!r} -> {'PASS' if a.passed else 'FAIL'}: {a.feedback}")
    verdict = "solved" if attempts and attempts[-1].passed else "did not solve within the attempt cap"
    print(f"\n{verdict} in {len(attempts)} attempt(s).")


if __name__ == "__main__":
    demo_task = make_arithmetic_task(
        "A ferry carries 42 cars per trip and makes 6 trips a day. "
        "How many cars does it carry in 5 days?",
        expected=42 * 6 * 5,
    )
    main(demo_task)
