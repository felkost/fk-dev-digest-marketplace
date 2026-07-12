/**
 * CI change detector for the marketplace evals.
 *
 * Reads a newline-separated list of changed files (repo-relative) from $CHANGED_FILES and maps
 * them onto the eval suites that should run for this PR:
 *
 *   plugins/<plugin>/skills/<name>/**   OR  evals/<plugin>/skills/<name>/**   → run evals/<plugin>/skills/<name>
 *   plugins/<plugin>/agents/<name>.md   OR  evals/<plugin>/agents/<name>/**   → run evals/<plugin>/agents/<name>
 *
 * A changed artifact with NO written evals is NOT a failure: it is reported on the `skipped_*`
 * outputs so the job can print a visible "SKIP <plugin>:<name> (no evals)" line instead of going red.
 *
 * Emits GitHub Actions step outputs (skills, agents, skipped_skills, skipped_agents) to
 * $GITHUB_OUTPUT. Pure filesystem + string work — no deps.
 */

import { existsSync, readdirSync, appendFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const EVALS_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO_ROOT = join(EVALS_DIR, "..");
const PLUGINS_DIR = join(REPO_ROOT, "plugins");

const changed = (process.env.CHANGED_FILES ?? "")
  .split("\n")
  .map((s) => s.trim())
  .filter(Boolean);

/** Does evals/<plugin>/<tier>/<name>/ contain at least one *.eval.ts? */
function hasEvals(plugin, tier, name) {
  const dir = join(EVALS_DIR, plugin, tier, name);
  if (!existsSync(dir)) return false;
  return readdirSync(dir).some((f) => f.endsWith(".eval.ts"));
}

/**
 * Does the artifact under test exist on this checkout? Evals can outlive their artifact (e.g. an
 * A/B variant's eval merged without the variant's agent .md) — running such a suite is a
 * guaranteed `agent not found` crash, so it must be skipped, not run.
 */
function hasArtifact(plugin, tier, name) {
  return tier === "skills"
    ? existsSync(join(PLUGINS_DIR, plugin, "skills", name, "SKILL.md"))
    : existsSync(join(PLUGINS_DIR, plugin, "agents", `${name}.md`));
}

/** Collect distinct {plugin, name} pairs touched under a `plugins/` and/or `evals/` prefix. */
function touched(tier) {
  const pluginsRe = new RegExp(`^plugins/([^/]+)/${tier}/([^/]+)`);
  const evalsFileRe = new RegExp(`^plugins/([^/]+)/${tier}/([^/]+)\\.md$`);
  const evalsRe = new RegExp(`^evals/([^/]+)/${tier}/([^/]+)/`);
  const seen = new Set();
  const out = [];
  for (const f of changed) {
    const m = f.match(pluginsRe) ?? f.match(evalsFileRe) ?? f.match(evalsRe);
    if (!m) continue;
    const [, plugin, name] = m;
    if (tier === "agents" && name.toLowerCase() === "readme") continue;
    const key = `${plugin}:${name}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ plugin, name });
  }
  return out.sort((a, b) => (a.plugin + a.name).localeCompare(b.plugin + b.name));
}

const skillArtifacts = touched("skills");
const agentArtifacts = touched("agents");

/**
 * Why a changed suite must NOT run on CI (null = runnable). A `.ci-skip` marker file in the
 * suite dir opts an experiment out of gating (e.g. an A/B variant whose cases are EXPECTED to
 * fail at threshold 1.0 — it exists for eval:repeat/eval:delta, not for pass/fail).
 */
function skipReason(tier, plugin, name) {
  if (!hasEvals(plugin, tier, name)) return "no evals";
  if (!hasArtifact(plugin, tier, name)) return "artifact missing in plugins/";
  if (existsSync(join(EVALS_DIR, plugin, tier, name, ".ci-skip")))
    return "marked .ci-skip (experiment, not a gate)";
  return null;
}

const skills = skillArtifacts.filter((a) => !skipReason("skills", a.plugin, a.name));
const skippedSkills = skillArtifacts.filter((a) => skipReason("skills", a.plugin, a.name));
const agents = agentArtifacts.filter((a) => !skipReason("agents", a.plugin, a.name));
const skippedAgents = agentArtifacts.filter((a) => skipReason("agents", a.plugin, a.name));

const label = (a) => `${a.plugin}:${a.name}`;
const evalGlob = (tier, a) => `${a.plugin}/${tier}/${a.name}`;

const out = process.env.GITHUB_OUTPUT;
const write = (k, v) => (out ? appendFileSync(out, `${k}=${v}\n`) : console.log(`${k}=${v}`));

write("skills", JSON.stringify(skills.map((a) => evalGlob("skills", a))));
write("agents", JSON.stringify(agents.map((a) => evalGlob("agents", a))));
write("skipped_skills", skippedSkills.map(label).join(" "));
write("skipped_agents", skippedAgents.map(label).join(" "));

// Human-readable summary in the step log.
console.error("── eval change detection ──");
console.error(`changed files : ${changed.length}`);
console.error(`skills → run  : ${skills.map(label).join(", ") || "(none)"}`);
console.error(`agents → run  : ${agents.map(label).join(", ") || "(none)"}`);
for (const a of skippedSkills)
  console.error(`SKIP skill ${label(a)} — ${skipReason("skills", a.plugin, a.name)}`);
for (const a of skippedAgents)
  console.error(`SKIP agent ${label(a)} — ${skipReason("agents", a.plugin, a.name)}`);

// Markdown summary on the run page (GITHUB_STEP_SUMMARY), so the trigger-table outcome is
// visible without opening the step log.
const summaryFile = process.env.GITHUB_STEP_SUMMARY;
if (summaryFile) {
  const row = (labelText, run, skipped) =>
    `| ${labelText} | ${run.length ? run.map((a) => `\`${label(a)}\``).join(", ") : "—"} | ${
      skipped.length ? skipped.map((a) => `\`${label(a)}\``).join(", ") : "—"
    } |`;
  appendFileSync(
    summaryFile,
    [
      "### Eval change detection",
      "",
      `Changed files: **${changed.length}**`,
      "",
      "| Tier | Runs | Skipped (no evals) |",
      "|---|---|---|",
      row("skills", skills, skippedSkills),
      row("agents", agents, skippedAgents),
      "",
    ].join("\n"),
  );
}
