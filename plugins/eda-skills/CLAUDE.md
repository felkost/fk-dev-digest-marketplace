# CLAUDE.md — eda-skills

This directory is one plugin inside the `fk-dev-digest-marketplace` monorepo (see the repo root
`README.md` and `.claude-plugin/marketplace.json`). Scope edits to this folder unless explicitly
asked to touch another plugin or the marketplace root.

- Skill content (`SKILL.md` bodies, `references/`, `README.md`, `README-beginner.md`,
  `HANDOFF.md`) is written in Ukrainian by design. See "Note on Ukrainian-language plugins" in
  the repo root `README.md` — this plugin is quarantined from the marketplace's English-only
  content checks in `scripts/validate-marketplace.mjs`, not translated. Don't translate it
  unprompted.
- Each `skills/<name>/agents/openai.yaml` is a custom-GPT action schema consumed by the
  `chatgpt/` packaging pipeline (`build_gpt_package.ps1` → `dist/*.zip`) — unrelated to Claude
  Code's plugin-level `agents/` convention, and not scanned as such.
- Repo-root scripts (`npm run lint`, `npm run build:catalog`) must be run from the marketplace
  root, not from here — paths in `scripts/*.mjs` are root-relative.
