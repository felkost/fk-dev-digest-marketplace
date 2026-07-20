// Harvests GitHub's repository clone traffic into clone_stats, because the Traffic API itself only
// keeps a rolling 14-day window. Run on a schedule by .github/workflows/harvest-clones.yml; safe to
// re-run any time (upserts by day, so it just refines the last couple of days as GitHub finalizes
// them and never duplicates history already recorded).
//
// Raw clone traffic is NOT a usage metric on its own. GitHub counts every `actions/checkout` as a
// clone, so this repository's own CI shows up in its own clone numbers. The Traffic API carries no
// attribution at all — no actor, no source — so the only way to tell self-generated traffic apart
// is to count our own workflow runs over the same days from the Actions API and subtract. That is
// what `ci_count` is for: the raw figure and the correction are stored side by side, and the
// externally-attributable number is derived at read time in app.ts.
//
// Usage: DATABASE_URL=... GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo npx tsx src/harvestClones.ts

import { drizzle } from "drizzle-orm/postgres-js";
import { pathToFileURL } from "node:url";
import postgres from "postgres";
import type { Db } from "./app.js";
import { cloneStats } from "./db/schema.js";

export interface TrafficClonesResponse {
  count: number;
  uniques: number;
  clones: Array<{ timestamp: string; count: number; uniques: number }>;
}

interface WorkflowRun {
  created_at: string;
  run_attempt?: number;
}

/**
 * Clones produced per workflow *attempt*. Every workflow in .github/workflows checks the repo out
 * exactly once (pages.yml has two jobs, but only `build` runs actions/checkout — `deploy` consumes
 * an artifact). Adding a second checkout step, or a matrix that fans a checkout job out, would make
 * this an undercount; keep it in step with the workflows.
 */
const CHECKOUTS_PER_RUN_ATTEMPT = 1;

/** GitHub API pages we are willing to walk. 100 runs per page — a hard stop on runaway paging. */
const MAX_RUN_PAGES = 20;

/** "2026-07-01T00:00:00Z" -> "2026-07-01" */
export function toDayKey(timestamp: string): string {
  return timestamp.slice(0, 10);
}

async function githubGet(url: string, token: string, what: string): Promise<unknown> {
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!res.ok) {
    const body = await res.text();
    // A 403 on the Traffic API almost always means the token lacks push access — that API requires
    // it, and the default Actions GITHUB_TOKEN does not qualify. See server/README.md for the
    // personal-access-token fallback.
    throw new Error(`GitHub ${what} request failed: ${res.status} ${res.statusText}\n${body}`);
  }
  return res.json();
}

export async function fetchClones(repo: string, token: string): Promise<TrafficClonesResponse> {
  return (await githubGet(
    `https://api.github.com/repos/${repo}/traffic/clones`,
    token,
    "Traffic API",
  )) as TrafficClonesResponse;
}

/**
 * Counts this repo's own Actions checkouts per day, for every run created on or after `since`.
 * Re-runs are counted per attempt, because each attempt checks the repo out again.
 *
 * Runs that never reach the checkout step (cancelled by a concurrency group, skipped by a path
 * filter) are still counted here, so the correction can slightly overshoot on days full of
 * cancelled runs. Overshooting is the safe direction: it understates external interest rather than
 * inflating it, and app.ts floors the result at zero.
 */
export async function fetchCiCheckoutsByDay(
  repo: string,
  token: string,
  since: string,
): Promise<Map<string, number>> {
  const byDay = new Map<string, number>();
  for (let page = 1; page <= MAX_RUN_PAGES; page++) {
    const url =
      `https://api.github.com/repos/${repo}/actions/runs` +
      `?per_page=100&page=${page}&created=${encodeURIComponent(`>=${since}`)}`;
    const body = (await githubGet(url, token, "Actions runs API")) as {
      workflow_runs?: WorkflowRun[];
    };
    const runs = body.workflow_runs ?? [];
    if (runs.length === 0) break;
    for (const run of runs) {
      const day = toDayKey(run.created_at);
      const checkouts = Math.max(1, run.run_attempt ?? 1) * CHECKOUTS_PER_RUN_ATTEMPT;
      byDay.set(day, (byDay.get(day) ?? 0) + checkouts);
    }
    if (runs.length < 100) break;
  }
  return byDay;
}

/** Upserts every day in the response; returns how many rows were written. */
export async function upsertCloneStats(
  db: Db,
  data: TrafficClonesResponse,
  ciByDay: Map<string, number> = new Map(),
): Promise<number> {
  for (const day of data.clones) {
    const key = toDayKey(day.timestamp);
    const ciCount = ciByDay.get(key) ?? 0;
    await db
      .insert(cloneStats)
      .values({ day: key, count: day.count, uniques: day.uniques, ciCount })
      .onConflictDoUpdate({
        target: cloneStats.day,
        set: { count: day.count, uniques: day.uniques, ciCount, updatedAt: new Date() },
      });
  }
  return data.clones.length;
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    console.error(`error: ${name} is required`);
    process.exit(1);
  }
  return value;
}

async function main() {
  const databaseUrl = requireEnv("DATABASE_URL");
  const repo = requireEnv("GITHUB_REPOSITORY"); // "owner/repo" — GitHub Actions sets this automatically
  const token = requireEnv("GITHUB_TOKEN");

  const data = await fetchClones(repo, token);

  // Correct exactly the days the Traffic API just returned, so the raw count and its CI correction
  // always come from the same window. Days that scroll out of the window keep the ci_count they
  // were last written with.
  const days = data.clones.map((d) => toDayKey(d.timestamp)).sort();
  const since = days[0] ?? toDayKey(new Date().toISOString());
  const ciByDay = await fetchCiCheckoutsByDay(repo, token, since);

  const client = postgres(databaseUrl, { max: 1 });
  const db = drizzle(client);
  const written = await upsertCloneStats(db, data, ciByDay);
  await client.end();

  const ciInWindow = days.reduce((sum, day) => sum + (ciByDay.get(day) ?? 0), 0);
  const external = Math.max(0, data.count - ciInWindow);
  console.log(
    `Harvested ${written} day(s) from the GitHub Traffic API for ${repo} since ${since}: ` +
      `${data.count} raw clones, ${ciInWindow} of them our own CI checkouts, ` +
      `${external} externally attributable (${data.uniques} raw uniques). ` +
      `Upserted into clone_stats.`,
  );
}

// Only run when executed directly (`tsx src/harvestClones.ts`) — not when imported by tests.
// Compared via pathToFileURL (not a raw `file://` template) so this also works on Windows, where
// import.meta.url uses forward slashes and an extra leading slash that argv[1] doesn't have.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
