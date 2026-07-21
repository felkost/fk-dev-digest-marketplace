"""Serving: a two-agent pass-off flow gated by a deterministic guardrail.

Spends the user's OpenRouter credit when run -- both the draft and execute
nodes are model calls. guardrail_core.py's logic (the gate itself) is free
and tested offline; this file adds the two things that cannot be tested
offline: actual models on both sides of the handoff.

Run:  python agent.py "renewable energy adoption in commercial shipping"
"""

from __future__ import annotations

import os
import pathlib
import sys
from typing import TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from guardrail_core import PlanReview, attempt_passoff

# Anchored to this file's directory, not CWD, so `python agent.py` works from
# anywhere. Must run before the os.environ read in _require() below.
load_dotenv(pathlib.Path(__file__).parent / ".env")

DRAFT_PROMPT = """Write a short research plan for the topic below. Structure it
with three labeled sections: Objective, Steps, Success criteria. Be concrete
and detailed enough that someone else could execute it without asking you
anything further.

Topic: {topic}"""

EXECUTE_PROMPT = """You are the research agent. Carry out the plan below and
report findings in 3-5 sentences. Work from the plan as given; do not ask
for clarification.

Plan:
{plan}"""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in; "
            "never commit the filled-in file."
        )
    return value


class GraphState(TypedDict):
    topic: str
    plan: str
    review: PlanReview | None
    approved: bool
    result: str


def draft_node(state: GraphState, model: ChatOpenAI) -> dict:
    """The planner. A real model call."""
    response = model.invoke(DRAFT_PROMPT.format(topic=state["topic"]))
    return {"plan": response.content}


def guardrail_node(state: GraphState) -> dict:
    """The gate. Deterministic -- see guardrail_core.py for why, and for the
    inverted-guardrail bug this shape cannot reproduce.
    """
    outcome = attempt_passoff(state["plan"])
    return {"review": outcome.review, "approved": outcome.approved}


def route_after_guardrail(state: GraphState) -> str:
    return "execute" if state["approved"] else "blocked"


def execute_node(state: GraphState, model: ChatOpenAI) -> dict:
    """The research agent. A real model call, reached only on an approved
    plan -- this is the pass-off the guardrail gates.
    """
    response = model.invoke(EXECUTE_PROMPT.format(plan=state["plan"]))
    return {"result": response.content}


def blocked_node(state: GraphState) -> dict:
    """No model call: a blocked handoff is reported, not retried here. A
    production system could loop back to draft_node with the guardrail's
    reason as feedback -- that shape is reflexion-example.md's, not
    duplicated here.
    """
    review = state["review"]
    assert review is not None  # guardrail_node always runs before this
    return {"result": f"Handoff blocked before reaching the research agent: {review.reason}"}


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
    builder.add_node("draft", lambda s: draft_node(s, model))
    builder.add_node("guardrail", guardrail_node)
    builder.add_node("execute", lambda s: execute_node(s, model))
    builder.add_node("blocked", blocked_node)
    builder.add_edge(START, "draft")
    builder.add_edge("draft", "guardrail")
    builder.add_conditional_edges("guardrail", route_after_guardrail)
    builder.add_edge("execute", END)
    builder.add_edge("blocked", END)
    return builder.compile()


def main(topic: str) -> None:
    model = build_model()
    app = build_graph(model)
    result = app.invoke(
        {"topic": topic, "plan": "", "review": None, "approved": False, "result": ""}
    )
    review: PlanReview = result["review"]
    print(f"Guardrail: {'APPROVED' if result['approved'] else 'BLOCKED'} -- {review.reason}")
    print()
    print(result["result"])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "renewable energy adoption in commercial shipping")
