"""Serving: a Layer-2 research loop with a real model as the explorer.

Spends the user's OpenRouter credit when run -- explore and write are model
calls. Everything guaranteed about the loop (the layered stop gate, queue
de-duplication, offloading, the explorer/writer split) lives in
loop_core.py, is deterministic code, and is tested offline for free; this
file adds only what cannot be tested offline -- an actual model behind
``explore_fn`` and ``write_fn``.

Run:  python agent.py
"""

from __future__ import annotations

import os
import pathlib
import time

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from loop_core import LoopBudget, run_loop

# Anchored to this file's directory, not CWD, so `python agent.py` works from
# anywhere. Must run before the os.environ read in _require() below.
load_dotenv(pathlib.Path(__file__).parent / ".env")

EXPLORE_PROMPT = """You are the EXPLORER in a research loop. Investigate ONE
question and nothing else. Return exactly three blocks:

ANSWER: <what you found, 3-6 sentences>
SUMMARY: <one sentence stating the key finding>
FOLLOW_UPS: <up to 2 new questions, one per line, or NONE>

Question: {question}"""

WRITE_PROMPT = """You are the WRITER. You did not do the research; synthesize
a short report (under 200 words) STRICTLY from the findings below. Cite
finding ids in square brackets, e.g. [obs-0001].

Findings:
{findings_block}"""


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
        temperature=0,
    )

    def explore_fn(question: str):
        reply = model.invoke(EXPLORE_PROMPT.format(question=question)).content
        answer, summary, follow_ups = reply, "", []
        for line in reply.splitlines():
            if line.startswith("SUMMARY:"):
                summary = line.removeprefix("SUMMARY:").strip()
        in_fu = False
        for line in reply.splitlines():
            if line.startswith("FOLLOW_UPS:"):
                in_fu = True
                rest = line.removeprefix("FOLLOW_UPS:").strip()
                if rest and rest.upper() != "NONE":
                    follow_ups.append(rest)
            elif in_fu and line.strip() and line.strip().upper() != "NONE":
                follow_ups.append(line.strip())
        # A flat per-call cost stands in for token accounting; production code
        # reads usage from the response and prices it per model.
        return answer, summary or answer[:120], follow_ups[:2], 0.01

    def write_fn(findings):
        block = "\n".join(
            f"[{rec_id}] {question} -> {summary}"
            for question, rec_id, summary in findings
        )
        if not block:
            return "No findings were gathered."
        return model.invoke(WRITE_PROMPT.format(findings_block=block)).content

    result = run_loop(
        seed_questions=[
            "What is Reciprocal Rank Fusion and where is it used?",
        ],
        explore_fn=explore_fn,
        write_fn=write_fn,
        budget=LoopBudget(max_iterations=4, max_cost=0.05, max_wall_clock_s=120),
        order="breadth",
        clock=time.monotonic,
    )

    print(f"stopped by: {result.stop} after {result.iterations} iteration(s), "
          f"cost {result.cost_spent}")
    print("--- report ---")
    print(result.report)


if __name__ == "__main__":
    main()
