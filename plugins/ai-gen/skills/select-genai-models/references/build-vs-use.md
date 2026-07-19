# Build vs use: the escalation ladder

Each rung costs more than the previous one. Climb only when the current rung is *measured*
insufficient on your own eval set — never on a hunch.

## Rung 0 — ready model + prompt engineering

A capable hosted model with a well-structured prompt (role, constraints, output schema,
few examples inline). Covers the majority of real tasks. Exhaust this first: most "the model
can't do it" cases are prompt or decomposition defects.

## Rung 1 — few-shot / in-context learning

Add 3–10 curated examples of input→output into the prompt (or via prompt caching). Fixes format
adherence and domain tone cheaply. Watch token cost: examples are paid on every call unless
cached.

## Rung 2 — RAG (retrieval-augmented generation)

When the failure is *missing or stale knowledge*: attach an encoder + vector store and inject
retrieved passages. Fixes grounding and citation; does NOT fix style, format discipline, or
reasoning. See `design-agent-architecture` for the architecture itself.

## Rung 3 — fine-tuning (LoRA/QLoRA or full)

When the failure is *behavior*: consistent style, strict schema, domain jargon, latency (a small
fine-tuned model replacing a large prompted one). Requires hundreds-to-thousands of quality
input→output pairs and an eval set *before* training. Does NOT reliably add facts — knowledge
keeps changing and fine-tuned facts go stale; that is RAG's job.

Decision test: "would showing the model better *instructions/examples* fix it?" → rungs 0–1.
"Does it lack *information*?" → rung 2. "Does it know and still misbehave?" → rung 3.

## Rung 4 — training from scratch

Justified only by: a modality/domain no foundation model covers, hard IP/licensing constraints,
or research goals. For application work in this plugin's scope, treat as out of budget by
default and say so explicitly when a user proposes it.

## Open weights vs hosted API

| Criterion | Hosted API (incl. via OpenRouter) | Open weights (self-hosted) |
|---|---|---|
| Time to first result | Minutes | Days (serving stack, GPU) |
| Data leaves premises | Yes (check provider terms/regions) | No |
| Cost profile | Per token, scales to zero | Per GPU-hour, fixed floor |
| Model ceiling | Frontier models | Best open checkpoints |
| Ops burden | None | Serving, updates, monitoring |

Privacy or offline constraints force open weights; otherwise start hosted, revisit when volume
makes GPU economics favorable (measure, don't assume — see `evaluate-optimize-models`).
