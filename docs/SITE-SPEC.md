# Site spec — contract for the marketplace website

The website that lets people browse and install plugins from this marketplace is a **separate
project** — it is not built in this repository. This document is the contract: what this
repository publishes, and what the website may assume about it. Nothing here describes the
website's own implementation, framework, or hosting.

## Indexing model (confirmed)

**Static index, built by this repository's CI.**

- `scripts/build-index.mjs` reads `.claude-plugin/marketplace.json` and every
  `plugins/<name>/.claude-plugin/plugin.json`, scans each plugin's `skills/`, `agents/`,
  `commands/` for their frontmatter descriptions, and writes one self-contained file:
  `dist/index.json`.
- The **build** GitHub Actions workflow (`.github/workflows/build.yml`) runs this script on a
  runner and publishes the result as a build artifact (every push/PR) and to GitHub Pages (on
  `main`). This is a workflow **separate from and not blocking on** the `validate` workflow
  that gates PRs — see the note on CI separation below.
- The website fetches the published `index.json` (a stable URL). It never clones this repository,
  parses raw markdown/frontmatter itself, or calls the GitHub API to list files at request time.

**Why not read the repository directly:**

- **Stability and speed.** A generated, schema-shaped JSON file is a contract the website can
  parse once and cache; raw repo access means re-parsing markdown frontmatter and re-deriving the
  same structure on every request.
- **No rate limits or auth.** Reading files from GitHub's API or raw content endpoints at request
  time is subject to GitHub's own rate limits; a static artifact has none.
- **Validation happens once, at build time**, not on every page load — `build-index.mjs` runs
  after `validate-marketplace.mjs` has already confirmed the catalog is well-formed, so the
  website can trust the shape of what it receives without its own defensive parsing.

## `dist/index.json` shape

```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-07-12T18:14:02.556Z",
  "marketplace": { "name": "...", "description": "...", "owner": { "name": "...", "email": "..." } },
  "plugins": [
    {
      "name": "...", "displayName": "...", "version": "...", "description": "...",
      "category": "...", "keywords": ["..."],
      "author": { "name": "...", "email": "..." }, "license": "...", "repository": "...",
      "dependencies": [{ "name": "...", "version": "..." }],
      "skills": [{ "name": "...", "description": "..." }],
      "agents": [{ "name": "...", "description": "...", "model": "..." }],
      "commands": [{ "name": "...", "description": "..." }],
      "hookEvents": ["Stop"]
    }
  ]
}
```

`schemaVersion` increments on any breaking change to this shape — the website should check it and
fail loudly rather than silently misrender on a future incompatible version.

## Local development

The website's local dev server fetches or generates the index **before** starting, not on demand
per request:

1. Either fetch the currently-published `index.json` from the deployed artifact/Pages URL, or run
   `node scripts/build-index.mjs` against a local checkout of this repository to produce a fresh
   one.
2. Then run the website's own dev server (`npm run dev`) against that file.

The website must never attempt to read this repository's raw files directly, in dev or in
production — the same static-index contract applies in both.

## Internationalization

If the website supports more than one display language, all UI strings live in **one dedicated
translations file per language** (e.g. `locales/en.json`, `locales/uk.json`) — never hardcoded
inside components. `index.json` itself is language-neutral: plugin/skill/agent descriptions come
from this repository's English-only source content (see `CONTRIBUTING.md`) and are not translated
by this repository; if the website wants localized copy, it maintains its own translation of the
descriptive strings independently, keyed by plugin/skill/agent name.

## CI separation

This repository runs two independent GitHub Actions workflows, deliberately not merged into one:

- **`validate`** — gates every PR and push: schema validation, the custom linter, `claude plugin
  validate --strict`, the eval static gate. This is the harness/content-quality check.
- **`build`** — builds `dist/index.json` and publishes it. This is the artifact the website
  depends on.

They show as two separate checks in the GitHub UI so a build failure (e.g. a transient Pages
deploy issue) is never confused with a content-validation failure, and vice versa.

## Screens (for the website to implement — informational, not a requirement of this repo)

- **Catalog** — list of plugins from `index.json`, filterable by `category`/`keywords`.
- **Plugin detail** — one plugin's full metadata, its skills/agents/commands tables, its
  dependency list (rendered as links to the depended-on plugin's own detail page), install
  command.
- **Search** — client-side, over the already-fetched `index.json` (name, description, keywords) —
  no server-side search index needed for a catalog this size.
