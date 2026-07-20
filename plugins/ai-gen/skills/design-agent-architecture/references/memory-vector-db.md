# Memory and vector databases

Two different problems that get conflated: *state within a session* (short-term) and *knowledge
across sessions* (long-term). Design them separately.

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

Choose the store by *retrieval pattern*, not fashion:

| Need | Store |
|---|---|
| Exact-key facts (user prefs, config, decisions) | Plain files / relational DB — retrieval by key, no embeddings needed |
| Semantic recall over unstructured text | Vector DB (see below) |
| Relations/graph traversal (who-worked-with-whom) | Graph or relational DB |
| Session handoff for a coding/analysis agent | A human-readable HANDOFF/memory file (auditable, editable) |

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
  answer, undersized ones sever context. Tune chunk size on your own retrieval eval.
- **Hybrid search**: dense vectors miss exact identifiers/rare terms; combine with keyword/BM25
  and merge (e.g. reciprocal-rank fusion), then optionally rerank with a cross-encoder.
- **Evaluate retrieval separately**: build a small labeled set (question → passages that answer
  it) and measure recall@k / MRR before blaming the generator. Changing the embedding model
  means re-embedding the corpus — version the index by embedding-model ID.
- Same-model rule: query and corpus must be embedded by the same model/version; mixing silently
  degrades to noise.

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
