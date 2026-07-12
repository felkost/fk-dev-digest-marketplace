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
| `src/components/` | `Header`, `Footer`, `Hero`, `Sidebar`, `PluginCard`, `InstallBlock`, `CommandPalette`. |
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
