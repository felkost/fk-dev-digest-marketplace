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
