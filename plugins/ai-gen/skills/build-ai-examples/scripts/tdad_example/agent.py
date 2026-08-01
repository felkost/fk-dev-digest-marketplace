"""Serving: run a real solver N times through the TDAD harness.

Spends the user's OpenRouter credit when run -- the solver is a model call.
Everything guaranteed about the harness (the normalizing evaluator, the
grounding check, N-repeat benchmarking, defect localization, the
minimum-change ladder, the retry-ceiling policy) lives in harness_core.py,
is deterministic code, and is tested offline for free; this file adds only
what cannot be tested offline -- an actual model as the solver.

Run:  python agent.py
"""

from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from harness_core import (
    AccumulatingContext,
    classify_failure,
    exact_match,
    is_grounded,
    run_benchmark,
)

# Anchored to this file's directory, not CWD, so `python agent.py` works from
# anywhere. Must run before the os.environ read in _require() below.
load_dotenv(pathlib.Path(__file__).parent / ".env")

SOLVER_PROMPT = """Answer using ONLY the passages below. State the answer as
a single short line, nothing else.

Passages:
{context}

Question: {question}"""

QUESTION = "What does RRF stand for and what does it combine?"
EXPECTED = "Reciprocal Rank Fusion"
PASSAGES = (
    "RRF (Reciprocal Rank Fusion) is a method for combining ranked lists "
    "from multiple retrieval systems by summing the reciprocal of each "
    "item's rank across the lists.",
)


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in; "
            "never commit the filled-in file."
        )
    return value


def main() -> None:
    model = ChatOpenAI(
        model=os.environ.get("CHAT_MODEL", "openai/gpt-4o-mini"),
        api_key=_require("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.7,  # nonzero on purpose -- N-repeat only tells you
        # anything if the solver can actually vary between runs.
    )

    context = AccumulatingContext()
    for p in PASSAGES:
        context.add(p)

    def solve_once() -> bool:
        reply = model.invoke(
            SOLVER_PROMPT.format(context="\n".join(context.snapshot()), question=QUESTION)
        ).content.strip()
        passed = exact_match(EXPECTED, reply) or EXPECTED.lower() in reply.lower()
        grounded = is_grounded(reply, context.snapshot())
        if not passed:
            verdict = classify_failure(
                expected=EXPECTED,
                raw_output=reply,
                evaluator_verdict=passed,
                tool_calls=["retrieve"],  # this demo always "retrieves" via PASSAGES
                required_tool="retrieve",
            )
            print(f"  red: {reply!r} -> {verdict}, grounded={grounded}")
        return passed and grounded

    result = run_benchmark(solve_once, n=5)
    print(f"pass_rate={result.pass_rate:.2f} ({result.passes}/{result.n})")


if __name__ == "__main__":
    main()
