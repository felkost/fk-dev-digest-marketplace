#!/usr/bin/env node
/**
 * Build the static catalog index consumed by the (separate) marketplace website.
 *
 * Reads .claude-plugin/marketplace.json and every plugins/<name>/.claude-plugin/plugin.json,
 * scans each plugin's skills/agents/commands for their frontmatter description, and writes one
 * self-contained JSON file: dist/index.json.
 *
 * The website never reads this repository directly — it fetches this generated file (see
 * docs/SITE-SPEC.md). Regenerate with: node scripts/build-index.mjs
 */

import { existsSync, readFileSync, readdirSync, statSync, mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DIST_DIR = join(REPO_ROOT, "dist");

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

/**
 * Minimal frontmatter reader for our own files: every SKILL.md / agent .md in this repo uses
 * flat `key: value` pairs (name, description, model, argument-hint) — no nested YAML, no lists
 * that matter for the index. This avoids adding a YAML dependency just for two string fields.
 */
function readFrontmatter(filePath) {
  // Normalize CRLF → LF first: some source files carry Windows line endings, and a trailing \r
  // on a line defeats `.`/`$` in the regex below (both treat \r as a line terminator).
  const raw = readFileSync(filePath, "utf8").replace(/\r\n/g, "\n");
  if (!raw.startsWith("---")) return {};
  const end = raw.indexOf("\n---", 3);
  if (end === -1) return {};
  const block = raw.slice(3, end);
  const fm = {};
  for (const line of block.split("\n")) {
    const m = line.match(/^([a-zA-Z-]+):\s*(.*)$/);
    if (!m) continue;
    const [, key, rawValue] = m;
    let value = rawValue.trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (value === "" || value === "|" || value === ">") continue; // multi-line block — skip, not needed here
    fm[key] = value;
  }
  return fm;
}

function listSkills(pluginDir) {
  const dir = join(pluginDir, "skills");
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((d) => statSync(join(dir, d)).isDirectory() && existsSync(join(dir, d, "SKILL.md")))
    .sort()
    .map((name) => {
      const fm = readFrontmatter(join(dir, name, "SKILL.md"));
      return { name: fm.name ?? name, description: fm.description ?? "" };
    });
}

function listAgents(pluginDir) {
  const dir = join(pluginDir, "agents");
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith(".md") && f.toLowerCase() !== "readme.md")
    .sort()
    .map((f) => {
      const name = f.replace(/\.md$/, "");
      const fm = readFrontmatter(join(dir, f));
      return { name: fm.name ?? name, description: fm.description ?? "", model: fm.model ?? null };
    });
}

function listCommands(pluginDir) {
  const dir = join(pluginDir, "commands");
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith(".md"))
    .sort()
    .map((f) => {
      const name = f.replace(/\.md$/, "");
      const raw = readFileSync(join(dir, f), "utf8");
      const fm = readFrontmatter(join(dir, f));
      const firstLine = raw.split("\n").find((l) => l.trim().length > 0) ?? "";
      return { name, description: fm.description ?? firstLine.trim() };
    });
}

function listHooks(pluginDir) {
  const hooksJson = join(pluginDir, "hooks", "hooks.json");
  if (!existsSync(hooksJson)) return [];
  const config = readJson(hooksJson);
  const events = Object.keys(config.hooks ?? {});
  return events;
}

function main() {
  const marketplacePath = join(REPO_ROOT, ".claude-plugin", "marketplace.json");
  if (!existsSync(marketplacePath)) {
    console.error("error: .claude-plugin/marketplace.json not found");
    process.exit(1);
  }
  const marketplace = readJson(marketplacePath);

  const plugins = (marketplace.plugins ?? []).map((entry) => {
    const pluginDir = join(REPO_ROOT, entry.source);
    const manifestPath = join(pluginDir, ".claude-plugin", "plugin.json");
    const manifest = existsSync(manifestPath) ? readJson(manifestPath) : {};

    return {
      name: manifest.name ?? entry.name,
      displayName: manifest.displayName ?? entry.name,
      version: manifest.version ?? null,
      description: manifest.description ?? entry.description ?? "",
      category: entry.category ?? null,
      keywords: manifest.keywords ?? entry.keywords ?? [],
      author: manifest.author ?? null,
      license: manifest.license ?? null,
      repository: manifest.repository ?? null,
      dependencies: (manifest.dependencies ?? []).map((d) =>
        typeof d === "string" ? { name: d } : d,
      ),
      skills: listSkills(pluginDir),
      agents: listAgents(pluginDir),
      commands: listCommands(pluginDir),
      hookEvents: listHooks(pluginDir),
    };
  });

  const index = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    marketplace: {
      name: marketplace.name,
      description: marketplace.description ?? "",
      owner: marketplace.owner,
    },
    plugins,
  };

  mkdirSync(DIST_DIR, { recursive: true });
  const outPath = join(DIST_DIR, "index.json");
  writeFileSync(outPath, JSON.stringify(index, null, 2) + "\n");

  console.log(`Wrote ${outPath.replace(REPO_ROOT + "\\", "").replace(REPO_ROOT + "/", "")}`);
  console.log(
    `  ${plugins.length} plugins, ${plugins.reduce((n, p) => n + p.skills.length, 0)} skills, ${plugins.reduce((n, p) => n + p.agents.length, 0)} agents, ${plugins.reduce((n, p) => n + p.commands.length, 0)} commands`,
  );
}

main();
