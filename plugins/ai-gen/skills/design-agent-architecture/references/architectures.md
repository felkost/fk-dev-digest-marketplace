# Agent architecture patterns: benefits and risks

Every pattern is presented with what it buys, what it costs, and how it fails. Recommend the
simplest one that covers the task; name the rejected alternative.

## Contents

- Workflows vs agents (decide this first)
- Single call (baseline)
- Workflow patterns
- ReAct (reason + act loop)
- RAG (retrieval-augmented generation)
- Multi-agent
- Human-in-the-loop / agent-in-the-loop
- Capability levels (a scoping vocabulary)
- Choosing

## Workflows vs agents (decide this first)

Anthropic's "Building Effective Agents"
(<https://www.anthropic.com/research/building-effective-agents>) draws the line this way:
in a **workflow**, LLMs and tools are orchestrated through predefined code paths; in an
**agent**, the LLM dynamically directs its own process and tool usage.

The distinction is operational, not academic. A workflow is testable step by step, costs a
predictable number of calls, and fails in ways you can enumerate. An agent handles problems
where you cannot predict the number of steps in advance, and pays for it with
non-determinism, variable cost, and a much larger debugging surface.

The source's guidance, and this plugin's default: start with simple prompts, optimize them
with evaluation, and add multi-step agentic systems only when simpler solutions demonstrably
fall short. Most requests arriving as "build me an agent" are workflows, and a large minority
are a single call.

## Single call (baseline, not an "architecture")

One model call, possibly with structured output. Buys: determinism of flow, lowest latency/cost,
trivial debugging. Fails when: the task needs external data, tools, or multi-step state.
Always ask first whether this suffices — most "agent" requests reduce to it.

## Workflow patterns

The five named patterns below are Anthropic's, from the source above. They compose: a routing
step feeding an orchestrator-workers stage is common.

### Prompt chaining

Decompose into fixed sequential steps, each LLM call processing the previous output, with
programmatic checks between stages. Buys: accuracy on tasks that decompose cleanly, and a place
to put a validity check between steps. Costs: latency accumulates linearly; the decomposition
is now a design commitment. Fails by: error propagation — a wrong step-1 output is elaborated
confidently downstream (put the check *between* steps, not only at the end); over-decomposition
into steps that each lose information the next one needed.

Use when the task splits into fixed subtasks and you will trade latency for accuracy.

### Routing

Classify the input, then send it to a specialized follow-up. Buys: specialized handling per
category, and cost control — simple inputs to small models, hard ones to capable models. Costs:
one extra classification call; a taxonomy to maintain. Fails by: misclassification that silently
degrades everything downstream (measure classifier accuracy separately, and design a default
route); category drift as real inputs stop matching the taxonomy; no path for "none of these".

Use when there are distinct categories that are genuinely better handled separately.

### Parallelization

Run LLM calls simultaneously and aggregate. Two sub-variants in the source:

- **Sectioning** — split into independent subtasks and run them concurrently (e.g. guardrail
  screening alongside response generation).
- **Voting** — run the *same* task several times and aggregate for confidence (e.g. multiple
  vulnerability-review passes, or content moderation against a threshold).

Buys: wall-clock speed for sectioning; higher confidence and tunable strictness for voting.
Costs: token cost multiplies with the number of branches; an aggregation rule you must define.
Fails by: sections that were not actually independent (results contradict and the merge step
hides it); voting that averages away a correct minority answer; threshold tuning done on the
same data used to claim the improvement.

### Orchestrator-workers

A central LLM decomposes the task dynamically, delegates to worker calls, and synthesizes the
results. Buys: flexibility where subtasks cannot be predicted up front. Costs: coordination
tokens, and a synthesis step that is itself a failure point. Fails by: orchestrator plans that
drift from the goal across delegations; workers duplicating or undoing each other; a synthesis
step that concatenates rather than reconciles.

Distinguished from parallelization by *who decides the split*: predefined in parallelization,
decided at runtime here.

### Evaluator-optimizer

One call generates, another evaluates and returns feedback, in a loop. Buys: measurable
iterative improvement where a clear rubric exists. Costs: at least two calls per round, and the
loop needs a stopping rule. Fails by: an evaluator that shares the generator's context or
prompt and so rehearses its reasoning (see maker-checker in `loop-engineering.md`); reward
hacking against the rubric; unbounded refinement with no cap.

Use when evaluation criteria are clear and iterative refinement measurably improves the result.
This is the workflow twin of the maker-checker discipline in `loop-engineering.md`.

## ReAct (reason + act loop)

The model alternates thought → tool call → observation until it answers. Buys: tool use, dynamic
decomposition, recovery from partial failures. Costs: token growth per iteration, latency,
non-determinism. Fails by: looping (cap iterations, detect repeated identical calls),
hallucinated tool arguments (validate schemas), acting on injected instructions from tool output
(treat tool results as data; sanitize/quote them). Modern "tool calling" agents (incl. LangGraph
prebuilt agents) are ReAct descendants with structured tool APIs instead of free-text actions.

Google's "Introduction to Agents" whitepaper (November 2025) describes the same cycle as a
five-step operational loop — get the mission, scan the scene, think it through, take action,
observe and iterate — summarized as the "Think, Act, Observe" cycle, with the orchestration
layer managing it, the model reasoning, and the tools executing.

## RAG (retrieval-augmented generation)

Encoder + vector store retrieve passages; the LLM answers grounded in them. Buys: fresh/private
knowledge without retraining, citations, smaller models sufficing. Costs: an entire retrieval
pipeline to build and *evaluate separately* (chunking, embeddings, index, rerank). Fails by:
retrieval misses (answer sounds confident, sources irrelevant — measure retrieval recall on a
labeled set); chunking that severs context; stale indexes; the model ignoring retrieved text
(require quoting/citing); prompt injection via retrieved documents. RAG fixes *knowledge*
failures, not *behavior* failures (see build-vs-use ladder in `select-genai-models`).

## Multi-agent

Several model instances with distinct roles/tools (planner+executors, debate, map-reduce over
subtasks). Buys: parallelism over independent subtasks, separation of concerns, context isolation
(each agent sees only its slice). Costs: coordination protocol, multiplied tokens, hardest
debugging. Fails by: error *compounding* across handoffs (each agent trusts the previous one's
output), divergent agents re-doing or undoing work, deadlocked handoffs, cost blow-up. Rule of
thumb: multi-agent is justified when subtasks are genuinely parallel or need conflicting
personas/permissions — not for decorating a linear pipeline with roles. A linear chain of
prompts is a pipeline, not multi-agent, and is easier to test.

**Some problems are multi-agent by definition**, not by choice of architecture: social
simulations, market/negotiation models, and adversarial red-team/blue-team setups require
multiple actors with genuinely distinct, sometimes conflicting goals — a single agent cannot
role-play both sides of an adversarial evaluation without the evaluation losing its point.

**How agents share state — a practitioner distinction, not a new pattern**, worth naming because
the choice changes both cost and failure mode:

| Substrate | How it works | Buys | Costs |
|---|---|---|---|
| Shared thread | Every agent reads and writes one conversation history | Full context for every agent | Grows unbounded; downstream agents drown in details irrelevant to their step |
| Blackboard | Agents post intermediate results under named keys in a shared structured store | Organized, selectively readable state | The team must agree on a schema up front; a key nobody reads is silent waste |
| Chained (handoff) | Each agent passes output only to the next, like a pipeline stage | Simplest to implement and reason about | Discards everything the receiving agent didn't explicitly need — including context a later step turns out to want |

Default to chained unless there's a concrete reason a downstream agent needs to see further
upstream than its immediate predecessor's output — "more shared context" is not free, and the
failure modes above (error compounding, divergent rework) get worse, not better, the more state
agents share.

## Human-in-the-loop / agent-in-the-loop

Checkpoints where a human approves, edits, or supplies missing facts; or an agent supervises
another process continuously. Buys: safety on irreversible/expensive actions, quality floor,
labeled data as a by-product. Costs: throughput bounded by human attention; UX design becomes
part of the architecture (queues, diffs, approve/reject). Fails by: rubber-stamping (approvals
too frequent to review — batch and prioritize), unclear responsibility ("the human approved it"),
checkpoint placement that interrupts flow where risk is low while missing the risky step.
Place gates at: irreversible external actions, spending, publishing, and low-confidence
decisions (route by model-reported uncertainty or validator score).

Gates interrupt a loop; contracts bound one. Where the agent runs unattended between gates, the
boundaries and stop conditions belong in an explicit contract — see `autonomy-contracts.md`.

## Capability levels (a scoping vocabulary)

The Google whitepaper cited above classifies agentic systems into levels, useful for scoping a
build and for telling a customer what they are actually asking for:

| Level | Name | What it can do |
|---|---|---|
| 0 | The Core Reasoning System | Model alone: no tools, no memory, no live data. Explains and plans; blind to anything outside training data |
| 1 | The Connected Problem-Solver | Uses tools (search, APIs, RAG) to answer from the live world |
| 2 | The Strategic Problem-Solver | Plans multi-part goals; actively curates the context each step needs |
| 3 | The Collaborative Multi-Agent System | A team of specialists; agents treat other agents as tools |
| 4 | The Self-Evolving System | Identifies its own capability gaps and creates new tools/agents to fill them |

Two cautions. The whitepaper itself notes Level 3 is constrained by current model reasoning, and
this plugin treats Level 4 as a research frontier, not a delivery target. And levels are
*capability*, not operational maturity: the scheduling, isolation, and checking machinery in
`loop-engineering.md` is orthogonal — a Level 1 agent inside a good loop beats a Level 3 design
that nobody verifies.

## Choosing

| Situation | Default |
|---|---|
| Transform/extract/classify, all inputs in the prompt | Single call + structured output |
| Fixed, cleanly decomposable steps; accuracy over latency | Prompt chaining with checks between steps |
| Distinct input categories handled differently | Routing (+ a default route) |
| Independent subtasks, or confidence via repetition | Parallelization (sectioning / voting) |
| Subtasks not predictable until runtime | Orchestrator-workers |
| Clear rubric, refinement measurably helps | Evaluator-optimizer (bounded) |
| Needs live external data or actions | Single agent with tools (ReAct) |
| Needs changing/private corpus with citations | RAG (possibly inside the agent as a tool) |
| Independent parallel subtasks, or conflicting roles | Multi-agent (bounded, with a merge step) |
| Irreversible/costly actions in the loop | Any of the above + human gates |
| Runs unattended on a cadence | Any of the above + a stop contract (`autonomy-contracts.md`) |
