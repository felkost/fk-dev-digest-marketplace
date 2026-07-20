# Prompt techniques: what each buys, costs, and how it fails

A prompt is not an incantation — it is a **document the model completes**. That framing, from
Berryman & Ziegler (*Prompt Engineering for LLMs*, O'Reilly, 2024 — the deepest source behind
this file), is what turns prompting from folklore into engineering: you are choosing what
document makes the desired continuation the most probable one.

Techniques below are ordered by cost. Climb only when the cheaper rung is *measured*
insufficient — the same discipline as the model-selection ladder in
`select-genai-models/references/build-vs-use.md`.

## Prompt anatomy

Berryman & Ziegler's shape of a well-constructed prompt:

1. **Introduction** — states what kind of document this is, so the model interprets everything
   after it correctly ("this is a book recommendation"). It also lets the model start reasoning
   immediately: it has a fixed thought budget per token and cannot pause to reflect.
2. **Context elements** — the dynamic material, ordered deliberately (see Assembly below).
3. **Refocus** — restate the question after long context. Most practitioners use the
   **sandwich technique**: open and close with what you want done.

### Two position effects you cannot prompt your way out of

- **In-context learning** — the closer information sits to the *end* of the prompt, the more
  impact it has.
- **The lost-middle phenomenon** — models recall the beginning and end well and struggle with
  material stuffed in the middle.

Together these produce what the authors call the **Valley of Meh**: a region in the early middle
where context is used least effectively. Its depth and exact location vary by model, but every
model has one. There is no perfect fix — keep high-value elements out of the valley, and keep
the prompt short enough that the valley is small.

## Techniques

### Zero-shot with a clear instruction and an output schema

State the role, the task, the constraints, and the exact output shape. Request structured output
(JSON schema / typed object) whenever the consumer is code.

- **Buys:** the cheapest possible call; deterministic parsing; a testable contract.
- **Costs:** essentially nothing.
- **Fails by:** ambiguity the author cannot see — the model resolves it differently than
  intended and does so confidently. Fix by showing the failure to a colleague, not by adding
  adjectives like "carefully".

**Exhaust this rung first.** Most "the model can't do this" reports are an under-specified
instruction or a missing output schema.

### Few-shot (in-context learning)

Add curated input→output examples.

- **Buys:** format adherence, tone, and edge-case handling — usually the highest-return
  technique after a clear instruction.
- **Costs:** tokens on **every** call unless prompt caching applies. Examples are not free.
- **Fails by:** examples that are unrepresentative (the model generalizes their accidental
  properties), all sharing one label (it copies the label), or contradicting the instruction —
  when instruction and examples disagree, examples usually win.

Curate rather than accumulate: a handful of well-chosen examples beats a pile.

### Chain-of-thought

Ask for intermediate reasoning steps before the answer. Wei et al., "Chain-of-Thought Prompting
Elicits Reasoning in Large Language Models" (2022, <https://arxiv.org/abs/2201.11903>).

- **Buys:** substantial gains on multi-step arithmetic, symbolic and commonsense reasoning.
- **Costs:** more output tokens, therefore latency and money, on every call.
- **Fails by:** being applied to tasks that are not multi-step (retrieval, classification,
  formatting) where it adds cost and an extra surface for the model to talk itself out of a
  correct answer. Reasoning text is also **not** a faithful explanation — do not show it to
  users as justification.
- **Caveat worth stating:** the paper frames these abilities as *emerging* in sufficiently large
  models. Do not assume CoT rescues a small model; measure it on your own eval set.

Modern reasoning models perform this internally — the behaviour is trained in, not prompted.
Adding "think step by step" on top of one may be redundant or actively harmful; check the
provider's current guidance rather than assuming. How that training works (RLVR, verifiable
rewards, distillation) and when such a model is worth its cost:
`explain-llm-internals/references/reasoning-models.md`.

### Self-consistency

Sample several independent reasoning paths at non-zero temperature and take the most consistent
answer instead of greedy decoding. Wang et al., "Self-Consistency Improves Chain of Thought
Reasoning in Language Models" (2022, <https://arxiv.org/abs/2203.11171>).

- **Buys:** accuracy on problems with one right answer reachable by several routes; the paper
  reports large gains across reasoning benchmarks.
- **Costs:** **N× the inference cost** — you pay for every sampled path. The abstract does not
  discuss this; it is the practical constraint that decides whether you can use it.
- **Fails by:** tasks with no single canonical answer (summaries, writing), where "most
  consistent" means "most generic"; and by systematic bias — if the model is confidently wrong
  the same way each time, voting ratifies the error.

### Least-to-most (decomposition)

Two stages: decompose the problem into simpler subproblems, then solve them in order, each using
the previous answers. Zhou et al., "Least-to-Most Prompting Enables Complex Reasoning in Large
Language Models" (2022, <https://arxiv.org/abs/2205.10625>).

- **Buys:** **easy-to-hard generalization** — the specific weakness it targets is that
  chain-of-thought performs poorly on problems harder than the exemplars shown.
- **Costs:** multiple calls; a decomposition that is now part of your design.
- **Fails by:** a bad split — errors in early subproblems propagate with full confidence. Put a
  programmatic check between stages (this is the prompt-chaining workflow in
  `design-agent-architecture/references/architectures.md`).

### Tree of Thoughts

Explore multiple reasoning branches with self-evaluation, lookahead and backtracking. Yao et al.,
"Tree of Thoughts: Deliberate Problem Solving with Large Language Models" (2023,
<https://arxiv.org/abs/2305.10601>).

- **Buys:** large gains on search-like puzzles where a single pass fails badly.
- **Costs:** many model calls per problem, plus an evaluation function and a search policy.
- **Judgment (not the paper's claim):** rarely justified in application work. Before reaching
  for it, ask whether the task is genuinely search — most business tasks are not, and the same
  budget spent on retrieval quality or a better decomposition returns more.

### Persona / role

- **Buys:** register, vocabulary, and audience calibration.
- **Costs:** a few tokens.
- **Fails by:** being treated as a capability upgrade. "You are a world-class expert" does not
  add knowledge; it changes style. Do not let a persona substitute for the actual constraints.

## Assembly mechanics

The part most prompt guides skip, and where Berryman & Ziegler are strongest. Assembling a
prompt is an **optimization problem**: choose the elements that maximize value subject to two
constraints — the dependency structure between elements, and the total length limit.

Three relationships govern the ordering:

| Relationship | What it decides | Practical rule |
|---|---|---|
| **Position** | Where an element goes | Preserve natural order (document order, chronology). Rearranging makes the document incoherent |
| **Importance** | Whether it is included at all under budget pressure | Rank explicitly; beginners conflate this with position because recency and importance often correlate — but the introduction is usually more important than mid-document detail |
| **Dependency** | How including one element forces or forbids another | Two kinds: **requirements** (A needs B) and **incompatibilities** (A excludes B) |

Two further mechanics worth knowing:

- **Elastic snippets.** One piece of content can be rendered at several lengths — the quote
  alone, the quote with surrounding context, or a combined snippet linking parts. Give the
  assembler a choice of forms and it can fill the budget optimally instead of truncating.
- **Inertness.** You want to compute a snippet's token length once, and one snippet's
  tokenization must not change its neighbour's. Tokenizers do not guarantee this: tokenizing
  `A + B` can differ from tokenizing `A` and `B` separately, so concatenation is not token
  concatenation. Budget arithmetic that assumes otherwise drifts.

## Common failure modes

- **Editing the prompt with no eval set.** Every change then trades an unmeasured win for an
  unmeasured regression. Build the set first — `evaluate-optimize-models`.
- **Stacking techniques.** CoT + self-consistency + a persona + ten examples, all at once: cost
  multiplies and nothing is attributable. Add one, measure, keep or drop.
- **Fixing a knowledge failure with prompting.** If the model lacks the information, no phrasing
  supplies it — that is retrieval (`design-agent-architecture/references/rag-pipeline.md`).
- **Confusing style with capability.** Personas and politeness change register, not competence.
- **Prompt tuning on the test set.** Iterating against the same examples you report on overfits
  exactly like hyperparameter tuning on validation data. Keep dev and test separate.
- **Treating retrieved or tool text as instructions.** Anything interpolated into a prompt from
  outside is data, and a prompt-injection surface.

## What to measure

Before/after on the *same* versioned eval set, reporting the operating point (model ID,
temperature, prompt version). A prompt improvement with no eval number attached is a preference,
not a result. Metric choice by task class: `evaluate-optimize-models/references/evaluation.md`.
