# CLAUDE.md — eda-skills

This directory is one plugin inside the `fk-dev-digest-marketplace` monorepo (see the repo root
`README.md` and `.claude-plugin/marketplace.json`). Scope edits to this folder unless explicitly
asked to touch another plugin or the marketplace root.

- Language is split by audience, and **neither direction should be translated unprompted**:
  - **Ukrainian** — `SKILL.md` bodies, `README.md`, `README-beginner.md`, `chatgpt/README.md`,
    `chatgpt/gpt_instructions.md`. These are read by the user.
  - **English** — every `skills/*/references/*.md`, `HANDOFF.md`, and each `SKILL.md`
    frontmatter `name`/`description` (the catalog site and Claude's skill matching read those).
  - Reference prose is English **with Ukrainian only as quoted material** — phrases the agent
    says to the user, domain examples, starter templates. `plan-eda-dataset/references/intake.md`
    and `references/mentoring.md` are the pattern to copy when adding a reference.

  See "Note on Ukrainian-language plugins" in the repo root `README.md` — the whole plugin is
  quarantined from the marketplace's English-only content checks in
  `scripts/validate-marketplace.mjs` (`QUARANTINED_PLUGINS`), not translated.
- Each `skills/<name>/agents/openai.yaml` is a custom-GPT action schema consumed by the
  `chatgpt/` packaging pipeline (`build_gpt_package.ps1` → `dist/*.zip`) — unrelated to Claude
  Code's plugin-level `agents/` convention, and not scanned as such.
- Repo-root scripts (`npm run lint`, `npm run build:catalog`) must be run from the marketplace
  root, not from here — paths in `scripts/*.mjs` are root-relative.
