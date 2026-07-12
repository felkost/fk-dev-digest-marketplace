// Harvests GitHub's repository clone traffic (the closest available proxy for real
// `/plugin install` runs — installs clone this repo directly and never touch the website or this
// backend) and persists it into clone_stats, because the GitHub Traffic API itself only keeps a
// rolling 14-day window. Run on a schedule by .github/workflows/harvest-clones.yml; safe to
// re-run any time (upserts by day, so it just refines the last couple of days as GitHub finalizes
// them and never duplicates history already recorded).
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

/** "2026-07-01T00:00:00Z" -> "2026-07-01" */
export function toDayKey(timestamp: string): string {
  return timestamp.slice(0, 10);
}

export async function fetchClones(repo: string, token: string): Promise<TrafficClonesResponse> {
  const res = await fetch(`https://api.github.com/repos/${repo}/traffic/clones`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!res.ok) {
    const body = await res.text();
    // A 403 here almost always means the token lacks push access to the repo — the Traffic API
    // requires it, and the default Actions GITHUB_TOKEN doesn't always qualify. See
    // server/README.md for the personal-access-token fallback.
    throw new Error(`GitHub Traffic API request failed: ${res.status} ${res.statusText}\n${body}`);
  }
  return (await res.json()) as TrafficClonesResponse;
}

/** Upserts every day in the response; returns how many rows were written. */
export async function upsertCloneStats(db: Db, data: TrafficClonesResponse): Promise<number> {
  for (const day of data.clones) {
    await db
      .insert(cloneStats)
      .values({ day: toDayKey(day.timestamp), count: day.count, uniques: day.uniques })
      .onConflictDoUpdate({
        target: cloneStats.day,
        set: { count: day.count, uniques: day.uniques, updatedAt: new Date() },
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

  const client = postgres(databaseUrl, { max: 1 });
  const db = drizzle(client);
  const written = await upsertCloneStats(db, data);
  await client.end();

  console.log(
    `Harvested ${written} day(s) from GitHub Traffic API for ${repo} ` +
      `(${data.count} clones / ${data.uniques} uniques in the current 14-day window); ` +
      `upserted into clone_stats.`,
  );
}

// Only run when executed directly (`tsx src/harvestClones.ts`) — not when imported by tests.
// Compared via pathToFileURL (not a raw `file://` template) so this also works on Windows, where
// import.meta.url uses forward slashes and an extra leading slash that argv[1] doesn't have.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
