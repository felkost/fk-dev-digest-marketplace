# architecture-review

Read-only architecture reviewers. Released as a separate plugin because architecture review serves
any workflow — CI gates, ad-hoc audits — not only the SDD pipeline that also consumes it.

## Install

```
/plugin install architecture-review@fk-dev-digest-marketplace
```

Depends on `engineering-paved-path@^1.0.0` (installed automatically) — both reviewers preload its
eight knowledge skills.

## Components

| Component | Type | Why other repositories need it | Why it versions with this plugin |
|---|---|---|---|
| `architecture-reviewer` | agent | Audits a diff against the **host repo's own documented rules** — layering, DI, module isolation, shared contracts. Strict: every finding cites a documented rule | The rule-discovery method and report contract are the plugin's core |
| `architecture-reviewer-lite` | agent | Relaxed variant: judgment findings allowed without exact citations | Shares method and output format with the strict variant; they change together |

## How generalization works

Instead of hardcoded checks for specific packages, the reviewers **discover repository-local
architecture docs** (root instruction file, `<module>/CLAUDE.md`, `docs/architecture*.md`) and
derive the checklist from what those docs actually state. A repo with no architecture docs gets a
`missing-reference-doc` finding, not rules invented from memory. Rule families the reviewers know
how to look for — applied only when the discovered docs actually state the rule — are:
inward-only-dependencies (layering), thin-boundaries (business logic kept out of entry points),
di-discipline (construction confined to the composition root), restricted-globals (env/secrets
access), module-isolation (I/O restrictions on a declared-pure module), mandatory-gates (a
required call that must never be bypassed), shared-contract-not-duplicated.

## architecture-reviewer

Read-only architectural auditor. Checks import direction, layer-boundary violations, side-effect
contamination in pure modules, and any project-wide invariant the host repo's own docs declare.
Never edits files. **It does not hunt bugs** — correctness review belongs to a separate code-review
process; this agent stays scoped to structural/layering/DI findings.

**What it reports:** Critical / High / Medium / Low findings, each with a file:line citation, the
exact rule family violated, the source doc the rule came from, and a remediation hint.

**Use when:**
- After a major feature is merged and you want an architectural health check
- Before a release to catch any layer violations introduced during fast iteration
- Onboarding new contributors — run it against a new module to verify it follows the repo's own
  documented conventions

**Example:**
```
Use architecture-review:architecture-reviewer to audit this diff against this repo's documented
layering rules — the diff is <path or pasted diff>.
```

## architecture-reviewer-lite

The same auditor with one hard rule relaxed: it does not have to cite an exact documented rule for
every finding — a well-reasoned judgment finding is allowed even without a traceable citation.
Same output format, same severity scale, same read-only guarantee. Use it where you want broader
coverage than "only what's explicitly documented" and are comfortable with a small increase in
false positives in exchange.

## What was deliberately left out

The prior hardcoded rule set (fixed identifiers, fixed doc paths tied to one repository's package
layout) was replaced by the doc-discovery method above — the reviewers now work against any
repository that documents its own architecture, not just the one they were extracted from.
