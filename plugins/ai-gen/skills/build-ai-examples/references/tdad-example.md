# tdad_example: a Test-Driven Agent Development harness whose fixes are structural

`scripts/tdad_example/` implements the pieces `evaluate-optimize-models/references/
agent-tdad.md` specifies, split the way every example in this plugin is:

- **`harness_core.py`** — pure stdlib, zero import-time side effects: the normalizing
  evaluator, the grounding check that takes context as an explicit argument, N-repeat
  benchmark running, defect-localization classification, the minimum-change ladder, and
  the retry-ceiling policy. Everything the harness *guarantees* is here.
- **`agent.py`** — the only part that costs money: a real solver model behind
  `run_benchmark`, guarded by `__main__`.

## Why this example exists

Its motivating bug is `chapter_07/06_RAG_grounding_with_guardrails.py` from the *AI
Agents in Action* companion repository, triaged in an earlier round. Its polarity is
correct (`tripwire_triggered = result.is_answer_grounded is False`), but the grounding
agent reads context from a module-level global that every search call overwrites — no
concurrency required to break it, since a two-search answer already only ever gets
checked against the *last* search's context in a single-threaded run, and
`get_last_context()` returns `"No context available."` instead of failing, so a check
with no context can still come back "grounded." This example is the structural fix:
context is always an explicit parameter, and accumulated evidence is checked as a whole.

## The design decisions worth copying

- **`is_grounded(answer, context, threshold=...)` takes context as a plain argument.**
  There is no module state to race, so nothing needs a lock or a "don't call this
  concurrently" comment — the fix is the signature, not a smarter check.
- **`AccumulatingContext.snapshot()` returns an immutable copy.** Callers check against a
  point-in-time snapshot; a later `add()` cannot retroactively change a check that already
  ran, and a caller that wants the *accumulated* evidence (not just the newest piece) gets
  it by passing the full snapshot rather than the latest `add()`'s argument.
- **`classify_failure()` checks the evaluator's own correctness first.** If a normalized
  comparison says the raw output actually matches but the evaluator's verdict says fail,
  everything downstream — including a trajectory check — is checked against a broken
  oracle, so that has to be ruled out before anything else is diagnosed.
- **`run_benchmark()` returns a rate, never a single boolean.** A case that is right 3
  times out of 5 hands a one-shot harness a pass 3 times out of 5 — indistinguishable
  from reliable until it is run more than once.
- **`escalate_fix_tier()` only moves one step and refuses to skip.** Calling it on the
  most expensive tier (`"model"`) raises rather than wrapping around — there is nothing
  more expensive to escalate to, and silently no-op-ing would hide that the ladder is
  exhausted.
- **`retry_ceiling_action()` returns a named outcome, never a silent retry.** Under the
  cap it says `"retry"`; at the cap it returns one of a fixed, named policy set — an
  unrecognized policy string is a `ValueError`, not a default that quietly picks one.

## What the smoke test pins (offline, no key, no network)

1. The module **imports without executing anything**, and imports **stdlib only**.
2. `exact_match("Photons.", "photons")` is `True` — the normalizing-evaluator case the
   reference names by name.
3. **Polarity**: an answer whose claims are drawn from the context is grounded; an answer
   whose distinctive claims are absent from the context is not.
4. **Concurrency**: two `AccumulatingContext` instances built for two different "requests"
   never contaminate each other's `is_grounded` result, however their `add()`/`snapshot()`
   calls are interleaved — because nothing is shared between them by construction.
5. **Accumulated, not last**: an answer citing a fact from the *first* of two searches is
   NOT grounded when checked against the second search's content alone, but IS grounded
   against the full accumulated snapshot — the exact shape of the companion repo's bug,
   reproduced and then fixed.
6. **N-repeat flakiness**: a stub that passes 3 times out of 5 reports `pass_rate == 0.6`
   over `n=5` runs, not a false clean pass.
7. **Defect localization**: three synthetic cases resolve to `"evaluator_bug"`,
   `"instruction_bug"` and `"capability_gap"` respectively, from the same function.
8. **The ladder** escalates one tier at a time and raises past `"model"`.
9. **The retry ceiling** returns `"retry"` under the cap, the named policy at the cap, and
   raises on an unrecognized policy.
10. `.env.example` covers every variable `agent.py` reads and ships no filled-in secret.

## Running the paid path

```bash
cd skills/build-ai-examples/scripts/tdad_example
cp .env.example .env      # fill in OPENROUTER_API_KEY
pip install -r requirements.txt
python agent.py
```

Expected shape: five solver calls at nonzero temperature (repetition only tells you
anything if the solver can vary), a `pass_rate=` line, and for any red run a
`classify_failure` verdict plus the grounding check's result printed alongside the raw
reply. The run costs real OpenRouter credit; `temperature=0.7` and `n=5` exist to make the
flakiness demonstration visible in one run, not as production settings.
