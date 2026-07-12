# research-tools

Generic read-only research and documentation agents. Released as a separate plugin because these
agents serve any workflow, not only SDD — they have their own consumer scenarios and release cadence.

## Install

```
/plugin install research-tools@fk-dev-digest-marketplace
```

No dependencies. Installed automatically when you install `sdd-engineering`.

## Components

| Component | Type | Why other repositories need it | Why it versions with this plugin |
|---|---|---|---|
| `researcher` | agent | Read-only scout for codebase patterns and web facts, returns a cited report — useful before any planning or debugging | The report contract is what downstream consumers (spec-creator, planners) rely on |
| `doc-writer` | agent | Generates module READMEs, design docs, API references with verified symbols | Pairs with the doc-writer skill below |
| `doc-writer` | skill | Doc type → location mapping, per-symbol structure, quality checks | The agent preloads it; they change together |
| `dependency-checker` | skill | Dependency audit with graph, sizes, and severity-tiered findings for any JS/TS repo | Standalone analysis capability |

## Soft references

`doc-writer` uses `engineering-paved-path:mermaid-diagram` for diagrams and
`sdd-engineering:engineering-insights` when documenting discoveries — **only if those plugins are
installed**. This plugin declares no dependencies so it can be used entirely on its own; when
installed via `sdd-engineering`, both soft references always resolve.

## researcher

The primary information-gathering agent. Use **before** planning or implementing — when you need
to understand what already exists or gather external context. It will:

- Ask clarifying questions if the request is vague (interview mode)
- Search the codebase with `Glob`, `Grep`, `Read`, `Bash`
- Search the web with `WebSearch` + `WebFetch`
- Return a structured report (Format A for codebase findings, Format B for web findings)
- Explicitly flag what was searched but not found

No domain-specific skills — it reads raw code and web pages directly. Read-only by design:
omitting `Edit`/`Write` from its tool list prevents it from acting on what it finds.

**Use when:**
- You need to understand how a module is implemented before touching it
- You want to find all usages of a symbol, pattern, or convention
- You need external documentation (library version, API shape, best practice)
- Another agent (e.g. `sdd-engineering:spec-creator` or `sdd-engineering:implementation-planner`)
  needs a codebase snapshot or fact-check during its own run — spawn `research-tools:researcher`
  via the Agent tool instead of pulling raw files into that agent's own context

**Example:**
```
Use research-tools:researcher: find every place this repo renders a severity badge, and how the
severity levels are named.
```

**Based on:**
- [Claude Code sub-agents documentation](https://code.claude.com/docs/en/sub-agents)
- [PubNub — Best practices for Claude Code sub-agents](https://www.pubnub.com/blog/best-practices-for-claude-code-sub-agents/)
- Structured reporting pattern: citation-first output ("a finding without a citation is an
  opinion") borrowed from scientific peer-review norms and adapted for codebase analysis

## doc-writer (agent + skill)

Generates and maintains technical documentation. Detects the input type (implementation plan,
source code, route definitions, conversation) and writes to the correct location per the host
repository's doc conventions. Includes Mermaid diagrams for architecture and API flows. Verifies
all referenced code entities exist before writing — never documents hypothetical code.

**Doc types produced:**
- `docs/design/` — architecture and design docs (from implementation plans or code)
- `<package>/README.md` — module overviews (from source code)
- `docs/design/api-<module>.md` — API references (from route definitions)

Feature specs (`docs/feature-requirements/`) are **not** produced here — if `sdd-engineering` is
installed, that folder is `spec-creator`'s exclusive write surface; `doc-writer` hands off to it.

**Use when:**
- A feature is complete and needs permanent documentation
- You want to convert an implementation plan into a design doc for future reference
- A module's README is missing or stale

**Example:**
```
Use research-tools:doc-writer: the CSV-export feature is merged — generate the API reference and
update server/README.md.
```

## dependency-checker (skill)

Audits a repository's dependencies and emits one structured five-section report: Scope →
Dependency Graph (Mermaid) → Size Breakdown → Findings & Priorities (P0/P1/P2/Info) → Summary.
Detects the repository's own linkage model (npm/pnpm workspaces vs. path-alias + relative-import
sharing) rather than assuming one — this generalization is what let it leave DevDigest without
carrying that repo's specific package layout.

**Use when:**
- Auditing what each package weighs, or finding unused/duplicated/version-drifted dependencies
- Mapping cross-package imports to catch boundary violations (deep imports into another package's
  internals instead of its public entry point)
- Deciding which dependencies to remove or upgrade first

**Example:**
```
Use the dependency-checker skill to audit this repo's dependencies and flag anything worth
removing before the next release.
```

## What was deliberately left out

The dependency-checker's hardcoded package inventory (a fixed list of package names) was removed;
it now detects the host repo's packages and linkage model itself, generically.
