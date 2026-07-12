#!/usr/bin/env node
/**
 * Roll back a bad plugin release: delete its tag (locally and, with --push, on origin) so
 * `claude plugin install`/update dependency resolution against `{plugin}--v<range>` falls back to
 * the highest remaining good tag, then print the manual follow-up checklist.
 *
 * Usage:
 *   node scripts/rollback.mjs <plugin> <bad-version> [--push]
 *
 * This script only removes the tag — it does not revert the content commit, rewrite
 * marketplace.json, or edit CHANGELOG.md. Those are judgment calls documented in
 * docs/RELEASES.md § Rollback and printed below as a checklist.
 */

import { existsSync } from "node:fs";
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

function git(args) {
  return execFileSync("git", args, { cwd: REPO_ROOT, encoding: "utf8" }).trim();
}

function main() {
  const argv = process.argv.slice(2);
  const push = argv.includes("--push");
  const positional = argv.filter((a) => !a.startsWith("--"));
  const [plugin, badVersion] = positional;

  if (!plugin || !badVersion) {
    fail("usage: node scripts/rollback.mjs <plugin> <bad-version> [--push]");
  }

  const pluginDir = join(REPO_ROOT, "plugins", plugin);
  if (!existsSync(pluginDir)) fail(`plugins/${plugin} does not exist`);

  const tag = `${plugin}--v${badVersion}`;
  const existingLocal = git(["tag", "--list", tag]);
  let existingRemote = "";
  try {
    existingRemote = git(["ls-remote", "--tags", "origin", tag]);
  } catch {
    // No network / no remote — treat as "unknown", not "absent".
  }

  if (!existingLocal && !existingRemote) {
    fail(`tag "${tag}" was not found locally or on origin — nothing to roll back.`);
  }

  // The highest remaining tag for this plugin, so the operator can see what installs resolve to
  // after this rollback (dependents constrained to e.g. "^1.0.0" will move to this on next update).
  const remainingTags = git(["tag", "--list", `${plugin}--v*`])
    .split("\n")
    .filter(Boolean)
    .filter((t) => t !== tag)
    .sort();
  const fallback = remainingTags[remainingTags.length - 1] ?? "(none — this was the only release)";

  if (existingLocal) {
    git(["tag", "-d", tag]);
    console.log(`${GREEN}Deleted local tag ${tag}.${RESET}`);
  }

  if (existingRemote) {
    if (push) {
      git(["push", "origin", `:refs/tags/${tag}`]);
      console.log(`${GREEN}Deleted remote tag ${tag} on origin.${RESET}`);
    } else {
      console.log(
        `${YELLOW}Remote tag ${tag} still exists — run with --push to delete it on origin, or manually:${RESET}`,
      );
      console.log(`  git push origin :refs/tags/${tag}`);
    }
  }

  console.log(`\nDependency resolution for "${plugin}" now falls back to: ${fallback}`);

  console.log(
    [
      "",
      `${YELLOW}Manual follow-up (docs/RELEASES.md § Rollback):${RESET}`,
      `  [ ] Revert the content commit(s) for plugins/${plugin} that shipped ${badVersion}, or fix forward with a new patch version — never leave main on the bad content with the tag gone.`,
      `  [ ] Add a dated entry to plugins/${plugin}/CHANGELOG.md documenting what was wrong with ${badVersion} and what replaced it.`,
      `  [ ] If ${badVersion} shipped a genuine security or correctness issue, follow docs/SECURITY.md's disclosure steps.`,
      `  [ ] If the plugin is being withdrawn entirely (not just this version), add it to the "renames" map in .claude-plugin/marketplace.json pointing to null — see docs/RELEASES.md.`,
      `  [ ] Once a fixed version is ready, release it normally: node scripts/release.mjs ${plugin} --push`,
    ].join("\n"),
  );
}

main();
