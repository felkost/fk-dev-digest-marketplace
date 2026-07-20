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
- The plugin's fixed enrichment roadmap (rounds 0–4) is complete and rounds 5–7 have shipped on
  top of it; it is no longer a bare scaffold (8 skills, 27 references), but version stays `0.0.1`
  and untagged until the user says otherwise. Read `HANDOFF.md` first in every new session, and
  keep it updated at the end of a working session (the handoff protocol is part of the plugin's
  own methodology — see `skills/plan-ai-solution/SKILL.md` § «Handoff між сесіями»).
- Do not invent benchmark numbers, prices, or model-capability claims: when a reference needs a
  concrete figure, either cite the source it came from or mark it as "verify against the provider's
  current docs". Model catalogs (OpenRouter etc.) change weekly — skills teach *how to choose*,
  not a frozen leaderboard. **Peer review does not make a number citable either**: the Karim et al.
  annotation survey triaged in round 7 prints the same cost pair as `$0.00006 vs $0.082` in a table
  and as `CNY 0.00006 vs CNY 0.082` in prose two pages later. Carry the mechanism; say where the
  figure can be read.
- **Source admissibility splits in two, and the halves have different bars.** *Facts and figures*
  need a traceable primary source — the rule above. *Techniques and practitioner recipes* do not:
  a named, recognizable technique may go into a reference without an academic citation, provided
  it contradicts neither the current documentation of the tool it uses nor the underlying theory.
  Check it against that documentation before writing, and label it as a practitioner technique
  instead of dressing it up as a citation. Consequently, a book with no publisher and no
  bibliography is rejected only when it also carries no such technique — missing credentials are
  not the disqualifier; having nothing checkable is. (User's rule, 2026-07-20; the triage
  procedures in `HANDOFF.md` carry the same exception.)
- Repo-root scripts (`npm run lint`, `npm run build:catalog`) must be run from the marketplace
  root, not from here — paths in `scripts/*.mjs` are root-relative.
- The RAG example (`skills/build-ai-examples/scripts/rag_example/`) needs a real
  `OPENROUTER_API_KEY` in its own `.env` (gitignored repo-wide; `.env.example` is the tracked
  template, values blank). Never ask the user to paste the key into chat and never write one into
  a file yourself — the user fills `.env` in their own editor. `ingest.py`/`agent.py` load it via
  `python-dotenv`, anchored to the script's directory; `settings.py` stays stdlib-only on purpose
  and only reads `os.environ` (see `rag-example.md`) — don't add dotenv or any other third-party
  import there.
