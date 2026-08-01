# Reasoning models: what changed, and what it changes for you

A reasoning model spends a variable amount of compute "thinking" — generating a long chain of
thought, often thousands of tokens — before answering. The trace shows search-like behaviour:
decomposing the problem, criticizing itself, trying alternatives, catching its own errors.

This file explains the mechanism and then, as this skill requires, what decision follows.
Post-training in general (SFT → RLHF → DPO) is `architecture-training.md`; prompt-level
chain-of-thought is `engineer-prompt-context/references/prompt-techniques.md`; the serving cost
of extra tokens is `inference-internals.md`.

**Note on numbers:** benchmark percentages are deliberately not quoted here, per the plugin's
standing rule. The papers cited below report them; read them there, at the version you are
actually considering.

## Contents

- RLVR: reinforcement learning with verifiable rewards
- DeepSeek-R1: the open demonstration
- Distillation: reasoning transfers by SFT
- Inference-time scaling
- What this changes for application work
- Model-native reasoning vs a structured pattern on top
- How to decide, in one line

## RLVR: reinforcement learning with verifiable rewards

The training idea behind current reasoning models. **The term is introduced by Tülu 3**
(Lambert et al., "Tulu 3: Pushing Frontiers in Open Language Model Post-Training", AI2, 2024,
<https://arxiv.org/abs/2411.15124>), which presents RLVR as a novel method alongside supervised
finetuning and DPO — worth attributing correctly, because it is commonly credited to the
DeepSeek work that popularized it.

The mechanism: instead of a *learned* reward model that predicts what a human would prefer, use
a **check that is actually right**. If a domain lets you verify an answer, the reward is a
binary signal from that verification:

| Domain | Verification |
|---|---|
| Mathematics | Extract the final answer, compare to ground truth |
| Code | Execute the test cases |
| Constrained output | Check the format/constraint mechanically |

**Why verifiability is the whole point.** A neural reward model can be gamed — the policy learns
to satisfy the *model of the reward* rather than the goal, which is reward hacking. A test suite
cannot be flattered. This is the same principle as the machine-checkable criteria in
`design-agent-architecture/references/autonomy-contracts.md`, and it has the same limit: it only
works where a mechanical check exists.

**GRPO** is the RL algorithm most associated with this line of work, introduced in DeepSeekMath
(Shao et al., 2024, <https://arxiv.org/abs/2402.03300>) as a PPO variant that improves
mathematical reasoning while reducing PPO's memory usage. The mechanism people usually cite —
estimating the baseline from a group of sampled outputs rather than training a separate value
network — is in the paper body rather than the abstract; verify there before repeating it.

## DeepSeek-R1: the open demonstration

DeepSeek-AI, "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement
Learning" (2025, <https://arxiv.org/abs/2501.12948>, published in Nature).

**R1-Zero** is the striking result: reasoning trained by **pure RL**, which the abstract states
obviates the need for human-labeled reasoning trajectories. No supervised fine-tuning on
demonstrations of how to think. The paper reports capabilities *emerging* from this —
self-reflection, verification, and dynamic strategy adaptation — on verifiable tasks such as
mathematics, coding competitions and STEM.

That is the conceptually important claim: nobody demonstrated the reasoning; the optimization
found it because the reward could tell right from wrong.

**R1** exists because R1-Zero had practical defects — notably unreadable traces and language
mixing. Its pipeline is four stages:

1. **Cold start** — a small supervised set of long chain-of-thought examples, to establish a
   readable reasoning template.
2. **Reasoning-oriented RL** — with an added language-consistency reward.
3. **Rejection sampling** — generate, keep what verifies, curate a large mixed SFT set
   (reasoning plus general data).
4. **General-purpose RLHF** — rules-based rewards for reasoning tasks, neural reward models for
   general ones.

The shape worth remembering: **verifiable rewards where they exist, human preference where they
do not.** Stage 4 is not a step backwards — it covers everything RLVR structurally cannot.

## Distillation: reasoning transfers by SFT

DeepSeek distilled R1 into smaller dense models (Qwen, Llama) by plain supervised fine-tuning on
the curated traces from stage 3. The paper's framing is that emergent reasoning patterns from
large-scale models can be systematically harnessed to enhance smaller models.

The finding that matters for anyone with a budget: **distillation outperformed running RL
directly on the small model.** The implication is that discovering reasoning patterns takes
scale, but *copying* them does not. If you want a small reasoning model, you are far better off
distilling from a large one's traces than trying to RL your way there — which also means the
practical path for most teams is to use a distilled open model, not to train one.

Mechanics of doing SFT on such data: `fine-tuning-mechanics.md`.

## Inference-time scaling

Two distinct levers, often conflated:

- **Longer thinking** — more tokens in a single chain of thought. Providers expose this as a
  reasoning-effort setting on some models.
- **More samples** — generate several answers in parallel and select by majority vote,
  consensus, or best-of-N. This is `prompt-techniques.md`'s self-consistency, applied to a
  reasoning model.

Both convert money and latency into accuracy, and both are **decode-phase** costs — see
`inference-internals.md` for why that phase is the expensive, memory-bound one. Neither is free,
and neither helps on tasks that were never reasoning-bound.

## What this changes for application work

This is the part the mentor owes the user.

| Situation | What to do |
|---|---|
| Task is multi-step, verifiable, and correctness matters more than latency | A reasoning model is a genuine fit — measure it against a standard model on your own eval |
| Retrieval, extraction, classification, formatting, summarization | Standard model. Reasoning tokens are pure cost here |
| You already prompt "think step by step" | **Stop** on a reasoning model — the behaviour is trained in. Extra CoT instructions can be redundant or harmful; check the provider's current guidance |
| Latency is user-facing | Reasoning traces add tokens *before* the first useful output. Budget for it or don't use one |
| You want the reasoning shown as justification | Don't. Traces are not faithful explanations, and some providers hide them and return a summary instead |
| You need a small reasoning model | Prefer a distilled open model over training your own |

Two further cautions:

- **Verifiable ≠ your domain.** RLVR's gains concentrate where a mechanical check exists. A
  model trained this way is not automatically better at open-ended judgment, tone, or tasks with
  no ground truth — and those are most business tasks.
- **Cost accounting changes shape.** Reasoning tokens are billed and are often invisible in the
  final answer's length. Measure **cost per solved task**, not per response
  (`evaluate-optimize-models/references/token-latency-cost.md`), or a reasoning model will look
  cheaper than it is.

## Model-native reasoning vs a structured pattern on top

A separate question from "should I use a reasoning model at all": given the reasoning capability
a modern frontier model already has built in, when is that enough, and when do you still need to
layer a structured pattern (ReAct, Tree of Thoughts, Reflexion, explicit planning — which one,
`design-agent-architecture/references/reasoning-patterns.md`; self-consistency and per-technique
cost, `prompt-techniques.md`) on top?

**Native reasoning is usually enough** when the task has a short horizon (roughly one to three
steps), the tool surface is small, a wrong action is cheap and reversible, and the model is a
frontier reasoner operating inside its strong domains.

**Layer a structured pattern** when any of the following holds: the task is long-horizon or
branches into subgoals; the agent must choose carefully among many tools; a wrong action is
expensive or irreversible (spending money, sending an external message, modifying production
data); the domain sits outside the model's training strengths; or the reasoning trace itself
needs to be auditable or reproducible, which built-in reasoning generally is not — it is opaque
and varies between runs, while an explicit pattern gives you something to inspect and constrain.

**Always** add the structured layer for safety-critical or regulated work, regardless of how
capable the underlying model's native reasoning is. This is a practitioner heuristic, not a
finding from the papers above — it composes with the RLVR material rather than restating it: a
reasoning model with a good verifiable-reward training signal can still reason opaquely at
inference time, and the two concerns (was it trained to reason well, can you inspect *this* run)
are independent.

## How to decide, in one line

Reasoning models are a *rung*, like everything else in this plugin: try the standard model with
a good prompt first, and escalate only when your own eval shows the task is genuinely
reasoning-bound (`select-genai-models/references/build-vs-use.md`). "It's the newest model" is
not a measurement.
