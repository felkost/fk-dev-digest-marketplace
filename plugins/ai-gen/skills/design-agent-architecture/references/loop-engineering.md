# Loop engineering: building the system the agent runs inside

Most "make the agent better" requests are not model problems. They are *loop* problems: the
agent has no schedule, no isolation, no written project knowledge, no connection to the real
tools, and nobody checking its work except the thing that produced it. This file is about the
machinery around the model.

Primary source for the component set: Addy Osmani, "Loop Engineering",
<https://addyosmani.com/blog/loop-engineering/>. Where a claim is not his, it is marked.

## Contents

- The frame
- The five components
- The sixth thing: external state
- Maker-checker, stated as a rule
- Where loops sit in the capability taxonomy
- What the loop does not do for you
- When not to build a loop
- Recommending a loop: the minimum viable set

## The frame

A single agent invocation is a transaction: prompt in, answer out. A *loop* is a standing
arrangement where work is discovered, executed, checked, and recorded without a human
initiating each cycle. The engineering question is not "how smart is the model" but "what does
the model sit inside".

Osmani's framing is that the operator role — a human typing one prompt at a time and grading
each answer — does not scale, and the alternative is to build the loop rather than to be it.

> **Judgment (not in the source):** the loop is worth building when the same shape of task
> recurs on a cadence *and* its output can be checked mechanically. One-off work does not repay
> the setup, and unverifiable work turns the loop into an unattended mistake generator (see
> "What the loop does not do" below).

## The five components

Osmani names five pieces, listed here in his order with the trade-offs this plugin requires
for every recommendation.

### 1. Automations — the heartbeat

Scheduled runs that "go off on a schedule and do discovery and triage by themselves". This is
what makes the loop a loop rather than a faster manual session.

- **Buys:** work starts without a human present; triage happens before you open the laptop;
  the backlog is surveyed on a cadence instead of when someone remembers.
- **Costs:** every scheduled run spends tokens whether or not there was work to do; a
  misconfigured schedule multiplies that silently.
- **Fails by:** running on a stale definition of "work to do"; producing a queue nobody
  drains, which converts a scheduling problem into a human-attention problem.

Session-level variants exist alongside scheduled ones: Osmani distinguishes a loop that re-runs
on a cadence from one that runs until a condition is met. The second form is the one that needs
a stop contract — see `autonomy-contracts.md`.

### 2. Worktrees — parallelism without collisions

Isolated checkouts so "two agents working in parallel don't step on each other".

- **Buys:** genuine concurrency; a failed experiment is discarded by deleting a directory.
- **Costs:** disk, setup, and per-tree environment installation; merge work returns at the end.
- **Fails by:** shared mutable state the worktree does not isolate (one database, one cache,
  one API rate limit, one `.env`); long-lived trees that drift far enough to make the merge
  more expensive than the parallelism saved.

> **Local gotcha (this repo, not the source):** on Windows, worktrees belong on a short path
> because of `MAX_PATH`, and `node_modules` is cheaper as a junction than a copy. Removing a
> tree may need `cmd /c rmdir`.

### 3. Skills — project knowledge, written down once

`SKILL.md` files that record what the agent would otherwise guess, so you "stop explaining your
project every single time".

- **Buys:** consistency across sessions and across models; conventions survive context resets;
  review effort moves from every answer to the skill file itself.
- **Costs:** skills are code that rots. A stale skill is worse than none because it is trusted.
- **Fails by:** encoding a decision without its reason (the next session cannot tell an
  invariant from an accident); growing past what an agent will actually read; drifting from
  the repo it describes with nothing checking the drift.

The counter-measure to the last failure is a docs guard that fails the build when the written
claim and the repo disagree — this plugin's `tests/check_docs.py` exists for that reason.

### 4. Plugins and connectors — the loop touches real tools

Connections that let the agent "read your issue tracker, query a database, hit a staging api,
drop a message in Slack". MCP is the protocol this plugin uses for that surface; tool design and
permissions live in `mcp-tools.md`.

- **Buys:** the loop acts on the real system of record instead of on a description of it.
- **Costs:** every connector is credentials, an availability dependency, and a new blast radius.
- **Fails by:** write access granted where read would have done; tool output treated as
  instructions rather than data (prompt injection through a ticket title or a fetched page);
  silent connector failure that the loop interprets as "nothing to do".

### 5. Sub-agents — keep the maker away from the checker

Separate agents for producing and for reviewing. Osmani's argument is blunt: the model that
wrote the code is "way too nice grading its own homework", and a second agent with different
instructions "catches the stuff the first one talked itself into".

- **Buys:** an independent read of the work; specialization of instructions per role.
- **Costs:** multiplied tokens; a coordination surface; two things to keep in sync.
- **Fails by:** a checker that inherits the maker's context or its prompt — it then rehearses
  the same reasoning and approves it. Independence is the entire mechanism; sharing context
  destroys it while leaving the appearance of review intact.

## The sixth thing: external state

Osmani adds state outside the model — "a markdown file, or a Linear board" — holding what is
done and what is next. Without it, the loop's memory is the context window, and the context
window ends.

- Cheap form: a tracked markdown file in the repo (auditable, diffable, editable by hand).
- Structured form: the issue tracker the team already uses, so humans and agents share one
  queue rather than two.
- This is the per-project twin of the per-session `HANDOFF.md` protocol in
  `plan-ai-solution/references/handoff.md`, and of the persistent knowledge base pattern in
  `memory-vector-db.md`. Same problem — state that outlives the context — at three scopes.

## Maker-checker, stated as a rule

1. The checker runs with **different instructions** from the maker.
2. The checker does **not** receive the maker's reasoning trace — only the artifact and the
   criteria. (Osmani notes a different model is optionally useful; the non-negotiable part is
   the separation of instructions and context.)
3. The criteria are **machine-checkable wherever possible**: tests, schema validation, a lint
   run, a diff against an expected shape. An LLM judge covers what is left, with its biases
   named — see `evaluate-optimize-models/references/evaluation.md`.
4. A checker that never rejects anything is not calibrated; measure its rejection rate before
   trusting it.

Point 2's optional part has a named mechanism behind it: coordinating a generator–reviewer pair
introduces confirmation bias when both agents share similar training data, so a reviewer drawn
from a different model family is what turns the check into independent evidence rather than a
second opinion from the same prior (Karim, Khan, Van, Liu, Wang & Qu, "Transforming Data
Annotation with AI Agents", *Future Internet* 2025, 17(8), 353, §7.2,
<https://doi.org/10.3390/fi17080353>).

This is the same shape as the **evaluator-optimizer** workflow in Anthropic's "Building
Effective Agents" (<https://www.anthropic.com/research/building-effective-agents>): one call
generates, another evaluates and feeds back, in a loop. Anthropic's condition for it applies
here too — it pays when evaluation criteria are clear and iterative refinement measurably
improves the result. See `architectures.md` for the full pattern set.

## Where loops sit in the capability taxonomy

Google's "Introduction to Agents" whitepaper (November 2025) classifies agentic systems by
capability, not by tooling maturity: Level 0 reasoning-only, Level 1 tool-connected, Level 2
strategic planner, Level 3 multi-agent collaboration, Level 4 self-evolving. Loop engineering
is orthogonal to that ladder: it is the operational scaffolding that lets a Level 1–3 system run
unattended. A better loop does not raise the capability level, and a higher level does not
supply automations, isolation, or a checker. Do not sell one as the other. (Table and citation:
`architectures.md`.)

## What the loop does not do for you

Osmani's own list of what remains after the loop is built — these are the risks to name when
recommending one:

| Risk | What it looks like | Counter-measure |
|---|---|---|
| Verification burden | "A loop running unattended is also a loop making mistakes unattended" | Machine-checkable criteria; maker-checker; gates on irreversible steps |
| Comprehension debt | The faster the loop ships code you did not write, the wider the gap between what exists and what you understand | Cap merged-without-reading volume; require the loop to explain diffs, not just produce them |
| Cognitive surrender | "It's very tempting to stop having an opinion and just take whatever it gives back" | Review the criteria, not only the output; periodically reject on principle and see if the loop notices |
| Token cost variability | Usage patterns "can vary wildly" | Budget caps in the stop contract; alerting on per-run cost, not monthly totals |

> **Judgment (not in the source):** add *false-confidence-from-green-tests*. A loop optimizing
> against a test suite optimizes against the suite, not the requirement; tests the agent wrote
> for its own output are the checker sharing the maker's context in another costume.

## When not to build a loop

- The task runs once, or its shape changes every time — setup cost never amortizes.
- No mechanical success criterion exists, and no human will read every output. The loop then
  produces unverifiable volume.
- The action is irreversible and cheap to get wrong (money movement, publishing, deletion).
  Keep a human gate; see human-in-the-loop in `architectures.md`.
- The bottleneck is upstream: unclear requirements do not become clear by being processed faster.

## Recommending a loop: the minimum viable set

Not every loop needs all five components. In order of what usually pays first:

| Situation | Minimum set |
|---|---|
| Same task, recurring, output checkable | Automation + external state + machine criteria |
| Agent keeps re-learning the project | Skills first; automation is premature |
| Work must touch the real tracker/DB | Connectors, read-only, before any write path |
| Output quality is the complaint | Sub-agent checker before more capable models |
| Multiple experiments at once | Worktrees; otherwise the experiments corrupt each other |

Pair every recommendation here with a stop contract from `autonomy-contracts.md`: an
autonomous loop without one is not an architecture, it is an open-ended spend.
