# Session handoff — ai-gen

Newest round on top (eda-skills convention). Last updated 2026-07-20, end of **round 10** —
production RAG and eval-set construction. **This closes the round-7 roadmap; there is no round 11
planned and the next unit of work needs a new user request.** Written for a fresh Claude session
with no conversation history — read this whole file before touching anything.

## What just happened (round 10 — production RAG + label production, 2026-07-20, branch `feat/ai-gen-production-rag-evalset` off `main`)

The last round of the round-7 roadmap. Three files, no new references (still 8 skills / 28):
`rag-pipeline.md` 233 → **322 lines**, `evaluation.md` 42 → **100**, `loop-engineering.md`
179 → **186**.

### The finding that matters most: our own triage record was wrong

Round 7 filed this in its Tier A entry as verified: *"prompt injection overwriting stored
annotations as a measured failure, not a hypothetical (§10.1)"*. Re-opening the PDF before
writing showed the article contains **zero** instances of "prompt injection" as a finding of its
own. The phrase appears exactly once, in §1, saying that robustness against adversarial and
prompt-injection attacks is *rarely covered* by existing surveys. §10.1 does carry a real
incident — adversarial control steering an annotator into rewriting stored product tags at scale
before rollback — but it is not called prompt injection, and its record count is cited to another
work, so the figure does not transfer either.

The round-7 entry now carries an inline `CORRECTION` block rather than being silently rewritten,
and `CLAUDE.md` gained the general rule: **a brief is not a source, and neither is this project's
own triage record.** That rule now has three consecutive instances behind it — round 8's brief
misattributed an implementation feature to a paper, round 9's brief mixed FAISS parameter names
into pgvector, round 10's own HANDOFF misreported a source.

Everything else in the round-7 Tier A paragraph re-verified as accurate, with one wording fix:
§7.2 says confirmation bias arises when both agents share **similar** training data, not "the
same". Also verified fresh and used: the §7 ladder (single → dual generator-reviewer → multi-agent
role-based → HITL-as-agent, with CoAnnotating framed as *dynamic work allocation*), and Figure 4's
QA loop (orchestrator → annotator → quality checker → accept-or-re-annotate with human
intervention available → aggregator). **No numbers from the article were carried**, per the
standing rule the article itself motivated.

Access note: MDPI returns **403 to WebFetch** (Cloudflare). The PDF from the round-7 batch was
still in `C:\Users\felko\Downloads\` and PyMuPDF read it fine — that is how verification was
possible at all. If it is gone in future, the article is CC BY and mirrors exist.

### What the three edits argue

**`rag-pipeline.md` — a production section after the diagnosis table.** Hallucination handling
split into detection *and* correction, because pipelines routinely implement the first and stop:
per-claim checking (mechanical citation verification first — a citation pointing at a passage
that does not support the sentence is catchable in code, with no model), then a correction table
keyed on *where* the failure lives, with re-retrieval **using the failed claim as the query**
since a specific claim beats the original question. Abstention is named a first-class measured
outcome. Then the retrieval-surface security section, built on the rule `architectures.md`
already states — retrieved documents *are* tool output — and led by enumerating write paths to
the index, because that list is the threat model. Then index freshness, where deletion is called
out as the hard direction and staleness is defined as a property of *retrieved passages*, not of
the indexer job.

**`evaluation.md` — the gap it created for itself.** The file demanded labelled question→passage
pairs and never said where labels come from. Now: the Karim ladder as a cost-ordered table, the
backwards trick for RAG labels (sample a chunk, generate a question it answers, and the gold
passage is free) together with its flattering failure mode — questions written from a chunk reuse
its vocabulary, so lexical overlap alone retrieves them and recall@k looks excellent; the QA-loop
topology; and the rule that keeps it honest, **explicitly marked as this plugin's engineering
discipline and not a finding of the review**: a machine-labelled eval set measures the labeller
until a human-verified subsample bounds it.

**`loop-engineering.md` — one sentence, as briefed.** The maker-checker rules were already
correct and were not touched; the added sentence gives point 2's "different model is optionally
useful" a named mechanism and the citation.

### Verification actually run

`check_docs.py` 7/7 (8 skills / 28 references) · `smoke_test.py` 14/14 · `npm run lint` (8
plugins, 0 warnings) · `lint:markdown` (399 files, 0 errors) · `lint:format` clean · zip rebuilt
(135,046 bytes; `gpt_instructions.md` unmoved at 6928) · CJK scan over all English references: 0
(non-ASCII is `§`, `–`, `—`, `→` only). `build:catalog` skipped correctly — the Довідки body list
in `evaluate-optimize-models/SKILL.md` changed, the frontmatter `description` did not.

**Worth flagging for whoever works here next:** `rag-pipeline.md` is now 322 lines, the longest
reference in the plugin and past the ~300 soft band the sibling `agent-ml-interviewer` plugin
enforces. It was not trimmed to hit a number, but it is the first candidate for a split (the
production layer would stand alone) if it grows again.

## What happened before (round 9 — ANN indexes + chunking strategies, 2026-07-20, branch `feat/ai-gen-ann-chunking` off `main`, merged as `1a9864d` via PR #14)

Second content round off round 7's roadmap. `memory-vector-db.md` 133 → **268 lines** (the brief
said ~220–260; the overshoot is real and was not trimmed to hit a number). No new file, so the
reference count stays 28 and the skill-list twins check stayed silent by design.

### The decision taken at the start of the round: `ingest.py` was NOT changed

The brief asked for an explicit verdict on closing `rag-example.md:148` by adding an ANN index to
the example. **Verdict: no**, and the reasoning is recorded so it is not re-litigated:

- That line lives in the example's "what to change for production" section. It is correct
  documentation, not an outstanding defect.
- An approximate index over a demo corpus of a handful of chunks speeds up nothing measurable and
  teaches reaching for ANN before the exact scan is a measured bottleneck — the opposite of what
  the rest of the plugin teaches.
- Verifying it live would spend the user's OpenRouter credit for no functional gain (round 6's
  discipline binds any code change here, and it is the right discipline).

Instead the *documentation* got stronger: `rag-example.md` now says the exact scan is deliberate,
that the index goes in when the scan is the measured bottleneck, and points at the new section
for family and parameter names. The gap is closed by explanation rather than by code.

### Attribution corrections this round (round 8's rule earning its keep)

- **The brief itself carried the wrong parameter names.** It asked for "`m`, `nlist`" and
  "`ef_search`, `nprobe`" — that mixes two libraries. **pgvector** uses `m`, `ef_construction`,
  `hnsw.ef_search`, `lists` and `ivfflat.probes`; `nlist`/`nprobe` are **FAISS**. The reference
  now carries a side-by-side table precisely because mixing them produces config that silently
  does nothing. `CLAUDE.md` gained the general rule: never copy a parameter name from one library
  into a sentence about another.
- **Doc URLs rotted mid-round**: LangChain's `python.langchain.com/docs/concepts/text_splitters`
  308-redirects to a generic overview, and LlamaIndex's docs moved to `developers.llamaindex.ai`.
  Class names differ between LangChain's new integrations page and its API reference
  (`MarkdownHeaderMetadataSplitter` vs `MarkdownHeaderTextSplitter`), so the reference names the
  *technique* and flags identifiers as check-at-write-time rather than pinning names that are
  visibly drifting.

Primaries verified before writing, per the standing rule: HNSW = Malkov & Yashunin
(<https://arxiv.org/abs/1603.09320>, layered proximity graphs, logarithmic scaling); product
quantization = Jégou, Douze & Schmid (*IEEE TPAMI* 33(1):117–128, 2011, doi:10.1109/TPAMI.2010.57);
RRF = Cormack, Clarke & Büttcher (SIGIR 2009). pgvector's defaults and `lists` guidance were read
from its README, not from the books — Jia Huang's translation artifacts (round 7) make it
unusable as a mechanism source.

### What the two new sections argue

**ANN.** Leads with the contract rather than the taxonomy: every ANN index buys speed by agreeing
not to always return the true nearest neighbours, and pgvector says so in its own README. Then
the recall/latency/memory triangle, with the honest warning that a change appearing to improve
all three has something unmeasured — usually recall, because nothing in the system complains when
it drops. Families table (Flat/IVF/HNSW/PQ/LSH) with how each fails, not just what it buys; the
build-time vs query-time knob split as the economically important distinction; the pgvector/FAISS
name table; pgvector's quantization types and the six distance operators, including that the
operator must match the index or the index simply is not used. Closes with sparse-vs-dense: a
rare token contributes almost nothing to a compressed dense vector and cannot be recovered from
it, which is why "our RAG cannot find ticket `INC-4471`" is a structural failure and hybrid + RRF
is a fix rather than a hedge.

**Chunking.** A ten-row strategy table (recursive character, structural, code-aware, regex,
table-aware, time-based, metadata-grouped, semantic, hierarchical/parent-child, sentence-window),
each with when it fits and what it costs — labelled explicitly as **practitioner technique
verified against tool docs**, per round 7's rule (в), not dressed as citation. Two closing rules:
carry metadata through every strategy (a chunk that cannot say where it came from cannot be
cited), and no strategy wins by argument — measure recall@k on your own set.

### Verification actually run

`check_docs.py` 7/7 (8 skills / 28 references) · `smoke_test.py` 14/14 · `npm run lint` (8
plugins, 0 warnings) · `lint:markdown` (399 files, 0 errors) · `lint:format` clean · zip rebuilt
(130,292 bytes; `gpt_instructions.md` unmoved at 6928) · CJK scan over all English references: 0.
Non-ASCII in the edited file is `é`, `ü`, `–`, `—`, `⁵`, `→`, `≤` — all intentional.
`build:catalog` correctly skipped: the Довідки list in `SKILL.md` changed, the frontmatter
`description` did not.

**The zip rebuild mattered this round for the reason round 8 recorded**: `check_docs.py` check 5
counts references and would have passed happily while shipping the *old* 133-line file inside the
archive. Content-only changes need the rebuild too.

## What happened before (round 8 — GraphRAG reference, 2026-07-20, branch `feat/ai-gen-graph-rag` off `main`, merged as `3fac365` via PR #13)

Round 7's roadmap named this round completely, so it needed no new material from the user: a new
`skills/design-agent-architecture/references/graph-rag.md` (235 lines) closing the plugin's only
zero-coverage gap. References 27 → **28**; skills unchanged at 8.

### The attribution error this round caught, and why it is now a `CLAUDE.md` rule

The brief said to describe "Microsoft GraphRAG's two query modes, global vs local". Verifying
Edge et al. (<https://arxiv.org/abs/2404.16130>, v2 Feb 2025) **before** writing showed the paper
describes the **global map-reduce mode only**. *Local search* is a mode of the Microsoft
implementation, documented at <https://microsoft.github.io/graphrag/query/local_search/>. Citing
the paper for it would have been exactly the round-5 mistake again (RLVR attributed to DeepSeek
instead of Tülu 3), so `CLAUDE.md` now carries the general rule: **a famous paper and its
reference implementation are two different sources — check which one owns the feature.** The
reference states the split explicitly rather than hiding it, since a reader who cites the paper
for local search will be wrong in public.

Other things verified against primaries rather than the books, per the standing rule:

- **Leiden** community detection, used hierarchically — Traag, Waltman & van Eck, "From Louvain
  to Leiden: guaranteeing well-connected communities", *Scientific Reports* 9:5233, 2019
  (<https://arxiv.org/abs/1810.08473>). The guarantee over Louvain is that communities are
  internally connected.
- **text2cypher** against the Neo4j GraphRAG Python package docs
  (<https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html>): the
  `neo4j_schema` and `examples` parameters are real API surface, and the docs state directly that
  a generated query is not guaranteed valid — it raises `Text2CypherRetrievalError`. Written as a
  practitioner technique checked against current tool docs, per round 7's rule (в).
- Bratanic & Hane was used as a **map only** — no claim in the file rests on it.

**Two paper figures were deliberately not carried**, in house style: the chunk-size/entity-recall
ratio from the appendix and the token-cost ratio in Table 2. The file carries the *direction* and
the knob (smaller chunks recall more entity references, at more LLM calls; gleaning rounds are the
counter-measure) and points at the paper for the numbers.

### What the reference actually argues

Leads with the decision rule, because it is the part that changes a recommendation: vector top-k
**structurally** cannot answer global/aggregative questions (similarity to the question is not
coverage of the corpus, and `k` out of `N` cannot become `N`) or multi-hop ones — and reranking
cannot fix either, because it only reorders a candidate set that is still `k`. Then: LLM graph
construction with **entity resolution as the hard part** (over-merging is the dangerous direction
— the graph looks clean while facts contaminate each other); the index pipeline and the two query
modes; text2cypher with its failure modes, including that generated Cypher can contain `DELETE`
and must run under a database-enforced read-only role, not a prompt instruction; a cost-honesty
section with a "when it is *not* worth it" table and three cheaper rungs to try first; and the
retriever router cross-referenced to `architectures.md`, not restated. The one router failure
mode kept here is the asymmetric one: **a misroute toward vector search is silent** — it returns
a fluent, well-cited answer of the wrong scope, while the reverse merely wastes money.

### Wiring done (the twins check does not cover any of it)

`rag-pipeline.md` scope note + a new row in the "what RAG fixes" table; `memory-vector-db.md`'s
one-line graph row expanded into a pointer paragraph that separates *store choice* from
*retrieval architecture*; `SKILL.md` Довідки entry; two routing rows in `skill-router.md`; README
tree line and trigger phrases.

### Verification actually run

`check_docs.py` 7/7 (8 skills / **28** references) · `smoke_test.py` 14/14 · `npm run lint` (8
plugins, 0 warnings) · `lint:markdown` (399 files, 0 errors) · `lint:format` clean ·
`build_gpt_package.ps1` rebuilt · stray-codepoint scan over all English references: **0 CJK**, and
`graph-rag.md` contains exactly two non-ASCII characters (`—`, `→`).

**A belief from the round-7 brief needed correcting:** "a new reference rides into the zip free"
is true of `gpt_instructions.md` **bytes** (6928, headroom 1072 — unmoved, confirmed), but *not*
of the zip artifact. `check_docs.py` check 5 failed with "knowledge zip has 27 references,
expected 28" until `build_gpt_package.ps1` was re-run (zip now 125,592 bytes). Recorded in
`CLAUDE.md`: rebuild the zip in any round that adds or removes a reference. `build:catalog` was
correctly skipped — no SKILL.md `description` changed.

## What happened before (round 7 — source-batch triage + rounds 8–10 roadmap, 2026-07-20, branch `docs/ai-gen-source-triage-round7` off `main`, merged as `de3f084` via PR #12)

A round-0-shaped session: **no reference content written.** The user supplied 13 files and asked
for a verdict on each, a plan for using them, and then the bookkeeping chain. Both standing
procedures below governed the work; nothing beyond metadata and tables of contents was extracted
from any book.

### The user's new rule, and why it changed a verdict mid-session

**Source admissibility now splits in two** (user's instruction, this session; recorded in
`CLAUDE.md` and in *both* triage procedures below):

- *Facts and figures* still need a traceable primary source. Unchanged.
- *Techniques and practitioner recipes* do **not** need an academic citation, provided they
  contradict neither the current documentation of the tool they use nor the underlying theory.
  Verify against that documentation before writing, and label the result a practitioner technique
  rather than dressing it as a citation.

Consequence: **absence of a bibliography is no longer a rejection reason by itself** — absence of
anything checkable is. This flipped one verdict the same session. Dhyani's *RAG with Python
Cookbook* had been rejected on a misreading ("the TOC is just `Recipe 1…51`"); the recipes in fact
sit under descriptive subheadings — n-gram, topic-based, regex, metadata, time-based, HTML-tag,
table-aware and custom-separator splitting, plus embedding chunk graphs and noise-resistant
embeddings via pre-normalization. That is a real spread of chunking technique, and Polzer does not
carry it. Accepted under the new rule.

### Verdicts (do not re-mine the rejected ones)

**Tier A, the only citable primary source.** Karim, Khan, Van, Liu, Wang & Qu, "Transforming Data
Annotation with AI Agents", *Future Internet* 2025, 17(8), 353, MDPI, **CC BY**, 38 pp, systematic
review over 135 selected papers. <https://doi.org/10.3390/fi17080353>. What transfers: the
annotation architecture ladder (single-agent → dual-agent generator/reviewer → multi-agent
role-based ensemble → HITL-as-agent, §7/Table 5); **dual-agent review degenerating by confirmation
bias when both agents share training data** (§7.2) — a citable source for a rule the plugin
already teaches in `loop-engineering.md`; the QA-loop topology (§6.2, Fig. 4); prompt injection
overwriting stored annotations as a measured failure, not a hypothetical (§10.1).

> **CORRECTION (round 10, verified against the PDF):** the last item is wrong as written. The
> article contains **no** instance of "prompt injection" as a finding of its own — the phrase
> occurs once, in §1, in a sentence stating that robustness against adversarial and
> prompt-injection attacks is *rarely covered* by existing surveys. What §10.1 does carry is an
> incident of **adversarial control** steering an annotator into rewriting stored product tags at
> scale before rollback, with the conclusion that hallucination, bias and adversarial control are
> measurable failures rather than theoretical risks — and the record count attached to it is
> second-hand (cited to another work), so it does not transfer either. Round 10 wrote the
> corrected version into `rag-pipeline.md`. The rest of this paragraph re-verified as accurate,
> with one wording fix: §7.2 says "similar training data", not "the same".

**Its numbers do not transfer**, and the reason is now a `CLAUDE.md` rule: the paper prints the
same cost pair as `$0.00006 vs $0.082` in Table 6 (p. 19) and as `CNY 0.00006 vs CNY 0.082` in
prose (p. 21). Peer review missed it. It is also dense with second-hand figures (50%/74%/80% cost
and time reductions, +17–24 pp, 85–95% success rates) and unsourced framing statistics in §1.

**Tier B, accepted as citation backbone:**

| Source | Pages | What it uniquely buys |
|---|---|---|
| Mendelevitch & Bao, *Hands-On RAG for Production* (O'Reilly) | 359 | Production RAG: two-stage retrieval, hybrid search, reranking, guardrails and prompt-injection prevention on the serving path, hallucination detection **and correction**, latency/TCO, PoC→production, DIY-vs-platform |
| Bratanic & Hane, *Essential GraphRAG* (Manning) | 178 | The whole graph-retrieval topic: KG construction with LLMs, entity resolution, text2cypher, Microsoft GraphRAG (community detection, global vs local search), agentic RAG (retriever router + answer critic) |
| Jia Huang, *RAG from First Principles* (Packt) | 492 | ANN index internals (Flat/IVF/quantization/graph/hashing), sparse-vs-dense and BM25, BGE-M3 hybrid, chunk-size-vs-accuracy, embedding fine-tuning |
| Polzer, *RAG with Python Cookbook* (O'Reilly) | 378 | Recipe index for `build-ai-examples`: agentic chunking, embedding hypothetical questions, metadata filtering, Ollama, Pydantic structured outputs, multimodal parsing |
| Dhyani, *RAG with Python Cookbook* (BPB) | 485 | Chunking-strategy spread (see the rule above). **Practitioner technique, not an academic source** — verify each against LangChain/LlamaIndex docs before writing |

Caveats worth not re-deriving: Jia Huang's TOC shows translation artifacts ("Connect learner with
LlamaHub", stray "Wukong title" headings) — treat the prose as roughly edited and verify any
mechanism claim against a primary source. **The Polzer epub is an Early Release superseded by the
PDF** — one source, use the PDF.

**Tier B, marginal, no round assigned:** 汪鹏/谷清水/卞龙鹏, 大模型RAG实战 (247 pp, Chinese).
Sound structure; **RAG paradigm evolution** and **joint retriever/generator training** are the two
things the English books cover least. But the plugin's references are English and everything else
is better covered elsewhere. Fallback for round 8's paradigm framing only.

**Rejected — do not re-mine:**

- **Aki D, *LLM, Transformer, RAG AI*** (self-published, no publisher, no bibliography) — fails
  the *new* rule too: the TOC has no recipe or technique anywhere, only conceptual chapter names
  ("Choosing the Right Framework", "Handling Ethical and Bias Considerations"). An "FAQ" chapter
  sits second. Its "popular LLMs" roster is already stale (GPT-3/BERT/T5/XLNet/RoBERTa/Llama 2).
  `explain-llm-internals` covers transformers from primary papers (round 4).
- **Rubin, *Search Engines and RAG in AI*** (self-published, ~400 KB of text across 10 chapters) —
  generic chapter names with no technique or code detail; far too thin per topic.
- **"Utilizing Vector Databases to Enhance RAG Models (Fragment)"** — 42 pp, author "unknown",
  TOC entries are meaningless serial numbers (10870–10911). **Unattributable; cannot be cited.**
- **Sivabalaselvamani & Revathy et al., *Advanced AI and Data Science Applications*** (329 pp,
  20 chapters) — applied-domain ML case studies (IPL cricket, CRISPR, skin disease, rainfall
  XGBoost, fraud detection). No GenAI-engineering methodology. Wrong plugin.
- **Streamlit Essentials** — already triaged 2026-07-20; that verdict stands, not re-evaluated.

All twelve book files carry libgen/z-lib markers in their filenames. Recorded factually, per
step 5 of the book procedure.

### Decision: no 9th skill

The user explicitly allowed one and it is still not warranted. GraphRAG is a *retrieval
architecture* and `design-agent-architecture` already owns RAG — a separate skill would split one
decision ("how should this system retrieve?") across two discovery surfaces. Agent-driven
annotation has a better home than its own skill: `evaluation.md:13` demands "labeled
question→passage pairs" and `evaluation.md:17` tells the reader to build an eval set, while the
plugin nowhere says how to produce labels at scale — the article answers exactly that, *inside*
`evaluate-optimize-models`. A 9th skill would also cost ~340 bytes of the 1,072-byte
`gpt_instructions.md` headroom plus a full wiring set, and 12 of 27 references are still 37–63
lines, which is the better place for the effort.

### Gaps this batch closes (verified by grep, not from memory)

1. **GraphRAG: zero hits** across the whole plugin for
   `graphrag|knowledge graph|cypher|neo4j|community detection|multi-hop`. Total absence.
2. **ANN index internals: two hits, neither substantive** — and one of them is
   `build-ai-examples/references/rag-example.md:148`, *"The example's query does an exact scan.
   Add an HNSW or IVFFlat index…"*. The plugin flagged this gap against itself and never filled
   it; `memory-vector-db.md`, which owns vector stores, never explains what the approximation in
   "approximate nearest neighbour" is or how to tune it.
3. **Eval-set construction: metrics exist, label production does not.**
4. **Chunking strategy: one paragraph** (`memory-vector-db.md:43-45` — "split on semantic units,
   not fixed characters", and nothing else).
5. Maker-checker **is** already covered (`loop-engineering.md:113`, `architectures.md:81`). The
   article is a citation for it, not new content — **do not rewrite those sections.**

### Roadmap for rounds 8–10 (fixed this round)

- **Round 8 — GraphRAG.** New `design-agent-architecture/references/graph-rag.md` (~180–240
  lines). Lead with the decision rule: vector top-k **structurally** cannot answer global or
  aggregative questions ("what are the main themes in this corpus?") or multi-hop ones — no amount
  of reranking fixes a question whose answer requires the whole corpus. Then KG construction with
  LLMs (**entity resolution is the hard part**, not extraction); Microsoft GraphRAG indexing and
  its global (map-reduce over community summaries) vs local (entity-anchored) query modes;
  text2cypher as the general NL→query-language pattern; a cost-honesty section (an LLM pass per
  chunk plus summarization per community) with a decision table that says when it is *not* worth
  it; the agentic-RAG router cross-referenced to `architectures.md`, not restated. **Verify Edge
  et al., <https://arxiv.org/abs/2404.16130> before writing** — Bratanic & Hane is the map, the
  paper is what gets cited. Wiring: a row in `rag-pipeline.md`'s "what RAG fixes" table, expand
  the one-line graph row in `memory-vector-db.md`, SKILL.md Довідки, router rows, README tree.
  **No `gpt_instructions.md` bytes** — a new reference rides into the zip free.
- **Round 9 — retrieval substrate depth.** `memory-vector-db.md` 123 → ~220–260 in two parts:
  (a) ANN index families (Flat/IVF/HNSW/PQ/LSH) against the recall–latency–memory triangle,
  build-time knobs (`m`, `nlist`) vs per-query knobs (`ef_search`, `nprobe`), what pgvector
  exposes, sparse vs dense and why BM25 still wins on rare identifiers, RRF — verify HNSW against
  Malkov & Yashunin <https://arxiv.org/abs/1603.09320>, not the books; (b) chunking strategies
  from Dhyani as practitioner technique, cross-referenced to `rag-pipeline.md`'s "Split" (which
  already points here) rather than duplicated. Then decide whether to close `rag-example.md:148`
  by adding the index to `ingest.py` — **if yes, round 6's discipline binds: re-run the live path.**
- **Round 10 — production RAG + eval-set construction.** `rag-pipeline.md` += hallucination
  detection *and correction*, guardrails and prompt injection on the retrieval surface, index
  freshness at scale. `evaluation.md` 42 → ~90–120 += how to produce the labels its own metrics
  demand (single → dual → ensemble → HITL ladder, the confirmation-bias caveat, and the honest
  rule that a machine-labelled eval set needs a human-verified subsample or it measures the
  labeller). `loop-engineering.md` maker-checker += one sentence and the Karim citation.

### Verification actually run

`python tests/check_docs.py` · `python tests/smoke_test.py` · from repo root: `npm run lint`,
`lint:markdown`, `lint:format`. **Not run:** `build:catalog`, `evals`, `site build`,
`build_gpt_package.ps1` — no SKILL.md description, skill roster or reference count changed this
round (still 8 skills / 27 references), so the catalog and zip surfaces did not move.

## What happened before (round 6 — post-merge accuracy pass + RAG DB verified live, 2026-07-20, branch `docs/ai-gen-post-merge-accuracy` off `main`)

Two unrelated threads the user asked about in the same breath: whether `CLAUDE.md` → memory →
this file were still accurate after the merge, and what to do about the RAG example's
never-actually-run live path. Both turned out to have real content, not just bookkeeping.

### Docs were stale in a specific, checkable way

**PR #10 merged into `main` as `e3894cd`** (squash-merge; tree identical to the pre-merge
squashed commit `c7a7413` on `feat/gen` — confirmed with `git diff`, not assumed). Local `main`
was behind by one commit and was fast-forwarded. Found stale by reading, not by a check (none of
this is covered by `tests/check_docs.py`):

- This file's own "Open threads" section still said *"the fixed roadmap (rounds 1–4) is
  COMPLETE, there is no round 5 defined"* — three lines below a header that said round 5 had
  already shipped. Also said 26 references where round 5's own entry already said 27.
- `enabledPlugins` guidance across three spots in this file (and in the
  `marketplace-autoupdate-and-global-enable` memory) was written from the pre-merge world, where
  enabling early would load the stale 6-skill scaffold from the installed plugin cache. That
  blocker is gone now that `main` has the content — checked directly: the cache at
  `~/.claude/plugins/marketplaces/fk-dev-digest-marketplace` was still on `64d772c` (6-skill
  `ai-gen`) as of this round, because `autoUpdate` refreshes on its own schedule, not the instant
  a merge lands. That lag is the one real remaining wrinkle, not the merge itself.
- `CLAUDE.md` still called the plugin "a v0.x scaffold by design" — undersold 8 skills.

All fixed in place; see `git log` on this branch for the exact diffs rather than restating them
here.

### The RAG example's database layer is now genuinely verified, and it found three bugs

The honest state before this round: `smoke_test.py` never touches a database (offline by
design), so nothing had ever executed `ingest.py`'s DDL or `agent.py`'s ranking query against
real Postgres. "Nobody has run it end to end" was sitting in this file as an acknowledged gap,
not a resolved one.

Checked what was actually possible without the user's involvement: **Docker was installed but
not running** (daemon started this round); **Ollama was not installed at all** (no binary, no
service on :11434); the OpenRouter key is the user's credential and spending against it, however
small, is not this session's call. So the embedding and chat calls stay manual-verification —
but the whole Postgres/pgvector layer, which needs neither, was fully testable right now.

Brought up the real `docker-compose.yml`, reset to a **genuinely fresh** database each time (no
half-credit from a previous attempt), and imported the actual `EXTENSION`/`build_schema()`
constants from `ingest.py` and mirrored `agent.py`'s exact `<=>` query — not a reimplementation,
the real code. Three real bugs surfaced, in order, each only visible against a real server:

1. **`register_vector(conn)` before `CREATE EXTENSION IF NOT EXISTS vector`** in both
   `ingest.py` and `agent.py`. Crashes on literally the first run against a fresh database —
   `psycopg.ProgrammingError: vector type not found in the database`. This is the golden-path
   failure: exactly what a user following the Quickstart hits on step one.
2. **`vector(%(dim)s)` as a bound query parameter inside `CREATE TABLE`** — Postgres rejects a
   server-side parameter as a DDL type modifier (`type modifiers must be simple constants or
   identifiers`). `ingest.py` now has `build_schema(dim: int) -> str`, which validates `dim` is a
   positive int and formats it directly into the DDL text.
3. **A raw Python list sent as the `<=>` query vector** in `agent.py`'s `search_docs` —
   `operator does not exist: vector <=> double precision[]`. An `INSERT` can infer `vector` from
   the target column; a bare comparison has no column to infer from, so psycopg's default list
   adapter wins and sends a plain array. Fixed by wrapping with `pgvector.Vector(...)` before
   binding — `from pgvector import Vector`, added to `agent.py`'s imports.

All three fixed, then **re-verified end to end against a fourth fresh database** with all three
fixes applied together: schema, insert, upsert-on-reingest, the exact ranking query (correct
chunk ranked first), and model-ID index versioning — 5/5 checks, real container, real query
plumbing. Container and volume torn down afterward (`docker compose down -v`); nothing left
running. Full detail, including *why* the INSERT path didn't need the `Vector()` wrapper but the
query did (column-type inference exists for one, not the other) — see the round-6 section of
`references/rag-example.md`.

**What remained unverified at that point:** Ollama (needs installing) and the OpenRouter chat
call (needs the user's key; spending against it needs the user's say-so). Both were manual
verification, not CI. **This gap closed later the same session** — see the next section.

### Postscript: the full live path is now verified too — Ollama installed, real OpenRouter call made, and a 4th real bug found

Same session, continued after the database-layer work above. The user asked how to install
Ollama on a non-`C:` drive (F:), then filled in a real `OPENROUTER_API_KEY`, then asked to
proceed. All of it done for real, not simulated:

- **Ollama installed to `F:\Ollama`**, models to `F:\Ollama\models`
  (`OllamaSetup.exe /DIR="F:\Ollama"`, then `setx OLLAMA_MODELS "F:\Ollama\models"`). Verified
  by byte count on disk, not by trusting the installer's exit code.
- **A real environment-inheritance trap, specific to this agent-tool's process ancestry, not to
  Windows or Ollama in general:** the first `ollama pull` landed 274MB on
  `C:\Users\felko\.ollama\models` instead of `F:\Ollama\models`, even though the registry held
  the correct value and the Ollama processes started *after* `setx` ran. Diagnosis:
  `$env:OLLAMA_MODELS` inside a freshly-spawned PowerShell process in this session was **empty**
  — every process this tool spawns inherits environment from a parent that predates the `setx`
  call, so no amount of "open a new terminal" *within this session* would have picked it up.
  Worked around by exporting `$env:OLLAMA_MODELS` explicitly in the same process that launched
  `ollama.exe serve`, which bypasses inheritance entirely. **This is not expected to affect the
  user's own normal terminals** (opened via Start Menu/Explorer, which do get the broadcast) —
  confirmed separately when the user later started Ollama themselves and it worked correctly.
- Re-pulled with the fix; confirmed via **isolated, single-purpose checks** (one command per
  path, not a combined script whose output could be misread) that `F:\Ollama\models` held the
  274MB and `C:\Users\felko\.ollama\models` did not gain anything new. Tested the actual
  `/v1/embeddings` endpoint with a real request — got a real 768-dimension vector back,
  `"model":"nomic-embed-text"`. The stray `C:\Users\felko\.ollama\models` duplicate was deleted
  on request; `id_ed25519`/`id_ed25519.pub` (Ollama's own identity keypair, unrelated to model
  storage) were left alone since they were never part of what was flagged.
- **Bug #4, found only by running the actual documented Quickstart:** `cp .env.example .env`
  does nothing on its own — `settings.py` reads `os.environ` directly and nothing loaded `.env`
  into it. `ingest.py` crashed with `RuntimeError: OPENROUTER_API_KEY is not set` even with a
  correctly filled-in `.env` sitting right next to it. Fixed by adding `python-dotenv` to
  `requirements.txt` and calling `load_dotenv(pathlib.Path(__file__).parent / ".env")` in
  `ingest.py` and `agent.py` — **not** in `settings.py`, which stays stdlib-only on purpose (the
  smoke-test invariant from round 2 still holds; check it before adding any import there).
- **Full real run, no stubs anywhere:** a 2-paragraph synthetic `handbook.md` corpus (refunds,
  shipping, warranty, account issues — clearly fictional, not user data) through `ingest.py`
  (real Ollama embeddings, real Postgres write) — "2 chunks to embed", "stored 2 chunks". Then
  `python agent.py "What is the refund policy?"` — real retrieval, real OpenRouter call,
  correct grounded answer citing `[handbook.md#0]`. This is the first time any part of this
  example ran against a real LLM.
- **One non-blocking finding to track:** `langgraph.prebuilt.create_react_agent` (what
  `agent.py` uses) printed a deprecation warning — moved to `langchain.agents.create_agent` in
  LangGraph V1.0, planned removal in V2.0. Not fixed this round: swapping it without re-running
  the live verification would be exactly the kind of unverified change this whole session argues
  against. `rag-example.md` now documents this as a known future-breakage risk with the
  migration pointer.
- **Where the OpenRouter key goes, now documented in three places** (the user asked
  specifically): `rag-example.md` (get the key at openrouter.ai, top up a balance, paste into
  `.env` yourself), the plugin `README.md` (a short pointer section), and this plugin's
  `CLAUDE.md` (a rule for future sessions: never ask for the key in chat, never write one into a
  file yourself, `settings.py` stays stdlib-only).
- Cleaned up afterward: Postgres container + volume torn down, temp corpus and venv were in the
  session scratchpad (not the repo), nothing left running that wasn't there before.

### Verification actually run (all green)

`python tests/check_docs.py` (7/7, 27 references, 8 SKILL.md — unaffected by the code fix since
it doesn't inspect Python semantics) · `python tests/smoke_test.py` (14/14 — unaffected for the
same reason: it never imports `ingest.py`/`agent.py`) · `python -m py_compile ingest.py agent.py`
· from repo root: `npm run lint`, `lint:markdown`, `lint:format`.

**Not run this round:** `build:catalog`, `evals eval:quality`, `site build` — no skill/reference
content changed, only `scripts/rag_example/*.py` and doc accuracy; those three gates cover
catalog/skill surface, which did not move. Run them anyway before merging if pulling this branch
forward, since running them is cheap and "should be a no-op" is not the same as "verified a
no-op" — this round's whole point.

### Round-6 facts worth not re-deriving

- **pgvector-python 0.5.0's `register_vector()` needs the extension to exist first, full stop —
  there is no defensive order that avoids this.** Any future `scripts/*/ingest.py`-shaped code in
  this plugin that touches pgvector should create the extension before registering.
- **`INSERT` and comparison/`ORDER BY` parameters are not the same trust level for type
  inference in psycopg + pgvector.** A raw list works when Postgres can infer the type from a
  target column; it does not when there is no column to infer from. Wrap explicitly with
  `pgvector.Vector(...)` for anything that isn't a plain column-typed insert.
- **Docker Desktop killed a container it had just started**, mid-session, while a slow `pip
  install` ran in another shell — a cold-start backend restart, not user action. The container
  and its named volume survived (`docker compose up -d` again just restarted the same one, same
  data). Don't assume a container that answered `pg_isready` a few minutes ago still is — a
  fresh `docker compose ps` before trusting a connection costs nothing.

## What happened before (round 5 — reasoning models, 2026-07-20, branch `feat/gen`)

First round **outside** the round-0 roadmap. The user chose to place the Cameron Wolfe source
that their own triage section (below) had accepted but left unplaced.

- **New `explain-llm-internals/references/reasoning-models.md`** — long CoT and variable
  thinking compute; **RLVR** and why verifiability (not preference modelling) is the point;
  GRPO; DeepSeek-R1-Zero vs R1 and the four-stage pipeline; distillation of reasoning;
  inference-time scaling as two distinct levers; and a decision table for when a reasoning model
  is *not* worth it. 27 references now.
- **Wiring:** SKILL.md Довідки + a row in its request table, router row, README tree line, and a
  cross-ref from `prompt-techniques.md` where CoT already warned that reasoning models do this
  internally. **No instruction bytes spent** — still 6,928 (headroom 1,072), because a new
  reference rides into the zip free. Zip 110,592 → 114,730.

### Postscript: squashed and merged (2026-07-20, same day)

The user asked to squash the branch and push, and merged the PR themselves. The seven working
commits (round 0 → round 5) became **one commit** on `feat/gen`
(`c7a7413`), verified identical in tree content to the pre-squash state (`git diff` against a
local-only safety tag `pre-squash-feat-gen` was empty) before force-pushing with
`--force-with-lease`. GitHub's squash-merge then created `e3894cd` on `main` — same tree again,
confirmed the same way.

**`main` is now current**: `plugins/ai-gen` on `main` has all 8 skills and 27 references. Local
`main` in this working copy was fast-forwarded to match. `feat/gen` still exists, pointing at the
same content as `main` — safe to delete once you're confident nothing else is pending on it; this
session did not delete it, only merges/deletes on request.

**What this changes for the two open questions below:** `enabledPlugins` is no longer blocked by
"would load a stale scaffold" — that was true only pre-merge. The **installed plugin cache**
(`~/.claude/plugins/marketplaces/fk-dev-digest-marketplace`) is still separate from this and was
checked directly: as of this session it is still on an old commit (`64d772c`) with the 6-skill
`ai-gen`, because `autoUpdate` refreshes on its own schedule, not the instant a merge lands. If
you enable now, don't be surprised if the 7th/8th skill don't appear immediately — that is the
cache lagging, not a wiring bug; it should catch up on its own refresh cycle, or force it by
reinstalling.

### Attribution corrected against the primary sources

The Wolfe post is a good secondary source (free, full text, ~22 citations) and was used as a
*map*, per the standing rule. Two things worth recording:

- **RLVR is introduced and named by Tülu 3** (Lambert et al., AI2, 2024,
  <https://arxiv.org/abs/2411.15124> — "a novel method we call Reinforcement Learning with
  Verifiable Rewards"), **not** by the DeepSeek work that popularized it. The reference says so
  explicitly, because the misattribution is common.
- **GRPO is from DeepSeekMath** (Shao et al., 2024, <https://arxiv.org/abs/2402.03300>). Its
  abstract confirms only "a variant of PPO ... optimizing the memory usage of PPO". The
  mechanism everyone quotes — group-sampled baseline instead of a value network — is in the
  paper *body*, and the file says to verify there rather than repeating it as abstract-verified.
- DeepSeek-R1 (<https://arxiv.org/abs/2501.12948>, Nature 2025): pure RL "obviating the need for
  human-labeled reasoning trajectories", emergent self-reflection/verification, and distillation
  into smaller dense models — all confirmed from the abstract.

**Benchmark percentages were deliberately omitted**, including the AIME numbers the Wolfe post
quotes. They are real and cited there, but the plugin's standing rule is not to carry benchmark
scores; the file says where to read them instead. This is the same call made for MTEB in round 2.

## What this project is

`ai-gen` is a plugin in the `fk-dev-digest-marketplace` monorepo: a senior-developer/mentor
agent with 8 linked skills for generative-AI engineering. Structure mirrors the neighboring
`eda-skills` plugin (Ukrainian SKILL.md bodies + English frontmatter, English `references/`,
per-skill `agents/openai.yaml`, a `chatgpt/` Custom-GPT packaging pipeline), plus one thing
eda-skills does not have: a plugin-level Claude Code agent, `agents/ai-gen-mentor.md`.

Skills: `plan-ai-solution` (orchestrator with task-to-model-class routing, the skill router and
the session-handoff protocol), `select-genai-models`, `engineer-prompt-context`,
`design-agent-architecture`, `explain-llm-internals`, `deploy-ai-environments`,
`evaluate-optimize-models`, `build-ai-examples`. **The roadmap's eight skills are complete** —
anything further is round 5+ and needs new material.

## Current verified state (as of this handoff)

- Plugin registered in `.claude-plugin/marketplace.json` and quarantined (Cyrillic content) in
  `scripts/validate-marketplace.mjs` → `QUARANTINED_PLUGINS`.
- `npm run lint` (validate-marketplace), `npm run lint:markdown`, and `npm run lint:format`
  pass from the repo root; `npm run build:catalog` regenerates `dist/index.json` +
  `site/public/catalog.json` with ai-gen included (8 skills, 1 agent; 61 skills repo-wide).
- `chatgpt/build_gpt_package.ps1` builds `dist/ai_gen_knowledge.zip` and reports the
  `gpt_instructions.md` UTF-8 **byte** count against the 8000-byte budget (same byte-not-chars
  trap as eda-skills: Cyrillic is 2 bytes/letter).
- **2026-07-19:** the script gained a `skillsRoot` fallback (checks `skills/` exists before
  building paths from it, falls back to the plugin root otherwise) — the same fix applied to
  `eda-skills`, `agent-database`, and `agent-ml-interviewer` after a cross-plugin audit found
  their build scripts assumed skills lived at the plugin root, a pre-migration layout none of
  the four still use. This plugin's own layout was already correct (skills always under
  `skills/`), so the fallback here is precautionary, not a fix for an observed failure.
- Version is `0.0.1` and **no release tag exists** — deliberately unreleased (not because the
  plugin is thin: it has 8 skills and 27 references; the user simply has not asked for a tag);
  `scripts/release.mjs` gates only its own plugin directory, so other plugins' releases are
  unaffected.

## What happened before (round 4 — the 8th skill `explain-llm-internals` + Agent Ops, 2026-07-20, branch `feat/gen`)

**The fixed roadmap from round 0 is now complete.** Eight skills, 26 references, two test guards.

### Shipped

- **New skill `skills/explain-llm-internals/`** — the "why" layer, with `SKILL.md`
  (826-char description), `agents/openai.yaml`, and three references:
  - `architecture-training.md` — tokenization/BPE and its practical consequences (letter
    counting, token-per-language cost, rare-string fragmentation), embeddings and the
    transformer block, quadratic attention as the *architectural* root of the context budget,
    pretraining as plausibility-not-truth, the Chinchilla scaling correction, post-training
    (SFT → RLHF → DPO), and how to read benchmark claims.
  - `inference-internals.md` — prefill vs decode as two opposite workloads, the KV cache as the
    real capacity limit, PagedAttention, continuous batching, FlashAttention, speculative
    decoding, GQA/MQA, MoE, quantization; closing table of **what each technique trades**.
  - `fine-tuning-mechanics.md` — LoRA, QLoRA, dataset shape and chat templates, the training
    loop, three adapter-serving shapes, and the failure modes.
- **New `evaluate-optimize-models/references/agent-ops.md`** — why deterministic testing does
  not transfer, business KPIs plus this plugin's two (cost per *solved* task, p95) and a third
  for agents (steps-to-success), trajectory tracing, sampled online judging, metrics-gated
  deploys, the incident→eval-case loop, defense-in-depth security, agent identity, A2A caution,
  and a "minimum viable Agent Ops" list of five things to do first.

### Design decision: internals is not a stage

`explain-llm-internals` is deliberately **not** numbered in the router's stage table. It is a
cross-cutting layer pulled in from any stage when the mechanism changes the decision. The router,
`gpt_instructions.md` and the skill's own SKILL.md all say this, and all three add the same
guard: an internals explanation must never substitute for the measurement the stage still owes.

### The guard found a bug in itself

Wiring produced `explain-llm-internals/SKILL.md links references/agent-ops.md which is not on
disk` — a **false positive**. The same-skill link regex `references/([a-z0-9-]+\.md)` also
matched the tail of a *cross-skill* path (`evaluate-optimize-models/references/agent-ops.md`).
Fixed with a `(?<!/)` lookbehind. Note the pattern across rounds: check 7 needed two corrections
in round 2, check 3 needed one here — **each was found by running the check against real
content, never by reading it.** Write the check, then feed it something new.

### Byte budget after the full roadmap

`gpt_instructions.md`: 6,586 → **6,928 bytes** (headroom 1,072). Skill #8 cost 342 bytes, in
line with #7's 334. Final tally: the round-1 compaction freed ~1,000 bytes and the two new
skills consumed ~680 of them, so the roadmap completed **without a second compaction pass** —
which is what round 1 was betting on. Zip grew 58,397 → **110,592 bytes** across rounds 1–4.

### Sources verified this round (nine papers + the whitepaper)

Nothing written from memory. Chinchilla (arXiv 2203.15556 — equal scaling of parameters and
tokens; models of that era "significantly undertrained"; Chinchilla 70B vs Gopher 280B at equal
compute), InstructGPT (2203.02155 — the three-step pipeline, and **1.3B preferred over 175B**),
DPO (2305.18290 — no reward model, no RL sampling), FlashAttention (2205.14135 — **exact**, IO-
aware; its block-sparse extension is the approximate one, kept separate in the text),
PagedAttention (2309.06180 — OS paging analogy, 2–4× throughput), speculative decoding
(2211.17192 — **distribution preserved**, 2–3×), GQA (2305.13245), LoRA (2106.09685 — 10,000×
fewer trainable parameters, **no added inference latency**), QLoRA (2305.14314 — NF4, double
quantization, paged optimizers; 65B on one 48GB GPU). Agent Ops, security and A2A material read
from the Google whitepaper text directly.

**One source moved:** the **OpenTelemetry GenAI semantic conventions are no longer at the
`opentelemetry.io/docs/specs/semconv/gen-ai/` page** — it is now a redirect notice pointing to
<https://github.com/open-telemetry/semantic-conventions-genai>. `agent-ops.md` cites the repo and
explicitly tells the reader to treat attribute names as a moving target rather than a stable
contract, because stability status could not be confirmed.

### Deliberately not done

The Cameron Wolfe "Demystifying Reasoning Models" source, triaged and accepted in the user's own
HANDOFF section below, **remains unplaced**. That section reserves round/file placement for the
user personally; asked at the start of this round and no answer came, so round 4 ran strictly to
the roadmap. Reasoning models are still uncovered by the plugin — the obvious home is a fourth
reference under `explain-llm-internals`, and the byte budget has room.

### Verification actually run (all green)

`build_gpt_package.ps1` (6,928 bytes, zip 110,592) · `check_docs.py` (7/7, **8 SKILL.md,
26 references**) · `smoke_test.py` (14/14) · from repo root: `npm run lint` (8 plugins,
0 warnings), `lint:plugins`, `lint:markdown` (397 files, 0 errors), `lint:format`,
`build:catalog` (**61 skills**) · `evals`: `eval:quality` (61 skills, 0 failures) ·
`site`: `npm run build`. Frontmatter re-parsed with PyYAML (8/8, name == dir, no `": "` trap).
Stray-codepoint scan over all SKILL.md + references returned 0 (round 3 caught a CJK character
this way; it is now a standing pre-commit check on this box).

## What happened before (round 3 — the 7th skill `engineer-prompt-context`, 2026-07-20, branch `feat/gen`)

The skill count changed for the first time since the scaffold: **6 → 7**. Everything the roadmap
warned would be expensive about this round was cheap, because round 1 pre-paid it.

### Shipped

- **New skill `skills/engineer-prompt-context/`** — full kit: `SKILL.md` (Ukrainian body,
  English frontmatter, 816-char description), `agents/openai.yaml`, and two references.
- **`references/prompt-techniques.md`** (~150 lines) — prompt-as-document framing; prompt
  anatomy (introduction → context → refocus/sandwich); the two position effects and the
  **Valley of Meh**; techniques ordered by cost (zero-shot+schema, few-shot, CoT,
  self-consistency, least-to-most, ToT, persona) each with buys/costs/fails; and the assembly
  mechanics most guides skip — **position vs importance vs dependency**, **elastic snippets**,
  **token inertness**, and prompt assembly as a constrained optimization.
- **`references/context-engineering.md`** (~120 lines) — PE-vs-CE table; the attention budget
  and context rot; compaction / structured note-taking / sub-agent isolation; just-in-time
  retrieval; tool schemas as context; a working procedure and failure modes. Cross-refs to the
  memory/loop/RAG references instead of restating them.

### Wiring (nine places, four of them caught by the guard)

`tests/check_docs.py` check 2 listed exactly what was missing the moment the skill directory
appeared: build script `$skills`, mentor agent, README tree, router. That is the check earning
its build cost — it turned "remember five files" into a checklist the machine produces.

Also wired by hand (**not** covered by the twins check): `gpt_instructions.md` stage chain,
`plan-ai-solution/SKILL.md` orchestration table + default order, `skill-router.md` stage table
and three routing rows, `build-vs-use.md` rung-0 cross-ref, `README.md` trigger phrases.

**Stage order decision:** prompt/context is stage **3**, before architecture. A prompt defect
misdiagnosed as an architecture problem produces an agent nobody needed; the router and both
SKILL.md files now say so explicitly.

### Byte budget: the round-1 compaction paid off exactly as intended

`gpt_instructions.md` went **6,252 → 6,586 bytes** (headroom 1,748 → 1,414). Adding a whole
skill cost **334 bytes** and needed no compaction pass — the roadmap had listed one as a
precondition for this round and for round 4. Round 4's 8th skill has ~1,400 bytes of room, so it
will not need one either.

### Stale docs found by hand (the gap the twins check does not cover)

`chatgpt/README.md` still routed edits to a section called **«Шість етапів»**, which round 1 had
renamed to «Етапи», and its "new 7th skill" row described a procedure that no longer matched.
Both fixed: the row now lists all five places a new skill must be added and names
`check_docs.py` check 2 as the thing that enforces it, plus a note that routing detail belongs
in the router, not the instruction. **This file is still outside the automated check** — the
marketplace catalog is regenerated so it self-heals, but `chatgpt/README.md` must be read by
hand whenever the skill roster or the instruction's section names change.

### Sources verified this round (all four papers + the book)

Nothing was written from memory. Verified before use: Wei et al. 2022 (arXiv 2201.11903, CoT —
including the *emergence with scale* caveat, which is why the reference tells you not to assume
CoT rescues a small model), Wang et al. 2022 (arXiv 2203.11171, self-consistency — the abstract
does **not** discuss cost, so the N× multiplier is flagged as the practical constraint the paper
omits), Zhou et al. 2022 (arXiv 2205.10625, least-to-most — the specific weakness it targets is
easy-to-hard generalization), Yao et al. 2023 (arXiv 2305.10601, ToT — the abstract states no
cost implication; "rarely justified in application work" is marked as this plugin's judgment,
not the paper's).

Berryman & Ziegler, *Prompt Engineering for LLMs* (O'Reilly, 2024) is the backbone, and it is
**not** where round 0 said the books live: the actual path is
`F:\Data\Lenovo\Документы\AI_courses\BigData_Course\Books\LLM\` (round 0 wrote
`...\AI_courses\`, which only holds `AI_agent_prompts\`). Raschka, Godoy, Huyen, Labonne and
Alammar are all in that same `BigData_Course\Books\LLM\` folder — **round 4 will need it**.
Pages were read directly (PyMuPDF) rather than summarized from the table of contents; the
distinctive material — Valley of Meh, refocus/sandwich, inertness, elastic snippets,
position/importance/dependency — is quoted accurately because of that.

### Verification actually run (all green)

`build_gpt_package.ps1` (6,586 bytes, zip 90,344) · `check_docs.py` (7/7, 22 references,
7 SKILL.md) · `smoke_test.py` (14/14) · from repo root: `npm run lint` (8 plugins, 0 warnings),
`lint:plugins`, `lint:markdown` (392 files, 0 errors), `lint:format`, `build:catalog`
(**60 skills**, up from 59) · `evals`: `eval:quality` (60 skills, 0 failures — the new skill is
picked up with the same standard "no eval file" WARN every skill in the repo carries) ·
`site`: `npm run build`. Frontmatter re-parsed with PyYAML (7/7, name == dir, no `": "` trap).

One self-inflicted bug caught before commit: a stray CJK character typed into
`context-engineering.md`. A scan for codepoints above U+2E7F across the new references now
returns 0 — worth re-running when writing long English references on this box.

## What happened before (round 2 — RAG depth, runnable example, offline smoke test, 2026-07-20, branch `feat/gen`)

Round 2 of the roadmap, stacked on the still-open PR #10 (round 1 was not merged first — the
branch carries both rounds).

### Shipped

- **New `design-agent-architecture/references/rag-pipeline.md`** (~200 lines) — RAG as *two*
  pipelines (offline ingestion, online serving), each stage with its failure mode and
  counter-measure; a "what RAG fixes / does not fix" table whose last row is "corpus fits in the
  window → skip the pipeline"; the embedding-model choice as a **filter procedure** over MTEB
  rather than a ranking to copy; advanced retrieval (cross-encoder rerank, RankGPT-style LLM
  rerank, multi-query, contextual compression, HyDE) each with buys/costs/fails; and an
  "order of work when RAG underperforms" table keyed on measurements.
- **New `build-ai-examples/references/rag-example.md`** (~130 lines) + runnable code in
  **`build-ai-examples/scripts/rag_example/`**: `chunking.py`, `retrieval.py`, `settings.py`
  (pure, stdlib-only), `ingest.py`, `agent.py` (framework), `docker-compose.yml`,
  `.env.example`, `requirements.txt`. The build script already stages `scripts/`, so it rides
  into the knowledge zip with no script change (zip 58,397 → 78,081 bytes).
- **New `tests/smoke_test.py`** — **14 checks, fully offline**: no network, no keys, no
  Postgres, and no langchain/langgraph installed.
- **`tests/check_docs.py` gained check 7** — a smoke-check-count claim in prose must match
  `@check` reality. This is the eda-skills lesson (its README advertised a stale
  "30/30 перевірок" for ~14 rounds) applied pre-emptively, because `rag-example.md` states
  "14 checks" in prose. The check needed **two corrections of its own**, both found by running
  it: matching anywhere on a line made a sentence naming both test files report the
  `check_docs` count as a smoke claim (false positive), and excluding `.` from the search window
  meant `smoke_test.py (14 checks)` never matched at all — silently skipping HANDOFF.md, the
  file most likely to go stale. It now requires the number to follow "smoke" within 30
  characters, dots allowed: 3 prose claims covered, verified by breaking one in each file.
- **Wiring:** both SKILL.md Довідки + two new mandatory rules in `build-ai-examples`
  (don't attribute undocumented provider capabilities; separate pure logic from framework);
  `build-vs-use.md` rung-2 now points at `rag-pipeline.md` and names the cheaper rung below it;
  `stack-langgraph-openrouter.md` gained an "Adding RAG to this scaffold" section; the router
  gained three RAG rows.

### The claim that died this round (a design constraint, not a doc fix)

The roadmap said "ingest + retrieve on pgvector/LangGraph" with OpenRouter as *the* model
provider. **OpenRouter's API reference documents chat completions and does not document a
`/v1/embeddings` endpoint** — verified before writing the code, not after. An example built on
the roadmap's wording would not have run.

Resolution, and the reason it is worth keeping: chat and embeddings are now **separate
providers** in `settings.py` — OpenRouter for generation, any OpenAI-compatible embeddings
endpoint for retrieval, defaulting to a **local Ollama**. That needs one paid key instead of
two and keeps the corpus on the host. `build-ai-examples/SKILL.md` gained a standing rule out of
it: do not attribute to a provider a capability it does not document; check the current API
reference. If a future round wants to revisit, re-verify first — provider surfaces change.

### Why the example is split into "pure" and "framework" modules

`chunking.py` / `retrieval.py` / `settings.py` import **only** the standard library; everything
third-party lives in `ingest.py` / `agent.py`. That is what makes a genuinely offline smoke test
possible, and **smoke check 3 asserts the property by AST-walking the imports**, so it cannot
rot back. Worth preserving in later rounds: the interesting semantics (windowing, ranking,
config validation) should not need a database to test.

### Both guards were tested by breaking them

Same discipline as round 1. Smoke: an env var read by code but absent from `.env.example`
(caught), a `numpy` import added to `chunking.py` (caught, with the "move it to
ingest.py/agent.py" message), and an off-by-one in the splitter stride (caught by two
independent checks). check_docs: the new count guard flagged "claims 14 smoke checks;
smoke_test.py has 13". All restored clean afterwards.

### Verification actually run (all green)

`chatgpt/build_gpt_package.ps1` (6,252 bytes, zip 78,081) · `python tests/check_docs.py` (7/7,
"docs OK", 20 references) · `python tests/smoke_test.py` (14/14) · from repo root: `npm run
lint` (8 plugins, 0 warnings), `lint:plugins` (9 targets, 4 accepted), `lint:markdown`
(389 files, 0 errors), `lint:format`, `build:catalog` (59 skills) · `evals`: `eval:quality`
(59 skills, 0 failures) · `site`: `npm run build`. Frontmatter re-parsed with PyYAML (6/6,
name == dir, no `": "` trap).

Note: **`.yml` files ARE prettier-checked** (only `*.md` is prettier-ignored repo-wide), so the
new `docker-compose.yml` had to satisfy prettier — confirmed by checking that file directly, not
just by the suite passing.

### Round-2 facts worth not re-deriving

- The Tom Yeh RAG deck (`C:\Users\felko\Downloads\Intro_Rag_Blank.pdf`) is a **fill-in-the-blank
  workbook** — "generate ____ different versions" — so it is a *stage map and technique index*,
  the same status as the "Top 25" doc, never a citable explanation. Depth came from primary
  papers instead, all verified this round: Lewis et al. 2020 (arXiv 2005.11401, RAG,
  parametric + non-parametric memory), Muennighoff et al. 2022 (arXiv 2210.07316, MTEB — 8 tasks,
  58 datasets, 112 languages, **"no particular text embedding method dominates across all
  tasks"**, which is exactly why MTEB is taught as a filter), Sun et al. 2023 (arXiv 2304.09542,
  RankGPT — distilled 440M beats a 3B supervised model on BEIR), Gao et al. 2022
  (arXiv 2212.10496, HyDE — the hypothetical document is embedded, never shown to the user).
- Smoke tests and `check_docs.py` stay **local gates, not CI** (round-1 decision 2 still holds).
- `dist/` is gitignored, so the zip is never committed; `site/public/catalog.json` is tracked and
  must be committed with plugin changes.

## What happened before (round 1 — agent-architecture core, docs guard, skill router, 2026-07-20, branch `feat/gen`)

Round 1 of the roadmap, plus one unplanned item the user asked for up front: a **skill router**
that moves routing detail out of the byte-starved ChatGPT instruction and into a file.

### Shipped

- **New `skills/plan-ai-solution/references/skill-router.md`** (89 lines) — the routing map:
  stage table with the invariant that makes each stage "done", a request-signal → skill →
  entry-reference table keyed on Ukrainian phrasings, six routing rules, and named misroutes.
  Follows the eda-skills precedent (`plan-eda-dataset/references/modality-routing.md`): the map
  lives in a reference because the 8000-byte instruction cannot hold it, and it rides into the
  knowledge zip for free. Serves Claude and the Custom GPT from one source.
- **`chatgpt/gpt_instructions.md` recompacted: 7,254 → 6,252 bytes (headroom 746 → 1,748).**
  The six stage paragraphs collapsed to one arrow line plus a pointer to the router; the router
  now carries strictly more routing detail than the instruction ever did. This is the compaction
  pass the roadmap deferred to round 3/4 — done early, so skills #7 and #8 (~150–200 bytes each)
  now fit without another one. A stage-3 autonomy clause was added in the same pass.
  *First attempt went the wrong way* (7,434 bytes) because the stage detail was duplicated into
  the router instead of moved; the fix was to delete it from the instruction.
- **New `design-agent-architecture/references/loop-engineering.md`** (179 lines) — Osmani's five
  components with buys/costs/fails, external state, maker-checker as a rule, relation to
  Anthropic's evaluator-optimizer and to Google's capability levels, the risk table, when not to
  build a loop, minimum viable component sets.
- **New `design-agent-architecture/references/autonomy-contracts.md`** (161 lines) — contract vs
  gate, five-part anatomy, an emittable markdown template, six failure modes, and what to
  recommend when a task is not contract-ready.
- **Extended `architectures.md`** (61 → 174) — workflows-vs-agents preamble, the five Anthropic
  workflow patterns in house format, Google Levels 0–4 table, extended Choosing table.
- **Extended `memory-vector-db.md`** (52 → 123) — the LLM-wiki three-layer pattern with its
  ingest/query/lint operations and honest scale limit, plus a write-back/consolidation section
  tied to Anthropic's compaction / structured note-taking / sub-agent isolation.
- **New `tests/check_docs.py`** (6 checks, cp1251-safe, exit 0/1) — byte budget with a
  headroom warning, **skill-list twins across five lists** (build script, `skills/` on disk,
  mentor agent, README tree, router), two-way SKILL.md↔references link integrity plus
  cross-skill reference resolution, cited-paths-resolve-in-zip, zip contents, bytes-not-chars in
  `chatgpt/README.md`.
- **Wiring:** both SKILL.md files (Довідки, procedure step 7, a mandatory autonomy rule,
  frontmatter descriptions), `agents/ai-gen-mentor.md` (router pointer, new principle 4,
  expanded architecture bullet), `README.md` (router paragraph, tree line).

### Claims that died on verification (do not re-mine)

Round 0 briefed two Osmani claims from the ASR transcripts. Both are **absent from the primary
source** (<https://addyosmani.com/blog/loop-engineering/>), verified against its actual section
list:

1. **"Outer loop vs inner loop"** — the post never uses either phrase. It distinguishes loops
   that re-run on a cadence from loops that run until a condition is met. `loop-engineering.md`
   uses that real distinction instead; the inner/outer framing was dropped, not renamed.
2. **"Osmani's 5-level adoption maturity matrix"** — does not exist. The post has *five
   components* ("The five pieces"), which round 0 conflated with five maturity levels. Nothing
   in the plugin now claims Osmani has a maturity ladder; `loop-engineering.md` instead states
   explicitly that loop engineering is **orthogonal** to Google's capability Levels 0–4, which
   is the distinction the roadmap actually wanted.

This is why `loop-engineering.md` came in at 179 lines against a 260–320 estimate: roughly
50 lines of the estimate were those two sections. The content scope is complete; the estimate
was inflated by claims that turned out not to exist. Also corrected: the component is
"**Plugins and connectors**" in the source, not "MCP connectors" — MCP is this plugin's
mechanism for that surface, and the file says so rather than putting the word in Osmani's mouth.

### Decisions taken this round

1. **Router lives in `plan-ai-solution/references/`, not in `chatgpt/`.** It rides into the zip
   with no build-script change, serves Claude too, and matches the eda-skills precedent. A
   `chatgpt/`-only file would have needed new staging logic and helped only one of two consumers.
2. **`check_docs.py` stays a local gate, not a CI step** — consistent with eda-skills, whose
   `check_docs.py` is also absent from `validate.yml`. It needs `dist/ai_gen_knowledge.zip`,
   which is gitignored and never built in CI.
3. **Byte-budget compaction pulled forward from round 3.** Cheaper now than mid-round later, and
   it removes the "requires a compaction pass" precondition from rounds 3 and 4.

### Verification actually run (all green)

`chatgpt/build_gpt_package.ps1` (6,252 bytes, zip 58,397 bytes) · `python tests/check_docs.py`
(6/6, "docs OK") · from repo root: `npm run lint` (8 plugins, 0 warnings), `npm run lint:plugins`
(9 targets, 4 accepted), `npm run lint:markdown` (387 files, 0 errors), `npm run lint:format`,
`npm run build:catalog` (59 skills) · `evals`: `npm run eval:quality` (59 skills, 0 failures) ·
`site`: `npm run build` (tsc + vite) — site-build CI triggers on `plugins/**`, so it runs on
this PR. Frontmatter re-parsed with PyYAML across all 6 skills (name==dir, no `": "` trap).

**The docs guard was itself tested by breaking things:** renaming a skill in the mentor agent
produced "never mentions skill `build-ai-examples`", and unlinking a reference from its SKILL.md
produced the orphan error; both restored clean afterwards. A guard nobody has seen fail is
decoration.

### Round-1 facts worth not re-deriving

- Instruction headroom is now **1,748 bytes**. `check_docs.py` NOTEs below 100. House rule
  stands: instruction bytes buy *procedure* only; references ride into the zip free.
- All 18 references now measure 37–179 lines. The four touched this round are in band; the
  remaining 14 are still 37–63 and are the backlog the later rounds keep chipping at.
- `site/public/catalog.json` is tracked and must be committed with plugin changes (git log
  confirms this on every prior plugin PR).
- PDF page rendering is unavailable on this box (`pdftoppm` missing), but **PyMuPDF (`fitz`) and
  `pdfplumber` are installed** — extract PDF text to a UTF-8 file in the scratchpad and Read it.
  That is how the Google whitepaper's Levels 0–4 and 5-step loop were verified.

## What happened before (round 0 — source analysis and enrichment roadmap, 2026-07-20, branch `feat/gen`)

No content was written this round. The user supplied the enrichment materials promised in the
scaffolding session; this round catalogued them, decided ownership, and fixed a roadmap.
The plan file is `~/.claude/plans/enumerated-weaving-pond.md`.

### Source inventory

Tier A — primary sources, mined directly (transcripts were the *pointer*; the linked primary
source is what gets cited, because the transcripts are machine ASR and unquotable):

- Karpathy "LLM wiki" pattern — <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
  (three layers: read-only raw sources / agent-maintained wiki / schema file; ingest workflow;
  "lint the wiki"; wiki-vs-RAG contrast; personal-scale limit). Transcript:
  `C:\Users\felko\Downloads\Karpathy's LLM Wiki - Full Beginner Setup Guide.txt`.
- Loop engineering — Addy Osmani, <https://addyosmani.com/blog/loop-engineering/> (outer vs
  inner loop; five components — automations, worktrees, skills, MCP connectors, subagents —
  plus external state; maker-checker; adoption maturity levels; risks). Transcripts:
  `Не будь оператором LLM – освой Loop Engineering с агентами.txt` and
  `Loop Engineering на практике_ автономный цикл.txt` in `C:\Users\felko\Downloads\`.
- Anthropic canon — <https://www.anthropic.com/research/building-effective-agents> (workflows
  vs agents; the five named patterns: prompt chaining, routing, parallelization,
  orchestrator-worker, evaluator-optimizer) and
  <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>.
- Google, "Introduction to Agents" whitepaper (Nov 2025, 54 pp, first of a five-part series;
  authors Blount, Gulli, Saboo, Zimmermann, Vuskovic): Model/Tools/Orchestration/Deployment
  anatomy, Think-Act-Observe loop, capability Levels 0–4, Agent Ops, A2A interop, security.
  Local: `F:\Data\Lenovo\Документы\AI_courses\AI_agent_prompts\Google Introduction to Agents.pdf`.
- Tom Yeh, "Beginner's Guide to RAG — AI by Hand" deck (45 pp, 2024; by-hand mechanics of
  load/split/embed/store, retrieval, reranking, multi-query, contextual compression, HyDE,
  MTEB as a *selection procedure*). Local: `C:\Users\felko\Downloads\Intro_Rag_Blank.pdf`.
- "Prompt engineering vs Context Engineering" (Shailesh Shakya, Aug 2025, 34 pp) — used as a
  topic map only; the depth comes from Berryman & Ziegler and the Anthropic context post.
- "Top 25 LLM System Design Interview Questions" (Hao Hoang, Nov 2025, 54 pp) — a **topic map
  with paper citations**, not itself a citable source; each item points at a primary paper.

Tier B — books, used as a citation backbone rather than ingested wholesale (all under
`F:\Data\Lenovo\Документы\AI_courses\`): Chip Huyen *AI Engineering* (2025) — planning, model
selection, evaluation, inference optimization; Huyen *Designing ML Systems* (2022) —
production/monitoring; Labonne & Iusztin *LLM Engineer's Handbook* (2024) — end-to-end
pipelines, SFT/DPO, deployment; Berryman & Ziegler *Prompt Engineering for LLMs* (2024) —
prompt construction (deepest source for skill #7); Alammar & Grootendorst *Hands-On LLMs*
(2024) — worked examples, intuition; Raschka *Build an LLM From Scratch* (2024) and *Build a
Reasoning Model* (MEAP, 2025) — internals; Godoy *Hands-On Fine-Tuning* (2024) —
QLoRA/SFTTrainer/llama.cpp; Towards AI *Building LLMs for Production*; Ozdemir *Quick Start
Guide*; Foster *Generative Deep Learning* (2023).

Also supplied: an "Agentic AI projects" catalog (~50 project blurbs, Analytics Vidhya) — kept
as an idea mine for `build-ai-examples`, not a content source.

### Decisions taken this round (user-confirmed)

1. **Prompt/context engineering becomes a 7th skill**, not a reference inside
   `design-agent-architecture`. The user chose the expensive option knowingly: a separate skill
   buys a discovery trigger for "напиши промпт"-shaped requests, and costs a full wiring set
   plus scarce `gpt_instructions.md` bytes.
2. **LLM internals becomes an 8th skill** with broad scope (architecture + training + fine-tuning
   mechanics + serving internals), not a single narrow serving reference. This deliberately
   shifts the plugin's profile from pure app-building toward mentor-grade "why" answers.
3. **RAG gets a full runnable example** (ingest + retrieve on pgvector/LangGraph), not a
   pointer section — which makes `tests/smoke_test.py` an obligation in the same round.
4. **The materials are complete.** Rounds 1–4 are fixed against this set; anything new goes to
   round 5+.

Proposed skill names, to confirm when they land: `engineer-prompt-context` (#7),
`explain-llm-internals` (#8). Both fit the schema `^[a-z0-9]+(-[a-z0-9]+)*$` and the verb-first
naming of the existing six.

### Roadmap

- **Round 1 — agent-architecture core + docs guard.** New
  `design-agent-architecture/references/loop-engineering.md` (~260–320 lines) and
  `autonomy-contracts.md` (~150–220). Extend `architectures.md` (61 → ~170–200: workflows vs
  agents, the five Anthropic patterns, Google Levels 0–4) and `memory-vector-db.md` (52 →
  ~130–150: the LLM-wiki persistent-KB pattern, write-back/consolidation). Add
  `tests/check_docs.py` adapted from eda-skills — byte budget, zip-vs-instructions paths, zip
  contents, two-way SKILL.md↔references link integrity, and a skill-list-twins check across
  `build_gpt_package.ps1` / `skills/` / `agents/ai-gen-mentor.md` / README (that last check is
  what makes adding skills #7 and #8 safe).
- **Round 2 — RAG depth.** New `design-agent-architecture/references/rag-pipeline.md`
  (~250–320) and `build-ai-examples/references/rag-example.md` (~150–200) with runnable code
  under `build-ai-examples/scripts/rag_example/`; new `tests/smoke_test.py` that runs offline
  with a stub embedder (no network, no keys).
- **Round 3 — skill #7 `engineer-prompt-context`.** Full kit (SKILL.md, `agents/openai.yaml`,
  `references/prompt-techniques.md`, `references/context-engineering.md`) plus the expensive
  wiring: build-script skill list, a 7-stage `gpt_instructions.md` (needs a compaction pass —
  see the byte-budget note below), mentor-agent routing, orchestration table in
  `plan-ai-solution/SKILL.md`, README.
- **Round 4 — skill #8 `explain-llm-internals` + Agent Ops.** Kit with
  `architecture-training.md`, `inference-internals.md`, `fine-tuning-mechanics.md`; plus
  `evaluate-optimize-models/references/agent-ops.md` (tracing, online judging cadence,
  metrics-gated deploys, incident→eval loop).

### Facts worth not re-deriving

- `chatgpt/gpt_instructions.md` measured at **7,254 / 8,000 UTF-8 bytes** (746 spare) at the
  end of this round. Two new skills add roughly 150–200 bytes each as new stage lines, so
  round 3 or 4 will need a compaction pass. House rule to keep: instruction bytes are spent
  only on *procedure* changes; new references ride into the zip for free.
- All 15 current references measure 37–63 lines — far below the eda-skills mature band of
  ~250–380, which is why every round below adds depth to existing files as well as new ones.
- The build script stages `SKILL.md` + `references/` + `scripts/` + `assets/` per named skill
  and excludes `agents/`, `README*`, `HANDOFF.md`, `CLAUDE.md`, `dist/`, `chatgpt/`. A new
  skill is invisible to the GPT package until its name is added to the `$skills` array.

### Deliberately out of scope, recorded so it is not re-mined

- The "Agentic AI Pioneer Program" brochure — marketing; only its 14-module list has any
  signal, and that is already covered by the roadmap.
- The YC Paper Club transcript (`01_Inference_Diffusion_World_Models_and_More...txt`) — heavily
  degraded ASR mixing Ukrainian and English; at most one or two pointers (speculative decoding,
  data-constrained scaling) in round 4, and only if the primary paper can be cited instead.
- ASR transcripts as quotable sources anywhere. They point at primary sources; the primary
  source gets cited.
- Benchmark scores, prices, context-window figures — the standing house rule in `CLAUDE.md`.
- Wholesale ingestion of the Tier B books. They are a citation backbone; transcribing them
  would both bloat references past the soft cap and be the wrong kind of content.
- Foster's generative theory (VAE/GAN/diffusion) — deferred unless the mentor's scope expands
  to image/audio generation.

## What happened before (initial scaffold, 2026-07-19)

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

## Standing procedure: triaging practitioner-advice sources

Adopted 2026-07-20, after live-triaging two candidate sources (see the `Open threads` entry
below for the verdicts). Applies whenever the user proposes a blog/Substack/LinkedIn/X-style
"practitioner advice" post as a source — a genre distinct from the papers/whitepapers/books
governed by the Tier A/B rules above, with its own failure modes (unsourced engagement-hook
statistics, real technique names dropped without depth, uneven author reliability). Use this
every time such a source comes up, not only during a round-0-style batch intake. The block is
self-contained (does not depend on this file being in context) — paste it with the link/file
filled in:

```
Контекст: плагін `ai-gen` (`plugins/ai-gen` у `fk-dev-digest-marketplace`) — агент-ментор
`agents/ai-gen-mentor.md` + скіли з довідками в `skills/*/references/*.md`. Перед роботою
прочитай `CLAUDE.md` і `HANDOFF.md` цього плагіна, якщо ще не читав(ла) їх у поточній сесії.

Вхідні дані: {посилання або шлях до файлу з порадою практикуючого розробника — Substack,
LinkedIn, X, Medium тощо}.

Завдання: оціни матеріал як кандидата в довідки агента-ментора. Це тріаж, не імплементація —
нічого в SKILL.md, references чи HANDOFF.md не редагувати без окремого явного дозволу
користувача (сама згода на план не є командою починати).

Процедура:

1. Отримай повний текст. Для URL — спробуй WebFetch. Якщо контент за пейволом чи обрізаний —
   прямо скажи, що видно лише частину, і попроси користувача надіслати повний текст або файл
   (PDF/скрін). Не добудовуй відсутнє.

2. Зʼясуй жанр і автора. Це особиста думка/маркетинговий гачок практика, чи є бібліографія на
   першоджерела? Перевір, чи цей автор уже зустрічався серед джерел плагіна (grep по
   HANDOFF.md і references/) — якщо так, це попередній вердикт, а не оцінка з нуля.

3. Розбий текст на окремі твердження й перевір кожне:
   - Конкретні цифри, бенчмарки, відсотки без посилання на джерело → не факт, а авторський
     гачок/ілюстрація. Явно познач так, ніколи не переноси як дані (правило CLAUDE.md про
     вигадані показники).
   - Названі техніки/методи → чи це впізнавана реальна річ? Знайди першоджерело (пейпер,
     офіційна документація) для кожної. Якщо опис автора спрощує або перекручує механізм —
     зафіксуй розбіжність окремо, не переноси мовчки.
   - Якщо для твердження-**факту** нема першоджерела і його не можна верифікувати незалежно —
     не пропонуй як контент, хоч би як правдоподібно воно звучало.
   - **Виняток для технік (правило користувача, 2026-07-20):** практичний прийом розробника —
     не цифра й не факт — можна брати й без академічного першоджерела, якщо він не суперечить
     (1) поточній документації інструмента, який застосовується, і (2) фундаментальній теорії.
     Звір із тією документацією до написання й познач у довідці як практичну техніку, не
     вдягай у вигляд цитати. Тобто відсутність бібліографії сама по собі не є вироком —
     вироком є відсутність будь-чого перевірюваного.

4. Звір із чинним планом. Прочитай description кожного SKILL.md (не з пам'яті) і секцію
   round'ів у HANDOFF.md. Тема справді належить одному з них, чи це нова гілка знань? Якщо
   домівки немає — так і скажи, не притягуй силою до найближчого скіла.

5. Видай короткий вердикт у чат (не файл):
   - придатність джерела як такого (аналог Tier A / Tier B / непридатне — і чому);
   - твердження, що пройшли перевірку — з кандидатом на першоджерело для кожного;
   - твердження, які варто відкинути або позначити «неверифіковано»;
   - куди це потенційно лягає (round, файл) — як пропозиція користувачу, не рішення.

Тверда межа: результат цього тріажу — звіт, не патч. Чекай на окрему явну команду користувача
щодо round і формулювання, навіть якщо джерело виглядає бездоганним.
```

## Standing procedure: analyzing full-length books

Adopted 2026-07-20, after triaging the Streamlit Essentials epub structurally (metadata and
table of contents only, no chapter text — see the `Open threads` entry below). Applies to any
full-length book file (epub/PDF) proposed as a source. Copyright exposure here is categorically
higher than for a blog post, so the extraction ceiling is stricter: metadata and table of
contents only, never chapter body text, in the conversation or in any file. Paste this (with the
path filled in) at the start of the analysis — it is self-contained:

```
Контекст: плагін `ai-gen` (`plugins/ai-gen` у `fk-dev-digest-marketplace`) — агент-ментор
`agents/ai-gen-mentor.md` + скіли з довідками в `skills/*/references/*.md`. Перед роботою
прочитай `CLAUDE.md` і `HANDOFF.md` цього плагіна, якщо ще не читав(ла) їх у поточній сесії.

Вхідні дані: {шлях до файлу книги — epub або PDF}.

Завдання: оціни книгу як кандидата в довідки агента-ментора. Це тріаж, не імплементація —
нічого в SKILL.md, references чи HANDOFF.md не редагувати без окремого явного дозволу
користувача.

Тверда межа задається одразу, а не наприкінці: НІКОЛИ не витягуй і не переказуй текст розділів
книги — ні в чат, ні у скретчпад-файл, ні в жоден файл плагіна. Дозволено лише метадані
(назва/автор/видавництво/мова), повний зміст (назви розділів і підрозділів — структура, не
контент) і сигнали цілісності файлу (кількість файлів/сторінок, обсяг). Якщо колись знадобиться
конкретний факт із середини розділу — це окрема, свідома, точкова дія під цей один факт,
переказана власними словами, ніколи не дослівна цитата довша за кілька слів.

Процедура:

1. Витягни структуру, не прозу.
   - epub: розпакуй як zip, прочитай META-INF/container.xml → OPF-файл (dc:title/creator/
     publisher/language), далі nav.xhtml (epub3) або toc.ncx (epub2) для повного змісту.
   - PDF: PyMuPDF (`fitz`) встановлений — `doc.get_toc()` дає закладки без рендерингу сторінок
     (pdftoppm на цій машині недоступний). Якщо закладок нема — прочитай лише перші кілька
     сторінок, де зазвичай друкований зміст, і зупинись.

2. Перевір цілісність: кількість файлів чи сторінок і приблизний обсяг тексту — підтверджує, що
   книга справжня й повна, а не пошкоджена чи уривок.

3. Звір зміст книги (за назвами розділів) із description кожного SKILL.md (прочитай свіжо, не з
   пам'яті) — яким скілам це реально поглиблює знання, якщо взагалі якимось.

4. Класифікуй за замовчуванням як Tier B (citation backbone), не Tier A: книги в цьому плагіні
   не імпортуються цілком — це чинне рішення round 0 (роздуває references понад м'яку межу й не
   той тип контенту). Tier A — виняток, і лише якщо користувач окремо це підтвердить.
   **Книга без видавця й без бібліографії ще не відхилена** (правило користувача, 2026-07-20):
   дивись, чи є в змісті впізнавані практичні прийоми. Якщо є — це Tier B «практична техніка»:
   придатна, але кожен прийом звіряється з поточною документацією інструмента перед записом і
   позначається як практична техніка, не як цитата. Якщо в змісті самі концептуальні назви
   розділів без жодного прийому — тоді відхиляй, і саме з цієї причини, а не через видавця.
   Обидва випадки трапилися в партії round 7: Dhyani прийнято, Aki D і Rubin відхилено.

5. Зафіксуй походження файлу, якщо видно з імені чи метаданих (легітимний доступ, чи тіньова
   бібліотека на кшталт libgen/z-lib/anna's archive) — фактично, без моралізаторства: якщо книгу
   колись логуватимуть у HANDOFF, запис не повинен приписувати легітимність, якої не було.

6. Видай короткий вердикт у чат (не файл): цілісність, структура і теми за змістом,
   Tier-класифікація, яким скілам/раундам це потенційно підсилює знання (або чесне «немає
   домівки»).

Тверда межа: результат — звіт, не патч і не переказ розділів. Чекай на окрему явну команду
користувача щодо round і формулювання.
```

## Environment gotchas

- Console encoding is cp1251 on this machine — don't `print()` Cyrillic from Python via Bash;
  write UTF-8 files and Read them instead (inherited from eda-skills sessions). **Exception found
  in round 7:** `sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')` at the top
  of a `python - <<'PY'` heredoc through the Bash tool does round-trip UTF-8 correctly, CJK
  included — that is how a Chinese-language book's table of contents was read without writing a
  file. Useful when plan mode forbids scratch files.
- **The harness's attachment listing under-reports PDF page counts — badly.** In round 7 it
  claimed 12 pages for a 38-page article, 178 for a 378-page book, 185 for 492, 78 for 359, and
  22 for 178. Judging "this is only a fragment" from that listing would have rejected four good
  books. Open the file with PyMuPDF and read `doc.page_count` before triaging. (Genuine fragments
  do exist — one file in the same batch really was 42 pages with unusable metadata — which is
  exactly why the count has to be measured rather than read off the listing.)
- PDF *page rendering* is unavailable (`pdftoppm` missing), so the Read tool fails on PDFs.
  PyMuPDF (`fitz`) and `pdfplumber` are installed; `doc.get_toc()` gives bookmarks without
  rendering, and `page.get_text("text")` gives text. Known since round 1, re-confirmed in round 7.
- Repo-root scripts must run from the marketplace root (`npm run lint`, `npm run
  build:catalog`); paths in `scripts/*.mjs` are root-relative.
- `dist/` is gitignored repo-wide, including this plugin's `dist/` — knowledge zips are built
  artifacts, never committed. **They still have to be rebuilt when a reference is added or
  removed** — `check_docs.py` check 5 compares the zip's contents against disk and fails on a
  stale zip even though nothing about it gets committed (round 8 hit this).
- **`pwsh` is not installed on this machine** — only Windows PowerShell 5.1. Run the packaging
  script as `& .\chatgpt\build_gpt_package.ps1` from the plugin root; `pwsh -File ...` fails with
  `CommandNotFoundException`.
- Markdown is prettier-ignored repo-wide (`.prettierignore`); markdownlint-cli2 with the
  root `.markdownlint.jsonc` is the md gate instead.

## Open threads / not done

- **Every planned round is now done.** The fixed roadmap (rounds 1–4) plus rounds 5 (reasoning
  models), 6 (live RAG verification), 7 (source triage), 8 (GraphRAG), 9 (ANN + chunking) and 10
  (production RAG + label production) have all shipped. `main` has rounds 0–9 (round 7 =
  `de3f084`/PR #12, round 8 = `3fac365`/PR #13, round 9 = `1a9864d`/PR #14); round 10 is on
  `feat/ai-gen-production-rag-evalset` awaiting the user's merge. 8 skills, **28** references, a
  runnable example, two test guards.
- **There is no round 11 planned. The next unit of work needs a new user request** — do not
  invent one from the leftovers below.
- **What the round-7 source batch still has left in it**, if the user ever wants more:
  - **Polzer's cookbook recipes** (agentic chunking, embedding hypothetical questions, metadata
    filtering, Ollama, Pydantic structured outputs, multimodal parsing) were triaged as a recipe
    index for `build-ai-examples` and **never used** — rounds 8–10 all landed in
    `design-agent-architecture` and `evaluate-optimize-models` instead.
  - **汪鹏/谷清水/卞龙鹏, 大模型RAG实战** (Chinese) stays the marginal fallback it was: only its
    RAG-paradigm-evolution and joint retriever/generator training framing are not better covered
    elsewhere, and round 8 did not need it.
  - **Mendelevitch & Bao** and **Jia Huang** are spent as maps; **Dhyani** is spent on round 9's
    chunking table; the **Karim article** is spent across rounds 10's three edits.
  - The rejected list stands and must not be re-mined — see the round-7 entry.
- **Decisions still waiting on the user, not on work:**
  1. ~~Whether to place the Cameron Wolfe reasoning-models source~~ — **done in round 5**; that
     content gap is closed. The other triaged source (Hao Hoang, rejected) stays rejected.
  2. Whether to bump the version off `0.0.1` and tag a release. Still deliberately unreleased —
     merging the PR did not tag one, and none of `eda-skills`, `agent-ml-interviewer`,
     `agent-database` is tagged either.
  3. Whether to add the plugin to `~/.claude/settings.json` → `enabledPlugins`. **No longer
     blocked on the merge** — that already happened. The one remaining wrinkle is the installed
     plugin cache lagging behind `main` until its own refresh; see the round-5 postscript.
  4. Whether references should keep growing. **Measured in round 10, not carried forward: 9 of
     28 references are ≤63 lines**, the rest span 64–322. The "12 of 27/28" figure this file
     repeated from round 4 onward was never re-counted and was wrong — same lesson as the round-7
     triage correction above, applied to our own arithmetic. The nine, smallest first:
     `python-visualization.md` (37), `react19-frontend.md` (37), `local-docker.md` (41),
     `openrouter.md` (44), `task-to-model.md` (46), `cloud-aws-gcp-azure.md` (47),
     `mcp-tools.md` (47), `handoff.md` (49), `model-landscape.md` (52). **They have no plan at
     all now** — deepening them is a user decision, not a queued task, and it would need new
     material since the round-7 batch is spent. Note two of them are deliberately thin:
     `openrouter.md` and `model-landscape.md` describe a catalog that changes weekly, which the
     standing rule says not to freeze.
- Books for any future internals work are in
  `F:\Data\Lenovo\Документы\AI_courses\BigData_Course\Books\LLM\` (Raschka ×2, Godoy, Huyen ×2,
  Labonne, Alammar, Berryman/Ziegler) — round 0 recorded the wrong path.
- **The skill roster is 8 and guarded**: `tests/check_docs.py` check 2 fails when the build
  script, `skills/` on disk, the mentor agent, the README tree, and the router disagree — it
  produced the exact to-do list when skills #7 and #8 landed. Still *outside* the check:
  `chatgpt/README.md` (round 3 found two stale claims there by hand) and
  `gpt_instructions.md`'s stage chain. The marketplace catalog self-heals via `build:catalog`.
- `tests/check_docs.py` (7 checks) and `tests/smoke_test.py` (14 checks) both exist. Neither runs
  in CI — see round-1 decision 2. Run both before every commit that touches this plugin.
- **The RAG example's full live path was run for real in round 6** — database layer, Ollama
  embeddings, and a real OpenRouter chat call, all against live services, all in the same
  session. Four real bugs came out of it: extension-before-register ordering, a DDL type
  modifier that can't be a bound parameter, a raw list where pgvector needed `Vector(...)`, and
  `.env` never actually loading into `os.environ` (fixed with `python-dotenv` in the two
  entrypoint scripts, not in `settings.py`). All four fixed and re-verified. Nothing about this
  example's live path is unverified anymore — see round 6's postscript for the full run,
  including the correct, grounded, cited answer it produced.
- No `README-beginner.md` yet — add one if/when the user asks (eda-skills precedent).
- **`enabledPlugins` status — see the fuller note in the round-5 postscript above and the
  "Decisions still waiting" item 3.** Short version: merged, so no longer structurally blocked;
  the installed plugin cache just hasn't refreshed to it yet as of this session.
- Deferred backlog with no round assigned: the ~50-project Agentic-AI catalog as an idea mine
  for `build-ai-examples`; deeper SFT/DPO pipelines (Labonne & Iusztin) beyond what
  `fine-tuning-mechanics.md` already covers (that file shipped in round 4 — the backlog item is
  *more* depth than it has, not a claim the file is missing).
- **Two practitioner-advice sources triaged 2026-07-20** with the standing procedure above, both
  evaluated-but-unplaced — the user will decide round/file placement personally, it is not on
  the roadmap above:
  - Cameron Wolfe, "Demystifying Reasoning Models"
    (<https://cameronrwolfe.substack.com/p/demystifying-reasoning-models>) — accepted: free, full
    text, ~22 citations, covers RLVR, CoT, test-time scaling, DeepSeek-R1/R1-Zero's four-stage
    pipeline, distillation. Strong fit for round 4 `explain-llm-internals` — nothing currently in
    the plugin covers reasoning models.
    **PLACED in round 5** (user chose "separate reference", 2026-07-20) →
    `explain-llm-internals/references/reasoning-models.md`. Used as a map; every claim traced to
    the primary papers, and two attributions corrected in the process — see the round-5 entry.
  - Hao Hoang, "LLM Agents Interview Questions #1 — The Privacy Scaling Trap"
    (aiinterviewprep.substack.com, PAID) — rejected as a citable source: no bibliography, and its
    hook stat ("+400% PII extraction" from a 7B→70B upgrade on identical data) is invented
    framing, not a reported figure. Same author already logged above as a topic-map-not-primary-
    source ("Top 25 LLM System Design Interview Questions"). The underlying phenomenon
    (memorization scales with model size and data duplication, independent of the interview
    framing) is real but uncited in this post; primary-source candidates if the topic is ever
    wanted: Carlini et al. on training-data extraction/memorization scaling, Lee et al. on
    deduplication, Abadi et al. on DP-SGD — none currently used anywhere in ai-gen. No skill in
    the current 8-skill plan owns training-data privacy/memorization (checked
    `evaluate-optimize-models`: it's metrics + efficiency, not safety) — a scope gap, not a
    round-4 slot-in.
- **Streamlit Essentials** (Surabhi Pandey, BPB Publications, epub; filename indicates a
  libgen.li source, not a confirmed purchase) — triaged 2026-07-20 with the book-analysis
  procedure above: structure only (13 chapters + 3 appendices, 26 hands-on projects, 666 KB of
  xhtml text), no chapter body extracted. Verdict: not a knowledge source for any of the 8
  skills — it is a Streamlit how-to, not GenAI methodology. Closest touchpoint is as a candidate
  demo-frontend framework for `build-ai-examples`'s worked examples, not reference content.
  Evaluated-but-unplaced, no round assigned. **Re-supplied in the round-7 batch and deliberately
  not re-triaged** — this verdict stands.
- **The round-7 batch (13 files) is fully triaged; see the round-7 entry at the top for the
  per-source verdicts.** Five accepted (one Tier A article, four Tier B books), one marginal
  (Chinese-language), five rejected, one duplicate, one already-triaged. **Do not re-mine the
  rejected five** — Aki D, Rubin, the unattributable "Utilizing Vector Databases (Fragment)",
  Sivabalaselvamani et al., and (as a source rather than a frontend) Streamlit Essentials. The
  accepted four are assigned to rounds 8–10; nothing in the batch is left unplaced.
