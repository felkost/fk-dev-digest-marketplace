import cors from "@fastify/cors";
import rateLimit from "@fastify/rate-limit";
import { count, desc, sql } from "drizzle-orm";
import type { PostgresJsDatabase } from "drizzle-orm/postgres-js";
import Fastify from "fastify";
import { z } from "zod";
import { cloneStats, events } from "./db/schema.js";

export const EVENT_TYPES = ["copy_install", "plugin_view"] as const;

// Same kebab-case rule the marketplace enforces for plugin names.
const eventSchema = z
  .object({
    type: z.enum(EVENT_TYPES),
    plugin: z
      .string()
      .max(64)
      .regex(/^[a-z0-9]+(-[a-z0-9]+)*$/),
  })
  .strict();

export type Db = PostgresJsDatabase<Record<string, unknown>>;

interface AppOptions {
  corsOrigins: string[];
}

const STATS_CACHE_MS = 60_000;

export async function buildApp(db: Db, opts: AppOptions) {
  const app = Fastify({
    logger: true,
    bodyLimit: 1024, // events are tiny; anything bigger is not ours
    trustProxy: true, // Render terminates TLS in front of us
  });

  await app.register(cors, {
    origin: opts.corsOrigins,
    methods: ["GET", "POST"],
  });

  await app.register(rateLimit, {
    max: 120,
    timeWindow: "1 minute",
  });

  let statsCache: { at: number; body: unknown } | null = null;

  app.post(
    "/api/events",
    { config: { rateLimit: { max: 30, timeWindow: "1 minute" } } },
    async (request, reply) => {
      const parsed = eventSchema.safeParse(request.body);
      if (!parsed.success) {
        return reply.code(400).send({ error: "invalid event" });
      }
      await db.insert(events).values({ type: parsed.data.type, plugin: parsed.data.plugin });
      return reply.code(204).send();
    },
  );

  app.get("/api/stats", async (_request, reply) => {
    const now = Date.now();
    if (!statsCache || now - statsCache.at > STATS_CACHE_MS) {
      const rows = await db
        .select({ plugin: events.plugin, type: events.type, count: count() })
        .from(events)
        .groupBy(events.plugin, events.type);

      const perPlugin: Record<string, Record<string, number>> = {};
      const totals: Record<string, number> = {};
      for (const row of rows) {
        (perPlugin[row.plugin] ??= {})[row.type] = row.count;
        totals[row.type] = (totals[row.type] ?? 0) + row.count;
      }

      // Clone counts harvested from the GitHub Traffic API (see harvestClones.ts). GitHub counts
      // every `actions/checkout` as a clone, so the raw figure includes this repo's own CI; the
      // `external*` numbers subtract that per day (floored at zero, since the CI correction is an
      // upper bound — see fetchCiCheckoutsByDay). Raw and correction are both exposed so the
      // published number can always be traced back. `since` is null until the harvester has run.
      //
      // What survives the subtraction is "clones we did not cause" — which still includes crawlers,
      // mirrors and AI scrapers. It is an interest trend, never an install count. The only counters
      // here that measure a deliberate human action are the copy_install/plugin_view totals above.
      const cloneRows = await db
        .select()
        .from(cloneStats)
        .orderBy(desc(cloneStats.day))
        .limit(3650); // ~10 years — effectively "all of it" without an unbounded scan
      const last14 = cloneRows.slice(0, 14);
      const externalOn = (r: (typeof cloneRows)[number]) => Math.max(0, r.count - r.ciCount);
      const sum = (rows: typeof cloneRows, pick: (r: (typeof cloneRows)[number]) => number) =>
        rows.reduce((total, r) => total + pick(r), 0);
      const clones = {
        since: cloneRows.length ? cloneRows[cloneRows.length - 1].day : null,
        recordedDays: cloneRows.length,
        rawTotal: sum(cloneRows, (r) => r.count),
        ciTotal: sum(cloneRows, (r) => r.ciCount),
        externalTotal: sum(cloneRows, externalOn),
        raw14d: sum(last14, (r) => r.count),
        ci14d: sum(last14, (r) => r.ciCount),
        external14d: sum(last14, externalOn),
        // GitHub's per-day unique-cloner counts, added up. The same machine cloning on two days
        // counts twice, so this is an activity measure, not a headcount — hence the name.
        uniques14dSummed: sum(last14, (r) => r.uniques),
      };

      statsCache = {
        at: now,
        body: { generatedAt: new Date(now).toISOString(), perPlugin, totals, clones },
      };
    }
    return reply.header("cache-control", "public, max-age=60").send(statsCache.body);
  });

  app.get("/healthz", async () => {
    // Proves both the process and the database connection are alive.
    await db.execute(sql`select 1`);
    return { ok: true };
  });

  return app;
}
