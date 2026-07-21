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
- The plugin's fixed enrichment roadmap (rounds 0–4) is complete and rounds 5–14 have shipped on
  top of it; it is no longer a bare scaffold (8 skills, 31 references), but version stays `0.0.1`
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
  marker rather than silently rewriting it. **Round 13 adds a cheaper-to-hit variant: a book's
  own chapter summary is not a source for that chapter's body.** Lanham's summaries contradict
  his prose twice — the body names the OpenAI *o-series* as the reasoning-native family while
  the summary bullet writes "e.g., GPT-4o family", and the body says cognitive memory labels
  "obscure the real distinction" while the summary says they "map cleanly to implementation
  layers". Summaries are written to be quotable, which is exactly what makes them the tempting
  thing to mine. Carry the body. **And a third species, found by reading the companion repo's
  chapters 3–6: prose versus code.** The book explains Reciprocal Rank Fusion as the production
  default for hybrid search; its own hybrid-RAG script implements an ad-hoc keyword scorer and
  delegates fusion to the agent's judgement — no fusion function exists. When a source ships
  runnable code, the code is a separate claim from the prose, and the two are checked
  separately. Neither one ratifies the other. **Your own coverage grep is a brief too.** Round 13
  produced two false "zero coverage" verdicts in one session from regex mistakes alone: `\b` in
  `\bTree of Thought\b` refused to match the plural heading "Tree of Thoughts", and under `-E` the
  alternation `a\|b` is a *literal pipe*, which silently turned six patterns into literal strings
  and reported prompt caching as absent from a plugin that documents it in six files. Before
  writing "this is a gap", open the file the grep searched.
- **Tool documentation is a moving target: cite the technique, treat the identifier as volatile.**
  Class names, parameter names and doc URLs drift between releases — round 9 found LangChain's
  concept URLs 308-redirecting to a generic overview and LlamaIndex's docs on a new host, and the
  same round's brief carried FAISS's `nlist`/`nprobe` for what pgvector calls
  `lists`/`ivfflat.probes`. Name the mechanism, name the implementation you checked, and say the
  identifier should be verified against current docs. Never copy a parameter name from one
  library into a sentence about another. **A third instance (round 12):** OpenAI's own docs host
  moved from `platform.openai.com` to `developers.openai.com` mid-plugin-lifetime, and its
  primary documented text-generation surface shifted from the Chat Completions guide toward the
  Responses API. `generation-parameters.md` cites OpenRouter (the plugin's actual provider) for
  concrete parameter ranges instead, precisely because it stayed reachable and current when the
  upstream OpenAI guide didn't. **A fourth instance (round 13) is a different and worse species:
  a source can be current by publication date and stale by protocol.** Lanham's chapter 3,
  supplied in 2026, teaches "MCP supports two transports, STDIO and SSE" throughout its tables,
  listings and exercises — but the spec defines **stdio and Streamable HTTP**, and says
  Streamable HTTP "replaces the HTTP+SSE transport from protocol version 2024-11-05", calling
  that one deprecated. Note the trap on the correction side too: SSE did not disappear, it
  became an optional streaming mechanism *inside* Streamable HTTP's single endpoint. Check the
  specification, not the copyright year — and check your correction as hard as the claim. That
  last clause is not rhetorical: round 13's own correction was verified against revision
  `2025-06-18`, which the spec's versioning page already listed as superseded by `2025-11-25`
  hours later. **Find the current revision through
  <https://modelcontextprotocol.io/specification/versioning> rather than any pinned URL — a
  pinned spec link in our own notes is exactly the artifact this rule warns about** — and date
  the check when you record it. (Every claim carried this round survived verbatim in the newer
  revision, and the `Origin` requirement got stronger, not weaker: an invalid `Origin` now
  **MUST** be answered with HTTP 403.) **A fifth instance (round 14) needs no protocol history at
  all — two current libraries in this plugin's own stack spell the same thing two different
  ways.** The official MCP Python SDK's `FastMCP.run()` takes `transport="streamable-http"`
  (hyphenated — verified against the pinned `v1.28.1` source); `langchain-mcp-adapters`'
  client-side connection config takes `transport="streamable_http"` (underscored — verified
  against its `sessions.py` source), though it also accepts `"streamable-http"`/`"http"` as
  aliases. Both are current, both are correct for their own library, and copying either spelling
  into the other library's code is a plausible-looking bug. Round 9's rule ("never copy a
  parameter name from one library into a sentence about another") already covered this shape of
  error across unrelated libraries; this instance is the same trap between two libraries meant to
  be used *together*, which makes it easier to miss, not harder.
- **Skill frontmatter descriptions must be in third person** (e.g. "Designs…", "Explains…"), per
  Anthropic's Skill authoring guidance — not the imperative ("Design…", "Explain…") this plugin
  used for its first eleven rounds without anyone checking against the published best-practices
  doc. Fixed across all 8 `SKILL.md` files in round 12
  (<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>). Apply
  this to any new skill's `description` field from the start; don't wait for an audit to catch it
  again. The same source recommends a table of contents at the top of any reference file that
  exceeds ~100 lines — also applied in round 12 to every reference that had crossed that line.
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
