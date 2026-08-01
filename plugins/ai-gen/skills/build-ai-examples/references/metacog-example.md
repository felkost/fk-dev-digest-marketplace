# metacog_example: a gate that reads state, not a claim

`scripts/metacog_example/` implements the testable pieces `design-agent-architecture/
references/agent-metacognition.md` specifies: a confidence gate that decides from tracked state
instead of a verbal claim, a stagnation detector with two independent signals (content repeating,
confidence flatlining), and a resolver that prefers a genuinely implicit confidence signal when
one is available and degrades to a declared fallback when it is not.

- **`metacog_core.py`** — pure stdlib, zero import-time side effects: `check_confidence_gate`,
  `detect_stagnation` (and its two component checks, `detect_content_stagnation` and
  `detect_confidence_plateau`), `resolve_confidence`.
- **`agent.py`** — the only part that costs money: asks a real model for its per-token logprobs
  (OpenRouter's `logprobs`/`top_logprobs`), turns them into an implicit confidence estimate, and
  runs the result through the gate. When the provider returns no logprobs, `resolve_confidence`
  demotes to a declared fallback instead of guessing.

## Why this example is shaped the way it is

The reference's central correction is that a source can argue for an implicit,
logprob-derived confidence signal in prose while its own shipped code never touches a logprob
anywhere — the confidence value it actually computes is an LLM's self-reported float, a verbal
judgment wearing a numeric type. This example is built to not repeat that gap: `agent.py` is the
one place a real logprob is requested and read, `metacog_core.py`'s `resolve_confidence` never
fabricates an implicit-looking number when none was returned, and the two paths are
distinguishable in the output (`source=implicit_logprob` vs `source=fallback_declared`) rather
than silently merged into one undifferentiated `confidence` field.

The stagnation detector is deliberately two independent checks rather than one. `agent-loop.md`'s
existing detector compares consecutive summaries by word overlap — "the offline stand-in for
embedding cosine, mechanism identical" in that file's own words. This example carries the
mechanism it stood in for (cosine over embeddings, injectable as stub vectors so no embedding
endpoint is needed to test it) and adds a signal that has no analogue there at all: a confidence
trend that has flatlined even while the content keeps marginally changing. A detector that
watches only one of the two misses the failure shape the other one catches.

## The design decisions worth copying

- **`ConfidenceState.trend` is history strictly *before* the current reading.** The caller appends
  the previous value before updating `value`, so the declining-trend check in
  `check_confidence_gate` can never compare a reading against itself.
- **An open contradiction blocks presentation even above the confidence ceiling.** Confidence and
  consistency are independent axes in this design on purpose — a high-confidence answer that
  still has an unresolved contradiction is not safe to present just because the number is high.
- **`detect_stagnation` always reports *which* signal fired** (`"content_overlap"` or
  `"confidence_plateau"`), never a bare boolean — the same "name the reason" discipline
  `loop_example` and `tdad_example` both use for their own stop/failure verdicts, so a caller
  logs why it replanned instead of just that it did.
- **`resolve_confidence` returns a `source` alongside every `value`.** A caller (or this example's
  own `agent.py`) can print or log which path produced the number; nothing downstream can mistake
  a declared 0.5 fallback for a model's actual token probabilities, because the label travels with
  the value instead of being inferable only from which branch happened to run.

## What the smoke test pins (offline, no key, no network)

1. The module **imports without executing anything**, and imports **stdlib only**.
2. **The gate signals uncertainty below the floor**, regardless of any other state.
3. **The soft band gathers more while a retry budget remains, and signals uncertainty once it is
   exhausted** — the same confidence value produces two different decisions depending on
   `retries_used`.
4. **An open contradiction forces `GATHER_MORE` even at high confidence** — confidence alone does
   not clear the gate.
5. **A declining confidence trend forces `GATHER_MORE` at high confidence; a flat-or-rising trend
   presents** — the trend check only ever tightens the gate, never loosens it.
6. **`cosine` rejects mismatched dimensions and returns `0.0` for a zero vector**, mirroring
   `rag_example`'s own cosine edge cases rather than reinventing them differently.
7. **Content stagnation fires on near-identical injected vectors and not on dissimilar ones.**
8. **Confidence-plateau stagnation fires on a flatlined trend even when the injected embeddings
   are deliberately dissimilar** — the case that proves the two signals are independent, not one
   dressed up as two.
9. **`implicit_confidence_from_logprobs` returns a value in `(0, 1]` given real logprobs, and
   returns `None` — never a guessed number — given none.**
10. **`resolve_confidence` labels its source correctly in both directions**, and the fallback
    branch returns the caller's fallback value **unchanged**.
11–12. `.env.example` covers every variable `agent.py` reads and ships no filled-in secret.

## Running the paid path

```bash
cd skills/build-ai-examples/scripts/metacog_example
cp .env.example .env      # fill in OPENROUTER_API_KEY
pip install -r requirements.txt
python agent.py
```

Expected shape: two questions, each printed with the model's answer and a line naming the
confidence value, its source, and the gate's decision. Whether the second line reads
`source=implicit_logprob` or `source=fallback_declared` depends entirely on whether the chosen
model returns logprobs through OpenRouter — both are a correct run of this example, and seeing
the fallback path fire is exactly the graceful-degradation property `agent-metacognition.md`
describes, not a bug in the demo.
