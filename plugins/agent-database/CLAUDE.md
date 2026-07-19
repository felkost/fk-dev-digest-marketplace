# CLAUDE.md — agent-database

This directory is one plugin inside the `fk-dev-digest-marketplace` monorepo (see the repo root
`README.md` and `.claude-plugin/marketplace.json`). Scope edits to this folder unless explicitly
asked to touch another plugin or the marketplace root.

- Skill content (`SKILL.md` bodies, `references/*.md`, `README.md`, `HANDOFF.md`, `chatgpt/`) is
  written in Ukrainian by design; SKILL.md and agent **frontmatter** (`name`/`description` — what
  the catalog site and Claude's skill matching actually read) is English. See "Note on
  Ukrainian-language plugins" in the repo root `README.md` — this plugin is quarantined from the
  marketplace's English-only content checks in `scripts/validate-marketplace.mjs`, not translated.
  Don't translate it unprompted.
- `agents/sql-mentor.md` at the plugin root is a Claude Code agent (teacher/analyst persona) that
  routes work through the seven skills by namespaced name (`agent-database:<skill>`). It has no
  write tools **on purpose** — see the curator mode below.
- **Curator mode is the plugin's core discipline.** The agent never edits its own knowledge base;
  it proposes «📌 Урок-кандидат» (a generalized rule + target file) and «📒 Запис у банк задач»
  (a full worked example for `analyze-sql-examples/references/task-bank.md`). A human approves,
  and only then does an assistant with write access apply it. Do not "helpfully" write approved-
  looking proposals into `references/` without an explicit human yes — that is the exact failure
  mode the design prevents.
- **Factual errors are the exception**: when a test run proves a reference states something false
  (wrong syntax, superseded product name, a recipe that would break), fix it directly and record
  it in `HANDOFF.md`. New *lessons* need approval; *defects* do not.
- **DDL and schema/ETL design examples must cover PostgreSQL, MySQL, and ClickHouse** — the three
  mandatory course DBMSs. Always comment ClickHouse specifics (MergeTree/ORDER BY, no FK). This is
  a standing requirement from the plugin's owner, not a stylistic preference.
- **Verify when you can, don't invent.** SQLite examples can be run through `sqlite3` (Bash) before
  they enter a reference; dialect-specific claims are checked against official documentation. Do
  not fabricate syntax, version numbers, or product behaviour — vendor lakehouse and vector-DB
  APIs move fast (`APPLY CHANGES INTO` → `AUTO CDC INTO` is a worked example of exactly this).
- **Editing a `description:` frontmatter line: if it contains a colon followed by a space, the value MUST be double-quoted.**
  An unquoted colon-space inside a YAML plain scalar is invalid and makes `gray-matter` throw, failing
  `evals`' `eval:quality` gate. Claude Code itself and `scripts/build-index.mjs` (which has its own
  naive frontmatter reader) both tolerate it, so nothing local flags it — this reached CI once
  already. `build-index.mjs` strips the surrounding quotes, so `catalog.json` is unaffected. See
  `HANDOFF.md` § «Гейти CI» for the one-liner that checks every file at once.
- After changing any `SKILL.md` or `references/*.md`, rebuild the ChatGPT knowledge bundle:
  `powershell -ExecutionPolicy Bypass -File chatgpt\build_gpt_package.ps1`. The script also checks
  `gpt_instructions.md` against ChatGPT's **8000 UTF-8 byte** limit — Cyrillic is 2 bytes/letter,
  so a text that fits in 8000 *characters* can still be rejected. Watch for `OK` in its output.
- Repo-root scripts (`npm run lint`, `npm run build:catalog`) must be run from the marketplace
  root, not from here — paths in `scripts/*.mjs` are root-relative.
