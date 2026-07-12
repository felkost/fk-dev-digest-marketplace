/**
 * Discover the skills/agents across every plugin under plugins/ and scaffold eval files for one
 * of them. Teams bring their own skill set, so this is how they add tests without hand-copying
 * the file trio.
 *
 * Eval suites are grouped by plugin, mirroring the marketplace's plugin-first layout:
 *
 *   pnpm eval:scaffold                                # list every skill/agent and whether it has evals
 *   pnpm eval:scaffold <plugin> <skill-name>           # create evals/<plugin>/skills/<name>/{<name>.eval.ts, .cases.ts, fixtures/}
 *   pnpm eval:scaffold <plugin> --agent <agent-name>   # same under evals/<plugin>/agents/<name>/
 *
 * Refuses to overwrite existing files.
 */

import { existsSync, mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { GREEN, DIM, YELLOW, RESET } from "./ansi.js";
import { skillsDirs, agentsDirs, EVALS_DIR, PLUGINS_DIR } from "./artifacts/paths.js";

interface Artifact {
  plugin: string;
  name: string;
}

function listSkills(): Artifact[] {
  const out: Artifact[] = [];
  for (const dir of skillsDirs()) {
    const plugin = dir.split(/[/\\]/).slice(-2, -1)[0];
    for (const d of readdirSync(dir)) {
      if (statSync(join(dir, d)).isDirectory() && existsSync(join(dir, d, "SKILL.md"))) {
        out.push({ plugin, name: d });
      }
    }
  }
  return out.sort((a, b) => (a.plugin + a.name).localeCompare(b.plugin + b.name));
}

function listAgents(): Artifact[] {
  const out: Artifact[] = [];
  for (const dir of agentsDirs()) {
    const plugin = dir.split(/[/\\]/).slice(-2, -1)[0];
    for (const f of readdirSync(dir)) {
      if (f.endsWith(".md") && f !== "README.md") {
        out.push({ plugin, name: f.replace(/\.md$/, "") });
      }
    }
  }
  return out.sort((a, b) => (a.plugin + a.name).localeCompare(b.plugin + b.name));
}

const evalPath = (tier: "skills" | "agents", plugin: string, name: string) =>
  join(EVALS_DIR, plugin, tier, name, `${name}.eval.ts`);
const hasEval = (tier: "skills" | "agents", plugin: string, name: string) =>
  existsSync(evalPath(tier, plugin, name));

function list(): void {
  console.log(`\n${"=".repeat(56)}\nSkills (${PLUGINS_DIR}/*/skills)\n${"=".repeat(56)}`);
  for (const { plugin, name } of listSkills()) {
    const mark = hasEval("skills", plugin, name)
      ? `${GREEN}✓ evals${RESET}`
      : `${DIM}— no evals${RESET}`;
    console.log(`  ${(plugin + ":" + name).padEnd(48)} ${mark}`);
  }
  console.log(`\n${"=".repeat(56)}\nAgents (${PLUGINS_DIR}/*/agents)\n${"=".repeat(56)}`);
  for (const { plugin, name } of listAgents()) {
    const mark = hasEval("agents", plugin, name)
      ? `${GREEN}✓ evals${RESET}`
      : `${DIM}— no evals${RESET}`;
    console.log(`  ${(plugin + ":" + name).padEnd(48)} ${mark}`);
  }
  console.log(
    `\nScaffold one:  pnpm eval:scaffold <plugin> <skill-name>   |   pnpm eval:scaffold <plugin> --agent <agent-name>`,
  );
}

function casesTemplate(kind: "Skill" | "Agent"): string {
  return `import type { ${kind}Case } from "../../../src/index.js";

// To inline a fixture file into a prompt, uncomment these two lines and drop the file in
// fixtures/, then use fx("your-fixture.ext") inside a prompt string:
//   import { fixtureReader } from "../../../src/index.js";
//   const fx = fixtureReader(import.meta.url);

export const cases: ${kind}Case[] = [
  {
    name: "TODO describe the good behavior this checks",
    kind: "quality",
    prompt: "TODO the user/task prompt the ${kind.toLowerCase()} should handle",
    practices: [
      "TODO a specific, binary, citable thing the answer must do",
      "TODO another one — keep each verifiable from a verbatim quote",
    ],
    // grounding: ["exact-substring-that-must-appear-before-judging"], // optional cheap gate
    // threshold: 0.6,
    // maxTurns: 8,
  },
  // Keep it minimal — one or two cases is enough to start.
];
`;
}

function evalTemplate(tier: "skills" | "agents", name: string): string {
  const describe = tier === "skills" ? "describeSkill" : "describeAgent";
  const run = tier === "skills" ? "runSkillCases" : "runAgentCases";
  return `import { ${describe}, ${run} } from "../../../src/index.js";
import { cases } from "./${name}.cases.js";

${describe}("${name}", () => ${run}("${name}", cases));
`;
}

function scaffold(tier: "skills" | "agents", plugin: string, name: string): void {
  const kind = tier === "skills" ? "Skill" : "Agent";
  const available = tier === "skills" ? listSkills() : listAgents();
  if (!available.some((a) => a.plugin === plugin && a.name === name)) {
    console.error(
      `${YELLOW}warning:${RESET} '${plugin}:${name}' not found among ${tier} in plugins/*/ — scaffolding anyway.`,
    );
    console.error(
      `  available ${tier}: ${available.map((a) => `${a.plugin}:${a.name}`).join(", ") || "(none)"}`,
    );
  }

  const dir = join(EVALS_DIR, plugin, tier, name);
  const files: [string, string][] = [
    [join(dir, `${name}.eval.ts`), evalTemplate(tier, name)],
    [join(dir, `${name}.cases.ts`), casesTemplate(kind)],
    [join(dir, "fixtures", ".gitkeep"), ""],
  ];

  const existing = files.filter(([f]) => existsSync(f)).map(([f]) => f);
  if (existing.length) {
    console.error(`${YELLOW}refusing to overwrite:${RESET}\n  ${existing.join("\n  ")}`);
    process.exit(1);
  }

  mkdirSync(join(dir, "fixtures"), { recursive: true });
  for (const [f, content] of files) writeFileSync(f, content);

  console.log(`${GREEN}scaffolded ${plugin}/${tier}/${name}:${RESET}`);
  for (const [f] of files) console.log(`  ${f.replace(EVALS_DIR + "/", "")}`);
  console.log(
    `\nNext: fill in ${name}.cases.ts, then run  pnpm vitest run ${plugin}/${tier}/${name}`,
  );
}

function main(): void {
  const argv = process.argv.slice(2);
  if (argv.length === 0) return list();
  const plugin = argv[0];
  const agentIdx = argv.indexOf("--agent");
  if (agentIdx !== -1) {
    const name = argv[agentIdx + 1];
    if (!name) return void console.error("usage: pnpm eval:scaffold <plugin> --agent <agent-name>");
    return scaffold("agents", plugin, name);
  }
  const name = argv[1];
  if (!name) return void console.error("usage: pnpm eval:scaffold <plugin> <skill-name>");
  scaffold("skills", plugin, name);
}

main();
