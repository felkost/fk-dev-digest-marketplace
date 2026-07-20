# Fine-tuning mechanics: what actually happens when you adapt a model

**Scope split, deliberately:** *whether* to fine-tune is a decision that belongs to
`select-genai-models/references/build-vs-use.md` (rung 3 — behaviour defects, not knowledge
gaps). This file is the mechanism: what LoRA changes, what QLoRA makes possible, how a dataset
must be shaped, and how an adapter is served. Read the decision file first; if the answer there
was "no", nothing here applies.

Worked-code source for this material: Godoy, *A Hands-On Guide to Fine-Tuning Large Language
Models with PyTorch and Hugging Face* (2024).

## Full fine-tuning vs parameter-efficient

Full fine-tuning updates every weight. The memory cost is the killer: you hold the weights, the
gradients, and the optimizer state (Adam keeps two additional values per parameter). For any
model you would actually want to adapt, that is multiple times the model's size in VRAM.

Parameter-efficient fine-tuning (PEFT) freezes the base model and trains a small number of new
parameters instead.

## LoRA

Hu et al., "LoRA: Low-Rank Adaptation of Large Language Models" (2021,
<https://arxiv.org/abs/2106.09685>).

The mechanism: **freeze the pretrained weights** and inject **trainable rank-decomposition
matrices** into the transformer's layers. Instead of learning a full weight update, you learn a
low-rank factorization of it.

Reported in the paper, for GPT-3 175B versus Adam fine-tuning: **10,000× fewer trainable
parameters** and **3× less GPU memory**. Two further claims worth carrying:

- quality **on par with or better than** full fine-tuning despite far fewer trainable parameters;
- **no additional inference latency**, unlike adapter approaches — because the learned update
  can be merged back into the base weights.

That last property is the one that decides deployments: a merged LoRA is just a model. An
unmerged one lets you keep many adapters over a single base — see serving below.

The knob you will be asked about is **rank**. Higher rank means more capacity to change
behaviour and more parameters to train; too low underfits, too high starts recovering full
fine-tuning's costs without its benefits. There is no universal right value — it is tuned
against your eval set, like everything else in this plugin.

## QLoRA

Dettmers et al., "QLoRA: Efficient Finetuning of Quantized LLMs" (2023,
<https://arxiv.org/abs/2305.14314>).

LoRA on top of a **4-bit quantized** frozen base. Three named innovations:

1. **4-bit NormalFloat (NF4)** — a data type the paper describes as information-theoretically
   optimal for normally distributed weights;
2. **double quantization** — quantizing the quantization constants themselves to cut average
   memory further;
3. **paged optimizers** — to absorb memory spikes.

The headline capability: finetuning a **65B parameter model on a single 48GB GPU** while
**preserving full 16-bit finetuning task performance**.

Practical reading: QLoRA is what moved fine-tuning from "cluster" to "one rented GPU". Note
carefully what is quantized — the *frozen base* during training. That is a separate decision
from whether you quantize at **serving** time (`inference-internals.md`), and the two are often
conflated in blog posts.

## The dataset is the project

The mechanics above are a weekend; the dataset is the work. Realistic proportions: most of the
effort is producing consistent, correct (input, output) pairs that demonstrate exactly the
behaviour you want.

- **Volume.** Rung 3 in `build-vs-use.md` states the honest range: hundreds to thousands of
  quality pairs. Fewer, cleaner examples beat more, noisier ones.
- **Consistency is the actual signal.** The model learns the pattern in your labels, including
  the accidental ones. If two examples format dates differently, you have taught it that both
  are acceptable.
- **Chat templates matter and are model-specific.** Instruction-tuned models were post-trained
  with a particular structure of role markers and special tokens. Training with the wrong
  template — or serving with a different one than you trained with — degrades results in a way
  that looks like "the fine-tune didn't work". Use the tokenizer's own chat template rather than
  hand-assembling strings.
- **Held-out set first.** Build the eval set *before* training (`evaluate-optimize-models`).
  Without a before/after on the same set, you cannot tell adaptation from damage.
- **Catastrophic forgetting is real.** A model tuned hard on a narrow task can lose general
  ability. Keep a slice of general-capability checks in the eval set, not only task checks.

## Training loop, in outline

Hugging Face's `SFTTrainer` (TRL) wraps the standard flow, and the steps are worth naming
because each is a place people get stuck:

1. Load the base model — quantized if QLoRA (`bitsandbytes`), otherwise in the working dtype.
2. Attach the LoRA configuration (rank, alpha, dropout, and **which modules** get adapters —
   commonly the attention projections).
3. Format the dataset through the model's chat template.
4. Train, watching **both** training and validation loss. Training loss alone tells you the
   model is memorizing, not that it is learning.
5. Save the adapter — typically megabytes, not gigabytes.
6. Evaluate on the held-out set against the *pre-fine-tune* baseline, on the same metric.
7. Optionally merge the adapter into the base for deployment.

Preference-tuning (DPO and relatives) sits on top of this with pairs of preferred/rejected
responses instead of single targets — the conceptual background is in
`architecture-training.md`.

## Serving what you trained

Three shapes, with different economics:

| Shape | When | Trade-off |
|---|---|---|
| Merged weights | One adapter, maximum simplicity | Just a model to serve; no per-request adapter switching |
| Adapter kept separate | Many tenants/tasks over one base | One base in memory, adapters swapped per request; slight overhead |
| Local quantized (llama.cpp / GGUF) | Desktop, offline, or privacy-bound deployment | Runs on CPU/consumer GPU; quantization quality cost applies |

Whichever shape, the deployment questions — GPU or hosted, secrets, cost control — are
`deploy-ai-environments`, and the serving-time efficiency knobs are
`evaluate-optimize-models/references/token-latency-cost.md`.

## Failure modes to name before anyone starts

- **Fine-tuning to add facts.** It does not reliably work, and the facts go stale in the weights.
  Knowledge is retrieval's job (`rag-pipeline.md`). This is the single most common wasted
  fine-tune.
- **No baseline.** Without the pre-tuning number on the same eval set, "it's better" is a
  feeling.
- **Template mismatch** between training and serving — silent, and looks like a bad model.
- **Tuning on the eval set.** Same overfitting trap as prompt tuning; keep dev and test apart.
- **Ignoring the maintenance cost.** A fine-tuned model is a version you now own: base-model
  upgrades, re-tuning, re-evaluating. Hosted models improve without you; yours does not.
