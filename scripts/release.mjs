#!/usr/bin/env node
/**
 * Release a single plugin: validate → verify the plugin's name is unchanged → verify version
 * consistency → tag `<plugin>--v<version>` → optionally push.
 *
 * Usage:
 *   node scripts/release.mjs <plugin> [--push] [--dry-run]
 *
 * Tag convention (see docs/RELEASES.md): `{plugin-name}--v{version}`, where `{version}` matches
 * the `version` field in that plugin's `.claude-plugin/plugin.json` at the tagged commit. This is
 * the convention `claude plugin install` uses to resolve a dependency's semver range against git
 * tags on this marketplace repository.
 */

import { existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const RED = "\x1b[31m";
const YELLOW = "\x1b[33m";
const GREEN = "\x1b[32m";
const RESET = "\x1b[0m";

function fail(msg) {
  console.error(`${RED}error:${RESET} ${msg}`);
  process.exit(1);
}

function git(args, opts = {}) {
  return execFileSync("git", args, { cwd: REPO_ROOT, encoding: "utf8", ...opts }).trim();
}

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function main() {
  const argv = process.argv.slice(2);
  const push = argv.includes("--push");
  const dryRun = argv.includes("--dry-run");
  const plugin = argv.find((a) => !a.startsWith("--"));

  if (!plugin) fail("usage: node scripts/release.mjs <plugin> [--push] [--dry-run]");

  const pluginDir = join(REPO_ROOT, "plugins", plugin);
  const manifestPath = join(pluginDir, ".claude-plugin", "plugin.json");
  const marketplacePath = join(REPO_ROOT, ".claude-plugin", "marketplace.json");

  // 1. The plugin must exist on disk and in the marketplace catalog.
  if (!existsSync(pluginDir)) fail(`plugins/${plugin} does not exist`);
  if (!existsSync(manifestPath))
    fail(`plugins/${plugin}/.claude-plugin/plugin.json does not exist`);
  if (!existsSync(marketplacePath)) fail(".claude-plugin/marketplace.json does not exist");

  const manifest = readJson(manifestPath);
  const marketplace = readJson(marketplacePath);
  const entry = marketplace.plugins.find((p) => p.source === `./plugins/${plugin}`);
  if (!entry) fail(`no marketplace.json entry with source "./plugins/${plugin}"`);

  // 2. Name immutability: plugin.json's name, the marketplace entry's name, and the directory
  //    name must all agree. A plugin's name is its stable identifier — renaming it silently
  //    breaks every existing install (see docs/RELEASES.md § Renaming).
  if (manifest.name !== plugin) {
    fail(
      `plugin.json name "${manifest.name}" does not match directory "plugins/${plugin}". ` +
        `A plugin's name must never change without going through the marketplace.json "renames" map — see docs/RELEASES.md.`,
    );
  }
  if (entry.name !== plugin) {
    fail(
      `marketplace.json entry name "${entry.name}" does not match directory "plugins/${plugin}".`,
    );
  }

  // 3. Version must exist and be valid semver (X.Y.Z, optionally with a pre-release suffix).
  const version = manifest.version;
  if (!version) fail(`plugins/${plugin}/.claude-plugin/plugin.json has no "version" field`);
  if (!/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/.test(version)) {
    fail(`"${version}" is not valid semver (expected X.Y.Z or X.Y.Z-prerelease)`);
  }

  // 4. version must not also be duplicated (and potentially stale) in the marketplace entry.
  if (entry.version && entry.version !== version) {
    fail(
      `marketplace.json entry declares version "${entry.version}" but plugin.json declares ` +
        `"${version}" — plugin.json always wins at load time, so a mismatch here is a silent trap. ` +
        `Remove "version" from the marketplace.json entry.`,
    );
  }

  // 5. The plugin's own directory must have a clean working tree — never tag partial or
  //    uncommitted work.
  const dirty = git(["status", "--porcelain", "--", `plugins/${plugin}`]);
  if (dirty) {
    fail(`plugins/${plugin} has uncommitted changes:\n${dirty}\nCommit or stash before releasing.`);
  }

  // 6. Run the repo-wide validator (schema + cross-checks + forbidden-marker + Cyrillic gate).
  //    A release must never ship something CI would reject.
  console.log("Running scripts/validate-marketplace.mjs …");
  execFileSync("node", [join(REPO_ROOT, "scripts", "validate-marketplace.mjs")], {
    cwd: REPO_ROOT,
    stdio: "inherit",
  });

  // 7. The tag must not already exist — releasing the same version twice is always a mistake
  //    (bump the version, or use rollback.mjs if the last release was bad).
  const tag = `${plugin}--v${version}`;
  const existingLocal = git(["tag", "--list", tag]);
  if (existingLocal)
    fail(`tag "${tag}" already exists locally. Bump the version, or run rollback.mjs first.`);
  let existingRemote = "";
  try {
    existingRemote = git(["ls-remote", "--tags", "origin", tag]);
  } catch {
    // No network / no remote configured — non-fatal, the local check above is authoritative for --dry-run.
  }
  if (existingRemote)
    fail(`tag "${tag}" already exists on origin. Bump the version, or run rollback.mjs first.`);

  console.log(`${GREEN}All checks passed for ${plugin}@${version}.${RESET}`);

  if (dryRun) {
    console.log(
      `${YELLOW}--dry-run: would create tag "${tag}"${push ? " and push it to origin" : ""}.${RESET}`,
    );
    return;
  }

  git(["tag", "-a", tag, "-m", `${plugin} ${version}`]);
  console.log(`${GREEN}Created tag ${tag}.${RESET}`);

  if (push) {
    git(["push", "origin", tag]);
    console.log(`${GREEN}Pushed ${tag} to origin.${RESET}`);
  } else {
    console.log(`${YELLOW}Not pushed — run: git push origin ${tag}${RESET}`);
  }

  console.log(
    `\nDon't forget: update plugins/${plugin}/CHANGELOG.md with the ${version} entry (before or in the same commit as the version bump — the tag should point at a commit whose CHANGELOG already documents the release).`,
  );
}

main();
