# Releases

## Versioning

Each plugin has its own SemVer line, independent of the others: `MAJOR.MINOR.PATCH` in
`plugins/<name>/.claude-plugin/plugin.json`. Bump:

- **MAJOR** — a breaking change: a skill's guidance flips a prior rule, an agent's write boundary
  narrows or widens in a way that changes behavior, a dependency's version constraint tightens
  incompatibly.
- **MINOR** — a new skill/agent/command, a new (backward-compatible) capability.
- **PATCH** — a bug fix, a clarity edit, a generalization that doesn't change documented behavior.

**Bump `version` on every release.** If you push new commits to `plugins/<name>/` without changing
`version`, Claude Code treats the plugin as unchanged and existing installs never see the update —
this is the single most common release mistake.

## Boundary of responsibility

- **A plugin's `version`** describes the behavior of that plugin alone.
- **A commit or tag on this marketplace repository** fixes the state of the whole catalog at that
  point — it is not itself a version any plugin resolves against.
- **Changing `engineering-paved-path` does not change `sdd-engineering`'s version.** A dependent
  plugin only needs its own version bumped if the change in its dependency requires the dependent
  to widen its `dependencies` version constraint (e.g. the dependency made a breaking change and
  the dependent needs `^2.0.0` instead of `^1.0.0`).
- **`claude plugin marketplace update`** (refreshing the catalog) never by itself updates an
  already-installed plugin to a newer version — that's a separate `claude plugin update` step, and
  it only moves a version-constrained dependency within its declared range.

## Tags

Claude Code resolves a dependency's semver range (`^1.0.0`) against git tags on this repository,
using the convention `{plugin-name}--v{version}` — e.g. `sdd-engineering--v1.0.0`,
`engineering-paved-path--v1.2.0`. The `{version}` in the tag must match the `version` field in
that plugin's `plugin.json` at the tagged commit.

## Releasing

Use the release script — it runs the pre-release checks and creates the tag in one step:

```
node scripts/release.mjs <plugin>            # checks + creates the tag locally
node scripts/release.mjs <plugin> --push      # also pushes the tag to origin
node scripts/release.mjs <plugin> --dry-run   # checks only, prints what it would do
```

It verifies, in order: the plugin's directory has no uncommitted changes; `plugin.json`'s `name`
matches the directory and the marketplace entry (name immutability — see below); `version` is
valid SemVer and not duplicated/conflicting in the marketplace entry;
`scripts/validate-marketplace.mjs` passes; the tag doesn't already exist locally or on origin.
Only after all of that does it create `{plugin}--v{version}`.

Before running it, make sure `plugins/<name>/CHANGELOG.md` has a dated entry for the version
you're releasing — the tag should point at a commit whose CHANGELOG already documents the release,
not one that documents it in a follow-up commit.

## Eval gate before a release

`cd evals && pnpm eval:quality` (the static, no-model gate) is mandatory before every release.
LLM-judged suites (`pnpm eval:agents`, `pnpm eval:skills`) run on your Claude Code subscription —
not part of this repo's CI, but a strong recommendation before releasing a change to an agent's or
skill's actual *behavior* (as opposed to a docs-only edit). See `evals/` for the full methodology
and `evals/sdd-engineering/workflow/README.md` for why the workflow tier isn't run from this
repository.

## Rollback

If a released version turns out to be broken or dangerous:

```
node scripts/rollback.mjs <plugin> <bad-version>            # deletes the tag locally
node scripts/rollback.mjs <plugin> <bad-version> --push      # also deletes it on origin
```

Deleting the tag makes semver-constrained dependency resolution (`^1.0.0`, etc.) fall back to the
highest remaining good tag for that plugin — existing installs pinned to an exact version are
unaffected until they next update. The script prints the fallback version and a manual follow-up
checklist (revert or fix-forward the content, update the CHANGELOG, consider a `renames` entry if
the plugin is being withdrawn entirely). See `docs/SECURITY.md` for the fuller incident-response
sequence when the bad release is a security concern.

## Renaming or removing a plugin

A plugin's `name` is permanent once released — it's the key every install, every dependency
constraint, and every cache path is built from. To change it anyway, add an entry to the
`renames` map in `.claude-plugin/marketplace.json`:

```json
{
  "renames": {
    "old-plugin-name": "new-plugin-name",
    "removed-plugin-name": null
  }
}
```

Treat `renames` as append-only history — never edit or remove an existing entry, even after every
user has plausibly migrated; a later rename chains through it. Run `claude plugin validate .`
after editing the map — it rejects a chain that cycles or doesn't terminate at `null` or a real
plugin name.

## Release channels

Not set up in this marketplace yet. If needed later: two marketplace entries pointing at different
refs of the same plugin source (`stable` vs `latest`), assigned to different user groups via
managed settings — see the Claude Code plugin-marketplaces documentation for the pattern.
