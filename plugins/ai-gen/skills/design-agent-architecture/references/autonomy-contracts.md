# Autonomy contracts: what an agent is allowed to do without asking

An autonomous loop is an agent acting without per-step approval. The contract is what makes
that defensible: it states the goal, how success is checked *without asking the model*, what
the agent may touch, and when it must stop. No contract, no autonomy — an unbounded loop is a
budget with an agent attached.

Related: `loop-engineering.md` (the machinery the contract governs), `architectures.md`
(human-in-the-loop gates), `plan-ai-solution/references/handoff.md` (the per-session twin of
this per-task document).

## Contents

- Contract vs gate
- Anatomy
- Template
- Failure modes
- When a task is not ready for a contract

## Contract vs gate

Two different instruments, routinely confused:

- A **contract** *bounds* the loop. It is agreed once, up front, and evaluated mechanically
  while the agent runs. Its job is to make "keep going" and "stop" decidable without a human.
- A **gate** *interrupts* the loop. It is a checkpoint where a human approves, edits, or
  supplies a fact before the agent proceeds.

Contracts scale, gates do not. Gates belong where an action is irreversible, external, or
spends money; contracts cover everything between the gates. A design with only gates throttles
to human speed; a design with only contracts eventually does something irreversible that no
criterion anticipated. Most real systems need both, and the contract should name where the
gates are.

## Anatomy

A usable contract has five parts. Missing any one of them produces a specific failure, listed
in the last column.

| Part | What it states | Missing it causes |
|---|---|---|
| Measurable goal | The end state, in terms of an observable artifact — not an activity | The agent optimizes effort, not outcome; "worked on it" reads as success |
| Success criteria | Checks that pass or fail without a human or the model's own opinion | Self-graded completion; the maker approves its own homework |
| Boundaries | Files, services, credentials, and actions in and out of scope | Scope creep into systems nobody sanctioned |
| Budget | Iteration cap, wall-clock cap, token/cost cap | Unbounded spend on a task that was never converging |
| Stop factors | Conditions that end the run *without* success | Loops that thrash on an impossible task until the budget runs out |

### Measurable goal

State the artifact and its observable property. "Fix the flaky test" is an activity.
"`tests/test_sync.py::test_retry` passes on 20 consecutive runs" is a goal — it names the
artifact and how the world will differ.

### Success criteria that the model cannot satisfy by assertion

The criterion must be checkable by something that is not the agent: an exit code, a schema
validation, a diff, a metric threshold computed by a script. "The code is clean and well
documented" is not a criterion; "`npm run lint` exits 0 and every exported symbol has a
docstring, verified by `scripts/check_docs.py`" is.

Where no mechanical check exists, an LLM judge may stand in — but then it is a *measurement
instrument* and inherits the obligations in
`evaluate-optimize-models/references/evaluation.md`: named biases, human calibration on a
sample, and a rejection rate you have actually looked at. A judge that shares the maker's
context or prompt is not an independent check (see maker-checker in `loop-engineering.md`).

### Boundaries

Enumerate positively (what may be touched) rather than negatively (what may not). Negative
lists are always incomplete. Default to read-only for anything outside the named set, and treat
credentials as part of the boundary, not an implementation detail.

### Budget

Three caps, because they fail differently: **iterations** catch logical thrashing, **wall
clock** catches hangs and slow external calls, **cost** catches the expensive-model-in-a-loop
case. A loop with only an iteration cap can still burn an unbounded amount if each iteration
grows.

### Stop factors

The conditions under which the agent stops *and reports*, rather than continuing:

- The same failure repeats N times with no change in the error signature.
- A criterion that was passing starts failing (regression introduced by the loop itself).
- The task requires an action outside the boundaries — stop and ask, never widen scope silently.
- An external dependency is unavailable, so results would be meaningless rather than negative.
- Budget exhausted on any of the three axes.

Stopping is a success mode. A contract that only defines completion teaches the agent that
giving up is failure, and it will churn to avoid it.

## Template

The mentor can emit this directly into a user's repo. Keep it next to the code, in version
control, and update it when scope changes.

```markdown
# Autonomy contract: <task name>

**Goal (observable end state)**
<artifact + the property that will be true of it>

**Success criteria (machine-checked)**
1. <command> exits 0
2. <metric> >= <threshold>, measured by <script> on <dataset>
3. <artifact> conforms to <schema/shape>

**Boundaries**
- May read: <paths / services>
- May write: <paths only>
- May call: <tools/APIs, with read or write noted>
- Must not: touch credentials, publish externally, spend money, delete data

**Budget**
- Max iterations: <N>
- Max wall clock: <duration>
- Max cost: <amount or token count>

**Stop and report if**
- The same error signature repeats <N> times
- A previously passing criterion fails
- The task needs anything outside Boundaries
- Any budget cap is reached

**Gates (human approval required, loop pauses)**
- <irreversible / external / spending actions>

**On completion, report**
- Which criteria passed, with the command output
- What was changed, as a diff summary
- What was attempted and abandoned, and why
```

## Failure modes

- **Vacuously satisfiable criteria.** "All tests pass" when the agent may also write the tests.
  The loop deletes the failing test and reports success — technically honest, entirely useless.
  Fix: criteria must reference artifacts the agent may not modify, or the test suite must be
  inside the boundary as read-only.
- **Rubber-stamp gates.** Approvals arriving faster than a human can evaluate them get approved
  by reflex. Fix: fewer gates, placed on genuinely risky steps, batched with enough context to
  decide; measure how often a gate is rejected — a gate that never rejects is decoration.
- **Unbounded loops wearing a cap.** An iteration cap with no cost cap, or a cost cap reset
  by a retry wrapper. Fix: caps enforced by the harness, not by the agent's own accounting.
- **Boundaries stated as prose.** "Be careful with production" is not a boundary. Enforce in
  the tool layer — read-only credentials, a sandbox, a dry-run flag — because a boundary the
  agent can talk itself past is a suggestion.
- **Contract drift.** The task evolves, the contract does not, and criteria now check something
  nobody wants. Fix: the contract is reviewed when scope changes, and a stale contract is a
  stop factor in itself.
- **Success criteria copied from the goal.** Restating the goal in check form ("the feature
  works") adds ceremony without adding a check. If you cannot name the command that decides it,
  the task is not yet ready for autonomy.

## When a task is not ready for a contract

If you cannot write criterion #1 as a command, the honest recommendation is *not* an autonomous
loop. Options, in order of preference:

1. Make it checkable — build the eval set or the script first, then automate. This is often the
   real work, and it pays off beyond the loop.
2. Run it as a gated workflow with a human checkpoint per step, and use the observed decisions
   to derive criteria for a later contract.
3. Leave it manual. Some judgment-heavy work has no mechanical proxy, and forcing one produces
   a loop that optimizes the proxy instead of the goal.

Recommending option 1 or 2 with reasons is a complete answer; recommending autonomy without a
contract is not.
