# Agent architecture patterns: benefits and risks

Every pattern is presented with what it buys, what it costs, and how it fails. Recommend the
simplest one that covers the task; name the rejected alternative.

## Single call (baseline, not an "architecture")

One model call, possibly with structured output. Buys: determinism of flow, lowest latency/cost,
trivial debugging. Fails when: the task needs external data, tools, or multi-step state.
Always ask first whether this suffices — most "agent" requests reduce to it.

## ReAct (reason + act loop)

The model alternates thought → tool call → observation until it answers. Buys: tool use, dynamic
decomposition, recovery from partial failures. Costs: token growth per iteration, latency,
non-determinism. Fails by: looping (cap iterations, detect repeated identical calls),
hallucinated tool arguments (validate schemas), acting on injected instructions from tool output
(treat tool results as data; sanitize/quote them). Modern "tool calling" agents (incl. LangGraph
prebuilt agents) are ReAct descendants with structured tool APIs instead of free-text actions.

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

## Human-in-the-loop / agent-in-the-loop

Checkpoints where a human approves, edits, or supplies missing facts; or an agent supervises
another process continuously. Buys: safety on irreversible/expensive actions, quality floor,
labeled data as a by-product. Costs: throughput bounded by human attention; UX design becomes
part of the architecture (queues, diffs, approve/reject). Fails by: rubber-stamping (approvals
too frequent to review — batch and prioritize), unclear responsibility ("the human approved it"),
checkpoint placement that interrupts flow where risk is low while missing the risky step.
Place gates at: irreversible external actions, spending, publishing, and low-confidence
decisions (route by model-reported uncertainty or validator score).

## Choosing

| Situation | Default |
|---|---|
| Transform/extract/classify, all inputs in the prompt | Single call + structured output |
| Needs live external data or actions | Single agent with tools (ReAct) |
| Needs changing/private corpus with citations | RAG (possibly inside the agent as a tool) |
| Independent parallel subtasks, or conflicting roles | Multi-agent (bounded, with a merge step) |
| Irreversible/costly actions in the loop | Any of the above + human gates |
