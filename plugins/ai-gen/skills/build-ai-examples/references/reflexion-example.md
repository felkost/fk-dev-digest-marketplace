# Worked example: a solver-critic Reflexion loop (`reflexion_example`)

Runnable code lives in `scripts/reflexion_example/`. A pure `reflexion_core.py` implements the
loop's control flow and an anti-oracle checker; `agent.py` wires the same logic into a real
LangGraph `StateGraph` with a model as the solver. The pattern — what Reflexion actually is, the
primary-source citation, and the feedback-signal honesty this example exists to demonstrate — is
in `design-agent-architecture/references/reasoning-patterns.md`; this file covers the build.

## Contents

- Run it
- Layout
- Decisions worth explaining
- What the tests pin
- Production deltas

## Run it

```bash
cd scripts/reflexion_example
pip install -r requirements.txt
cp .env.example .env          # fill in OPENROUTER_API_KEY -- get one at openrouter.ai
python agent.py
```

`reflexion_core.py` needs no key at all — the loop's control flow and the checker are plain
Python, not model calls. Only `agent.py` spends OpenRouter credit, and only when you run it.

## Layout

```
scripts/reflexion_example/
├── reflexion_core.py   # pure: Task/checker, the loop, the stopping rule
├── agent.py             # framework: LangGraph graph, the solver's model call, CLI entry
├── .env.example
└── requirements.txt
```

## Decisions worth explaining

### 1. The critic is deterministic, on purpose — not a compromise

A triaged book's demo hands its LLM critic the expected answer directly, so the "critic" compares
against a memorized target instead of evaluating the work
(`reasoning-patterns.md` has the primary-source correction). This example does not fix that by
finding a cleverer prompt for an LLM critic — it removes the LLM from the critic role entirely.
`Task.check` in `reflexion_core.py` is a plain function: extract the last number in the answer,
compare it to the value the task was built with. Shinn et al.'s abstract explicitly allows an
"external" feedback signal, and a deterministic checker is the *strongest* form one can take — it
cannot be talked out of a wrong answer the way a second model call sometimes can be. The solver in
`agent.py` is the only model call in the whole loop.

### 2. The task binds its own checker — the fix is structural, not a discipline to remember

The book's demo checks every problem against one module-level `TARGET_DAYS`, which is still set to
an earlier puzzle's answer by the time a later puzzle runs (the puzzle variable is assigned twice;
the check is not). `make_arithmetic_task(prompt, expected)` in `reflexion_core.py` builds the
prompt and its checker in the same call, so there is no shared global for a second task to
inherit. `tests/smoke_test.py`'s "success predicate is derived from the current task" check builds
two tasks from the factory and proves neither accepts the other's answer — the way to catch this
bug class is to make it structurally hard to write, not to remember to avoid it.

### 3. Numeric extraction, not substring containment — both of the book's bugs share one shape

`TARGET_DAYS in answer` passes for `"the trip takes 126 days"` because `"26"` is a substring of
`"126"`; a second, leftover condition, `"correct" in answer.lower()`, passes for an answer that
says the claim is **"incorrect"**, because `"correct"` is a substring of `"incorrect"`.
`_extract_last_int` in `reflexion_core.py` uses `re.findall(r"-?\d+", text)` and compares the
**parsed integer**, never a string, to `expected` — a longer number cannot satisfy a shorter one,
and no word ever gets compared to another word. `tests/smoke_test.py` pins both traps by name with
the same numbers the book's demo uses (26 and its substring "126"; "correct" inside "incorrect").

### 4. One decision function, used by both the pure loop and the LangGraph conditional edge

`should_stop(passed, attempt_number, max_attempts)` is the loop's entire stopping rule.
`run_reflexion` (the pure core) calls it at the end of every attempt; `agent.py`'s
`route_after_check` — the LangGraph conditional edge — calls the *same* function to decide whether
to route back to the `solve` node or to `END`. Reflexion needs orchestration code the same way
Tree of Thoughts does (`reasoning-patterns.md`); the risk that code introduces is a graph that
loops on a different rule than the one that was tested offline. Sharing the function instead of
reimplementing the check twice removes that risk rather than documenting it.

### 5. Hint accumulation is one item per failed attempt, threaded through state, not memory

Each failed attempt's feedback is appended to a `hints` tuple carried in the graph's state (and in
`run_reflexion`'s local list); the solver's prompt renders the full accumulated list on every
attempt. This is the "plan is a property of the architecture, re-read each step" point from
`reasoning-patterns.md`, applied to feedback instead of a plan: the model never carries anything
between calls on its own, so growing context has to be assembled and handed back explicitly.

## What the tests pin

`python tests/smoke_test.py` — this file's share is checks 24-34 (rag_example's and mcp_example's
shares are in their own reference files). All offline, bare interpreter, no key/network/langgraph
installed:

| Checks | What breaks if they go |
|---|---|
| Files exist; `reflexion_core` imports; imports are **stdlib-only** | The loop stops being testable without a full install |
| `"126"` does not pass for `expected=26`; `"the trip takes 26 days"` does | The exact substring trap the book's demo has |
| `"That is incorrect."` does not pass for any expected value | The exact leftover-condition trap the book's demo has |
| Two tasks from the same factory never accept each other's answers | A predicate that quietly outlives the task it was built for |
| `run_reflexion` stops the instant a check passes (not one attempt later, not one earlier) | An off-by-one that burns an extra model call or reports failure on a solved task |
| Hints grow by exactly one per failed attempt, and `solve()` receives them | Feedback silently not reaching the next attempt — the loop retries blind |
| `run_reflexion` halts at `max_attempts` when never solved | An agent that can loop forever calling the same broken solver |
| `.env.example` covers every variable `agent.py` reads; ships no filled-in secret | Silent misconfiguration or a leaked key |

**The LangGraph wiring itself was run for real, not only reviewed** — `build_graph()` compiled and
`.invoke()`d against a scripted stub standing in for the model (`.invoke(message) -> object with
.content`, no API key, no network), exercising the actual `StateGraph`, the actual conditional
edge, and the actual state merge across nodes. Four cases: solved on the first attempt; failed
once with the hint verified reaching the second `solve()` call; never solved, halting at
`max_attempts` rather than hitting `recursion_limit`; and the substring-trap answer resolving
correctly inside the compiled graph, not only inside the pure module it delegates to. **Not run
this round, and it needs the user's OpenRouter key to change that:** `agent.py`'s actual model
call — the graph's wiring was verified live; the solver's real answer was not, per the plugin's
standing rule that spending the user's credit needs their say-so first.

## Production deltas (state these with the example)

This is a teaching scaffold. Before it carries real traffic:

- **The critic only checks arithmetic.** A real Reflexion deployment's checkable property is
  whatever the domain actually offers — tests passing, a schema validating, a compiler not
  erroring. Swap `Task.check` for that domain's verifier; the loop and the graph do not change.
- **No cost cap.** `max_attempts` bounds iterations, not spend — pair it with a wall-clock/cost
  budget the way `autonomy-contracts.md` requires for any unattended loop, especially once the
  solver is a larger or slower model than the demo's default.
- **No persistence.** State lives in one `.invoke()` call; a production loop that can be
  interrupted needs the attempt history and hints durable across a restart (checkpointing is
  LangGraph's own mechanism for this — verify its current API before adding it, per this plugin's
  standing rule on identifier drift).
- **A richer feedback signal than "too high/too low"** is worth the extra latency once the domain
  supports it — an LLM-generated hint layered *on top of* the deterministic pass/fail, never
  replacing it, keeps the stopping decision incorruptible while improving what the solver has to
  work with.
- **Structured logging per attempt**, not `print` — the same operational gap
  `mcp-example.md` names for its own scaffold.
