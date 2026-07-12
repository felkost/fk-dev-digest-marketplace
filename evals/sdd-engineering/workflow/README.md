# Workflow-tier evals — out of scope for this repository

The `workflow` tier (`describeWorkflow` / `runWorkflowCases` / `workflowTask` in `evals/src/`)
loads a **real on-disk harness** (`settingSources: ["project"]` — the host repository's own
`CLAUDE.md` plus its skills and agents) and asserts systemic behavior: does a documented "read
this doc" rule actually make the model read it, does a subagent actually get dispatched.

That tier needs a host repository with real product code and real documentation to route to —
this marketplace repository has neither. It defines plugins; it is not itself a product that gets
reviewed. The dev-digest-specific cases that originally lived here asserted routing into
`server/docs/api-contracts.md` and `reviewer-core/insights.md`, paths that only exist in the
product repository this marketplace was extracted from — they do not port here and were removed
rather than faked.

## What this means for plugin authors

The framework capability is preserved in `evals/src/` for anyone who wants to verify that,
**once these plugins are installed in a real project**, the documented routing and dispatch rules
still fire correctly for that project's own `CLAUDE.md`. To write such a suite:

1. Stand up a small fixture project with a `CLAUDE.md`, install this marketplace's plugins into it
   (`claude plugin marketplace add <path-to-this-repo>`, `claude plugin install sdd-engineering@...`).
2. Write `WorkflowCase` entries against that fixture project, following the DSL in
   `evals/src/dsl/case.ts`.
3. Point `expectSubagents` at the **plugin-scoped** agent name (e.g. `architecture-review:architecture-reviewer`),
   not the bare name — that is what a plugin install dispatches.

This is intentionally not automated in this repository's CI. The manual smoke test in
`CONTRIBUTING.md` / `docs/RELEASES.md` (install the marketplace locally, invoke a skill and an
agent, confirm namespaced preload works) covers the same risk at release time without requiring a
maintained fixture project in CI.
