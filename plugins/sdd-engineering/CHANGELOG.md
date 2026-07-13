# Changelog — sdd-engineering

All notable changes to this plugin are documented here. Follows SemVer; releases are tagged
`sdd-engineering--v<version>`.

## 1.1.0 — 2026-07-13

Defines supersession as a first-class `engineering-insights` behavior and resolves a contradiction
between the skill's two format sources.

- **New behavior:** when a session proves an existing insight wrong, the skill now supersedes it
  with a defined **two-bullet** shape — the original struck in place as
  `- ~~**…**~~ (superseded YYYY-MM-DD)`, the correction appended as a new bullet directly below —
  and an explicit footer rule: the `Entries:` count does **not** change on supersession (the struck
  entry leaves the count as its correction joins it).
- **Bug fix:** `format.md` § Stale Entry previously documented a single-bullet inline-correction
  form that contradicted `SKILL.md` Step 3's two-bullet instruction. Both now agree on the
  two-bullet form.
- **Eval:** adds `supersede-stale-entry` (eval-4) to the `engineering-insights` suite — a fixture
  seeding a now-wrong `fastify-type-provider-zod` Quirk, graded on strikethrough presence, the
  `(superseded …)` marker, a two-bullet entry count, and a flat footer.

## 1.0.1 — 2026-07-13

Docs-only patch: the install example's version number had drifted from `plugin.json`.

- README install example bumped from `sdd-engineering@1.0.0` to `sdd-engineering@1.0.1`.

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
