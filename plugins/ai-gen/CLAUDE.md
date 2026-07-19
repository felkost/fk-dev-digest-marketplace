# CLAUDE.md — ai-gen

This directory is one plugin inside the `fk-dev-digest-marketplace` monorepo (see the repo root
`README.md` and `.claude-plugin/marketplace.json`). Scope edits to this folder unless explicitly
asked to touch another plugin or the marketplace root.

- Skill content (`SKILL.md` bodies, `README.md`, `HANDOFF.md`) is written in Ukrainian by design;
  `references/*.md` are English (agent-efficient detail). See "Note on Ukrainian-language plugins"
  in the repo root `README.md` — this plugin is quarantined from the marketplace's English-only
  content checks in `scripts/validate-marketplace.mjs`, not translated. Don't translate it
  unprompted.
- `agents/ai-gen-mentor.md` at the plugin root is a Claude Code agent (senior developer + mentor
  persona). Each `skills/<name>/agents/openai.yaml` is a custom-GPT/Codex packaging descriptor
  consumed by the `chatgpt/` pipeline (`build_gpt_package.ps1` → `dist/*.zip`) — unrelated to the
  plugin-level `agents/` convention, and not scanned as such.
- The plugin is a v0.x scaffold by design: skill methodology will be extended from user-supplied
  materials in later sessions. Read `HANDOFF.md` first in every new session, and keep it updated
  at the end of a working session (the handoff protocol is part of the plugin's own methodology —
  see `skills/plan-ai-solution/SKILL.md` § «Handoff між сесіями»).
- Do not invent benchmark numbers, prices, or model-capability claims: when a reference needs a
  concrete figure, either cite the source it came from or mark it as "verify against the provider's
  current docs". Model catalogs (OpenRouter etc.) change weekly — skills teach *how to choose*,
  not a frozen leaderboard.
- Repo-root scripts (`npm run lint`, `npm run build:catalog`) must be run from the marketplace
  root, not from here — paths in `scripts/*.mjs` are root-relative.
