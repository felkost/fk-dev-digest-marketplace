#!/usr/bin/env node
/**
 * The marketplace's own linter — everything `claude plugin validate` doesn't check.
 *
 * (a) JSON Schema validation (ajv) for .claude-plugin/marketplace.json and every
 *     plugins/<name>/.claude-plugin/plugin.json.
 * (b) Cross-checks: every `source` path exists and has no `..`, plugin names are unique and
 *     match their directory, dependencies resolve within this marketplace, the dependency graph
 *     is acyclic, `version` is not duplicated (and potentially stale) between plugin.json and the
 *     marketplace entry.
 * (c) Content checks across every file under plugins/: no leftover markers from the repository
 *     these plugins were extracted from, no absolute filesystem paths, no Cyrillic text (this
 *     marketplace's materials are English-only — see CONTRIBUTING.md).
 *
 * Exit code 0 = clean, 1 = at least one error. Warnings are printed but do not fail the build.
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, dirname, sep } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv from "ajv";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SCHEMAS_DIR = join(REPO_ROOT, "scripts", "schemas");

const RED = "\x1b[31m";
const YELLOW = "\x1b[33m";
const GREEN = "\x1b[32m";
const RESET = "\x1b[0m";

const errors = [];
const warnings = [];
const err = (msg) => errors.push(msg);
const warn = (msg) => warnings.push(msg);

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

// ---------------------------------------------------------------------------
// (a) Schema validation
// ---------------------------------------------------------------------------

const ajv = new Ajv({ allErrors: true, strict: false });
const marketplaceSchema = readJson(join(SCHEMAS_DIR, "marketplace.schema.json"));
const pluginSchema = readJson(join(SCHEMAS_DIR, "plugin.schema.json"));
const validateMarketplace = ajv.compile(marketplaceSchema);
const validatePlugin = ajv.compile(pluginSchema);

const marketplacePath = join(REPO_ROOT, ".claude-plugin", "marketplace.json");
if (!existsSync(marketplacePath)) {
  err(".claude-plugin/marketplace.json does not exist");
  report();
}

const marketplace = readJson(marketplacePath);
if (!validateMarketplace(marketplace)) {
  for (const e of validateMarketplace.errors) {
    err(`marketplace.json ${e.instancePath || "/"} ${e.message}`);
  }
}

const plugins = new Map(); // name -> { entry, manifest, dir }

for (const [i, entry] of (marketplace.plugins ?? []).entries()) {
  const prefix = `marketplace.json plugins[${i}] (${entry.name ?? "?"})`;

  if (entry.source && entry.source.includes("..")) {
    err(`${prefix} source "${entry.source}" contains ".." — not allowed`);
  }
  if (entry.source && !entry.source.startsWith("./")) {
    err(`${prefix} source "${entry.source}" must start with "./"`);
  }

  const pluginDir = entry.source ? join(REPO_ROOT, entry.source) : null;
  if (!pluginDir || !existsSync(pluginDir)) {
    err(`${prefix} source path does not exist: ${entry.source}`);
    continue;
  }

  const dirName = relative(join(REPO_ROOT, "plugins"), pluginDir);
  if (dirName !== entry.name) {
    err(
      `${prefix} entry name "${entry.name}" does not match its source directory "plugins/${dirName}"`,
    );
  }

  const manifestPath = join(pluginDir, ".claude-plugin", "plugin.json");
  if (!existsSync(manifestPath)) {
    err(`${prefix} plugins/${dirName}/.claude-plugin/plugin.json does not exist`);
    continue;
  }

  const manifest = readJson(manifestPath);
  if (!validatePlugin(manifest)) {
    for (const e of validatePlugin.errors) {
      err(`${prefix} plugin.json ${e.instancePath || "/"} ${e.message}`);
    }
  }

  if (manifest.name !== entry.name) {
    err(
      `${prefix} plugin.json name "${manifest.name}" does not match marketplace entry name "${entry.name}"`,
    );
  }
  if (manifest.name !== dirName) {
    err(
      `${prefix} plugin.json name "${manifest.name}" does not match its directory "plugins/${dirName}" — a plugin's name must never drift from its directory (see docs/RELEASES.md on renames)`,
    );
  }

  if (entry.version && manifest.version && entry.version !== manifest.version) {
    err(
      `${prefix} declares version "${entry.version}" in marketplace.json but "${manifest.version}" in plugin.json — ` +
        `plugin.json always wins at load time, so this mismatch silently masks the version you set in marketplace.json. Remove "version" from the marketplace.json entry.`,
    );
  }

  if (plugins.has(entry.name)) {
    err(`duplicate plugin name "${entry.name}" in marketplace.json`);
  } else {
    plugins.set(entry.name, { entry, manifest, dir: pluginDir, dirName });
  }
}

// ---------------------------------------------------------------------------
// (b) Cross-checks: dependency resolution + acyclicity
// ---------------------------------------------------------------------------

function depName(dep) {
  return typeof dep === "string" ? dep : dep.name;
}

for (const [name, { manifest }] of plugins) {
  for (const dep of manifest.dependencies ?? []) {
    const dn = depName(dep);
    if (typeof dep === "object" && dep.marketplace) {
      // Cross-marketplace dependency — out of scope for this repo's own resolution check.
      continue;
    }
    if (!plugins.has(dn)) {
      err(`plugin "${name}" depends on "${dn}", which is not a plugin in this marketplace`);
    }
    if (typeof dep === "object" && dep.version && !/^[\^~]?\d+\.\d+\.\d+/.test(dep.version)) {
      warn(
        `plugin "${name}" dependency "${dn}" has an unusual version constraint "${dep.version}" — expected a semver range like "^1.0.0"`,
      );
    }
  }
}

function findCycle() {
  const WHITE = 0,
    GRAY = 1,
    BLACK = 2;
  const color = new Map([...plugins.keys()].map((n) => [n, WHITE]));
  const stack = [];

  function visit(name) {
    if (!plugins.has(name)) return null; // already reported as missing above
    color.set(name, GRAY);
    stack.push(name);
    const { manifest } = plugins.get(name);
    for (const dep of manifest.dependencies ?? []) {
      const dn = depName(dep);
      if (typeof dep === "object" && dep.marketplace) continue;
      if (!plugins.has(dn)) continue;
      const c = color.get(dn);
      if (c === GRAY) return [...stack, dn];
      if (c === WHITE) {
        const cycle = visit(dn);
        if (cycle) return cycle;
      }
    }
    stack.pop();
    color.set(name, BLACK);
    return null;
  }

  for (const name of plugins.keys()) {
    if (color.get(name) === WHITE) {
      const cycle = visit(name);
      if (cycle) return cycle;
    }
  }
  return null;
}

const cycle = findCycle();
if (cycle) err(`dependency cycle detected: ${cycle.join(" → ")}`);

// ---------------------------------------------------------------------------
// (c) Content checks — leftover project markers, absolute paths, Cyrillic
// ---------------------------------------------------------------------------

const FORBIDDEN_MARKERS = [
  { re: /DevDigest/i, label: "reference to the source repository's product name" },
  { re: /@devdigest\//, label: "reference to the source repository's npm scope" },
  { re: /\breviewer-core\b/, label: "reference to the source repository's internal package name" },
  {
    re: /\.claude\/skills\//,
    label: "hardcoded .claude/skills/ path (use a namespaced Skill reference instead)",
  },
  {
    re: /\.claude\/agents\//,
    label: "hardcoded .claude/agents/ path (use a namespaced Agent reference instead)",
  },
];

const ABSOLUTE_PATH_RE = /(^|[\s"'`(])(?:[A-Za-z]:[\\/]|\/home\/|\/Users\/|\/mnt\/[a-z]\/)/;
const CYRILLIC_RE = /[Ѐ-ӿ]/;

const TOP_LEVEL_DOC_NAMES = new Set(["README.md", "CHANGELOG.md", "COMPATIBILITY.md"]);

function isTopLevelPluginDoc(filePath, pluginDir) {
  return (
    dirname(filePath) === pluginDir && TOP_LEVEL_DOC_NAMES.has(filePath.slice(pluginDir.length + 1))
  );
}

function walkFiles(dir, out) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) walkFiles(p, out);
    else out.push(p);
  }
}

const TEXT_EXT_RE = /\.(md|ts|mjs|js|json|sh|txt|yml|yaml)$/i;

for (const [name, { dir }] of plugins) {
  const files = [];
  walkFiles(dir, files);
  for (const f of files) {
    if (!TEXT_EXT_RE.test(f)) continue;
    let content;
    try {
      content = readFileSync(f, "utf8");
    } catch {
      continue;
    }
    const rel = relative(REPO_ROOT, f).split(sep).join("/");

    if (ABSOLUTE_PATH_RE.test(content)) {
      err(
        `${rel}: contains an absolute filesystem path — plugins must reference files by \${CLAUDE_PLUGIN_ROOT}/\${CLAUDE_SKILL_DIR} or repo-relative paths only`,
      );
    }

    if (CYRILLIC_RE.test(content)) {
      err(`${rel}: contains Cyrillic text — all marketplace materials must be English`);
    }

    if (!isTopLevelPluginDoc(f, dir)) {
      for (const { re, label } of FORBIDDEN_MARKERS) {
        if (re.test(content)) {
          err(`${rel}: ${label} — extraction should have generalized this`);
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------

function report() {
  if (warnings.length) {
    console.log(`\n${warnings.length} warning(s):`);
    for (const w of warnings) console.log(`  ${YELLOW}WARN:${RESET} ${w}`);
  }
  if (errors.length) {
    console.log(`\n${errors.length} error(s):`);
    for (const e of errors) console.log(`  ${RED}ERROR:${RESET} ${e}`);
    console.log(`\n${RED}validate-marketplace: FAILED${RESET}`);
    process.exit(1);
  }
  console.log(
    `${GREEN}validate-marketplace: PASSED${RESET} (${plugins.size} plugins, ${warnings.length} warnings)`,
  );
  process.exit(0);
}

report();
