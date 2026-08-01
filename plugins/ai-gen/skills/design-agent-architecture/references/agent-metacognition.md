# Agent metacognition: five failure modes as a diagnostic

Reasoning patterns (`reasoning-patterns.md`) are primitives — CoT, ReAct, ToT, Reflexion. An
agent built entirely out of them still fails in the same handful of ways once it reaches
production, because none of those patterns knows when it is the wrong one, or when it has
stopped working. This file is the diagnostic layer above them: which of five recurring failure
modes a shipped agent is exhibiting, and the structural fix for each — confidence gating,
stagnation detection, and knowledge-boundary awareness, the pieces `agent-loop.md`'s stop
conditions and `agent-tdad.md`'s evaluation loop do not already cover.

## Contents

- The five failure modes as a diagnostic
- Cognition and metacognition, defined for engineering
- Confidence gating: a structural check, not a verbal one
- A misattributed citation, corrected
- Stagnation detection: two independent signals
- Knowledge-boundary awareness and the "I don't know" off-ramp
- Evaluation-during vs Reflexion-after
- Measuring metacognitive calibration
- Four behaviours, reframed as rules
- Worked example

## The five failure modes as a diagnostic

Every one of these has shipped in a production agent, and each is a diagnostic, not an edge
case: run an agent against a handful of diverse queries and watch which pattern shows up in the
logs — the pattern names the missing piece, not a missing prompt line.

| Failure mode | Observable symptom | Missing capability | Structural fix |
|---|---|---|---|
| Confident wrong answer | Retrieval returns a table-of-contents page or a metadata record; the agent treats it as content and answers from it | Evidence evaluation | Score retrieved evidence for quality *before* synthesis, not after |
| Broken record | The same failed query is retried with near-identical phrasing until the iteration cap fires | Stagnation awareness | Structural stagnation detection — see below |
| Rigid plan | New evidence contradicts the plan; the agent finishes the original plan anyway | Model updating | Replan on a contradiction signal, not only on cap exhaustion |
| Overcommitted guess | The agent has no data on the topic and hallucinates a plausible answer instead of signalling uncertainty | Knowledge-boundary detection | Confidence gate blocks presentation below a floor |
| Shallow composition | A question needs two lookups joined; the agent treats it as one flat query | Compositional reasoning | Recognize the composition need at the planning step (`reasoning-patterns.md`'s decomposition-vs-planning split, `architectures.md`'s orchestrator-workers) |

None of the five fixes is a prompting trick — each is harness code, specified in the sections
below. The middle two are already the anti-patterns `agent-loop.md` treats as stop conditions
under these same names: "broken record" is its own stagnation section, and a self-graded
terminal message is the same self-assessment bias as a plan that never revises. This file names
the full set formally and adds the two `agent-loop.md` does not cover at all: confidence gating
and knowledge-boundary awareness.

A five-query diagnostic, one per failure mode, runnable against any existing agent: a query
whose retrieval returns only a TOC page (evidence evaluation should refuse to answer from it); a
query with no good search results (the agent should pivot within a bounded number of iterations,
not repeat); a query followed by a contradicting fact (the plan should revise); a question
outside the agent's tool/memory coverage (it should signal uncertainty, not guess); a question
needing two joined lookups (it should decompose, not flatten). Failing more than one or two of
the five is the signal that the fixes below are worth building, not that the prompt needs work.

## Cognition and metacognition, defined for engineering

Not a philosophical claim about machine consciousness — two observable, measurable capability
sets.

**Cognition** is the quality of the agent's model of the task: task decomposition (splitting a
novel problem without a template), dependency reasoning (sequencing subtasks correctly, not just
producing them), compositional tool use (chaining tools in configurations nobody wrote a plan
for), and model updating (revising the plan when evidence contradicts the working hypothesis).
`reasoning-patterns.md` supplies the primitives; cognition is choosing among them and combining
them for a specific problem, not a fifth primitive.

**Metacognition** is the agent monitoring its own cognition: confidence calibration (does
expressed confidence correlate with correctness), stagnation detection (does the agent notice it
isn't moving), and knowledge-boundary awareness (does its behaviour change outside its
coverage). All three below are structural checks against state the harness already tracks, not
a prompt asking the model to "double check itself" — a model grading its own output is the same
**biased self-assessment** `agent-loop.md` already warns about for goal-predicate-vs-terminal-
message, applied here to answer quality instead of task completion.

**What this file deliberately does not import.** A cognitive-science vocabulary — specialized
modules, a shared blackboard, a fast/slow routing switch — can motivate an architecture, but
citing Minsky, Baars or Kahneman does not make the architecture correct; it is borrowed
language, not an engineering warrant, the same distinction `memory-vector-db.md`'s taxonomy
section already draws for cognitive-science memory labels ("the vocabulary is a tool, not a
model"). Nor does this file adopt one fixed module set — a perception/planning/execution/
evaluation/attention/memory split behind a single shared state object — as something to build
wholesale; that is one implementation's shape, not a required one. What follows are the
individually checkable mechanisms, usable inside whatever architecture already exists: a single
ReAct loop, `agent-loop.md`'s Layer 2 harness, or a multi-agent system from `architectures.md`.

## Confidence gating: a structural check, not a verbal one

The fix for the overcommitted guess. Before a response reaches the user, check whether the
confidence *state* the harness has been accumulating — not a sentence the model produces on
request — warrants presenting it. A verbal "I'm not sure" can be prompted out of a model
regardless of whether it is actually uncertain; a gate reads a number the harness tracked across
the turn.

The shape, not tuned values (every threshold below is an illustrative starting point to
calibrate against your own eval set, the same caution `agent-tdad.md` already states for rubric
thresholds — none of these numbers is a measured optimum):

- A **hard floor**: below it, never present — signal uncertainty instead.
- A **soft band** above the floor: worth one more attempt within a small retry budget before
  deciding, not an immediate gate.
- An **unresolved-contradiction check**: an open contradiction blocks presentation even at high
  confidence — confidence and consistency are independent axes.
- A **trend check**: confidence that has been declining over the last few steps is a reason to
  gather more, even above the floor — a single high reading can follow a run of low ones.

### A misattributed citation, corrected

The source motivating this section claims implicit, token-likelihood-derived confidence
predicts correctness better than an agent's verbalized confidence, attributing the finding to
"Wang et al. (2025) in the DMC framework." **That attribution does not hold up.** DMC is a real
paper — Wang, Wu, Ye, Cheng, Chen & Zheng, "Decoupling Metacognition from Cognition," *AAAI*
39(24), 2025, pp. 25353–25361 — but neither its abstract nor its body makes this comparison. The
abstract states only that different confidence-elicitation methods change the quantified
metacognitive score, not that any one method beats another at predicting correctness. Its own
experiments compare **verbalized** methods (vanilla, chain-of-thought, top-k) against
**consistency-based** methods (self-random, perturbation) — a different axis than
implicit-vs-verbal — and the one place its related-work section touches token-likelihood
confidence at all, it characterizes a *different* paper (Tian et al., 2023) as favouring verbal
confidence *over* token-likelihood confidence for RLHF-tuned models — the opposite direction
from the claim attached to it here. Whether Tian et al. itself holds up was not independently
re-verified; only DMC's own characterization of it was read.

The deeper problem is that the source's own shipped code never implements the signal its prose
argues for. Its confidence value is not derived from token probabilities anywhere — it is a
float an evaluation-agent LLM call self-reports each step ("return a value from −0.3 to +0.3"),
accumulated across iterations. That is a verbalized judgment wearing a numeric type, not the
implicit signal the citation was recruited to justify — a prose-vs-code gap in the family this
plugin has flagged before (production code silently substituting a weaker mechanism for the one
the surrounding text argues for), not a new species of it.

The practical conclusion for a gate you actually build: prefer a genuinely implicit signal when
a provider exposes one — OpenRouter documents `logprobs`/`top_logprobs` (0–20, requires
`logprobs: true`) with no published per-model support matrix, so treat it as
documented-but-unverified per model, the same two-sided caution this plugin already applies to
structured outputs. When it is unavailable, degrade to a declared, honestly-labelled fallback
(a rubric-scored evaluator is defensible; presenting a self-reported float as if it were
principled is not) — never let the fallback quietly masquerade as the real signal. The worked
example below implements exactly that fallback path.

## Stagnation detection: two independent signals

The fix for the broken record. `agent-loop.md` already ships a stagnation detector — word-set
Jaccard overlap on consecutive iteration summaries, built explicitly as "the offline stand-in
for embedding cosine, mechanism identical." This file carries the mechanism it stood in for,
plus a signal that file does not have at all:

- **Content stagnation** — cosine similarity between the embeddings of consecutive findings,
  above a threshold, means the agent found the same thing twice. Testable offline exactly like
  the word-overlap version: inject stub vectors instead of calling an embedding endpoint, and the
  comparison logic is identical either way.
- **Confidence-plateau stagnation** — the last few confidence readings sit inside a narrow band,
  moving neither up nor down. This is a *different* failure signature from repeated content: an
  agent can keep finding marginally different things while its certainty stops moving at all, so
  a detector that watches only content misses it, and a detector that watches only confidence
  misses genuine repetition with noisy confidence. Run both; either firing is stagnation.

Either signal routes to a replan step that receives the failed strategy explicitly and is
constrained not to propose it again — the same "don't repeat what failed" shape as the
rigid-plan fix above, and the same de-duplication discipline `agent-loop.md`'s follow-up queue
already applies to re-asked questions.

## Knowledge-boundary awareness and the "I don't know" off-ramp

The other half of the overcommitted-guess fix. Blend a small number of signals the harness
already has — retrieval quality, whether anything resembling this problem has been seen before,
current confidence — into a bounded judgment of whether the agent is operating within, at the
edge of, or outside its coverage. **Outside** routes to the same graceful-degradation path the
confidence gate's hard floor uses: present whatever partial evidence exists, mark the uncertain
parts explicitly, and stop — an explicit "I don't know, here is what I do have" off-ramp, never a
hallucinated answer and never a silent failure either.

This is the gap MetaMedQA measured directly and by name: Griot, Hemptinne, Vanderdonckt &
Yuksel, "Large Language Models lack essential metacognition for reliable medical reasoning,"
*Nature Communications* 16, article 642 (2025) — a benchmark built on multiple-choice medical
questions where the correct option is sometimes deliberately absent from the choices. Models
tested answered confidently anyway; they could not tell the question had no right answer among
the options offered. The fix is architectural for the same reason the rest of this file is:
telling a model to "say when you don't know" competes with every other instruction in the
prompt, while a boundary check the harness evaluates every turn does not.

## Evaluation-during vs Reflexion-after

Two valid, complementary timings for the same kind of check, not competing techniques.
**Reflexion** (`reasoning-patterns.md`) is post-hoc: a full attempt exists, a critic reviews it,
and the episodic-memory loop tries again. **Evaluation-during** runs inside the loop, after each
step rather than after the final answer, so a bad intermediate result is caught before later
steps compound it — cheaper to correct one step than to redo a whole trajectory. Use both where
each earns its cost: mid-loop evaluation on every step that feeds later steps, Reflexion on the
complete artifact where a full-attempt critique is what the check actually needs.

## Measuring metacognitive calibration

Four things worth tracking once any of the above ships — a practical diagnostic, not a formal
benchmark:

- **Cognitive efficiency** — steps taken versus the optimal count for that task type; a simple
  lookup taking six steps means the fast-path routing needs tuning, not that the agent improved.
- **Metacognitive calibration** — plot confidence against actual correctness; a well-calibrated
  agent traces close to the diagonal, a poorly calibrated one is confident-when-wrong or
  hedges-when-right.
- **Adaptation rate** — iterations between a stagnation signal firing and a successful strategy
  pivot; lower is better, and it directly measures whether the replan path above is helping.
- **Knowledge-boundary accuracy** — track **false positives** (flagging uncertainty on questions
  the agent could have answered) **beside false negatives** (presenting a confident, wrong
  answer). Optimizing one in isolation is how a gate tuned too conservatively looks perfect on
  the metric someone happens to be watching while quietly refusing easy questions.

## Four behaviours, reframed as rules

The source frames these as behaviour that "emerges" from module interaction. Each is in fact the
traceable consequence of one explicit rule already stated above, and presenting them as emergent
obscures the rule a reader would actually need to build — so here they are as rules, keeping the
technique and dropping the framing:

- **Curiosity** is the knowledge-boundary check routing to a broader search when confidence is
  low *and* nothing relevant has been found yet, before falling back to a guess.
- **Adaptive persistence** is the stagnation-triggered replan excluding the strategy that just
  failed, recorded so an unrelated later task does not retry it either.
- **Selective depth** is the fast path: skip planning and evaluation when a query is simple *and*
  a high-confidence match already exists, and run the full cycle otherwise. (The source's own
  reported speedup figure for this path is an unaudited illustration, not a benchmark result — do
  not repeat it as measured.)
- **Graceful degradation** is what the confidence gate's floor and the knowledge-boundary
  "outside" verdict both do: present partial evidence, label the uncertain parts, stop. This is
  the agent-level instance of the pattern; `serving-release.md`'s reliability ladder uses the
  same name one layer down, for a service degrading under latency or infrastructure failure —
  related idea, different trigger, worth not conflating.

## Worked example

`build-ai-examples/scripts/metacog_example/` implements the confidence gate and the dual-signal
stagnation detector as pure, offline-testable logic: cosine similarity over dependency-injected
stub vectors (no embedding call needed to test the comparison), the confidence-plateau check, and
a resolver that degrades gracefully — to a declared, honestly-labelled fallback, never a silently
substituted guess — when no logprob-derived signal is available. `agent.py` wires a real
OpenRouter call behind `__main__`, requesting `logprobs`/`top_logprobs` where the model supports
them. See `build-ai-examples/references/metacog-example.md`.
