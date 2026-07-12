import { bigserial, index, pgTable, text, timestamp } from "drizzle-orm/pg-core";

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
