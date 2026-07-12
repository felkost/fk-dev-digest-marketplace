import { drizzle } from "drizzle-orm/postgres-js";
import { migrate } from "drizzle-orm/postgres-js/migrator";
import postgres from "postgres";
import { buildApp } from "./app.js";
import * as schema from "./db/schema.js";

const DATABASE_URL = process.env.DATABASE_URL;
if (!DATABASE_URL) {
  console.error(
    "error: DATABASE_URL is required — set it to your Neon (or any PostgreSQL) connection string",
  );
  process.exit(1);
}

const corsOrigins = (
  process.env.CORS_ORIGINS ?? "https://felkost.github.io,https://fk-dev-digest-marketplace.onrender.com"
)
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

// Apply committed migrations (server/drizzle/) on boot, then serve.
const migrationClient = postgres(DATABASE_URL, { max: 1 });
await migrate(drizzle(migrationClient), { migrationsFolder: "drizzle" });
await migrationClient.end();

const client = postgres(DATABASE_URL);
const db = drizzle(client, { schema });

const app = await buildApp(db, { corsOrigins });

const port = Number(process.env.PORT ?? 3001);
await app.listen({ host: "0.0.0.0", port });
