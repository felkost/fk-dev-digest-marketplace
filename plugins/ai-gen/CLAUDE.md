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
- The plugin's fixed enrichment roadmap (rounds 0–4) is complete and rounds 5–10 have shipped on
  top of it; it is no longer a bare scaffold (8 skills, 28 references), but version stays `0.0.1`
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
- **A famous paper and its reference implementation are two different sources — check which one
  owns the feature before citing.** Popular systems grow capabilities in the codebase that were
  never in the paper, and the paper's name gets attached to all of them by association. This has
  now caught the plugin twice: RLVR is named in Tülu 3, not in the DeepSeek work that popularized
  it (round 5), and GraphRAG's *local search* mode exists only in the Microsoft implementation's
  docs — the paper describes the global map-reduce mode alone (round 8). Cite the artifact that
  actually documents the feature, and say which one it is.
- **A brief is not a source, and neither is this project's own triage record.** Three rounds in a
  row found an error in what they were handed: round 8's brief attributed an implementation
  feature to the paper, round 9's brief mixed FAISS parameter names into pgvector, and round 10
  found a claim recorded as verified in `HANDOFF.md`'s own round-7 triage entry ("prompt
  injection overwriting stored annotations, §10.1") that the article does not make — the phrase
  appears once, in a sentence saying the *literature rarely covers* such attacks. Re-open the
  primary source and check the specific claim you are about to write, even when a trusted local
  note already says it was checked. When a record turns out wrong, correct it in place with a
  marker rather than silently rewriting it.
- **Tool documentation is a moving target: cite the technique, treat the identifier as volatile.**
  Class names, parameter names and doc URLs drift between releases — round 9 found LangChain's
  concept URLs 308-redirecting to a generic overview and LlamaIndex's docs on a new host, and the
  same round's brief carried FAISS's `nlist`/`nprobe` for what pgvector calls
  `lists`/`ivfflat.probes`. Name the mechanism, name the implementation you checked, and say the
  identifier should be verified against current docs. Never copy a parameter name from one
  library into a sentence about another.
- Repo-root scripts (`npm run lint`, `npm run build:catalog`) must be run from the marketplace
  root, not from here — paths in `scripts/*.mjs` are root-relative.
- Adding a reference costs no `gpt_instructions.md` bytes, but the knowledge zip is **not**
  free-riding: `dist/*.zip` is a build artifact and `check_docs.py` check 5 fails until
  `chatgpt/build_gpt_package.ps1` is re-run. Rebuild it in any round that adds or removes a
  reference, even when the instruction text is untouched. (Invoke it as `& .\chatgpt\build_gpt_package.ps1`
  — `pwsh` is not installed on this machine, only Windows PowerShell 5.1.)
- The RAG example (`skills/build-ai-examples/scripts/rag_example/`) needs a real
  `OPENROUTER_API_KEY` in its own `.env` (gitignored repo-wide; `.env.example` is the tracked
  template, values blank). Never ask the user to paste the key into chat and never write one into
  a file yourself — the user fills `.env` in their own editor. `ingest.py`/`agent.py` load it via
  `python-dotenv`, anchored to the script's directory; `settings.py` stays stdlib-only on purpose
  and only reads `os.environ` (see `rag-example.md`) — don't add dotenv or any other third-party
  import there.
