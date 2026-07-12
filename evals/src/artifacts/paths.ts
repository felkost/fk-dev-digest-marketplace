/**
 * Filesystem anchors. In the marketplace repo, skills and agents live inside plugin
 * directories (`plugins/<plugin>/skills/<name>/SKILL.md`, `plugins/<plugin>/agents/<name>.md`)
 * rather than a single `.claude/` tree — these consts and resolvers are the single source of
 * those locations.
 */

import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { existsSync, readdirSync, statSync } from "node:fs";

const HERE = dirname(fileURLToPath(import.meta.url));
export const EVALS_DIR = join(HERE, "..", "..");
export const REPO_ROOT = join(EVALS_DIR, "..");
export const PLUGINS_DIR = join(REPO_ROOT, "plugins");
export const RESULTS_DIR = join(EVALS_DIR, "results");

function pluginDirs(): string[] {
  if (!existsSync(PLUGINS_DIR)) return [];
  return readdirSync(PLUGINS_DIR)
    .map((d) => join(PLUGINS_DIR, d))
    .filter((p) => statSync(p).isDirectory());
}

/** Every `plugins/<plugin>/skills` directory that exists. */
export function skillsDirs(): string[] {
  return pluginDirs()
    .map((p) => join(p, "skills"))
    .filter((p) => existsSync(p));
}

/** Every `plugins/<plugin>/agents` directory that exists. */
export function agentsDirs(): string[] {
  return pluginDirs()
    .map((p) => join(p, "agents"))
    .filter((p) => existsSync(p));
}

/**
 * Resolve a skill directory by name across all plugins. Accepts both bare (`zod`) and
 * plugin-scoped (`engineering-paved-path:zod`) names.
 */
export function resolveSkillDir(skillName: string): string | null {
  const [scope, bare] = skillName.includes(":")
    ? (skillName.split(":", 2) as [string, string])
    : [null, skillName];
  for (const dir of skillsDirs()) {
    if (scope && !dir.includes(join("plugins", scope))) continue;
    const candidate = join(dir, bare);
    if (existsSync(join(candidate, "SKILL.md"))) return candidate;
  }
  return null;
}

/**
 * Resolve an agent markdown file by name across all plugins. Accepts both bare
 * (`architecture-reviewer`) and plugin-scoped (`architecture-review:architecture-reviewer`) names.
 */
export function resolveAgentFile(agentName: string): string | null {
  const [scope, bare] = agentName.includes(":")
    ? (agentName.split(":", 2) as [string, string])
    : [null, agentName];
  for (const dir of agentsDirs()) {
    if (scope && !dir.includes(join("plugins", scope))) continue;
    const candidate = join(dir, `${bare}.md`);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}
