# Token, latency, and cost optimization

Order of leverage, highest first. Every change is a before/after pair on the same eval set —
an optimization that loses quality you didn't measure is a regression you shipped.

## 1. Prompt and context budget

- Cut dead weight: repeated instructions, over-long few-shot examples, boilerplate the model
  ignores. The system prompt is paid on every call.
- Retrieve less, better: in RAG, tighter top-k with reranking usually beats stuffing the
  window; measure groundedness before/after.
- Summarize history instead of replaying it (rolling summary + last N turns).
- Cap output: `max_tokens` sized to the task, "be concise" in the instruction, structured
  output instead of prose where a schema suffices (output tokens usually cost more than input).

## 2. Caching

- **Provider prompt caching**: keep a stable prefix (static instructions/tools first, volatile
  content last) so cached-token pricing applies; verify support per provider/model.
- **Response caching**: exact-match or normalized-key cache for repeated queries (FAQ-shaped
  traffic); semantic caching (embedding-similarity hit) buys more but needs a correctness
  threshold and an invalidation story.
- Cache tool results (search, DB lookups) inside agent runs — agents repeat calls.

## 3. Model right-sizing and routing

- Route easy traffic to a cheaper model, escalate hard cases (classifier or heuristic router;
  or draft-with-small + verify-with-large). Often the single biggest cost lever.
- Re-shortlist models periodically: price/performance moves monthly (see
  `select-genai-models`' micro-eval procedure).
- Fine-tuning a small model to replace a prompted large one pays off at sustained volume —
  do the arithmetic with measured tokens/request, not list prices.

## 4. Concurrency, batching, streaming

- Parallelize independent calls (map steps in LangGraph); agent latency is usually serial
  tool-call chains — shorten the chain before speeding the model.
- Batch offline workloads (many providers offer discounted batch APIs with relaxed latency).
- Stream user-facing output: perceived latency is time-to-first-token; report TTFT and
  p50/p95 total separately.

## 5. Self-hosted serving knobs (only for open weights)

- Quantization (4/8-bit) shrinks VRAM and speeds decoding; quality cost is model- and
  task-specific — eval before/after, don't trust generic claims.
- vLLM-class servers: continuous batching and KV-cache paging dominate naive serving;
  utilization (batch occupancy) is the metric that turns GPU-hours into throughput.
- Speculative decoding where supported: measured speedup varies with acceptance rate — verify
  on your traffic.

**Why these knobs work** — prefill vs decode, the KV cache as the real capacity limit,
PagedAttention, continuous batching, and which techniques are *exact* (FlashAttention,
speculative decoding) versus a genuine quality trade (quantization) — is
`explain-llm-internals/references/inference-internals.md`. Read it before promising a speedup:
two of the items above cost nothing in quality and one of them does.

## What to instrument (before optimizing anything)

Per request: input/output token counts, model ID, TTFT, total latency, cost (from usage
fields), cache hit/miss, agent iterations, tool-call count/duration. Aggregate: cost per
*solved* task and p95 end-to-end — those two are what the business feels; optimizing anything
else is proxy-chasing.

Once this runs in production, instrumentation becomes a discipline rather than a one-off:
trajectory tracing, sampled online judging, metrics-gated deploys and the incident→eval-case
loop are in [agent-ops.md](agent-ops.md).
