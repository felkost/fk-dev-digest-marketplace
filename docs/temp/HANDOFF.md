# Handoff — fk-dev-digest-marketplace build

**Status: build complete and verified live. Nothing committed to git yet.** This doc exists so a
new session can resume without re-deriving anything. Delete it along with the rest of `docs/temp/`
once the marketplace is released (see `docs/temp/README.md`).

## What this is

A Claude Code plugin marketplace repository (`F:\Data\Neoversity_ai\fk-dev-digest-marketplace`,
remote `github.com/felkost/fk-dev-digest-marketplace`), extracted and generalized from the
`.claude/` harness of the DevDigest project (`F:\Data\Neoversity_ai\dev-digest`, branch
`feat/lesson_08` / PR #17). **No changes were made to dev-digest** — this was a hard constraint
throughout.

## Repository state

Working tree is fully built; `git status` shows everything as untracked (no commits exist yet on
`main`). Nothing has been staged, committed, or pushed.

## What was built

Four plugins under `plugins/`, registered in `.claude-plugin/marketplace.json` (name
`fk-dev-digest-marketplace`):

| Plugin | Contents | Depends on |
|---|---|---|
| `engineering-paved-path` | 13 knowledge skills (onion-architecture, frontend-architecture, fastify-best-practices, drizzle-orm-patterns, postgresql-table-design, server-testing, next-best-practices, react-best-practices, react-testing-library, zod, typescript-expert, security, mermaid-diagram) | — |
| `research-tools` | researcher + doc-writer agents, doc-writer + dependency-checker skills | — (soft references to the other two) |
| `architecture-review` | architecture-reviewer + architecture-reviewer-lite agents (doc-discovery based, no hardcoded rules) | `engineering-paved-path@^1.0.0` |
| `sdd-engineering` | spec-creator, implementation-planner, implementer, test-writer, plan-verifier agents; run-plan, implement, plan-verifier, workflow-retro, engineering-insights skills; `/engineering-insights` command; Stop hook | all three above (`^1.0.0`) |

Every plugin has `.claude-plugin/plugin.json` (version `1.0.0`), `README.md`, `CHANGELOG.md`,
`COMPATIBILITY.md` (`Claude Code >= 2.1.196`).

Supporting infrastructure:

- `scripts/validate-marketplace.mjs` — this repo's own linter: ajv schema validation + cross-checks
  (source exists, names unique/immutable, dependencies resolve, acyclic graph, no duplicated
  version) + content checks (no leftover DevDigest markers, no absolute paths, **no Cyrillic
  anywhere under `plugins/`**).
- `scripts/build-index.mjs` — builds `dist/index.json`, the static catalog a *separate* website
  project consumes (see `docs/SITE-SPEC.md`). Never run this repo's own content through the website
  at request time — that's the whole point of the static-index model.
- `scripts/release.mjs <plugin> [--push] [--dry-run]` — pre-release checks + creates tag
  `{plugin}--v{version}`.
- `scripts/rollback.mjs <plugin> <bad-version> [--push]` — deletes a bad tag + prints a manual
  follow-up checklist.
- `evals/` — the vitest + Claude Agent SDK eval framework (copied from dev-digest's `evals/`,
  adapted to resolve `plugins/<plugin>/skills|agents` instead of `.claude/`). Suites grouped by
  plugin: `evals/architecture-review/agents/architecture-reviewer(-lite)/`,
  `evals/sdd-engineering/skills/engineering-insights/` (legacy Python grader, kept as-is).
  `evals/sdd-engineering/workflow/` intentionally has no cases — see its `README.md` for why the
  workflow tier doesn't port to this repo.
- `.github/workflows/validate.yml` and `.github/workflows/build.yml` — **two separate workflows**,
  deliberately not merged, so they show as independent checks in the GitHub UI (harness/content
  gate vs. the catalog-index build the website depends on).
- `docs/PLUGIN-GUIDELINES.md`, `docs/RELEASES.md`, `docs/SECURITY.md`, `docs/SITE-SPEC.md`,
  `CONTRIBUTING.md`, `CODEOWNERS`, root `README.md` (has the Mermaid dependency graph and
  scaffolding-a-new-plugin section).
- `docs/temp/` — **this folder**. Delete before/at release.

## Decisions locked (don't re-litigate without a reason)

- Marketplace name: `fk-dev-digest-marketplace` (matches repo name).
- 4 plugins at launch; knowledge (`engineering-paved-path`) separated from workflow
  (`sdd-engineering`) from review (`architecture-review`) from research (`research-tools`).
- Cross-plugin references are always namespaced (`<plugin>:<skill-or-agent>`) — a bare name only
  resolves within the same plugin.
- A plugin's `name` is permanent; changing it requires the `renames` map, never a silent rename —
  enforced by `validate-marketplace.mjs` and `release.mjs`.
- All materials are English-only, including README/CHANGELOG/COMPATIBILITY — no exception for
  "provenance" text (only the literal string "DevDigest" as a historical-origin mention in
  CHANGELOGs is allowed; Cyrillic has zero exceptions anywhere).
- The website that will browse this catalog is a **separate project**; this repo only publishes a
  static `dist/index.json` via CI. Local dev of that website fetches/builds the index first, never
  reads this repo's raw files. UI translations (if any) live in one file per language in that
  other project — not this repo's concern beyond stating the contract in `docs/SITE-SPEC.md`.
- `validate` and `build` are separate GitHub Actions workflows on purpose.

## Verification already done (live, this session — don't redo blindly, but do re-run before commit if more time has passed)

- `claude plugin validate . --strict` → ✔ passed (marketplace + all 4 plugins individually).
- `node scripts/validate-marketplace.mjs` → PASSED, 0 warnings.
- `node scripts/build-index.mjs` → wrote `dist/index.json` (4 plugins, 20 skills, 9 agents, 1 command).
- Install smoke test: `claude plugin marketplace add "./"` → `claude plugin install
  sdd-engineering@fk-dev-digest-marketplace` → all 3 dependencies auto-installed → `claude plugin
  list` confirmed all 4 enabled → cleaned up with `claude plugin uninstall sdd-engineering --prune`
  and `claude plugin marketplace remove fk-dev-digest-marketplace`.
- `cd evals && npm run eval:quality` (static gate) → 20 skills checked, 0 failures (warnings about
  missing per-skill `.eval.ts` files are expected/pre-existing, not errors).
- `node_modules/.bin/prettier --check .` and `markdownlint-cli2` → both clean.
- Real bugs found and fixed during this verification pass (already resolved, just for context):
  premature `/** */` comment closure from a literal `*/` inside comment text (2 eval `.ts` files),
  a CRLF line-ending bug in `build-index.mjs`'s frontmatter parser, a YAML parse error from an
  unescaped colon-space inside a description field, and a missing copy step for workflow eval files.

**Known non-issue**: `cd evals && tsc --noEmit` fails locally on this Windows machine due to a
broken/incomplete local npm install of the `typescript` package (missing lib `.d.ts` files) —
confirmed unrelated to any code here; not part of the CI gate; GitHub's Linux runners install
cleanly. Don't chase this again unless it also fails in CI.

## Open items (what's actually left)

1. **Nothing has been committed or pushed.** First action for the next session, once the user
   explicitly says to.
2. **No release tags exist yet.** After the first commit, run `node scripts/release.mjs <plugin>
   --push` for each of the 4 plugins to cut `v1.0.0`.
3. **Delete `docs/temp/`** (this file included) once the marketplace is released — not automated,
   track it as a manual to-do.
4. Optional, not blocking: adding same-name-skill-across-plugins detection to
   `validate-marketplace.mjs` (noted as a manual-review gap in `docs/PLUGIN-GUIDELINES.md`).

## Next-session kickoff prompt (ready to paste)

```
Продовжуємо роботу над fk-dev-digest-marketplace (F:\Data\Neoversity_ai\fk-dev-digest-marketplace).
Прочитай docs/temp/HANDOFF.md — там повний стан: що збудовано, які рішення зафіксовані, що вже
перевірено наживо (claude plugin validate, власний лінтер, build-index, install-smoke, eval
static gate — все зелене), і що лишилось: закомітити, запушити, нарізати перші релізні теги
чотирьох плагінів через scripts/release.mjs, і видалити docs/temp/ після релізу. Онови мене,
з чого почати.
```
