# Catalog website (`site/`)

A React + TypeScript + Vite single-page app that lets people browse this marketplace's plugins —
fuzzy search (MiniSearch) across names, descriptions, keywords, and every skill/agent/command;
deep-linkable plugin pages (`#/plugin/<name>`); a ⌘/Ctrl-K command palette; light/dark themes; and
a copy-install action. It is deliberately kept in its own directory so it never mixes with the
marketplace content under `plugins/`.

## Structure

| Path | Role |
|---|---|
| `index.html` | Vite entry: fonts + `#root` mount point. |
| `vite.config.ts` | Vite config — `base: "./"` (relative assets) so one build works on both a Pages subpath and Render's root. |
| `src/main.tsx` | Bootstraps React, imports the stylesheet. |
| `src/App.tsx` | Providers (theme, catalog, filters), `HashRouter` routes, ⌘K wiring, shell layout. |
| `src/styles/theme.css` | Design tokens (light + dark palettes on CSS variables) and all component classes. |
| `src/i18n/strings.ts` | Every user-facing UI string (English); add a locale by adding a sibling file. |
| `src/lib/types.ts` | TypeScript shapes of `catalog.json`. |
| `src/lib/catalog.tsx` | Catalog data context — fetched once from `./catalog.json`. |
| `src/lib/filters.tsx` | Shared search/category/keyword filter state. |
| `src/lib/search.ts` | MiniSearch index over plugins, skills, agents, and commands (prefix + fuzzy). |
| `src/lib/theme.tsx` | Light/dark theme context — `prefers-color-scheme` default, `localStorage` override. |
| `src/lib/util.ts` | Small helpers (`initials`, `plural`, `copyText`, …). |
| `src/lib/statsApi.ts` | Optional usage-stats client (events + cached `/api/stats`); no-op without `VITE_STATS_API`. |
| `src/components/` | `Header`, `Footer`, `Hero`, `Sidebar`, `PluginCard`, `InstallBlock`, `CommandPalette`, `StatsTiles`. |
| `src/pages/` | `CatalogPage` (`#/`), `PluginDetailPage` (`#/plugin/:name`). |
| `public/catalog.json` | Generated plugin data — copied into `dist/` by the build. Never edit by hand. |
| `public/.nojekyll` | Tells GitHub Pages to serve files as-is. |

## Data

`public/catalog.json` is generated from the repository — never edit it by hand:

```
npm run build:catalog        # (repo root) runs scripts/build-index.mjs then scripts/build-catalog.mjs
```

`build-index.mjs` reads `.claude-plugin/marketplace.json` and every plugin's manifest, skills,
agents, commands, and hooks into `dist/index.json`; `build-catalog.mjs` reshapes that into
`site/public/catalog.json` and adds the install commands the site renders. A copy is committed so
a fresh clone can run the site without regenerating first.

## Run it locally

```
npm run build:catalog        # repo root — regenerate the data
cd site
npm ci                       # first time only
npm run dev                  # dev server with HMR
# or the production pipeline:
npm run build && npm run preview
```

## Deploy — GitHub Pages

Already wired: [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) regenerates
`catalog.json`, builds the app, and publishes `site/dist` on every push to `main`. To turn it on
once: **Settings → Pages → Build and deployment → Source → GitHub Actions.**

The site is served from the repo subpath (`https://<owner>.github.io/<repo>/`). Vite's
`base: "./"` keeps every asset path relative and routing is hash-based (`#/…`), so no base-path
configuration or server rewrites are needed.

## Deploy — Render.com

The repo-root [`render.yaml`](../render.yaml) blueprint publishes the built app as a static site:

- **Build command:** `npm ci && npm run build:catalog && cd site && npm ci && npm run build`
- **Publish directory:** `./site/dist`

On Render, create a new **Blueprint** from this repository and it picks `render.yaml` up
automatically; the site is then served from the domain root.

## How the usage counters behave

The hero stat tiles come from the optional stats backend (`server/`) via `GET /api/stats`. They
render only when `VITE_STATS_API` is set at build time and a value is greater than 0, so the page
looks unchanged until real numbers exist. Each tile updates on its own schedule:

- **install copies / plugin views** — updated **automatically, in real time**. When any visitor on
  the deployed site opens a plugin page or clicks a copy button, the browser sends a fire-and-forget
  `POST /api/events` to the backend, which writes it to Postgres. The tile re-reads `/api/stats` on
  each page load (the server caches it for 60 s), so the numbers grow by themselves as people use
  the site — no redeploy, no manual step.
- **external clones / external clones · last 14 days** — updated **once a day**. They stay hidden
  (0) until the `harvest-clones` GitHub Action has run successfully at least once (it needs the
  `TRAFFIC_PAT` secret — see [`server/README.md`](../server/README.md) § Clone harvesting). After
  that it runs on a daily cron with no further action needed. "External" means GitHub's raw clone
  count minus this repository's own CI checkouts, which GitHub counts as clones; the remainder
  still includes bots and mirrors, so treat it as an interest trend rather than an install count.
  The 14-day tile stays hidden while it still equals the total.

### Nothing to do on the GitHub Pages side

The published frontend only *displays* numbers it fetches live from the Render backend at runtime.
The counters never require a Pages rebuild. You only redeploy Pages (by pushing to `main`) when you
change the site's **code** or the `VITE_STATS_API` value.

### Why Render numbers can be slow to appear (free plan)

On Render's free plan the `fk-dev-digest-stats` web service **spins down after ~15 minutes of
inactivity** and takes ~30–60 s to wake on the next request. Consequences:

- The first homepage load after an idle period waits for that cold start before the tiles appear
  (they show late, not as an error).
- A copy/view event fired at the exact moment the service is asleep can be **dropped** — events are
  fire-and-forget with no retry, so a rare miss during spin-up is expected and acceptable for a
  rough engagement metric.

The accumulated data itself is safe regardless: it lives in Neon Postgres, so nothing is lost while
the service sleeps — it just reads the existing totals once it wakes. If you need no missed events
or instant loads, either upgrade the Render service to an always-on paid instance or add an external
keep-alive ping (e.g. UptimeRobot every 5–10 min).

### Quick check that it is live

Open these directly in a browser (substitute your backend domain):

- `https://<stats-service>.onrender.com/healthz` → `{"ok":true}`
- `https://<stats-service>.onrender.com/api/stats` → raw numbers: `totals` (copies/views) and
  `clones` (zeros until `TRAFFIC_PAT` is configured and the harvester has run).
