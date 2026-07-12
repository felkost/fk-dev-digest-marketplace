#!/usr/bin/env node
/**
 * Build the catalog data file consumed by the standalone marketplace website (site/).
 *
 * Reads dist/index.json (produced by scripts/build-index.mjs) and writes site/public/catalog.json —
 * the same plugin list plus a marketplace block carrying the install commands the site renders.
 * The site (React + Vite, see site/) fetches ./catalog.json at runtime; Vite copies public/ into
 * the built site/dist, so this file is the single data source the UI depends on.
 *
 * Regenerate the whole chain with: node scripts/build-index.mjs && node scripts/build-catalog.mjs
 * (or `npm run build:catalog`, which runs both).
 */

import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const INDEX_PATH = join(REPO_ROOT, "dist", "index.json");
const SITE_PUBLIC_DIR = join(REPO_ROOT, "site", "public");
const OUT_PATH = join(SITE_PUBLIC_DIR, "catalog.json");

if (!existsSync(INDEX_PATH)) {
  console.error("error: dist/index.json not found — run `node scripts/build-index.mjs` first");
  process.exit(1);
}

const index = JSON.parse(readFileSync(INDEX_PATH, "utf8"));

// Every plugin.json in this repo points at the same marketplace repository; derive the GitHub
// "owner/repo" short form the `/plugin marketplace add` command expects from it.
const repository =
  index.plugins.find((p) => p.repository)?.repository ??
  "https://github.com/felkost/fk-dev-digest-marketplace";
const repoShort = repository.replace(/^https?:\/\/github\.com\//, "").replace(/\.git$/, "");

const catalog = {
  schemaVersion: 1,
  generatedAt: index.generatedAt ?? new Date().toISOString(),
  marketplace: {
    name: index.marketplace.name,
    displayName: "Dev Digest",
    description: index.marketplace.description ?? "",
    owner: index.marketplace.owner,
    repository,
    repoShort,
    // The two commands the detail page shows verbatim. `{plugin}` is substituted per plugin in the UI.
    addCommand: `/plugin marketplace add ${repoShort}`,
    installTemplate: `/plugin install {plugin}@${index.marketplace.name}`,
  },
  plugins: index.plugins,
};

mkdirSync(SITE_PUBLIC_DIR, { recursive: true });
writeFileSync(OUT_PATH, JSON.stringify(catalog, null, 2) + "\n");

const rel = OUT_PATH.replace(REPO_ROOT + "\\", "").replace(REPO_ROOT + "/", "");
console.log(`Wrote ${rel}`);
console.log(
  `  ${catalog.plugins.length} plugins, ` +
    `${catalog.plugins.reduce((n, p) => n + p.skills.length, 0)} skills, ` +
    `${catalog.plugins.reduce((n, p) => n + p.agents.length, 0)} agents, ` +
    `${catalog.plugins.reduce((n, p) => n + p.commands.length, 0)} commands`,
);
