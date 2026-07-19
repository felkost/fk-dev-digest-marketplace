# insights.md — server

> Append-only. Add new entries at the bottom of the correct section.
> Discovery bar: "Would a fresh agent save >=10 minutes from reading this?" If not, skip.

## Patterns
<!-- Reusable approaches that worked in this module. -->

## Mistakes
<!-- Failure modes, antipatterns, wrong assumptions. Prioritize this section. -->

## Decisions
<!-- Architectural or design choices with the reasoning behind them. -->

## Quirks
- ~~**2026-06-18 [Quirk]** — `fastify-type-provider-zod` compiles each route's reply schema once at boot, so editing a reply schema requires a full server restart; watch-mode reload does not recompile it. `server/src/modules/reviews/routes.ts:67`~~ (superseded 2026-07-13)
- **2026-07-13 [Quirk]** — `fastify-type-provider-zod` now recompiles a route's reply schema on each watch-mode reload after the dependency bump, so editing a reply schema no longer requires a full server restart. `server/src/modules/reviews/routes.ts:67`

## Open Questions
<!-- Unresolved. -->

---
Last updated: 2026-07-13 · Entries: 1
