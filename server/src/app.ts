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

      // Clone counts harvested from the GitHub Traffic API (see harvestClones.ts) — the closest
      // proxy for actual `/plugin install` runs, since installs clone the repo directly and never
      // touch this site or backend. `since` is null until the harvester has run at least once.
      const cloneRows = await db
        .select()
        .from(cloneStats)
        .orderBy(desc(cloneStats.day))
        .limit(3650); // ~10 years — effectively "all of it" without an unbounded scan
      const last14 = cloneRows.slice(0, 14);
      const clones = {
        since: cloneRows.length ? cloneRows[cloneRows.length - 1].day : null,
        recordedDays: cloneRows.length,
        totalSinceTracking: cloneRows.reduce((sum, r) => sum + r.count, 0),
        last14dCount: last14.reduce((sum, r) => sum + r.count, 0),
        last14dUniques: last14.reduce((sum, r) => sum + r.uniques, 0),
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
