# loop_example: a Layer-2 research loop whose guarantees live in the harness

`scripts/loop_example/` implements the inner execution loop that
`design-agent-architecture/references/agent-loop.md` specifies, split the same
way every example in this plugin is split:

- **`loop_core.py`** — pure stdlib logic, zero import-time side effects: the
  layered stop gate, the stagnation detector, the de-duplicated follow-up
  queue with a named breadth/depth parameter, the offload log, and `run_loop`
  with the explorer/writer separation. Everything the loop *guarantees* is
  here, in deterministic code, offline-testable.
- **`agent.py`** — the only part that costs money: a real model behind
  `explore_fn` and `write_fn` via OpenRouter, guarded by `__main__`.

## Why this example exists

Its published counterpart — the deep-research loop in *AI Agents in Action*
ch. 9 (`chapter_09/04_deep_research_loop.py`) — promises five layered stop
conditions in prose and ships three checks in code: status, iteration count,
non-empty queue. No cost cap, no stagnation detection, an ever-growing
follow-up queue, and a module that executes `asyncio.run(main())` (and reads
an API key) at import time. This example is the same pattern with the gate the
prose promises actually implemented, and with offline tests for exactly the
properties the specimen lacks.

## The design decisions worth copying

- **`stop_reason()` returns a name, not a bool.** "Why did it stop" is the
  first debugging question; the reason (`iteration_cap` / `cost_cap` /
  `wall_clock_cap` / `stagnation` / `queue_exhausted` / `goal_predicate`) is
  data in the run record, and the gate is a conjunction of independent
  families evaluated every iteration in the harness, never inside the model.
- **Stagnation is structural, not verbal.** `StagnationDetector` compares
  consecutive iteration summaries (word-set Jaccard, threshold 0.8) — the
  offline-computable stand-in for embedding cosine; the mechanism (compare
  consecutive summaries, stop above a threshold) is what the production
  upgrade keeps. The source this answers defines stagnation two incompatible
  ways (semantic 85% in prose, word overlap 80% in its exercise); here one
  mechanism is picked, named, and tested.
- **The queue refuses re-entry forever.** `FollowUpQueue` normalizes and
  remembers every question ever pushed (`_seen`), so a re-asked question
  cannot re-enter even after being popped — the "broken record" failure needs
  the queue's cooperation, and doesn't get it. `order="breadth"|"depth"` makes
  the which-end-do-you-pop decision a recorded parameter.
- **Tool output is offloaded every iteration.** `OffloadLog.store(raw)`
  returns `(id, digest)`; findings carry ids, the writer sees summaries, and
  `fetch(id)` keeps originals addressable — compaction must never orphan the
  evidence.
- **The explorer cannot write the report.** `run_loop` takes `explore_fn` and
  `write_fn` as separate callables and the findings list is the only thing
  that crosses between them. In `agent.py` they are separate prompts; the
  writer is instructed to cite finding ids and synthesize only from them.
- **The clock is injected.** `run_loop(clock=...)` defaults to a stub that
  never fires the wall-clock cap, so tests are deterministic; `agent.py`
  passes `time.monotonic`.

## What the smoke test pins (offline, no key, no network)

1. The module **imports without executing anything** — the property three of
   the published repo's own loop files fail.
2. `loop_core` imports **stdlib only**.
3. The loop **halts with `stop == "stagnation"`** when the explorer returns
   two near-identical summaries, and the third exploration never runs.
4. The queue **de-duplicates**: pushing the same question twice (in different
   case/punctuation) queues it once, and it can never re-enter after popping.
5. `breadth` pops the seed's siblings first; `depth` pops the newest
   follow-up first — the parameter provably changes traversal order.
6. The **cost cap** stops a loop whose explorer never stagnates and always
   has follow-ups, and the run record says `cost_cap`.
7. `.env.example` and `agent.py` agree on every required variable name.

## Running the paid path

```bash
cd skills/build-ai-examples/scripts/loop_example
cp .env.example .env      # fill in OPENROUTER_API_KEY
pip install -r requirements.txt
python agent.py
```

Expected shape: a handful of explore calls (budgeted at 4 iterations /
$0.05 / 120 s for the demo), then `stopped by: <reason>` and a short cited
report. The run costs real OpenRouter credit; the budget numbers exist to
keep a demo run cheap, not as recommendations.
