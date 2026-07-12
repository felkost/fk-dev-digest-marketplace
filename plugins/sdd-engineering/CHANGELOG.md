# Changelog — sdd-engineering

All notable changes to this plugin are documented here. Follows SemVer; releases are tagged
`sdd-engineering--v<version>`.

## 1.0.0 — 2026-07-12

Initial extraction from the DevDigest harness (branch `feat/lesson_08`).

- Agents: spec-creator, implementation-planner, implementer, test-writer, plan-verifier.
- Skills: run-plan (10-stage checkpointed pipeline), implement (plan-execution orchestrator),
  plan-verifier (methodology), workflow-retro, engineering-insights (generalized).
- Command: `/engineering-insights`; hook: Stop → `stop-insights.sh` via `hooks/hooks.json`.
- Editorial pass: DevDigest paths and module names removed; skill references rewritten to
  namespaced `engineering-paved-path:*`; agent references rewritten to plugin-scoped names
  (`research-tools:researcher`, `architecture-review:architecture-reviewer`,
  `sdd-engineering:*`); supporting-script paths use `${CLAUDE_SKILL_DIR}`; typecheck/test
  commands are discovered from `package.json` with an explicit no-command fallback.
- Declares version-constrained dependencies on engineering-paved-path, research-tools, and
  architecture-review (`^1.0.0`).
