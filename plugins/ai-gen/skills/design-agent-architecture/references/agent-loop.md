# The agent loop: the inner execution loop of a single agent turn

**Disambiguation first, because this plugin now carries four things called a
"loop" or a "level".** This file is about the **inner execution loop**: the
think → act → observe cycle one agent runs between receiving a goal and
stopping. `loop-engineering.md` is Osmani's **outer development loop** — how a
*human developer* runs automations, worktrees and sub-agents; its "cognitive
surrender" is about the developer, not the agent. Keep the two apart or every
sentence about "tightening the loop" becomes ambiguous.

The numbered scales collide too, and all three are orthogonal:

| Scale | What it measures | Where it lives |
| --- | --- | --- |
| Google capability **Levels 0–4** | what the *agent system* can do (single-turn → autonomous multi-agent) | `architectures.md` |
| Oracle harness **Levels 1–3** | how much *loop machinery* wraps the model (bare API → managed loop → durable, resumable harness) | this file |
| Lanham layer **Layers 1–3** | *where the loop's four elements live* (see below) | this file |

A "Level 3" claim means nothing until the speaker names the scale. When this
plugin cites one, it cites the scale by owner ("Google capability level",
"harness level", "loop layer").

## The loop and its four elements

A loop turn is: assemble context → model proposes (thought, action) → harness
executes the action → observation goes back into context → repeat until a stop
condition fires. Four elements exist in every non-trivial loop, whether or not
the code names them: the **goal** (what would count as done), the **plan**
(what remains to be tried), the **state** (what has been learned/produced so
far), and the **decision** (what to do next). Summaries of this taxonomy that
name only three ("goal, plan, decision") silently drop state — and state is
the element whose placement distinguishes the layers below.

**Model vs harness:** the model proposes; the harness disposes. Everything
that must be *guaranteed* — caps, budgets, termination, logging, deduplication
— belongs to the harness, in deterministic code, because a guarantee the model
is merely prompted to uphold is a preference, not a guarantee. This is the
same maker/checker separation `autonomy-contracts.md` applies to approvals,
applied to the loop's own plumbing.

## Layers 1–3: where the four elements live (Lanham ch. 9)

- **Layer 1 — inside the agent.** Goal, plan, state and decision all live in
  the model's context. Cheapest to build; every guarantee is soft. Acceptable
  when the whole task fits in one context window and failure is cheap.
- **Layer 2 — externalized into the harness.** Deterministic code owns the
  plan queue, the state store and the stop decision; the model is called for
  the steps that need judgment. This is where the deep-research pattern lives,
  and where the example below sits. Most production loops belong here.
- **Layer 3 — handed to another agent.** A second agent owns goal/plan/state
  for the first. When one delegator owns them for many workers this is
  **orchestration**; when peers share them it is **collaboration**.
  `architectures.md`'s rule stands: orchestration first — collaboration only
  when the task is genuinely adversarial or peer-review-shaped, because shared
  ownership of state is the most expensive coordination substrate there is.

## Stop conditions: the layered gate

`autonomy-contracts.md` owns the budget caps (iterations, wall-clock, cost).
Two stop conditions it deliberately does not cover live here:

- **Goal predicate vs terminal message.** "The model said it is done" is a
  *terminal message* — an utterance. A *goal predicate* is a harness-side
  check that the produced artifact satisfies the goal's testable form. Treat
  self-declared completion as a claim to verify, not a signal to stop:
  goal satisfaction reported by the agent about itself is a **biased
  self-assessment** (the same model that produced the answer grades it).
  Where no predicate is writable, downgrade the stop to "terminal message +
  budget", and say so in the run record.
- **Exit on absence of progress (stagnation).** Stagnation is harder to
  detect than failure. A failing loop trips the "same error signature
  repeats" stop factor; a stagnating loop produces *new, plausible,
  near-identical* output every iteration and never trips it — the "broken
  record" that still spends budget. Detect it structurally: compare
  consecutive iteration summaries and stop when overlap exceeds a threshold;
  de-duplicate the follow-up queue so re-asked questions cannot re-enter.
  A published specimen of the gap this closes: the deep-research loop whose
  prose promises five layered stop conditions (including semantic-overlap
  stagnation detection with a sidebar of its own) while its shipped
  `should_continue` checks only status, iteration count and a non-empty
  queue — no cost cap, no stagnation check, and a follow-up queue that grows
  without deduplication. The gate you write must be the gate the prose
  promises. (Beware also that the same source defines stagnation two ways —
  semantic overlap "say, 85%" in prose, word overlap ">80%" in its exercise;
  pick one mechanism, name their difference, and test the one you shipped.)

The full gate is a conjunction of independent families — budget caps (owned by
`autonomy-contracts.md`), progress checks (stagnation, empty queue), and goal
checks (predicate where writable) — evaluated in the harness every iteration.
Any one firing stops the loop; the run record says which one fired, because
"why did it stop" is the first debugging question.

## The programmatic / agent-triggered boundary

Every transition in the loop is either **programmatic** (the harness decides:
caps, schema validation, queue pops, retries) or **agent-triggered** (the
model decides: which follow-up matters, whether evidence suffices for a
claim). Draw the boundary explicitly. Two placement rules recur: anything
that spends money or mutates the world gets a programmatic gate even when
agent-triggered ("the model proposes the write; the harness performs it");
and reflection is cheapest as a *scheduled programmatic trigger* (every N
steps, or on a failure counter) that *asks* the model to reflect — an agent
told to "reflect when appropriate" under a broken-record failure mode is the
component least likely to notice the appropriate moment.

## Context economics inside the loop

The loop is where context dies by a thousand appends. Four rules:

- **Monitor the window** as a budget, not a limit to hit: past a fill
  threshold, compact — but compaction **summarizes forward while preserving
  originals** (offloaded, addressable), never destructive rewrites. An agent
  that cannot re-read the original evidence cannot recover from a bad
  summary.
- **Offload tool output.** Raw tool results go to an external log keyed by
  id; the context receives the id plus a short digest. Cross-referenced in
  `mcp-tools.md` (tool-count tax and result offloading) — the loop-side rule
  is that offloading happens *every iteration*, not once at the end.
- **Append, don't rewrite.** Prompt caches key on prefixes; a loop that
  rewrites its transcript each turn pays full price every turn. Stable
  prefix, appended turns, compaction as an explicit cache-breaking event.
- **Prefer filtering at the tool** (or in executed code) over hauling raw
  output into context and asking the model to filter — the "read the whole
  file to find the links" anti-pattern. Where tasks are batch-shaped, a code
  step that loops over ten files beats ten observe-act round-trips both in
  tokens and in latency.

## Separation of concerns in the loop

**The explorer must not write the report.** One role gathers (searches,
reads, accumulates findings into state); a distinct step — different prompt,
often different model — synthesizes the artifact from accumulated state. The
gathering role optimizes recall and is rewarded for appending; the writing
role optimizes precision and is rewarded for discarding. One prompt asked to
do both does neither, and the report inherits the exploration transcript's
noise. This is also what makes the state store the *only* interface between
the two — which is exactly what makes Layer 2 testable offline.

**Breadth vs depth is which end of the queue you pop.** With follow-up
questions in a queue, popping from the front (FIFO) explores broadly across
the original question's facets; popping from the back (LIFO) drills into the
most recently opened thread. Neither is right in general — but the choice is
one line of harness code, so make it a named parameter, not an accident of
`list.pop()`'s default.

## The loops around the loop

Three more loops surround the execution loop, on different clocks, and take
its records as input: the **feedback loop** (evaluation results and incident
cases become the regression set — `evaluation.md`, `agent-ops.md`), the
**training loop** (fine-tuning on accumulated trajectories, out of scope
here), and the **human loop** (HITL checkpoints; placement rules in
`architectures.md`, approval semantics in `autonomy-contracts.md`). The
execution loop's job toward all three is the same: leave a record complete
enough that the outer loops can learn from it — which stop condition fired,
what each iteration cost, and which evidence ids support the final artifact.

## Worked example

`build-ai-examples/scripts/loop_example/` implements the Layer-2 gate this
file specifies — iteration cap **and** cost cap **and** wall-clock cap **and**
a stagnation detector, a de-duplicated follow-up queue with a named
breadth/depth parameter, tool-output offloading to an id-keyed log, and an
explorer/writer split — as pure logic, fully offline-testable, with the
negative tests the published specimen fails: the loop halts on two
near-identical summaries, the queue provably de-duplicates, and the module
imports without executing anything. See
`build-ai-examples/references/loop-example.md`.
