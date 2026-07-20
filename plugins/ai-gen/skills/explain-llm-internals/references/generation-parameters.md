# Generation parameters: what they actually control

## Contents

- The distribution vs the pick
- Temperature and top-p
- Presence vs frequency penalty
- max_tokens as a cost guard, not a length target
- seed: best-effort reproducibility
- Provider surface varies — OpenRouter as the reference
- Presets by agent role
- What this changes for application work

## The distribution vs the pick

For a given prompt, the model computes one thing: a probability distribution over the next
token. Everything in this file controls a separate step — *sampling* — that picks one token out
of that distribution. The split matters for a decision people get backwards: **the model's
forward pass is deterministic, the sampler is not.** Pushing every generation parameter toward
"no randomness" (temperature near 0, top_p near 0) still doesn't guarantee bit-exact repeats —
non-associative floating-point arithmetic under batched inference can shift results run to run.
Verify a determinism claim empirically rather than assuming it from the parameters alone. Decode
is where sampling repeats, once per output token — see `inference-internals.md` for why that loop
is the expensive, memory-bound one.

## Temperature and top-p

Both reshape the distribution before sampling; neither adds information the model didn't already
compute.

- **Temperature** scales the logits before the softmax. Above 1, the distribution flattens — more
  tokens become plausible, output gets more varied and more likely to wander off-topic. Below 1,
  it sharpens toward the single most likely token.
- **top-p (nucleus sampling)** keeps the smallest set of tokens whose cumulative probability
  reaches *p*, discards the rest, and renormalizes before sampling. It bounds how far into the
  tail the sampler can reach, regardless of how flat temperature made the distribution.

They compose, which is the practical problem: temperature reshapes the whole distribution, then
top-p truncates whatever that reshaped distribution turned into. Tuning both at once changes the
same outcome through two coupled knobs, so a shift in output can't be attributed to either one —
which is why providers that document both commonly recommend adjusting one and leaving the other
at its default. Treat that as an interaction to check in the current API reference of whichever
provider you call, not a fixed rule to quote from memory.

## Presence vs frequency penalty

Both discourage repetition by subtracting from a token's logit once it has appeared, but on
different signals:

- **Presence penalty** fires once a token has appeared at all — a flat penalty regardless of how
  many times. It pushes the model toward *new* topics.
- **Frequency penalty** scales with how many times the token has already appeared. It suppresses
  *loops* (the model echoing the same phrase) without discouraging a token it only used once.

A model stuck restating the question needs frequency penalty; a model that won't leave one topic
needs presence penalty. They are not interchangeable, and stacking both aggressively degrades
coherence — the model starts avoiding common function words it still needs.

## max_tokens as a cost guard, not a length target

`max_tokens` (or the provider's current name for it — `max_output_tokens`,
`max_completion_tokens`) is a hard ceiling, not a target: the model isn't told to reach it, only
stopped there. Two consequences worth designing for:

- **Set it just above the expected length**, not to "leave room." A generous ceiling on a
  runaway generation is a runaway bill; a tight one silently truncates a valid answer
  mid-sentence — check the response's finish/stop reason to tell the two failure modes apart
  before trusting a short answer.
- **Prompt tokens + max_tokens must fit the context window.** This is a hard error on some
  providers and a silent truncation on others — verify which, for the one you call.

## seed: best-effort reproducibility

Passing the same seed with the same prompt and parameters is meant to make output reproducible —
useful for debugging and for eval runs where you need to isolate a prompt or model change from
sampling noise. It is documented as **best-effort, not guaranteed**: OpenRouter's own docs state
that repeated requests with the same seed and parameters *should* return the same result, not
that they will. Backend changes on the provider's side can still shift output under a fixed seed.
Treat it as noise reduction for evaluation, not as a correctness guarantee to build application
logic on.

## Provider surface varies — OpenRouter as the reference

Which parameters exist, and their ranges, are **per-provider and often per-model**, not
universal — the same standing rule this plugin applies everywhere: don't attribute a capability
to a provider without checking its current reference. OpenRouter's parameter documentation,
verified at time of writing:

| Parameter | Range | Notes |
|---|---|---|
| `temperature` | 0.0–2.0 | Lower = more predictable, higher = more varied |
| `top_p` | 0.0–1.0 | Nucleus threshold |
| `presence_penalty` / `frequency_penalty` | −2.0–2.0 | See above |
| `seed` | integer | Best-effort determinism, see above |
| `max_tokens` | 1+ | Bounded by context length minus prompt |

OpenRouter also passes through model-specific extras some underlying providers expose beyond
this common set (`top_k`, `min_p`, `top_a`, `repetition_penalty`) — these are not part of every
model's surface, and OpenRouter's own docs say to check the specific model's provider section
before relying on one. Do not carry this table into a claim about a different provider's API —
verify there separately, per the plugin's rule against copying a parameter name from one library
or provider into a sentence about another.

## Presets by agent role

**Practitioner technique, not a citation** — verify against the provider's current parameter
surface before relying on it, per the plugin's admissibility rule for techniques.

| Agent role | Typical shape | Why |
|---|---|---|
| Coder / structured-output agent | temperature near 0, low frequency_penalty | Consistency over variety; code repeats tokens (brackets, keywords) that shouldn't be penalized |
| Classifier / router | temperature near 0 | The same input should route the same way |
| Brainstorm / creative-writer agent | temperature raised, presence_penalty raised | Push toward new ideas instead of the safest continuation |
| Eval / regression-testing run | fixed seed, temperature near 0 | Isolate a prompt or model change from sampling noise |

In most agent work, the two parameters actually worth touching are **temperature** (by role) and
**max_tokens** (by cost and expected length). The rest are worth understanding well enough to
read a config or a bug report, not something to tune reflexively — reach for a preset like the
one above only when the default already measurably fails on your eval, not before.

## What this changes for application work

Sampling parameters are not a substitute for the things that actually control an agent's
reliability:

- They **do not fix** a wrong or ambiguous prompt — see `prompt-techniques.md`.
- They **do not fix** a persona or reasoning defect — see `architecture-training.md`
  (post-training) and `reasoning-models.md` (when native reasoning needs a structured pattern
  instead).
- They **do** change cost and latency in a way worth measuring — every extra token spent on a
  loosened penalty or a padded `max_tokens` is billed
  (`evaluate-optimize-models/references/token-latency-cost.md`).

If an agent's output is unreliable, check the prompt and the architecture before reaching for a
sampling parameter. A parameter change that "fixes" a flaky agent without a measured before/after
is usually masking a different defect, not curing it.
