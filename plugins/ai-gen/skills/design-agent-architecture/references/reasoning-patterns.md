# Reasoning patterns: which structure, and why

Chain-of-thought, self-consistency and least-to-most are **prompting** techniques —
`engineer-prompt-context/references/prompt-techniques.md` prices each one per call. This file
starts where that one stops: patterns that quit being a prompt choice and become an
**architecture** choice, because they need state across calls, a loop, or orchestration code the
model cannot supply for itself. "Which reasoning structure should this agent use" is answered
here, on one surface, by design — not scattered across that file, `architectures.md` and
`explain-llm-internals/references/reasoning-models.md`, where a reader would have to already know
the answer to know where to look.

## Contents

- Decomposition vs planning
- Selection table
- ReAct: what actually defines it
- Tree of Thoughts needs orchestration code
- Reflexion, from the primary source
- The plan is a property of the architecture
- `sequential-thinking` as the scratchpad instance
- How to decide

## Decomposition vs planning

Two operations, routinely named in the same breath and routinely conflated. They fail
independently, and the fix differs by which one broke:

- **Decomposition** — splitting a problem into subproblems. Least-to-most
  (`prompt-techniques.md`) is decomposition as a prompting technique; orchestrator-workers
  (`architectures.md`) is decomposition as an architecture.
- **Planning** — ordering those subproblems, tracking which are done, and revising the order as
  results arrive. Planning has nothing to sequence until decomposition has produced pieces.

A correct decomposition can still execute a bad plan (wrong order, a dependency between two
pieces that was treated as none); a sound plan can be faithfully executing a wrong decomposition
(a subproblem that never needed to exist, or one that silently merged two different questions).
When a multi-step output is wrong, diagnose which operation failed before patching either — a
plan fix does not repair a bad split, and a re-split does not repair bad sequencing.

## Selection table

| Structure | Needs beyond a single prompt | Use for | Don't reach for it when |
|---|---|---|---|
| Chain-of-thought | Nothing — one call | Short, verifiable reasoning that finishes in the same turn | The task needs external data/actions, or "reasoning" is really retrieval (`prompt-techniques.md`) |
| ReAct | A loop that feeds each tool observation into the next reasoning step | Tasks needing live/external state, with recovery from partial failure | No external interaction is needed — the loop adds latency and non-determinism for nothing |
| Tree of Thoughts | Orchestration code: branch generation, a scoring function, backtracking | Search-like problems where a single pass fails badly and partial paths are scorable | Almost everything else — most business tasks are not search, and `prompt-techniques.md` already flags this as rarely justified |
| Reflexion | A loop + a feedback signal + memory of past attempts (episodic text, not weights) | Iterative improvement where a check exists — tests pass, schema validates, a deterministic verifier runs — even though the first attempt is unreliable | No feedback signal better than the same model asked "are you sure?" is available — the pattern cannot outperform the quality of its own critique |

All four compose with a model's own built-in reasoning rather than replacing it —
`reasoning-models.md`'s "model-native reasoning vs a structured pattern on top" covers when the
structured layer is worth adding above a reasoning model's native thinking.

## ReAct: what actually defines it

Not the presence of a tool call. Yao et al., "ReAct: Synergizing Reasoning and Acting in Language
Models" (2022, <https://arxiv.org/abs/2210.03629>), define it by generating "reasoning traces and
task-specific actions in an **interleaved manner**": "reasoning traces help the model induce,
track, and update action plans... while actions allow it to interface with... external sources" —
each action's observation feeds the *next* reasoning step. That feedback loop is the defining
property, verified against the abstract rather than assumed from the name.

A single CoT pass that happens to end by emitting one tool call is **not** ReAct: nothing the tool
returns feeds back into further reasoning, because there is no further reasoning left to feed. The
test is whether an observation can change what the model does next, not whether a tool was
invoked. Implementation-level costs and failure modes (looping, hallucinated arguments, injected
tool output) stay in `architectures.md`'s ReAct section — this file only settles the definition.

## Tree of Thoughts needs orchestration code

`prompt-techniques.md` already prices ToT (many calls, an evaluation function, a search policy)
and calls reaching for it rarely justified. The architectural point underneath that price:
pruning, backtracking and self-evaluation cannot be expressed as a single prompt, because they are
a search algorithm **over** LLM-scored nodes — something outside the model has to hold the
frontier, decide what to expand, and decide what to discard. That something is orchestration code
(LangGraph, or a hand-rolled branch/queue), not a cleverer instruction.

The failure mode when that code is missing has a real instance, not a hypothetical one: a
triaged book's own `chapter_05/03_ToT_agents.py` evaluates only the first level of generated
thoughts, with no pruning and no backtracking — breadth without the search machinery. Labeling
that "Tree of Thoughts" is the trap; what it actually is is a wider single pass, at ToT's token
cost without ToT's result.

## Reflexion, from the primary source

Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning" (2023,
<https://arxiv.org/abs/2303.11366>). Three facts straight from the abstract, because the pattern
is easy to misdescribe as fine-tuning in disguise:

- Agents are reinforced "**not by updating weights**, but instead through linguistic feedback."
- They "maintain their own reflective text in an **episodic memory buffer**" — state living
  outside the model's weights and outside any single call, carried forward across attempts.
- The feedback signal is "flexible enough to incorporate various types (scalar values or
  free-form language) and sources (**external or internally simulated**)." An externally supplied,
  fully deterministic signal is explicitly in scope — not a deviation from the pattern.

**The feedback-signal honesty this plugin insists on.** The same triaged book claims Reflexion's
shortcoming is that it "requires understanding the correct solution." That is not a property of
the pattern — it is an artifact of one demo. That book's own companion repository,
`chapter_05/03_reflexion_agents.py`, hardcodes `TARGET_DAYS = "26"` and hands it to the critic
directly, so the critic compares against a memorized answer instead of evaluating the work; the
generalization is built on that shortcut, not on anything the paper requires. The demo also
carries a live bug worth knowing by shape, verified against the file directly: `TARGET_DAYS in
answer` is a **substring** test, so an answer like `"the trip takes 126 days"` reads as containing
`"26"` and passes. A second condition, `"yes" in answer.lower() or "correct" in answer.lower()`,
is left over from an earlier problem statement the script overwrites before running (`problem` is
assigned twice) — so it rewards an answer that says "the claim is **incorrect**" (because
`"incorrect"` contains `"correct"`) and fails a terse, correct one that uses neither word. Both
bugs share one root cause: the check was never derived from the task it was meant to grade — see
the worked example below, which makes that binding structural rather than a discipline to remember.

The honest framing, and the one that matches the paper: **the pattern's ceiling is the quality of
its feedback signal**, not whether the answer happens to already be known. A critic that shares
the generator's blind spots ratifies its own mistakes — the same reason a checker in a
maker-checker loop needs independence from the maker (`loop-engineering.md`'s "Maker-checker,
stated as a rule", sourced to Karim et al. §7.2 on confirmation bias between similar models). "No
actual learning happens, there is no weight update" is the part of that same triaged source's
critique that **is** correct and matches the abstract — carry that half, not the other.

## The plan is a property of the architecture

A model call carries no memory of a previous call beyond what is re-sent in the prompt, and no
world model between calls. A plan spanning several steps cannot live "in the model's head" — it
has to be written to state outside the model and **re-read at every step**, never trusted to be
remembered. This is the same requirement `architectures.md`'s state-substrate table (shared
thread / blackboard / chained) exists to satisfy for multi-agent state generally, applied here to
a single agent's own plan: pick a substrate, write the plan into it, and have every step start by
reading it back rather than assuming continuity the model does not have.

## `sequential-thinking` as the scratchpad instance

The MCP reference server `@modelcontextprotocol/server-sequential-thinking` (still an active
reference implementation; its `package.json` and `index.ts` checked directly, 2026-07-21 — the
package's own README alone summarized the tool name wrong, one word off, which is exactly the
kind of drift worth checking source over summary for) is the concrete case: **it does no
thinking; it is external storage for the outputs of thinking.** Its runtime dependencies are the
MCP SDK plus a CLI-parsing and a terminal-styling library — no model client, so nothing resembling
reasoning happens on the server itself. What it stores is structure: its one tool,
`sequentialthinking` (one word — note the mismatch with the hyphenated package name, another
instance of this plugin's standing identifier-drift caution), takes a `thought` string plus
explicit sequencing fields (`thoughtNumber`, `totalThoughts`, `nextThoughtNeeded`) and
revision/branch fields (`isRevision`, `revisesThought`, `branchFromThought`, `branchId`). The model
still does every bit of the reasoning; the server only gives it a place to externalize and revise
that reasoning step by step — the plan-as-external-state requirement above, packaged as a tool
instead of hand-rolled agent state.

## How to decide

Default to a single call, add chain-of-thought once the task is measurably multi-step, and climb
to a structure that needs a loop (ReAct, Reflexion) or a search (ToT) only when a failure on your
own eval set points at *which* operation is missing — never because the pattern is well-known.
Same ladder discipline as `select-genai-models/references/build-vs-use.md` and
`prompt-techniques.md`'s cost ordering, applied one level up: to the reasoning structure itself,
not only the prompt inside it. A worked solver-critic Reflexion loop that follows every rule above
— an externally checkable critic, a task-bound predicate, an offline-tested stopping rule — is in
`build-ai-examples/references/reflexion-example.md`.
