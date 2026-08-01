# reliability_example: the ladder as a state machine, idempotency as a name not a hash

`scripts/reliability_example/` implements the two pieces `deploy-ai-environments/references/
serving-release.md` specifies as testable: the time-budget → fallback → circuit-breaker →
graceful-degradation ladder, and the contrast between a correct operation-id-keyed idempotency
cache and the argument-hash anti-pattern from the companion repository.

- **`reliability_core.py`** — pure stdlib, zero import-time side effects: `CircuitBreaker`,
  `run_ladder()`, `IdempotencyCache` (correct), `ArgHashCache` (the anti-pattern, kept only to
  demonstrate the failure it causes).
- **`agent.py`** — the only part that costs money: a real primary model and a real fallback
  model behind `__main__`.

## Why this example exists

`chapter_08/06_idempotent_key_example.py` builds its cache key from `sha256(name + args)` with
**no caller-supplied operation id**. Two legitimately distinct operations that happen to share
arguments — a retry of the same logical action versus two separate actions that look identical
on the wire — collide under that key: the second call silently returns the first's cached result
instead of executing. `mcp-tools.md` already states the correct rule (an idempotency key needs a
caller-assigned operation id); this example is the executable version of that rule, contrasted
directly against the broken shape so the failure is something you can run, not just read about.

## The design decisions worth copying

- **`run_ladder()` always returns something usable, never a raw exception.** The result names
  which rung answered (`"primary"`, `"fallback:<name>"`, `"degraded"`, `"circuit_open"`) and the
  full attempt sequence — the same "return a name, not a bool" discipline `loop_example`'s
  `stop_reason()` and `tdad_example`'s `classify_failure()` both use, for the same reason: the
  caller (and whoever debugs the run later) needs to know *why*, not just *what*.
- **The circuit breaker's `HALF_OPEN` probe reopens immediately on failure**, without waiting to
  re-count failures — a failed probe is strong evidence the dependency is still down, and
  treating it as "one failure toward the threshold" would let a persistently broken dependency
  get probed on every request during its outage.
- **The time budget is checked by the caller, on the returned elapsed time — never trusted to
  the callee.** Both the primary and every fallback report `(elapsed, value)`; a call that
  returns fast but claims to have taken too long is treated as a budget failure just the same as
  a call that actually blocks, which is what makes the budget enforceable in a pure, clock-free
  test.
- **`IdempotencyCache` and `ArgHashCache` share the same call shape on purpose** — the only
  difference is what the key is built from (an explicit `operation_id` versus a hash of
  `name`+`args`), so the contrast test changes nothing except the cache class and still exposes
  the collision.

## What the smoke test pins (offline, no key, no network)

1. The module **imports without executing anything**, and imports **stdlib only**.
2. **The ladder tries primary first**, and a successful primary never touches any fallback.
3. **A primary that exceeds its time budget falls back**, and the fallback's own success is what
   the result reports.
4. **All rungs failing returns `"degraded"`** with the supplied degraded value — never an
   unhandled exception.
5. **The circuit breaker opens after the failure threshold** and sheds load (`"circuit_open"`)
   without calling primary at all while open.
6. **A successful `HALF_OPEN` probe closes the breaker**; a failed probe reopens it immediately.
7. **The idempotency contrast, the round's headline case**: two calls with the **same**
   `operation_id` and same args execute the underlying function once (the second is a cache
   hit); two calls with **different** `operation_id`s and **identical** args both execute under
   `IdempotencyCache` — but collapse into a single execution under `ArgHashCache`, reproducing
   `chapter_08/06`'s bug on purpose before the correct cache is shown fixing it.
8. `.env.example` covers every variable `agent.py` reads and ships no filled-in secret.

## Running the paid path

```bash
cd skills/build-ai-examples/scripts/reliability_example
cp .env.example .env      # fill in OPENROUTER_API_KEY
pip install -r requirements.txt
python agent.py
```

Expected shape: an `outcome: primary (attempts: primary)` line and the model's answer under
normal conditions. `CHAT_MODEL`/`FALLBACK_MODEL` are both `gpt-4o-mini` by default so the demo
runs cheaply; point `FALLBACK_MODEL` at a different model to see a real fallback substitution,
not just the ladder's control flow.
