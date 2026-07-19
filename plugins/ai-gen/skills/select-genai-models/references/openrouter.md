# Using the OpenRouter catalog well

OpenRouter is a single API over many providers' models (OpenAI-compatible `/chat/completions`),
useful for comparison shopping, fallback routing, and avoiding per-provider integration. Facts
below describe *mechanics*; concrete model IDs, prices and context sizes must be read from the
live catalog at decision time — never hardcode them into a recommendation as of a past date.

## Selection procedure

1. Filter the catalog by hard requirements first: modality (text/image in), tool-calling /
   structured-output support, context length, provider region/privacy policy if data is
   sensitive.
2. Shortlist 2–4 models across price classes (frontier / mid / budget). Include one open-weights
   model if self-hosting is a future option — it doubles as an exit strategy.
3. Run your own micro-eval (20–50 task examples) through the same prompt; compare quality,
   p50/p95 latency, and measured cost per request (usage is returned in the response).
4. Pin the exact model ID in config (not "auto") for reproducibility; record the choice and date
   in the project's HANDOFF.md.

## Mechanics worth knowing

- **API shape**: OpenAI-compatible; `base_url` override + `OPENROUTER_API_KEY` makes most SDKs
  and LangChain's `ChatOpenAI` work unchanged.
- **Fallbacks/routing**: a request can list several models (`models: [...]`) — OpenRouter falls
  through on errors/rate limits. Design the fallback chain deliberately: a cheaper fallback
  silently changes output quality; log which model actually served each request (the response
  carries it).
- **Variants**: some models expose `:free` (rate-limited, for prototyping only) and other
  suffixed variants; treat `:free` results as non-representative of paid latency/limits.
- **Provider routing**: the same model may be served by several backends with different privacy
  terms; when data is sensitive, constrain allowed providers explicitly in the request.
- **Cost control**: per-key spend limits in the dashboard; usage field per response for
  accounting; prompt caching support varies by underlying provider — verify before counting on
  cached-token discounts.

## Pitfalls

- Ranking by a public leaderboard instead of your eval set (leaderboard tasks ≠ your task).
- Letting "auto" routing pick models in production — irreproducible behavior across days.
- Ignoring tokenizer differences between shortlisted models when comparing "price per 1M
  tokens": the same text tokenizes to different counts; compare **cost per YOUR request**, not
  list price.
- Assuming every catalog model supports tool calling / JSON mode — check the capability flags
  per model, then verify with a live probe request; capability metadata can lag.
