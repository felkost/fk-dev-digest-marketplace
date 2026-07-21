# Worked example: a deterministic pass-off guardrail (`guardrail_example`)

Runnable code lives in `scripts/guardrail_example/`. A pure `guardrail_core.py` reviews a plan and
decides, deterministically, whether it may hand off to a second agent; `agent.py` wires that gate
into a real LangGraph `StateGraph` between two real model calls. The concepts — handoff failure
modes, the guardrail cost ladder, callbacks-vs-guardrails — are in
`design-agent-architecture/references/architectures.md` and
`evaluate-optimize-models/references/agent-ops.md`; this file covers the build.

## Contents

- Run it
- Layout
- Decisions worth explaining
- What the tests pin
- Production deltas

## Run it

```bash
cd scripts/guardrail_example
pip install -r requirements.txt
cp .env.example .env          # fill in OPENROUTER_API_KEY -- get one at openrouter.ai
python agent.py "renewable energy adoption in commercial shipping"
```

`guardrail_core.py` needs no key at all — the review and the decision point are plain Python, not
model calls. Only `agent.py` spends OpenRouter credit, and only when you run it (two calls: draft,
and — only if the guardrail approves — execute).

## Layout

```
scripts/guardrail_example/
├── guardrail_core.py   # pure: PlanReview, the guardrail, the decision point
├── agent.py             # framework: LangGraph graph, both model calls, CLI entry
├── .env.example
└── requirements.txt
```

## Decisions worth explaining

### 1. The guardrail's own field is already phrased as block/pass — nothing left to negate

The companion book's `chapter_04/09_agent_passoff_guardrails.py` sets
`tripwire_triggered=result.final_output.is_sufficiently_detailed` — no `is False`. The guardrail
therefore trips (blocks the handoff) on a *good*, sufficiently-detailed plan and waves a thin one
through. Its sibling, `chapter_04/08_agent_guardrails.py`, has the same field with the required
negation, and the book's own prose matches `08`, not `09` — two files in one repository disagree
about the polarity of the same field, and the wrong one is the one with the chapter's exercise
number. The fix here is not "remember the `is False`": `PlanReview.should_block` is named for what
it does to the flow, so there is no positive-sense field left for a caller to invert. See
`tests/smoke_test.py`'s polarity check below for what would have caught `09` outright.

### 2. No module-level state — the fix for a second, subtler bug in the same book

`chapter_07/06_RAG_grounding_with_guardrails.py` has the *correct* polarity
(`tripwire_triggered=result.is_answer_grounded is False`) but a module-level `_last_context`
global, written by every search and read by an optional tool call — so a two-search answer grounds
against only the *last* search, and `get_last_context()` returns `"No context available."` instead
of failing when nothing was ever searched. `guardrail_core.review_plan` takes the plan as its only
argument and keeps no state between calls, so this failure shape has nowhere to live. This is the
same design move `reflexion-example.md` makes with `Task.check` — bind behavior to its input at
the call, not to something a previous call left lying around at module scope.

### 3. Two real model calls, one deterministic gate between them

`agent.py`'s graph is `draft` (a real model call: the planner) → `guardrail` (pure) → a conditional
edge → `execute` (a real model call: the research agent, reached only on an approved plan) or
`blocked` (no model call at all). This mirrors the book's own two-agent shape — a planner handing
off to a research agent — rather than collapsing it into one call, because the guardrail's whole
point is gating a genuine *hand-off between agents*, not validating a single agent's own output.

### 4. The routing function returns literal node names, the same verified idiom as `reflexion_example`

`route_after_guardrail` returns `"execute"` or `"blocked"` directly, matching the node names
registered with `add_node`, and needs no `path_map` — the same current LangGraph idiom
`reflexion-example.md` verified against the framework's own docs. `guardrail_node` and
`route_after_guardrail` are the whole decision point; `draft_node` and `execute_node` are the only
places money gets spent.

## What the tests pin

`python tests/smoke_test.py` — this file's share is checks 35-43. All offline, bare interpreter,
no key/network/langgraph installed:

| Checks | What breaks if they go |
|---|---|
| Files exist; `guardrail_core` imports; imports are **stdlib-only** | The guardrail stops being testable without a full install |
| The polarity test — blocks a thin plan AND approves a detailed one | The exact `chapter_04/09` bug: a guardrail that only ever fires (or never fires) looks correct in a demo |
| A long-enough plan missing one required section still blocks, named specifically | Length alone silently becoming "detailed enough" |
| `attempt_passoff` never sets `next_stage_input` on a blocked plan | A blocked plan quietly reaching the next agent anyway |
| Interleaved reviews of different plans never contaminate each other | The `chapter_07/06` failure shape — shared state leaking between calls |
| `.env.example` covers every variable `agent.py` reads; ships no filled-in secret | Silent misconfiguration or a leaked key |

**The LangGraph wiring itself was run for real, not only reviewed** — `build_graph()` compiled and
`.invoke()`d against a scripted stub standing in for the model (`.invoke(message) -> object with
.content`, no API key, no network). Two cases, and the second is a stronger check than it first
looks: the blocked case supplies the stub with only **one** scripted answer, for the draft call —
if `execute_node` were reached despite the block (the exact failure a polarity bug produces), the
second `model.invoke()` would raise `StopIteration` with no second answer queued, so the graph
either returns the correct blocked result or fails loudly; it cannot silently do the wrong thing.
**Not run this round, and it needs the user's OpenRouter key to change that:** the real draft and
execute calls in `agent.py`.

## Production deltas (state these with the example)

This is a teaching scaffold. Before it carries real traffic:

- **The rubric is a length-and-section heuristic.** A real deployment's guardrail checks the
  property that actually matters for the handoff — a schema validating, required approvals
  present, a budget not exceeded — calibrated against labeled examples at the threshold where
  rubric/human agreement peaks (`evaluate-optimize-models/references/evaluation.md`), not a round
  number chosen once.
- **No escalation path.** A blocked handoff here just reports why. A production flow should
  route a block back to the drafting agent with the guardrail's reason as feedback (the same
  hint-accumulation shape `reflexion-example.md` already implements) or to a human reviewer, not
  dead-end silently.
- **One guardrail, one boundary.** Real systems typically need this at every handoff that is
  expensive to get wrong, not just one — `architectures.md`'s handoff-failure-modes section names
  the other two failure classes (context leakage, instruction injection) this specific guardrail
  does not check at all.
- **Structured logging per decision**, not `print` — the same operational gap named in
  `mcp-example.md` and `reflexion-example.md` for their own scaffolds, and the prerequisite for the
  agent-naming/registry point in `architectures.md`: a trace needs to say *which* guardrail blocked
  *which* agent's handoff.
