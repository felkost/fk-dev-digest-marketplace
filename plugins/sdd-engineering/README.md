# sdd-engineering

The complete **spec-driven development workflow**: from a feature idea to a verified, signed-off
implementation with a retrospective. This is the workflow plugin; the knowledge it relies on lives
in `engineering-paved-path`, and the reviewers/researchers it orchestrates live in
`architecture-review` and `research-tools`.

## Install

```
/plugin install sdd-engineering@fk-dev-digest-marketplace
```

The installer shows the full dependency plan before confirming:

```
sdd-engineering@1.0.0
├── engineering-paved-path@^1.0.0
├── research-tools@^1.0.0
└── architecture-review@^1.0.0
    └── engineering-paved-path@^1.0.0  # one shared installation
```

## Components

| Component | Type | Why other repositories need it | Why it versions with this plugin |
|---|---|---|---|
| `spec-creator` | agent | Turns a request + design sources into a verifiable EARS spec | Owns the spec stage of the pipeline |
| `implementation-planner` | agent | Builds a Development Plan with a dependency DAG and wave map | Owns the plan stage; its plan format is what implementer/verifier parse |
| `implementer` | agent | Executes exactly one plan task to green | Pipeline stage; consumes the plan format |
| `test-writer` | agent | Behavior-focused tests per Testing Plan row | Pipeline stage orchestrated by run-plan/implement |
| `plan-verifier` | agent | ✅/⚠️/❌ completeness audit of a plan against the codebase | Pipeline sign-off gate |
| `run-plan` | skill | 10-stage orchestrator with a human checkpoint after every stage | The pipeline itself |
| `implement` | skill | Plan-execution orchestrator (waves → gates → reviews → sign-off) | Stage 5–8 engine used by run-plan and standalone |
| `plan-verifier` | skill | Verification methodology preloaded by the agent | Agent and methodology change together |
| `workflow-retro` | skill | Real token/cache/parallelism metrics from transcripts + insights | Manual closing stage; no consumer scenario outside the SDD lifecycle |
| `engineering-insights` | skill (generalized) | Preserves verified discoveries between sessions in per-module `insights.md` | Its capture points are the pipeline's checkpoints and hooks |
| `/engineering-insights` | command | One-command session wrap-up | Thin entry to the skill above |
| `stop-insights.sh` | hook (Stop) | Prompts insight capture once per session at stop | Serves the skill above |

## Workflow conventions (documented, not assumed)

The workflow **creates its artifacts at fixed conventional paths** in the host repo:

| Artifact | Path |
|---|---|
| Feature specs | `docs/feature-requirements/YYYY-MM-DD-<slug>.md` |
| Development plans | `docs/plans/YYYY-MM-DD-<slug>.md` |
| Handoff docs | `docs/plans/YYYY-MM-DD-<slug>-<stage>-handoff.md` |
| Retros | `docs/retros/YYYY-MM-DD-<slug>.md` + `docs/retros/ledger.md` |
| Insights | `<module>/insights.md` |

If a package has no typecheck or test command, agents report that explicitly instead of skipping
verification silently.

## Pipeline: how the agents work together

> **Spec and plan are created manually** (invoke `spec-creator`, then `implementation-planner` —
> see the scenario table below). **Everything after the plan is runnable in one shot** via the
> `implement` skill — implementer waves, verifier pass 1, architecture review with fix iterations
> (capped at 2), test coverage, final verification, closeout. `run-plan` wraps the whole thing,
> spec through retrospective, with a mandatory human checkpoint after every stage.

```
spec-creator ──→ implementation-planner ──→ implementer (×N, wave by wave)
  (specify)          (plan)                      (build)
      ·                 ·                           ↓
      └── researcher ───┘              plan-verifier — PASS 1 (Steps + AC only)
   (research-tools, spawned for fact-finding)        ↓
                                       fix loop: ❌/⚠️ → implementer → re-verify
                                                    ↓
                                   ┌────────────────┴───────────────┐
                          architecture-reviewer              test-writer
                       (architecture-review plugin)      (coverage per Testing Plan)
                                   └────────────────┬───────────────┘
                                                    ↓
                                    plan-verifier — FINAL PASS (incl. Testing Plan) = sign-off
                                                    ↓
                                    doc-writer → spec status `implemented` → engineering-insights
                                  (research-tools)
```

1. **spec-creator** — capture the WHAT as an EARS spec before any plan or code exists
2. **implementation-planner** — verify the spec's requirements, design the work, surface all
   constraints, produce an atomic task list (both it and spec-creator delegate fact-finding to
   `research-tools:researcher`)
3. **implementer** — execute one task per instance; spawn waves of parallel instances per the
   plan's parallelization map; after the last wave the orchestrating session runs one full
   typecheck + hermetic suite
4. **plan-verifier, pass 1** — completeness gate right after implementation, BEFORE review and
   tests: no point reviewing or testing incomplete work. Gaps go back to an implementer; re-verify
   after fixes
5. **architecture-reviewer + test-writer** — run in parallel (reviewer is read-only, test-writer
   writes only test files); Critical/High findings go back to an implementer
6. **plan-verifier, final pass** — full verification including the Testing Plan; the ✅ report is
   the completion artifact
7. **doc-writer** (`research-tools`) — permanent documentation; then `spec-creator` flips the spec
   to `implemented`; `engineering-insights` (Mode B) wraps up

Fix loops (steps 4–5) are capped at 2 iterations — after that, escalate to a human instead of
burning tokens on circles.

## Usage scenarios

| # | Scenario | When to use | How to run |
|---|---|---|---|
| **A** | New feature — full pipeline | The idea is not yet written down as requirements; the feature spans modules or introduces a new contract/behavior | `spec-creator` → `implementation-planner` → `implement` skill (→ `doc-writer` in its closeout), or the whole thing via `run-plan` |
| A.1 | …spec step alone | A raw idea / design screenshot needs to become testable ACs | `spec-creator` (delegates `researcher` itself when needed) |
| A.2 | …planning step alone | A spec exists (`draft`/`approved`) and is ready to become a plan | `implementation-planner` (spec mode) |
| A.3 | …one implementation task alone | The plan is ready; execute one specific task | `implementer` (one instance per task; spawn several in parallel for independent tasks) |
| A.4 | …tests alone | Code exists, tests are missing or thin | `test-writer` |
| A.5 | …completeness check alone | All plan tasks are marked done; verify before closing | `plan-verifier` |
| A.6 | …architecture audit alone | After a major feature or before a release | `architecture-review:architecture-reviewer` |
| **B1** | Small fix | One file/layer, behavior obvious from the code, the WHAT does not change | `implementer` directly (no spec, no plan) |
| **B2** | Module-scoped change, clear requirements | Behavior change without a new contract, confined to one module | `implementation-planner` (standalone mode) → `implement` skill |
| **B3** | Change to documented behavior | A spec in `docs/feature-requirements/` exists and the change contradicts or extends it | `spec-creator` (draft revision, or a superseding spec if `approved`) → `implementation-planner` (spec mode) → `implement` skill |

Rules of thumb: **no plan → no `implement`** (it refuses and points you to the planner); **the
WHAT changed → spec first** (B3), never a silent reinterpretation; **B1 is the only route that
skips planning** — if the fix grows beyond one file/layer mid-flight, stop and switch to B2.

## Agents

### spec-creator

The requirements agent — the entry point of the pipeline. Use **before** planning — when a feature
idea needs to become a testable specification. Reads context autonomously, asks structured
questions across 6 categories (Problem & Users · Scope & Boundaries · Behavior & States · Data &
Provenance · Security & Untrusted Inputs · UX & Design Gaps), analyzes design digests for gaps,
and writes the spec only after the user confirms understanding. Write boundary: `docs/feature-requirements/`
only.

### implementation-planner

The HOW to spec-creator's WHAT. Two modes — **spec mode** (a spec is the single source of truth)
and **standalone mode** (captures just enough requirements through targeted questions when no spec
exists). Reviews every requirement for clarity, completeness, consistency, feasibility, and
testability before planning; asks whether execution should be multi-agent or single-agent. Write
boundary: `docs/plans/` only, and only after the user confirms.

### implementer

The code execution agent. Each instance handles **exactly one task** — spawn N instances in
parallel for N independent plan tasks. Loads domain skills from `engineering-paved-path` by scope,
implements, typechecks, self-reviews against the loaded skill rules, and runs hermetic tests before
reporting done.

### test-writer

Writes behavior-focused unit and integration tests. Detects whether the target file is frontend or
backend from its path and applies the matching strategy. Extends existing test files rather than
overwriting them.

### plan-verifier

Read-only completeness auditor. Given a Development Plan, searches the codebase for evidence that
each requirement in Implementation Steps, Acceptance Criteria, and Testing Plan has been
implemented. Reports ✅ Done / ⚠️ Partial / ❌ Missing per requirement. Two-pass usage: pass 1 right
after implementers finish (Steps + AC only), final pass at the end (everything incl. Testing Plan).

## Skills

### run-plan

The full 10-stage orchestrator, spec through retrospective, with a mandatory checkpoint after every
stage — the user decides at each pause whether to continue in the same session or hand off to a
new one via a written handoff doc. Use when you want the entire pipeline driven end-to-end with a
human checkpoint at every stage; do not use for single-stage work.

### implement

Executes a **finished** Development Plan end-to-end: implementer waves → completeness gate →
architecture review with fix iterations → test coverage → final verification → sign-off. Spec and
plan creation are explicitly out of scope — run `spec-creator` and `implementation-planner`
manually first.

### workflow-retro

Manual retrospective of a multi-agent run. Computes real token/cache/tool/parallelism metrics from
session transcripts on disk (including nested subagents — a parent context's own usage undercounts
this), turns them into insights and concrete recommendations, and appends a trend row to
`docs/retros/ledger.md`. Invoked manually after a run worth analyzing — never wired into hooks.

### engineering-insights

Captures non-obvious engineering discoveries (a diagnosed failure, a non-obvious constraint, an
architectural decision, a tool quirk) into the affected module's `insights.md`, so future sessions
inherit institutional knowledge instead of re-discovering it. Three modes: capture-as-you-go
(mid-session), wrap-up (session end), and session-start (read before touching a module). The Stop
hook prompts wrap-up once per session.

## What was deliberately left out

Product specs, the original repository's module names and paths, its `.claude/settings.json`
permissions, personal memory, and caches. Agents were generalized: repository structure is now an
explicit input, not an assumption.
