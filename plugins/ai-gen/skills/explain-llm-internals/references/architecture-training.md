# How an LLM is built: architecture and training

Mentor-altitude "why" answers. This file explains the mechanisms behind behaviour you will
observe in application work — why a model miscounts letters, why it is confidently wrong about
recent events, why a small aligned model can beat a huge unaligned one. It is not a build guide;
for that, Raschka's *Build a Large Language Model (From Scratch)* (Manning, 2024) is the
worked-code source this file follows.

Decisions that *use* this knowledge live elsewhere: which model to pick is
`select-genai-models`, whether to fine-tune is `build-vs-use.md`, serving behaviour is
`inference-internals.md`.

## Tokenization

Text is split into tokens by a deterministic tokenizer — typically byte-pair encoding, which
starts from bytes and merges the most frequent adjacent pairs into a learned vocabulary.

Consequences that show up in practice, and are worth explaining to users rather than
apologizing for:

- **Letter-level tasks are hard by construction.** The model sees token IDs, not characters.
  "How many r's in strawberry" is a question about a representation the model does not have.
  Fix the task (ask for code that counts), don't fix the prompt.
- **Token counts are not word counts**, and the ratio differs sharply by language. Cyrillic and
  CJK text usually costs more tokens per unit of meaning than English — which is a direct cost
  and context-budget issue for a Ukrainian-language product.
- **Rare strings fragment.** Identifiers, UUIDs and misspellings split into many tokens, which
  is one reason dense retrieval misses them (`design-agent-architecture/references/rag-pipeline.md`
  on hybrid search).
- Concatenation is not token concatenation — see the inertness note in
  `engineer-prompt-context/references/prompt-techniques.md`.

## Embeddings and the transformer block

Each token ID becomes a vector; position information is added; then a stack of identical blocks
transforms the sequence. A block is, in essence, **attention** (tokens exchange information)
followed by a **feed-forward network** (each position is transformed independently), each
wrapped with residual connections and normalization.

Attention computes, for every token, a weighted mixture of the other tokens' values, where the
weights come from query–key similarity. Two structural facts matter downstream:

1. **Cost is quadratic in sequence length** — every token attends to every other. This is the
   architectural root of the attention-budget argument in
   `engineer-prompt-context/references/context-engineering.md`, not a vendor limitation.
2. **Decoder-only models are causal**: a token may attend only to earlier positions. That is why
   generation is inherently sequential, and why the prefill/decode split in
   `inference-internals.md` exists at all.

Encoder-style models (bidirectional, no causal mask) are what embedding models are built from —
the reason `select-genai-models/references/model-landscape.md` treats encoders and decoders as
different tools rather than bigger and smaller versions of one thing.

## Pretraining

The objective is next-token prediction over a very large corpus: predict token *n+1* from tokens
*1..n*, measure cross-entropy loss, backpropagate. Nothing about this objective rewards
truthfulness — it rewards plausibility. A hallucination is not a malfunction of this objective;
it is the objective working on a region where plausible and true diverge.

This is also the honest answer to "why does it not know about last month": the weights are a
snapshot of the training corpus. Knowledge that changes belongs in retrieval, not in weights —
which is the rung-2/rung-3 distinction in `build-vs-use.md`.

### Scaling laws: the Chinchilla correction

Hoffmann et al., "Training Compute-Optimal Large Language Models" (2022,
<https://arxiv.org/abs/2203.15556>) found that for compute-optimal training, **model size and
training tokens should be scaled equally** — double the parameters, double the tokens. Their
conclusion about the models of that era was that they were **significantly undertrained**,
because the field had grown parameters while holding data roughly fixed.

The demonstration: Chinchilla (70B) was trained with the same compute budget as Gopher (280B)
but on 4× the data, and outperformed it across downstream tasks (67.5% on MMLU, which the paper
reports as more than 7% above Gopher).

Why a practitioner should care: it is the reason parameter count alone is a poor proxy for
capability, and the reason "bigger model" is not a strategy. Treat the specific ratio as a
finding about that compute regime, not an eternal constant — later work has revisited it, and
inference cost (not just training compute) now drives many sizing decisions.

## Post-training: from a text predictor to an assistant

A pretrained model completes documents. Turning it into something that follows instructions
takes further stages.

### Supervised fine-tuning (SFT)

Train on curated (instruction, response) pairs so the model learns the *shape* of helpful
answers. Mechanics of doing this yourself: `fine-tuning-mechanics.md`.

### Preference alignment

Ouyang et al., "Training language models to follow instructions with human feedback" (2022,
<https://arxiv.org/abs/2203.02155>) is the canonical three-step pipeline:

1. supervised fine-tuning on labeler demonstrations;
2. a **reward model** trained on human *comparisons* between outputs;
3. reinforcement learning (PPO) against that reward model.

Its headline result is the one worth remembering: outputs from the **1.3B** InstructGPT model
were preferred to those from **175B** GPT-3 — roughly 100× fewer parameters. Alignment, not
scale, produced the preferred assistant.

**DPO** (Rafailov et al., "Direct Preference Optimization: Your Language Model is Secretly a
Reward Model", 2023, <https://arxiv.org/abs/2305.18290>) collapses steps 2–3: no separate reward
model, no RL sampling loop, just a classification loss on preference pairs. The paper describes
it as stable, computationally lightweight, and substantially simpler to implement than
PPO-based alternatives — which is why most open-weight alignment work you will encounter uses
DPO or a descendant.

**What this buys you as an explanation:** "the model refuses / hedges / over-apologizes" is
usually a post-training artifact, not a capability limit. It is also why a model's *style* is
much easier to change by fine-tuning than its *knowledge*.

## Reading benchmark claims

Every number you meet about a model was produced by an evaluation with a methodology, and the
failure modes are systematic:

- **Contamination.** Test sets leak into training corpora scraped from the web. A high score on
  a public benchmark may measure memorization. This is why this plugin's standing rule is a
  micro-eval on *your own* data (`evaluate-optimize-models`).
- **Leaderboard incentives.** Public rankings reward the metric, and configurations are tuned
  to it. Prompt format, few-shot count and decoding settings move scores substantially.
- **Aggregate scores hide task-shape differences.** The MTEB finding in `rag-pipeline.md` —
  no embedding method dominating every task — generalizes: a single headline number rarely
  transfers to your task.

The plugin-wide house rule follows from this section: never quote benchmark scores, prices or
context windows from memory as facts. Teach the checking procedure and point at the live source.

## What to say when asked "should I care about internals?"

Yes, for four specific decisions, and no for the rest:

| Question you are actually answering | Internals that decide it |
|---|---|
| Why is it wrong about recent facts / my private data? | Pretraining snapshot → retrieval, not fine-tuning |
| Why does it fail at spelling/counting characters? | Tokenization |
| Why does context beyond N tokens stop helping? | Quadratic attention, attention budget |
| Why is a 7B model fine here but not there? | Alignment vs scale; task-shape, not parameter count |

Everything else — which provider, what it costs, how fast — is measured, not derived from
architecture. Do not let an internals explanation substitute for an eval.
