# Session handoff — ai-gen

Written 2026-07-19 at the end of the scaffolding session, for a fresh Claude session with no
conversation history. Read this whole file before touching anything.

## What this project is

`ai-gen` is a plugin in the `fk-dev-digest-marketplace` monorepo: a senior-developer/mentor
agent with 6 linked skills for generative-AI engineering. Structure mirrors the neighboring
`eda-skills` plugin (Ukrainian SKILL.md bodies + English frontmatter, English `references/`,
per-skill `agents/openai.yaml`, a `chatgpt/` Custom-GPT packaging pipeline), plus one thing
eda-skills does not have: a plugin-level Claude Code agent, `agents/ai-gen-mentor.md`.

Skills: `plan-ai-solution` (orchestrator with task-to-model-class routing and the
session-handoff protocol), `select-genai-models`, `design-agent-architecture`,
`deploy-ai-environments`, `evaluate-optimize-models`, `build-ai-examples`.

## Current verified state (as of this handoff)

- Plugin registered in `.claude-plugin/marketplace.json` and quarantined (Cyrillic content) in
  `scripts/validate-marketplace.mjs` → `QUARANTINED_PLUGINS`.
- `npm run lint` (validate-marketplace), `npm run lint:markdown`, and `npm run lint:format`
  pass from the repo root; `npm run build:catalog` regenerates `dist/index.json` +
  `site/public/catalog.json` with ai-gen included (6 skills, 1 agent).
- `chatgpt/build_gpt_package.ps1` builds `dist/ai_gen_knowledge.zip` and reports the
  `gpt_instructions.md` UTF-8 **byte** count against the 8000-byte budget (same byte-not-chars
  trap as eda-skills: Cyrillic is 2 bytes/letter).
- Version is `0.0.1` and **no release tag exists** — deliberately unreleased scaffold;
  `scripts/release.mjs` gates only its own plugin directory, so other plugins' releases are
  unaffected.

## What just happened (scaffolding session, 2026-07-19)

Created the whole plugin from scratch, modeled on eda-skills conventions. Key decisions:

- **Name is `ai-gen`, not `ai_gen`**: the marketplace schema (`scripts/schemas/*.json`)
  enforces `^[a-z0-9]+(-[a-z0-9]+)*$` and the validator requires name == directory. Same
  rename pattern as `eda_skills` → `eda-skills`.
- **Six skills, one orchestrator**: mirrors eda-skills' "orchestrator + linked stages" shape;
  the orchestrator owns the model-class verdict format (recommendation, defeated alternative,
  risks, PoC check) and the handoff protocol
  (`skills/plan-ai-solution/references/handoff.md`).
- **No invented numbers**: references deliberately teach selection *procedures* and contain no
  benchmark scores, prices, or context-window figures — model catalogs churn weekly and this
  repo has no eval harness for such claims yet. Keep it that way unless a claim is measured or
  cited (this is also recorded in `CLAUDE.md`).
- **References are English, SKILL.md bodies Ukrainian** — same split (and same reason:
  agent-efficiency vs user-facing language) as eda-skills.

## Environment gotchas

- Console encoding is cp1251 on this machine — don't `print()` Cyrillic from Python via Bash;
  write UTF-8 files and Read them instead (inherited from eda-skills sessions).
- Repo-root scripts must run from the marketplace root (`npm run lint`, `npm run
  build:catalog`); paths in `scripts/*.mjs` are root-relative.
- `dist/` is gitignored repo-wide, including this plugin's `dist/` — knowledge zips are built
  artifacts, never committed.
- Markdown is prettier-ignored repo-wide (`.prettierignore`); markdownlint-cli2 with the
  root `.markdownlint.jsonc` is the md gate instead.

## Open threads / not done

- **The main one: content enrichment.** The user will supply additional materials
  (документи/статті/курсові матеріали) in later sessions to deepen the skills. Follow the
  eda-skills working pattern: verify each claim before writing it into a reference; prefer
  cited/measured statements; record per-round history here.
- No `tests/` yet (eda-skills has smoke + doc-consistency tests). When references start
  carrying concrete claims/scripts, add a `tests/check_docs.py` analog — instructions-vs-zip
  path checking caught real drift in eda-skills.
- No `README-beginner.md` yet — add one if/when the user asks (eda-skills precedent).
- `chatgpt/gpt_instructions.md` has spare byte budget; when skills deepen, procedural additions
  go there, knowledge additions go into the zip via references.
- The plugin is not in `~/.claude/settings.json` → `enabledPlugins` yet (the other 4 released
  plugins are); enable after the user confirms the scaffold, or install via `/plugin install`.
