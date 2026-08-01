# Agent Ops: running an agent in production

Offline evaluation tells you whether a change is good before you ship it
(`evaluation.md`). Agent Ops is everything after: knowing what the agent did, whether quality
held, and how a production failure becomes a permanent test.

Primary source for this framing: Google, "Introduction to Agents" whitepaper (November 2025),
which describes Agent Ops as a natural evolution of DevOps and MLOps tailored to agents. The
motivating problem it names is exact: traditional unit tests assert `output == expected`, and
that does not work when a response is probabilistic by design.

## Contents

- Why deterministic testing does not transfer
- Measure what the business feels
- Trajectory tracing
- Online quality: sampled judging
- Metrics-gated deployment
- The incident → eval-case loop
- Security surface of a deployed agent
- Minimum viable Agent Ops

## Why deterministic testing does not transfer

Three properties break the usual toolchain, and each needs its own answer:

| Property | Consequence | Answer |
|---|---|---|
| Output is probabilistic | Pass/fail assertions are wrong-shaped | Rubric-scored quality, not equality |
| Behaviour is a *trajectory*, not a call | A wrong answer may come from step 3 of 9 | Trace the whole path, not just the response |
| Failures are open-ended | You cannot enumerate the test cases up front | Harvest cases from production continuously |

## Measure what the business feels

Define "better" before instrumenting. The whitepaper's guidance is to frame observability like
an A/B experiment and ask which KPIs prove the agent delivers value — going beyond technical
correctness to goal completion rate, user satisfaction, task latency, operational cost per
interaction, and the business outcome itself.

This plugin's two standing operational KPIs, consistent with `token-latency-cost.md`:

- **cost per *solved* task** — not cost per call, which improves when the agent gives up sooner;
- **p95 end-to-end latency** — not the mean, which hides the experience people complain about.

A third belongs specifically to agents: **steps-to-success**. A rising step count at constant
success rate means the agent is working harder for the same result, and it is usually the
earliest visible symptom of a regression.

## Trajectory tracing

When a metric dips, you need "why", and the answer is not in the final response. An
OpenTelemetry trace is a step-by-step recording of the agent's whole execution path: the exact
prompt sent, the model's reasoning where available, which tool was chosen, the parameters it
generated, and the raw observation that came back.

- Traces are for **debugging**, not for performance overviews; promote the few details that
  matter into metrics and leave the rest for root-cause work. (That distinction is the
  whitepaper's, and it is the one teams usually get wrong — dashboards built out of raw traces.)
- **OpenTelemetry has semantic conventions for generative AI** covering spans, metrics and
  events, including agent and tool execution spans. **Verify the current state before relying on
  specifics**: these conventions moved out of the main docs into a dedicated repository
  (<https://github.com/open-telemetry/semantic-conventions-genai>), and they have been evolving.
  Treat attribute names as a moving target, not a stable contract.
- Log what you would need to *replay* a failure: inputs, model ID, prompt version, tool
  responses, and the config. A trace you cannot reproduce from is a story, not evidence.

Privacy note this plugin adds: traces contain user data and often credentials-adjacent tool
arguments. Redaction is part of the tracing design, not a later cleanup.

## Online quality: sampled judging

Offline evals cover what you thought of. Online judging covers what users actually send.

Run an LLM judge against a **sample** of production traffic on a rubric — was the answer right,
was it grounded in the retrieved sources, did it follow instructions. Sampling, not everything:
judging every response doubles cost for information you do not need at that resolution.

The judge is a measuring instrument and inherits every obligation in `evaluation.md`: named
biases (self-preference, position, verbosity), human calibration on a sample before it is
trusted, and re-calibration whenever the judge model or rubric changes. The whitepaper makes the
same point from the other side — evaluation results should be reviewed by a domain expert
before being accepted as valid.

Golden datasets should be **sampled from real interactions**, cover the breadth of expected use
plus some unexpected cases, and be curated by someone who owns the domain.

## Metrics-gated deployment

Once enough scenarios are automated and the scores are trusted, deployment stops being a
judgment call: run the candidate against the full evaluation set and compare directly with the
version in production. Ship on the comparison, not on a demo.

Two additions the whitepaper makes explicitly, both worth enforcing:

- Do not gate on quality alone — **latency, cost and task success** are release criteria too.
- Use **A/B rollout** for real-world confirmation, because simulation scores and production
  behaviour diverge.

Practical shape: a quality gate that blocks the deploy, a cost/latency gate that blocks it, and
a staged rollout that can be reversed without a code change.

## The incident → eval-case loop

This is the part that compounds, and the part most teams skip.

When a user reports a bug or thumbs-downs a response, that is a real-world edge case your
automated scenarios missed. The loop: capture the feedback, **replicate** the issue, and convert
that scenario into a new permanent test case in the evaluation dataset. The whitepaper's phrase
for the effect is worth borrowing — you are not only fixing the bug, you are vaccinating the
system against that entire class of error.

Aggregate rather than react one-by-one: when a statistically significant cluster of similar
reports or a metric dip appears, tie it back to analytics and alert on it.

Consequence for planning: the eval set is not a deliverable that gets finished. It grows with
every incident, and that growth is the asset.

## Security surface of a deployed agent

Every tool granted is power granted, and the whitepaper's framing is that the primary concerns
are **rogue actions** and **sensitive data disclosure** — a leash long enough to work, short
enough to stay out of traffic, especially around irreversible actions and private data.

The load-bearing point: **you cannot rely on the model's judgment alone, because it can be
manipulated by prompt injection.** The recommended posture is hybrid, defense-in-depth:

1. **Deterministic guardrails first** — hardcoded policy outside the model's reasoning: block
   spending over a threshold, require explicit confirmation before an external write. These give
   predictable, auditable hard limits.
2. **Reasoning-based defenses second** — adversarial training, plus small specialized *guard
   models* that inspect a proposed plan before execution and flag risky or policy-violating
   steps.

Order matters: a guard model is a mitigation, a policy engine is a limit. Do not sell the first
as the second.

**The guardrail cost ladder**, sharpening the two-tier split above into what to reach for first:
code/schema/regex checks (free, deterministic, catches shape and policy violations) → a small
classifier model (cheap, catches patterns a regex cannot name) → a full LLM guardrail (most
flexible and most expensive — and it can rival the agent's own inference cost once every turn
passes through one). Climb only when the cheaper rung is measured insufficient, the same
discipline as `select-genai-models/references/build-vs-use.md`'s ladder. The caution worth
stating plainly: an LLM guardrail can be wrong in the *same* direction as the agent it is
checking, since it is drawn from the same kind of model — it is a mitigation, not a proof.

**Callbacks observe; guardrails block.** A callback that logs a step is not a guardrail: it has
no power to stop anything, and treating the two as interchangeable is how a step meant to
*prevent* a bad action turns out to have only *recorded* it. A guardrail acts as a semantic
circuit breaker — it halts the flow *before* the risky action executes, not a post-hoc filter on
what already happened.
`design-agent-architecture/references/architectures.md`'s handoff-failure-modes section names
where to place these; a worked, polarity-tested example (and the exact inverted-guardrail bug
this distinction exists to catch) is `build-ai-examples/references/guardrail-example.md`.

**Agent identity** is the whitepaper's third pillar and the one most easily overlooked: an agent
is a new class of principal, distinct from the user who invoked it and the developer who built
it, and it needs its own verifiable identity so it can carry **least-privilege** permissions.
Compromise of one agent is then contained rather than total.

### A2A and multi-agent interoperability

The Agent2Agent (A2A) protocol is the whitepaper's open standard for agents publishing
capabilities and collaborating across systems. The caution this plugin adds: interoperability
widens the injection surface — another agent's output is **untrusted input**, exactly like a
retrieved document or a tool result (`design-agent-architecture/references/mcp-tools.md`). Every
boundary crossed is a place where data can be mistaken for instructions. Recommend A2A when
genuinely crossing organizational boundaries; do not adopt it to connect two services you
already control.

## Minimum viable Agent Ops

For a team shipping their first agent, in order:

1. Structured traces with a request/session ID, redacted, replayable.
2. Three metrics: task success, cost per solved task, p95 latency.
3. An eval set that a deploy is gated on, however small.
4. A feedback capture path, and the discipline that every triaged incident becomes a case.
5. Deterministic guardrails on irreversible and spending actions.

Everything beyond that — sampled online judging, A/B rollout, guard models, agent identity —
is earned once these five exist. Recommending the advanced set to a team without traces is
the operational equivalent of adding HyDE to an unmeasured RAG pipeline.
