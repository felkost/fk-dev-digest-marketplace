# engineering-paved-path

Canonical **knowledge** skills for the TypeScript stack. This plugin is the single source of truth
for technical best-practice skills — the `sdd-engineering` and `architecture-review` plugins load
them by namespaced reference (`engineering-paved-path:<skill>`) instead of carrying copies.

## Install

```
/plugin install engineering-paved-path@fk-dev-digest-marketplace
```

No dependencies. Installed automatically when you install `sdd-engineering` or `architecture-review`.

## Skills (13)

| Skill | Scope | Why other repositories need it | Why it versions with this plugin |
|---|---|---|---|
| `onion-architecture` | Backend | Layer definitions and dependency rules for any Fastify/Node service | Referenced by reviewers and planners as one shared rulebook |
| `frontend-architecture` | Frontend | WHERE React/Next.js code belongs, feature organization | Same rulebook role for the frontend |
| `fastify-best-practices` | Backend | Routes, plugins, validation, error handling for any Fastify app | Loaded by implementer/planner/test-writer stages |
| `drizzle-orm-patterns` | Backend | Schema, queries, relations, transactions, migrations | Loaded on DB-change scope |
| `postgresql-table-design` | Backend | Types, indexing, constraints for any Postgres schema | Loaded on DB-change scope |
| `server-testing` | Backend | Fastify/Drizzle/Vitest test split, inject(), mocks | Read by test-writer's backend branch |
| `next-best-practices` | Frontend | App Router, RSC boundaries, data patterns | Loaded on frontend scope |
| `react-best-practices` | Frontend | Anti-pattern catalog, state, hooks discipline | Loaded on frontend scope |
| `react-testing-library` | Frontend | RTL + Vitest component/hook testing | Read by test-writer's frontend branch |
| `zod` | Full-stack | Schema validation, parsing, type inference | Loaded on backend scope |
| `typescript-expert` | Full-stack | Type-level programming, strict mode, tooling | Preloaded by implementer and planner |
| `security` | Full-stack | OWASP Top 10, auth, injection, secrets handling | Preloaded by implementer, planner, spec-creator |
| `mermaid-diagram` | Shared | Diagram syntax for docs, specs, and reports | Soft-referenced by doc-writer and dependency-checker |

## What is a skill, and how does it differ from an agent?

| Type | Loaded | Purpose |
|---|---|---|
| **Skill** (this plugin) | On-demand by an agent, or via `Skill(<plugin>:<name>)` | Domain knowledge — rules, patterns, anti-patterns for a specific technology |
| **Agent** (`sdd-engineering`, `architecture-review`, `research-tools`) | Via the `Agent`/`Task` tool | A workflow that *uses* skills to do a bounded job (plan, implement, review) |

Skills never act on their own — an agent (or the main session) loads a skill's content and applies
it while doing something else. That is why this plugin ships no agents of its own: it is a pure
knowledge library other plugins depend on.

## Using a skill directly

Outside any agent, invoke a skill by its namespaced name — for example, in a session with this
plugin installed:

```
Use the engineering-paved-path:zod skill to design the request-body schema for this endpoint.
```

Or let an agent from `sdd-engineering` / `architecture-review` load it automatically as part of
its own workflow — that is the common case; the skills here are written to be consumed by those
agents' `skills:` frontmatter (preloaded) or an explicit `Skill(engineering-paved-path:<name>)`
call (loaded on demand once scope is known).

## Conventions carried by these skills

Skills state **default conventions** from the reference implementation (composition root,
`AppError` taxonomy, workspace scoping, shared-contracts package). The host repository's own
architecture docs always win — skills say so explicitly where it matters. Treat every concrete
file path, class name, or error type in a skill as an illustrative example of the pattern, not a
requirement to match verbatim.

## Anatomy of a skill in this plugin

Each skill directory follows the same shape:

- `SKILL.md` — the skill itself: trigger conditions, rules, and conventions (required)
- `references/*.md` or `examples.md` — deeper examples, anti-patterns, worked cases (most skills)
- `README.md` — human-facing overview for skills complex enough to need one (some skills)

## What was deliberately left out

Product specs, module names, and rules that only apply to the repository these skills were
extracted from were removed during extraction. See the marketplace root `CONTRIBUTING.md` for the
extraction criteria and `docs/PLUGIN-GUIDELINES.md` for the naming and structure rules every skill
here follows.
