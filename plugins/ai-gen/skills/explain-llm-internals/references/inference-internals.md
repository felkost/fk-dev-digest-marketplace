# Inference internals: why serving behaves the way it does

This file explains **why** the serving knobs work. The knobs themselves — what to turn, in what
order, and what to measure — are `evaluate-optimize-models/references/token-latency-cost.md`.
Read that one to act; read this one to understand what you are trading away.

## Contents

- Prefill and decode are two different workloads
- The KV cache, and why memory is the real constraint
- Continuous batching
- FlashAttention
- Speculative decoding
- Attention variants that change serving economics
- Quantization
- Summary: what each technique actually trades

## Prefill and decode are two different workloads

A generation request has two phases with opposite hardware profiles:

- **Prefill** — the whole prompt is processed in one parallel pass. All tokens are known, so the
  GPU is doing large matrix multiplications: **compute-bound**. Cost scales with prompt length.
- **Decode** — tokens are produced one at a time, each depending on the last. Per token the
  arithmetic is small but the entire model's weights must be read from memory:
  **memory-bandwidth-bound**. Cost scales with output length.

Almost every serving surprise follows from this split:

- **Time-to-first-token is a prefill measurement; inter-token latency is a decode measurement.**
  Reporting one average hides which half is slow. This is why `token-latency-cost.md` insists on
  TTFT and p95 separately.
- **Output tokens usually cost more than input tokens**, because decode is the phase that cannot
  be parallelized across positions.
- **Batching helps decode enormously** — the weights are read once for the whole batch — and
  helps prefill much less.

## The KV cache, and why memory is the real constraint

During decode, the keys and values of all previous tokens are needed at every step.
Recomputing them each time would be quadratic, so they are cached — the **KV cache**.

The cache grows with batch size × sequence length, and it lives in the same GPU memory as the
weights. In practice **the KV cache, not the weights, is what limits how many concurrent
requests a GPU can serve**. That is the single most useful fact in this file for capacity
planning.

### PagedAttention

Kwon et al., "Efficient Memory Management for Large Language Model Serving with PagedAttention"
(2023, <https://arxiv.org/abs/2309.06180>) identified that naive serving wastes this memory
through **fragmentation** and **duplication**, which caps batch size.

The mechanism is borrowed from operating systems: manage the KV cache like **virtual memory with
paging** — non-contiguous blocks, allocated on demand, shareable within and across requests.
The paper reports **2–4× throughput improvement** at comparable latency versus systems of the
time, with larger gains for longer sequences and more complex decoding.

Practical reading: this is why a vLLM-class server beats a naive loop by a margin no prompt
tuning will recover, and why shared prefixes (a common system prompt across users) are cheaper
than they look.

## Continuous batching

Static batching makes every request in a batch wait for the slowest to finish. Continuous
(rolling) batching admits new requests as soon as any sequence completes, keeping the GPU busy.

- **Buys:** throughput at high concurrency; better tail latency than static batching.
- **Costs:** a scheduler, and latency that now depends on your neighbours in the batch.
- **Metric that matters:** batch occupancy. GPU-hours only become throughput if the batch is
  full — which is why `token-latency-cost.md` names utilization as the number to watch.

## FlashAttention

Dao et al., "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness" (2022,
<https://arxiv.org/abs/2205.14135>).

The key word is **exact**. FlashAttention is not an approximation — it computes the same
attention, faster, by being **IO-aware**: it tiles the computation so data moves less between
the GPU's large-but-slow HBM and its small-but-fast on-chip SRAM. The bottleneck it removes is
memory traffic, not arithmetic.

Reported speedups in the paper: ~15% end-to-end on BERT-large (seq 512), 3× on GPT-2 (seq 1K),
2.4× on long-range arena (seq 1K–4K). The authors separately extend it to *block-sparse*
attention, which **is** approximate — keep the two apart when explaining this.

Why it matters to an application engineer: you almost never enable it yourself, but it is the
reason long-context serving became practical, and it is a clean example of a speedup that costs
you **nothing in quality** — unlike quantization or sparse attention, which do.

## Speculative decoding

Leviathan, Kalman & Matias, "Fast Inference from Transformers via Speculative Decoding" (2022,
ICML 2023, <https://arxiv.org/abs/2211.17192>).

A small **draft model** proposes several tokens; the large **target model** verifies them in one
parallel pass, accepting the longest correct prefix. Decode's sequential bottleneck is partly
converted into a parallel one.

The property that makes it safe: the paper explicitly claims **the output distribution is
unchanged** — exact decoding from the large model, demonstrating identical outputs, with no
retraining or architecture change. Reported acceleration: 2–3× on T5-XXL versus the standard
implementation.

- **Fails by:** a draft model that disagrees too often. Speedup depends on the **acceptance
  rate**, which is workload-specific — verify on your traffic rather than quoting a paper's
  number, which is exactly what `token-latency-cost.md` says.
- Note the asymmetry worth teaching: this technique buys latency **without** a quality
  trade-off. Quantization does not. Treat them differently when advising.

## Attention variants that change serving economics

### Multi-query and grouped-query attention

Ainslie et al., "GQA: Training Generalized Multi-Query Transformer Models from Multi-Head
Checkpoints" (EMNLP 2023, <https://arxiv.org/abs/2305.13245>).

The KV cache is dominated by the number of key/value heads:

- **Multi-head attention (MHA)** — one KV head per query head. Best quality, biggest cache.
- **Multi-query attention (MQA)** — a single KV head. Much faster decoding, but can cost quality.
- **GQA** — an intermediate number of KV heads, grouping queries. The paper positions it as
  achieving quality close to MHA at speed comparable to MQA.

This is why two models with the same parameter count can have very different serving costs, and
why "how big is it" is a poor question compared with "what is its KV footprint per token".

### Mixture of experts

Only a subset of experts is activated per token, so **active** parameters are far fewer than
**total** parameters. Compute per token drops; memory does not — all experts must be resident.
An MoE model can therefore be fast and still require a large GPU footprint, which breaks the
intuition that a faster model is a smaller deployment.

## Quantization

Store (and often compute) weights at lower precision — 8-bit, 4-bit — to shrink memory and speed
the memory-bound decode phase.

- **Buys:** VRAM headroom (often the difference between fitting a model and not), faster decode,
  bigger batches because the KV cache has more room.
- **Costs:** a quality change that is **model- and task-specific**, and not reliably predicted by
  published averages.
- **The rule this plugin holds:** quantization claims are measured, never assumed. Run your own
  eval before and after, on your own task. Generic "4-bit is basically lossless" statements are
  the kind of claim `CLAUDE.md` forbids repeating.

Contrast with FlashAttention and speculative decoding above: those are exact and cost quality
nothing; quantization is a genuine trade. Say which kind you are recommending.

## Summary: what each technique actually trades

| Technique | Buys | Quality cost |
|---|---|---|
| FlashAttention | Speed, longer contexts | **None** (exact) |
| PagedAttention | 2–4× throughput, bigger batches | **None** (memory management) |
| Continuous batching | Throughput at concurrency | None; tail latency depends on neighbours |
| Speculative decoding | 2–3× decode latency | **None** (distribution preserved); gain varies with acceptance rate |
| GQA / MQA | Smaller KV cache, faster decode | MQA can cost quality; GQA close to MHA |
| MoE | Compute per token | Memory unchanged — all experts resident |
| Quantization | VRAM, decode speed | **Real and task-specific — measure it** |
