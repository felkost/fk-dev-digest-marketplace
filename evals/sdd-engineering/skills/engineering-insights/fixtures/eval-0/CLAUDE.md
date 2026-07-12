# Project
Node >=22, pnpm, TypeScript, Fastify 5, Next.js 15, Drizzle ORM, Postgres 16 + pgvector.
Packages: server/ (@example/api), client/ (@example/web), core-lib/, e2e/.
Secrets go through SecretsProvider only. Shared types in server/src/vendor/shared/.
