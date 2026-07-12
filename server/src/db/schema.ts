import { bigserial, date, index, integer, pgTable, text, timestamp } from "drizzle-orm/pg-core";

/**
 * One row per counted event. Deliberately PII-free: no IP, no user agent, no session id —
 * only what the counters need. `type` values are validated at the API layer (zod enum);
 * see EVENT_TYPES in app.ts.
 */
export const events = pgTable(
  "events",
  {
    id: bigserial("id", { mode: "number" }).primaryKey(),
    type: text("type").notNull(),
    plugin: text("plugin").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [index("events_plugin_type_idx").on(table.plugin, table.type)],
);

/**
 * One row per calendar day of GitHub repository clone traffic, harvested by
 * scripts/harvestClones.ts (run on a schedule by .github/workflows/harvest-clones.yml) since the
 * GitHub Traffic API only retains a rolling 14-day window itself. `count` and `uniques` are
 * GitHub's own per-day numbers (uniques = unique cloners *that day*, not deduplicated across
 * days — summing this column is "unique clones per day, added up", not a distinct-user count).
 * Upserted by `day` so re-running the harvest safely corrects the last couple of days as GitHub
 * finalizes them, without duplicating history already recorded.
 */
export const cloneStats = pgTable("clone_stats", {
  day: date("day", { mode: "string" }).primaryKey(),
  count: integer("count").notNull(),
  uniques: integer("uniques").notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});
