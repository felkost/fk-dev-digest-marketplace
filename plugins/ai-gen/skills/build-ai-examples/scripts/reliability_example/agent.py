"""Serving: run the reliability ladder with a real primary and fallback model.

Spends the user's OpenRouter credit when run -- both the primary and the
fallback are model calls. Everything guaranteed about the ladder (the time
budget, the circuit breaker, the fallback order, always returning something
usable) lives in reliability_core.py, is deterministic code, and is tested
offline for free; this file adds only what cannot be tested offline -- two
real models.

Run:  python agent.py
"""

from __future__ import annotations

import os
import pathlib
import time

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from reliability_core import CircuitBreaker, run_ladder

# Anchored to this file's directory, not CWD, so `python agent.py` works from
# anywhere. Must run before the os.environ read in _require() below.
load_dotenv(pathlib.Path(__file__).parent / ".env")

QUESTION = "In one short sentence, what does a circuit breaker do in a distributed system?"


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in; "
            "never commit the filled-in file."
        )
    return value


def main() -> None:
    api_key = _require("OPENROUTER_API_KEY")
    primary_model = ChatOpenAI(
        model=os.environ.get("CHAT_MODEL", "openai/gpt-4o-mini"),
        api_key=api_key, base_url="https://openrouter.ai/api/v1",
    )
    fallback_model = ChatOpenAI(
        model=os.environ.get("FALLBACK_MODEL", "openai/gpt-4o-mini"),
        api_key=api_key, base_url="https://openrouter.ai/api/v1",
    )

    def call_primary():
        t0 = time.monotonic()
        reply = primary_model.invoke(QUESTION).content
        return time.monotonic() - t0, reply

    def call_fallback():
        t0 = time.monotonic()
        reply = fallback_model.invoke(QUESTION).content
        return time.monotonic() - t0, reply

    breaker = CircuitBreaker(failure_threshold=3, cooldown=5)
    result = run_ladder(
        call_primary,
        fallbacks=[("secondary_model", call_fallback)],
        breaker=breaker,
        time_budget=15.0,  # seconds -- generous for a demo, tight for production
        now=time.monotonic(),
        degraded_value="Sorry, I couldn't get an answer right now. Please try again shortly.",
    )

    print(f"outcome: {result.outcome} (attempts: {' -> '.join(result.attempts)})")
    print(result.value)


if __name__ == "__main__":
    main()
