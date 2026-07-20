# Build vs use: the escalation ladder

Each rung costs more than the previous one. Climb only when the current rung is *measured*
insufficient on your own eval set — never on a hunch.

## Rung 0 — ready model + prompt engineering

A capable hosted model with a well-structured prompt (role, constraints, output schema,
few examples inline). Covers the majority of real tasks. Exhaust this first: most "the model
can't do it" cases are prompt or decomposition defects.

How to exhaust it properly — prompt anatomy, technique choice with its cost, and what to measure
before declaring this rung insufficient — is `engineer-prompt-context`
(`references/prompt-techniques.md`). Climbing to rung 2 or 3 without that evidence is the most
common expensive mistake on this ladder.

## Rung 1 — few-shot / in-context learning

Add 3–10 curated examples of input→output into the prompt (or via prompt caching). Fixes format
adherence and domain tone cheaply. Watch token cost: examples are paid on every call unless
cached.

## Rung 2 — RAG (retrieval-augmented generation)

When the failure is *missing or stale knowledge*: attach an encoder + vector store and inject
retrieved passages. Fixes grounding and citation; does NOT fix style, format discipline, or
reasoning. See `design-agent-architecture/references/rag-pipeline.md` for the stage-by-stage
anatomy, the failure mode of each stage, and the order to work in when RAG underperforms —
and note the cheaper rung *below* this one: if the corpus is small and stable enough to fit in
the context window, put it in the prompt and skip the pipeline entirely.

## Rung 2.5 — tune the retrieval side before you tune the model

The ladder as usually drawn jumps from "attach RAG" straight to "fine-tune the generator", and
that jump skips the rung most teams actually need. When RAG underperforms, the defect is
usually **retrieval**, and fine-tuning the generator cannot fix a passage that never arrived.

Escalate inside retrieval first, cheapest to dearest:

1. **Chunking, metadata and filters** — `design-agent-architecture/references/memory-vector-db.md`
   and `build-ai-examples/references/document-loading.md`. Free relative to everything below,
   and the most common actual fix.
2. **Hybrid search and reranking** — `design-agent-architecture/references/rag-pipeline.md`.
3. **Fine-tune the embedding model** on your own corpus. ← this rung.
4. **Jointly train retriever and generator** — see below, and expect to skip it.

### Fine-tuning the embedding model

The training data is a set of **positive pairs**: a question and the passage that answers it.
That is the same artifact `evaluate-optimize-models/references/evaluation.md` already makes you
build for recall@k, which is what makes this rung cheaper than it looks — if you did evaluation
properly, you have started the dataset already.

The sentence-transformers documentation recommends **`MultipleNegativesRankingLoss`** for
positive-pair data; it constructs negatives from the rest of the batch, which is why duplicate
pairs in a batch actively hurt. Training needs a model, a dataset shaped to the loss, the loss,
training arguments, and (optionally but do it) an evaluator. **The documentation gives no minimum
dataset size** — do not repeat a number you saw in a blog post; measure recall@k against the base
model on your own set and let that decide.

- **Pays off when** your vocabulary sits far from the base model's training distribution:
  internal part numbers and product codes, legal or clinical jargon, a language the base model
  underserves, or a domain where two texts that look similar in general English mean opposite
  things.
- **Does not pay off when** recall@k is already high and the failure is in generation, or when
  the corpus is general prose — you will spend a training cycle to move a number that was not the
  bottleneck.
- **The recurring cost is the real one.** Changing the embedding model means re-embedding the
  entire corpus, versioning the index by model ID, and running the dual-index migration described
  in `memory-vector-db.md`. A fine-tuned embedding model is a permanent operational commitment,
  not a one-off experiment.

### Joint retriever + generator training (know it, probably skip it)

Three primary sources define this space, and they are worth knowing even if you never run one:

- **REALM** (Guu, Lee, Tung, Pasupat & Chang, 2020, <https://arxiv.org/abs/2002.08909>) pre-trains
  the retriever end-to-end with the language model, using masked language modelling as the
  learning signal and backpropagating through a retrieval step over millions of documents.
- **Atlas** (Izacard, Lewis, Lomeli, Hosseini, Petroni, Schick, Dwivedi-Yu, Joulin, Riedel &
  Grave, 2022, <https://arxiv.org/abs/2208.03299>) shows a retrieval-augmented model handling
  knowledge-intensive tasks with far fewer parameters than a much larger model, and notes the
  document index can simply be updated — retrieval substituting for both parameters and retraining.
- **RA-DIT** (Lin et al., "Retrieval-Augmented Dual Instruction Tuning", 2023,
  <https://arxiv.org/abs/2310.01352>) retrofits an existing LLM with two lightweight fine-tuning
  stages: one updates the LM to make better use of retrieved information, the other updates the
  retriever to return what the LM prefers. The paper reports each stage helping on its own and
  combining for further gains.

For application work this is a platform- or research-scale rung, and this plugin's default is to
say so rather than quote it as an option. **The takeaway that transfers even if you never train
anything**: RA-DIT's split is the same split this plugin insists on everywhere — the retriever
and the generator have separate failure modes and separate fixes. Know which one you are fixing
before you spend anything, and measure them separately (`evaluation.md`).

## Rung 3 — fine-tuning (LoRA/QLoRA or full)

When the failure is *behavior*: consistent style, strict schema, domain jargon, latency (a small
fine-tuned model replacing a large prompted one). Requires hundreds-to-thousands of quality
input→output pairs and an eval set *before* training. Does NOT reliably add facts — knowledge
keeps changing and fine-tuned facts go stale; that is RAG's job.

Decision test: "would showing the model better *instructions/examples* fix it?" → rungs 0–1.
"Does it lack *information*?" → rung 2. "Is the information in the corpus but not coming back
from search?" → rung 2.5, and measure recall@k to confirm before spending. "Does it know and
still misbehave?" → rung 3.

Once this rung is chosen, the mechanics — LoRA/QLoRA, dataset shape and chat templates, the
training loop, and how an adapter is served — are
`explain-llm-internals/references/fine-tuning-mechanics.md`. It also lists the failure modes
that make a fine-tune wasted, the commonest being an attempt to add *facts* this way.

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
