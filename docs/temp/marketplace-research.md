# Marketplace research (temporary — see docs/temp/README.md)

Working notes from researching Claude Code plugin marketplaces before and during this repository's
build. Kept temporarily in case a structural decision needs to be traced back to its source;
delete along with `docs/temp/` once the marketplace is released.

## Official docs consulted

- `code.claude.com/docs/en/plugin-marketplaces` — marketplace.json schema, plugin sources, hosting,
  version resolution, `renames` map, validation commands.
- `code.claude.com/docs/en/plugins-reference` — plugin.json schema, component locations (skills,
  agents, commands, hooks, MCP/LSP servers), `${CLAUDE_PLUGIN_ROOT}` / `${CLAUDE_SKILL_DIR}`,
  strict mode, installation scopes.
- `code.claude.com/docs/en/plugin-dependencies` — dependency declaration syntax, version
  constraints, git-tag resolution convention (`{plugin-name}--v{version}`), cross-marketplace
  dependencies, enable/disable cascade, `claude plugin prune`.

## Key facts that shaped this repo's structure

- `.claude-plugin/` holds **only** `plugin.json` — `skills/`, `agents/`, `commands/`, `hooks/` live
  at the plugin root as siblings, not nested inside `.claude-plugin/`. A common mistake source.
- A plugin's `name` is its permanent identifier (keys `enabledPlugins`, cache paths, dependency
  constraints). Renaming requires the `renames` map in `marketplace.json`, never a silent rename —
  this directly drove the "name immutability" enforcement in `scripts/validate-marketplace.mjs`
  and `scripts/release.mjs`.
- Version resolution order: `plugin.json` version → marketplace-entry version → git commit SHA.
  Setting version in both places and letting them drift is a documented footgun (plugin.json
  always wins silently) — this is why the marketplace entries here never set `version`.
- Dependency version constraints resolve against git tags matching `{plugin-name}--v{version}` on
  this repository. This is the exact mechanism `scripts/release.mjs` automates.
- `claude plugin validate .` / `claude plugin validate <plugin-dir>` are the official schema +
  frontmatter validators; `--strict` promotes unrecognized-field warnings to errors. This repo's
  own `scripts/validate-marketplace.mjs` covers what the official validator doesn't (forbidden
  markers, Cyrillic, cross-plugin dependency-graph acyclicity).
- Namespaced references (`<plugin>:<skill>`, `<plugin>:<agent>`) are required across plugin
  boundaries — a bare name only resolves within the same plugin. This is the single most
  load-bearing fact behind the whole `engineering-paved-path` knowledge-sharing design.

## External best-practice sources (web search, not official)

- dev.to — "Build Your Own Claude Code Marketplace" (Nagell) — starter-template conventions,
  conventional-commit versioning, CI auto-sync of marketplace.json.
- ice-ice-bear.github.io — "Claude Code Plugin Marketplace: A Deep Dive" — SHA-pinning for
  reproducibility, release-channel pattern (stable/beta marketplaces), permission-rule precedence.

## Where this research ended up

- Dependency model, naming rules, `.claude-plugin/` structure → `docs/PLUGIN-GUIDELINES.md`
- Versioning, tagging, release/rollback mechanics → `docs/RELEASES.md`
- Marketplace composition and dependency graph → root `README.md`
- Secrets/permissions posture → `docs/SECURITY.md`
