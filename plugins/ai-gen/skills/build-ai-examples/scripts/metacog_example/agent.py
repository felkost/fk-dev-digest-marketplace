"""Serving: request an implicit confidence signal from the model's own token
logprobs when the provider returns them, gate presentation on it, and demote
to a declared, honestly-labelled fallback when it does not -- rather than
either crashing or quietly presenting a guess as if it were the real signal.

Spends the user's OpenRouter credit when run -- each question is a model
call. Everything that actually decides whether to present (the gate, the
fallback labelling) lives in metacog_core.py, is deterministic code, and is
tested offline for free; this file supplies the one input that has to come
from a live model: token-level logprobs, which OpenRouter documents
(`logprobs`/`top_logprobs`) without a published per-model support matrix --
so this file also doubles as the demonstration that graceful degradation is
not hypothetical.

Run:  python agent.py
"""

from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from metacog_core import ConfidenceState, check_confidence_gate, resolve_confidence

# Anchored to this file's directory, not CWD, so `python agent.py` works from
# anywhere. Must run before the os.environ read in _require() below.
load_dotenv(pathlib.Path(__file__).parent / ".env")

# A conservative, declared fallback -- used only when the model/provider
# returns no logprobs at all, never silently swapped in as if it were one.
FALLBACK_CONFIDENCE = 0.5

QUESTIONS = [
    "What is the capital of France?",
    "What was the exact attendance figure at the first Solvay Conference in 1911?",
]


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in; "
            "never commit the filled-in file."
        )
    return value


def _token_logprobs(message) -> list[float]:
    """Pull per-token logprobs out of a langchain-openai response, if present.

    Absent, empty, or malformed logprobs all fall through to an empty list --
    resolve_confidence() treats that identically to "not offered", which is
    the graceful-degradation path this example exists to demonstrate.
    """
    payload = (message.response_metadata or {}).get("logprobs") or {}
    content = payload.get("content") or []
    return [item["logprob"] for item in content if "logprob" in item]


def main() -> None:
    model = ChatOpenAI(
        model=os.environ.get("CHAT_MODEL", "openai/gpt-4o-mini"),
        api_key=_require("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        model_kwargs={"logprobs": True, "top_logprobs": 1},
    )

    for question in QUESTIONS:
        reply = model.invoke(question)
        logprobs = _token_logprobs(reply)
        estimate = resolve_confidence(logprobs or None, fallback=FALLBACK_CONFIDENCE)
        decision = check_confidence_gate(ConfidenceState(value=estimate.value))

        print(f"\nQ: {question}")
        print(f"A: {reply.content}")
        print(
            f"confidence: {estimate.value:.3f} (source={estimate.source}) "
            f"-> {decision.value}"
        )


if __name__ == "__main__":
    main()
