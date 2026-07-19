#!/usr/bin/env node
/**
 * Runs the official `claude plugin validate --strict` over the marketplace and every plugin,
 * then filters out one known-accepted warning so that everything else is a hard failure.
 *
 * Why this wrapper exists
 * -----------------------
 * Four plugins (eda-skills, agent-database, agent-ml-interviewer, ai-gen) keep a CLAUDE.md at
 * their plugin root. `claude plugin validate --strict` warns about that:
 *
 *   root: CLAUDE.md at the plugin root is not loaded as project context.
 *         To ship context with your plugin, use a skill (skills/<name>/SKILL.md) instead.
 *
 * The warning is correct about *installed* plugins and irrelevant to how these files are used.
 * They are not shipping context to installers — they are nested-directory project context for
 * maintainers editing this monorepo, which Claude Code loads when the session works under that
 * directory. Converting them to skills (the warning's suggestion) would ship maintainer-only
 * rules to every end user and downgrade an always-on guardrail into a model-invoked skill.
 * See CONTRIBUTING.md, "Accepted `claude plugin validate` warning".
 *
 * Because --strict turns that warning into a non-zero exit, a bare `--strict` run is permanently
 * red for those four plugins, which masks real findings. This script accepts that one warning —
 * and only for a plugin that actually has a CLAUDE.md at its root — and fails on anything else.
 *
 * Exit code 0 = clean (modulo accepted warnings), 1 = at least one real finding, 2 = CLI missing.
 */

import { existsSync, readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const RED = "\x1b[31m";
const YELLOW = "\x1b[33m";
const GREEN = "\x1b[32m";
const DIM = "\x1b[2m";
const RESET = "\x1b[0m";

// The single warning this repo accepts, matched on a stable substring of the validator's text.
const ACCEPTED_WARNING = "CLAUDE.md at the plugin root is not loaded as project context";

// `claude` may be a .cmd/.exe shim on Windows, so go through the shell to resolve it.
const USE_SHELL = process.platform === "win32";
const stripAnsi = (s) => s.replace(/\x1b\[[0-9;]*m/g, "");

function runValidator(target) {
  const arg = USE_SHELL ? `"${target}"` : target;
  const res = spawnSync("claude", ["plugin", "validate", arg, "--strict"], {
    cwd: REPO_ROOT,
    encoding: "utf8",
    shell: USE_SHELL,
  });
  if (res.error) return { unavailable: true };
  const output = stripAnsi(`${res.stdout ?? ""}\n${res.stderr ?? ""}`);
  // The validator prints each finding as a "❯ " bullet under a "Found N error/warning" heading.
  const findings = output
    .split(/\r?\n/)
    .filter((line) => line.trimStart().startsWith("❯ "))
    .map((line) => line.trim().slice(2).trim());
  return { status: res.status ?? 0, findings, output };
}

const cliProbe = spawnSync("claude", ["--version"], { encoding: "utf8", shell: USE_SHELL });
if (cliProbe.error || cliProbe.status !== 0) {
  const skippable = process.argv.includes("--skip-if-missing");
  console.log(
    `${YELLOW}validate-plugins: claude CLI not available${RESET} ` +
      `(install with: npm install -g @anthropic-ai/claude-code)`,
  );
  process.exit(skippable ? 0 : 2);
}

const pluginsDir = join(REPO_ROOT, "plugins");
const pluginNames = readdirSync(pluginsDir, { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .map((d) => d.name)
  .sort();

const targets = [{ label: "marketplace", target: ".", hasRootClaudeMd: false }].concat(
  pluginNames.map((name) => ({
    label: name,
    target: `plugins/${name}`,
    // Only excuse the warning for a plugin whose root CLAUDE.md actually exists. If the file is
    // removed the allowlist tightens itself; if the warning ever appears without one, it is new
    // behaviour and should fail rather than be silently swallowed.
    hasRootClaudeMd: existsSync(join(pluginsDir, name, "CLAUDE.md")),
  })),
);

const failures = [];
let acceptedCount = 0;

for (const { label, target, hasRootClaudeMd } of targets) {
  const result = runValidator(target);
  if (result.unavailable) {
    console.log(`${YELLOW}validate-plugins: could not execute the claude CLI${RESET}`);
    process.exit(2);
  }

  const real = [];
  let acceptedHere = 0;
  for (const finding of result.findings) {
    if (finding.includes(ACCEPTED_WARNING) && hasRootClaudeMd) {
      acceptedHere++;
      acceptedCount++;
      continue;
    }
    real.push(finding);
  }

  if (real.length) {
    failures.push({ label, target, findings: real });
    console.log(`${RED}FAIL${RESET} ${label}`);
    for (const f of real) console.log(`       ${f}`);
  } else if (result.status !== 0 && result.findings.length === 0) {
    // Non-zero with nothing parseable to report — surface the raw output rather than pass.
    failures.push({ label, target, findings: ["(unparsed validator failure)"] });
    console.log(`${RED}FAIL${RESET} ${label}`);
    console.log(result.output.trim().replace(/^/gm, "       "));
  } else if (acceptedHere) {
    console.log(`${GREEN}ok${RESET}   ${label} ${DIM}(accepted: plugin-root CLAUDE.md)${RESET}`);
  } else {
    console.log(`${GREEN}ok${RESET}   ${label}`);
  }
}

console.log("");
if (failures.length) {
  console.log(
    `${RED}validate-plugins: FAILED${RESET} ` +
      `(${failures.length} of ${targets.length} targets, ${acceptedCount} accepted warning(s))`,
  );
  process.exit(1);
}
console.log(
  `${GREEN}validate-plugins: PASSED${RESET} ` +
    `(${targets.length} targets, ${acceptedCount} accepted warning(s))`,
);
process.exit(0);
