# Site spec — the in-repo catalog website

The catalog website is built and hosted **from this repository**, under [`site/`](../site/). This
document is its contract: how the data is generated, what the site renders, and how it deploys.

> **History.** An earlier version of this spec described the website as a *separate project* that
> only consumed a published `dist/index.json`. That decision was reversed — the site now lives here.
> This document supersedes it.

## Status (what is actually built)

- A **React + TypeScript + Vite** single-page app (see [`site/README.md`](../site/README.md) for
  the file-by-file map) with a generated `site/public/catalog.json` data file fetched at load. No
  backend; the only runtime dependencies are React, `react-router-dom`, and `minisearch`.
- **Hash routing** (`HashRouter`): `#/` (catalog) and `#/plugin/:name` (plugin detail — a stable
  deep link); unknown routes redirect to `#/`.
- Client-side **fuzzy search** (MiniSearch — prefix + fuzzy, AND-combined terms) over every
  plugin, skill, agent, and command; a **⌘/Ctrl-K command palette** over the same index;
  **light/dark** theming; and a **copy-install** action.
- All UI strings live in one i18n module (`site/src/i18n/strings.ts`) — components never hardcode
  display text.

## Data flow

```
plugins/** + .claude-plugin/marketplace.json
        │  node scripts/build-index.mjs
        ▼
dist/index.json
        │  node scripts/build-catalog.mjs   (npm run build:catalog runs both)
        ▼
site/public/catalog.json
        │  vite build (site/) — copies public/ into the bundle
        ▼
site/dist/ ──► GitHub Pages | Render static
```

No backend and no runtime GitHub API calls: the app only fetches its own static `catalog.json`
(bundled next to it in `site/dist`). `site/public/catalog.json` is committed so a fresh clone can
run the site without regenerating; CI and Render regenerate it on every deploy so a published site
always reflects the current plugins.

## `site/public/catalog.json` shape

```jsonc
{
  "schemaVersion": 1,
  "generatedAt": "<ISO-8601>",
  "marketplace": {
    "name": "fk-dev-digest-marketplace",
    "displayName": "Dev Digest",
    "description": "...",
    "owner": { "name": "Fel Kost", "email": "teacherfkv@gmail.com" },
    "repository": "https://github.com/felkost/fk-dev-digest-marketplace",
    "repoShort": "felkost/fk-dev-digest-marketplace",
    "addCommand": "/plugin marketplace add felkost/fk-dev-digest-marketplace",
    "installTemplate": "/plugin install {plugin}@fk-dev-digest-marketplace"
  },
  "plugins": [
    {
      "name": "sdd-engineering",
      "displayName": "SDD Engineering",
      "version": "1.0.0",
      "description": "...",
      "category": "workflow",
      "keywords": ["sdd", "plan", "..."],
      "author": { "name": "...", "email": "..." },
      "license": "MIT",
      "repository": "https://github.com/felkost/fk-dev-digest-marketplace",
      "dependencies": [{ "name": "engineering-paved-path", "version": "^1.0.0" }],
      "skills":   [{ "name": "run-plan", "description": "..." }],
      "agents":   [{ "name": "implementer", "description": "...", "model": "sonnet" }],
      "commands": [{ "name": "engineering-insights", "description": "..." }],
      "hookEvents": ["Stop"]
    }
  ]
}
```

The `plugins` array is exactly `dist/index.json`'s `plugins` (see `scripts/build-index.mjs`); the
`marketplace` block adds the two install commands the detail page renders (`{plugin}` is substituted
per plugin in the UI). `schemaVersion` increments on any breaking change to this shape.

## The app (`site/src/`)

- **Routes** (`HashRouter`): `#/` — catalog; `#/plugin/:name` — plugin detail (stable deep link,
  works on a fresh page load); anything else redirects to `#/`.
- **Catalog page** — a centered hero (two-line headline), a category filter and keyword chips (both
  derived from the data), and a uniform tile grid of plugin cards. Each card shows the plugin's
  initials, name, version, category, description, and skill/agent/command counts.
- **Plugin detail page** — metadata header (version, category, package name, license), a
  terminal-styled **install** block with a **copy** button, tables for the plugin's skills, agents,
  commands, and hooks, its dependencies (each a link to the depended-on plugin's own detail route),
  and author / repository / keyword metadata.
- **Search** — MiniSearch over one index of every plugin, skill, agent, and command (fields: label,
  description, keywords, owning plugin). Prefix matching + fuzzy (0.2) with AND-combined terms, so
  typos still hit. The header search filters the catalog grid by mapping component hits back to
  their owning plugins. Pressing `/` focuses the search box.
- **Command palette** — `⌘/Ctrl + K` opens a palette over the same MiniSearch index; type to
  filter, arrow keys / Enter (or click) to jump — every hit opens its owning plugin's detail route.
- **Theming** — light and dark via CSS custom properties. Default follows `prefers-color-scheme`;
  the user's choice is stored in `localStorage` (`fkm-theme`) and applied as `data-theme` on the
  app root element, which also carries `color` so all inherited text follows the active theme.
  Palette is cool-neutral with a purple accent and a purple→teal gradient rule.
- **Install commands** — built from `marketplace.addCommand` and `marketplace.installTemplate`; the
  detail page shows both `/plugin marketplace add …` and `/plugin install <name>@…` and copies them
  together.

All displayed numbers and text come from `catalog.json` or `src/i18n/strings.ts` — nothing about
the catalog is hardcoded in components.

## Usage stats (`server/`)

An optional companion backend counts how the catalog is used. Full details in
[`server/README.md`](../server/README.md); the contract in short:

- **Stack** — Fastify + Drizzle + Zod + PostgreSQL (Neon), deployed as the `fk-dev-digest-stats`
  web service in [`render.yaml`](../render.yaml). The marketplace dogfoods its own
  `engineering-paved-path` stack.
- **Events** — the site fire-and-forgets `POST /api/events` with `{ type, plugin }` on
  copy-install clicks (`copy_install`) and plugin-page opens (`plugin_view`). No PII: no IP, UA,
  cookies, or session ids are stored. `GET /api/stats` returns per-plugin aggregates, plus
  `totals` and the `clones` summary.
- **Display** — the detail page shows this plugin's numbers as a "Usage" metadata cell; the
  homepage hero shows a `StatsTiles` row (external clones, external clones · last 14 days, install
  copies, plugin views) from `totals` + `clones`. Both fetch `/api/stats` once (shared cached
  promise in `statsApi.ts`). All of it renders nothing when `VITE_STATS_API` is unset or a value is
  still 0, so the UI is unchanged until real numbers exist. The 14-day tile also hides itself while
  it still equals the total, which it does until tracking outlives the 14-day window.
- **Wiring** — the site reads the backend base URL from `VITE_STATS_API` at build time (set in
  `pages.yml` and `render.yaml`). Unset it and the site builds with stats fully disabled — every
  stats call is a graceful no-op.
- **Honest limitation** — real installs happen via `git clone` of this repo by Claude Code and
  never touch the website, so `copy_install`/`plugin_view` measure catalog engagement, not
  installs. Nothing published here is an install count; `copy_install` is the only counter that
  records a deliberate human action aimed at installing.
- **Clone harvesting** — `.github/workflows/harvest-clones.yml` runs daily, pulling GitHub's
  Traffic API (`/traffic/clones`, a 14-day rolling window) and upserting each day into
  `clone_stats` (`server/src/harvestClones.ts`), so history survives past that window.
- **CI correction** — GitHub counts every `actions/checkout` as a clone, so raw clone traffic
  counts this repo's own CI as if it were interest from outside. The Traffic API carries no
  attribution, so the harvester also counts our own workflow runs over the same days
  (`/actions/runs`) into `ci_count`, and `GET /api/stats` publishes the difference. The `clones`
  field exposes `since`, `recordedDays`, `rawTotal`, `ciTotal`, `externalTotal`, `raw14d`, `ci14d`,
  `external14d`, `uniques14dSummed` — raw and correction side by side, so any published number can
  be traced back. Only `external*` reaches the UI, and even that still contains bots and mirrors.
  See [`server/README.md` § Clone harvesting](../server/README.md#clone-harvesting-github-traffic-api)
  for setup and the reading caveats.

## Not included in this version

Possible future work, deliberately not built now: dedicated skill/agent detail routes, rendered
README/`SKILL.md` markdown bodies (`marked` + `DOMPurify`), a "What's New" release feed (from
CHANGELOG parsing), and a multi-language UI switcher (the i18n module is ready; only `en` ships).
Auth and ratings are out of scope entirely.

## Build & deploy

Local:

```
npm run build:catalog          # repo root — regenerate site/public/catalog.json
cd site && npm ci && npm run build && npm run preview
```

(`npm run dev` inside `site/` gives the HMR dev server instead.)

**GitHub Pages** — [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) regenerates
`catalog.json`, builds the Vite app, and publishes `site/dist` on every push to `main`. Enable once
via *Settings → Pages → Source → GitHub Actions*. The site is served from the repo subpath
(`https://<owner>.github.io/<repo>/`); Vite's `base: "./"` keeps asset paths relative and routing
is hash-based, so no base-path configuration or server rewrites are needed.

**Render.com** — the repo-root [`render.yaml`](../render.yaml) blueprint builds with
`npm ci && npm run build:catalog && cd site && npm ci && npm run build` and publishes `./site/dist`
as a static site from the domain root.

## CI separation

Three independent workflows, deliberately not merged:

- **`validate`** (`.github/workflows/validate.yml`) — content-quality gate on every PR and push:
  Prettier, markdownlint, the marketplace linter, `claude plugin validate`, and the eval static gate.
- **`site-build`** (`.github/workflows/site-build.yml`) — build check on every PR and push touching
  the catalog data or the site (path-filtered): regenerates `catalog.json`, type-checks, and builds
  the Vite app. Build-only — nothing is published.
- **`pages`** (`.github/workflows/pages.yml`) — builds `catalog.json` + the app and deploys
  `site/dist` to GitHub Pages on push to `main`.

Keeping them separate means a deploy hiccup is never confused with a build break or a
content-validation failure.
