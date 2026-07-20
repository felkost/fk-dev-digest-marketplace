# Memory and vector databases

Two different problems that get conflated: *state within a session* (short-term) and *knowledge
across sessions* (long-term). Design them separately.

## Contents

- Short-term memory (within a session)
- Long-term memory (across sessions)
- Vector databases
- What the "approximate" in ANN is actually trading
- Chunking strategies
- Persistent knowledge base (the LLM-wiki pattern)
- Write-back and consolidation

## Short-term memory (within a session)

The context window is the short-term memory; managing it is a budget problem.

- Keep the system prompt + tool schemas lean; they are paid on every call.
- Summarize-and-truncate long histories (rolling summary + last N turns verbatim); in LangGraph
  this is a state-reduction node, not an afterthought.
- Externalize scratch state (plans, intermediate tables) into the graph state / files rather
  than re-narrating it in chat turns.
- Prompt caching (where the provider supports it) rewards a *stable prefix*: static instructions
  first, volatile content last.

## Long-term memory (across sessions)

This bucket itself splits into two things that are easy to conflate because they're often stored
the same way: **knowledge** is static and external — documents, manuals, schemas, a code
repository — curated on the timescale of its source and identical for every user of the agent.
**Memory** is dynamic and experiential — preferences, past decisions, session history — updated
continuously and scoped to a specific user, tenant, or session. The write policy below ("record
decisions with reasons," timestamps, superseding) is memory's discipline; a knowledge corpus is
instead re-ingested when its source changes (`document-loading.md`'s idempotent re-ingest). Both
are commonly surfaced through the same retrieve-then-generate pattern (RAG), which is why they
get conflated, but confusing "the corpus is stale" with "the user's stated preference wasn't
recorded" leads to fixing the wrong pipeline.

Choose the store by *retrieval pattern*, not fashion:

| Need | Store |
|---|---|
| Exact-key facts (user prefs, config, decisions) | Plain files / relational DB — retrieval by key, no embeddings needed |
| Semantic recall over unstructured text | Vector DB (see below) |
| Relations/graph traversal (who-worked-with-whom) | Graph or relational DB — see below |
| Session handoff for a coding/analysis agent | A human-readable HANDOFF/memory file (auditable, editable) |

**When the graph row is the answer.** Picking a graph *store* and building a graph *retrieval
architecture* are different decisions, and the second one is not made here. If the questions are
global ("what are the main themes across this corpus?") or multi-hop (joining facts that never
share a chunk), no vector store configuration answers them — that is `graph-rag.md`, which
covers LLM-driven graph construction, entity resolution, community summaries and their two query
modes, text2cypher, and what the index costs. If you only need relation lookups over data you
already hold, an ordinary graph or relational DB with hand-written queries is the cheaper answer
and needs none of that machinery.

Write policy matters more than the store: record *decisions with reasons* and *stable facts*;
do not archive raw transcripts as "memory" — retrieval will surface stale contradictions.
Add timestamps and let entries be superseded, not silently overwritten.

## Vector databases

Purpose: approximate nearest-neighbor search over embeddings for RAG/semantic recall.

- **Start small**: for ≤ ~1M vectors, a library/embedded option (FAISS, sqlite-vec, pgvector in
  the Postgres you already run) usually beats standing up a dedicated service. Dedicated servers
  (Qdrant, Weaviate, Milvus, managed offerings) earn their keep with scale, filtering, and
  multi-tenant ops.
- **pgvector default**: if the app already has Postgres, one database for rows + vectors removes
  a whole failure domain (sync between stores).
- **Chunking**: split by semantic units (headings/paragraphs/code blocks), not fixed characters;
  attach metadata (source, section, date) for filtering and citations; oversized chunks bury the
  answer, undersized ones sever context. Tune chunk size on your own retrieval eval. Strategies
  beyond the default are a section of their own below.
- **Hybrid search**: dense vectors miss exact identifiers/rare terms; combine with keyword/BM25
  and merge (e.g. reciprocal-rank fusion), then optionally rerank with a cross-encoder — see
  "Sparse, dense, and why BM25 refuses to die" below.
- **Evaluate retrieval separately**: build a small labeled set (question → passages that answer
  it) and measure recall@k / MRR before blaming the generator. Changing the embedding model
  means re-embedding the corpus — version the index by embedding-model ID.
- Same-model rule: query and corpus must be embedded by the same model/version; mixing silently
  degrades to noise.

## What the "approximate" in ANN is actually trading

Exact nearest-neighbour search is a full scan: compare the query against every stored vector.
It is perfectly accurate, trivially correct, and its cost grows with the number of vectors times
their dimensionality. ANN indexes exist to escape that scan, and every one of them buys speed by
**agreeing not to always return the true nearest neighbours**. That is the contract, not a bug —
pgvector states it plainly in its README: after adding an approximate index you will see
different query results than before.

So the design space is a triangle, and you cannot maximize all three corners:

- **Recall** — the fraction of true nearest neighbours the index actually returns.
- **Latency** — how long one query takes.
- **Memory** — how much RAM the index occupies beyond the vectors themselves.

Every knob below moves you along that triangle. If a change appears to improve all three,
something is unmeasured — usually recall, because nothing in the system complains when it drops.
Measure recall against an exact scan on a sample of your own queries before and after any index
change; it is the only way this stays honest.

### Index families

| Family | How it finds candidates | Buys | Costs / fails by |
|---|---|---|---|
| **Flat (exact)** | Scans everything | Perfect recall, no build step, no tuning | Latency grows with corpus size. Correct default under ~10⁵ vectors, and often well past it |
| **IVF** (inverted file) | Clusters vectors, searches only the nearest clusters | Big speedup for a small memory overhead; simple to reason about | Recall collapses when the answer sits just across a cluster boundary. Partitioning is *learned from the data*, so an index built before the data exists is meaningless, and it degrades as the corpus drifts away from the clustering |
| **HNSW** (graph) | Greedy descent through a multi-layer proximity graph | Strong recall/latency at scale — the default in most modern stores | The largest memory footprint of the four; slow to build; deletions age the graph |
| **PQ** (product quantization) | Compresses vectors into short codes, estimates distances from the codes | Order-of-magnitude memory reduction; makes huge corpora fit in RAM | Lossy *by construction* — distances are estimates. Usually layered onto IVF/HNSW rather than used alone |
| **LSH** (hashing) | Hashes near vectors into shared buckets | Cheap, simple, streaming-friendly | Generally worse recall-per-latency than graph methods on dense embeddings; largely displaced by HNSW in practice |

HNSW's primary source is Malkov & Yashunin, "Efficient and robust approximate nearest neighbor
search using Hierarchical Navigable Small World graphs" (2016,
<https://arxiv.org/abs/1603.09320>): it builds a hierarchy of proximity graphs over nested
subsets of the data, with elements assigned to layers with exponentially decaying probability,
which is what gives the search its logarithmic scaling. Product quantization is Jégou, Douze &
Schmid, "Product Quantization for Nearest Neighbor Search" (*IEEE TPAMI* 33(1):117–128, 2011,
doi:10.1109/TPAMI.2010.57) — the space is decomposed into a Cartesian product of low-dimensional
subspaces, each quantized separately, so a vector becomes a short code and distances are
estimated from codes rather than from the vectors.

### Build-time knobs versus query-time knobs

This distinction matters more than the specific numbers, because the two classes have completely
different economics:

- **Build-time knobs** are baked into the index. Changing one means rebuilding — minutes to hours
  on a real corpus, and usually a maintenance window.
- **Query-time knobs** are set per session or per query and cost nothing to change. This is where
  the recall/latency dial you actually operate lives.

**Names belong to implementations, not to algorithms** — the same idea ships under different
identifiers, and mixing them up produces config that silently does nothing:

| Idea | pgvector | FAISS |
|---|---|---|
| HNSW graph degree (build) | `m` | `M` |
| HNSW build beam width (build) | `ef_construction` | `efConstruction` |
| HNSW search beam width (query) | `hnsw.ef_search`, via `SET hnsw.ef_search = 100;` | `efSearch` |
| IVF partition count (build) | `lists` | `nlist` |
| IVF partitions probed (query) | `ivfflat.probes`, via `SET ivfflat.probes = 10;` | `nprobe` |

pgvector's own guidance for `lists` is `rows / 1000` up to 1M rows and `sqrt(rows)` beyond it;
its defaults are `m = 16`, `ef_construction = 64`, `hnsw.ef_search = 40`, and `ivfflat.probes = 1`
— that last one is why an untuned IVFFlat index so often looks broken. Read the current README
before committing to any of these; they are the sort of value that moves between releases.

pgvector also exposes the quantization axis through types rather than index parameters:
`halfvec` (half precision), `bit` with `binary_quantize()`, and `sparsevec`. Six distance
operators are available — `<->` L2, `<#>` inner product, `<=>` cosine, `<+>` L1, `<~>` Hamming,
`<%>` Jaccard — and the operator must match the one the index was built for, or the index is
simply not used.

**The plugin's own example is deliberately unindexed.** The RAG example in `build-ai-examples`
does an exact scan and says so (`references/rag-example.md`); on a demo corpus that is the
correct choice, and adding an approximate index there would teach the habit of reaching for one
before the scan is measurably too slow. Add the index when the scan is the measured bottleneck —
and re-measure recall when you do.

### Sparse, dense, and why BM25 refuses to die

A dense embedding compresses meaning into a few hundred fixed dimensions. A rare token — an
error code, a part number, an internal acronym, an unusual surname — contributes almost nothing
to that compressed representation and cannot be recovered from it. A lexical index has no such
problem: it matches the token exactly. This is why hybrid retrieval is not a hedge but a
structural fix, and why the failure mode "our RAG cannot find ticket `INC-4471`" is so common.

Merge the two rankings with **reciprocal rank fusion** — Cormack, Clarke & Büttcher, "Reciprocal
Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods" (SIGIR 2009): each
document scores the sum of the reciprocals of its ranks across the systems, damped by a
constant. It needs no score normalization between retrievers, which is exactly what makes it
usable when one system returns cosine similarities and the other returns BM25 scores.

## Chunking strategies

Chunk boundaries decide what can *ever* be retrieved together, which makes this the highest-
leverage decision in ingestion and the one most often left at a default. `rag-pipeline.md` owns
the Split stage and its failure modes; what follows is the strategy menu it points here for.

Start with recursive character splitting with overlap — LangChain's documentation recommends its
recursive splitter as the default for exactly this reason, and it is the right first answer for
undifferentiated prose. Reach past it when the corpus has structure the default destroys:

| Strategy | Split on | Fits when | Costs |
|---|---|---|---|
| **Recursive character** | Paragraph → sentence → word, in that order | Prose with no reliable markup. The default | Blind to document structure; can split a table down the middle |
| **Structural** | Markdown headings, HTML tags | Docs, wikis, handbooks — anything with a real heading hierarchy | Useless on documents whose headings are decorative or absent |
| **Code-aware** | Function/class boundaries per language | Source code, notebooks | Needs a parser per language; a huge function is still one huge chunk |
| **Regex / pattern** | A delimiter you know is meaningful (`^Article \d+`, log prefixes) | Legal text, transcripts, logs, machine-generated formats | Brittle; one format change silently reverts you to one giant chunk |
| **Table-aware** | Table boundaries, with the header row carried into every chunk | Documents where the answer lives in tables | Without the carried header, rows retrieve as unlabelled numbers — a silent correctness failure |
| **Time-based** | Timestamp windows or session boundaries | Chat logs, meeting transcripts, event streams | A window can cut mid-topic; pair it with overlap |
| **Metadata-grouped** | Group by a field (customer, product, version) before splitting | Multi-tenant or multi-version corpora | Uneven chunk sizes; needs clean metadata to start with |
| **Semantic** | Embedding-similarity breakpoints between sentences | Long unstructured prose that shifts topic without markup | An embedding pass over the corpus at ingest time, before you have any chunks |
| **Hierarchical / parent-child** | Small chunks for matching, larger parents returned for context | Retrieval precision and answer context pull in opposite directions | Two indexes to keep consistent; more moving parts |
| **Sentence-window** | One sentence per chunk, neighbours attached as metadata | Precise matching where surrounding context is still needed | Index size grows; assembly logic moves into the retriever |

**These are practitioner techniques, verified against the tool documentation rather than
imported from a paper.** Both major frameworks ship implementations of most of them —
LlamaIndex names `SemanticSplitterNodeParser`, `HierarchicalNodeParser`,
`SentenceWindowNodeParser`, `MarkdownNodeParser`, `HTMLNodeParser`, `CodeSplitter` and
`TokenTextSplitter`; LangChain ships a recursive splitter, header/tag-based splitters for
Markdown and HTML, a JSON splitter and a code splitter. **Class names and import paths drift
between doc revisions** — LangChain's documentation site reorganized and the old concept URLs now
redirect — so treat the technique as stable and the identifier as something to check against the
current docs before writing code.

Two closing rules, both learned the expensive way:

- **Carry metadata down through every strategy.** Source, section heading, date, and the table
  header if there was one. A chunk that cannot say where it came from cannot be cited, and a
  citation is most of what RAG is for.
- **No strategy survives contact with a corpus by argument.** Pick the one whose failure mode
  your corpus does not have, then measure recall@k on your own labelled set — the same
  measurement `rag-pipeline.md` demands before touching the prompt or the model.

## Persistent knowledge base (the LLM-wiki pattern)

An alternative to embedding-everything for long-term knowledge: let the model *compile* a
corpus into maintained prose once, instead of re-deriving it per query. Primary source:
Andrej Karpathy's LLM-wiki gist,
<https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>.

Three layers, with strictly different ownership — this separation is the whole pattern:

| Layer | Owner | Contents |
|---|---|---|
| Raw sources | Human; **immutable** | Curated documents, papers, data files. The model reads them and never modifies them |
| The wiki | The model, entirely | Markdown pages: summaries, entity pages, concept pages, cross-references |
| The schema | Human | A config document (`CLAUDE.md`, `AGENTS.md`) stating how the wiki is structured, its conventions, and its workflows |

Three operations:

- **Ingest** — read a new source, extract key information, write summaries, update the entity
  pages it touches, revise cross-references. The source notes one document may touch 10–15 wiki
  pages; ingestion is a graph update, not an append.
- **Query** — search the relevant pages and synthesize. Insights worth keeping get filed back
  as new pages, so answering improves the corpus instead of consuming it.
- **Lint** — periodically health-check the wiki for contradictions, stale claims, orphan pages,
  and missing cross-references. Without this the wiki accumulates confident contradictions,
  which is worse than no memory because they read as curated.

Two bookkeeping files carry the state: an `index.md` catalog organized by category and updated
on each ingest, and an append-only `log.md` with greppable prefixes recording what happened.

**Wiki vs RAG.** The contrast the source draws: RAG rediscovers knowledge from scratch on every
question — there is no accumulation. The wiki is a persistent, compounding artifact where the
cross-references already exist by the time a question arrives. The trade is up-front ingest cost
and maintenance against per-query retrieval cost and the risk of missing what was never linked.

**Honest scale limit.** The flat index works well at moderate scale — the source gives roughly
~100 sources and hundreds of pages — and beyond that needs real search infrastructure
(embeddings, a local search engine) layered on. Recommend this pattern at personal or
single-project scale; recommend RAG, or a hybrid where the wiki indexes a larger corpus, past it.

**Hybrid, in practice:** wiki pages as the retrieval corpus. Compiled, cross-referenced prose
chunks better than raw source documents, and citations point at a page a human can read and fix.

## Write-back and consolidation

Any long-term memory that only grows becomes a liability. Design the write path as deliberately
as the read path:

- **What gets written:** decisions with their reasons, stable facts, and corrections. Not raw
  transcripts, and not the model's restatement of what it just did.
- **When:** at task boundaries, not per turn. Per-turn writes produce a log, not knowledge.
- **Consolidation:** periodically merge duplicates, promote repeated observations into a single
  claim, and delete what proved wrong. This is the "lint" operation above, and it needs a
  scheduled trigger — nothing else will cause it to happen.
- **Supersede, don't silently overwrite:** timestamp entries and mark the replaced claim, so a
  reader can tell a correction from a contradiction.
- **Verify before trusting age.** A stored fact naming a file, flag, or endpoint reflects the
  world when it was written; check it still exists before acting on it.

Anthropic's context-engineering guidance
(<https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>) frames the
in-session counterpart of this as **structured note-taking**: the agent maintains an external
file (e.g. `NOTES.md`) so progress survives outside the context window, alongside **compaction**
(summarize the history when nearing the limit, reinitialize with the summary plus recent turns)
and **sub-agent isolation** (a focused agent returns a condensed summary rather than its whole
search trace). Same principle at session scope that the wiki applies at project scope: keep the
durable artifact outside the window, and pay attention only to what the current step needs.

The per-session, human-readable form of this discipline is the handoff protocol in
`plan-ai-solution/references/handoff.md`; the per-task form is the contract in
`autonomy-contracts.md`; the project-scale form is the wiki above.
