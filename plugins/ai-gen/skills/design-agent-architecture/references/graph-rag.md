# GraphRAG: graph-structured retrieval for global and multi-hop questions

Vector RAG and graph RAG are not competing implementations of the same idea. They answer
different **shapes of question**, and the shape is decidable before any code is written. Read
this file when a corpus question is global, thematic, or multi-hop; read `rag-pipeline.md` for
everything else, which is most cases.

Scope note: this file owns graph-structured retrieval only. Vector stores, chunking policy and
hybrid search stay in `memory-vector-db.md`; pipeline stages and failure modes stay in
`rag-pipeline.md`; the router and critic *patterns* stay in `architectures.md` and are
cross-referenced here rather than restated.

## Contents

- The decision rule: what vector top-k structurally cannot do
- Building the graph: extraction is easy, resolution is hard
- The GraphRAG index and its two query modes
- text2cypher: natural language into a query language
- Cost honesty: what a graph index actually costs
- Routing between retrievers
- Evaluation hooks

## The decision rule: what vector top-k structurally cannot do

A vector retriever returns the `k` passages most similar to the query. That is the right
primitive when the answer *lives in a small number of passages* — a policy, a definition, a
specific fact. Two question types break it, and they break it structurally, not by being tuned
badly:

- **Global / aggregative questions** — "what are the main themes in this corpus?", "how has the
  tone of these reports changed?", "which risks recur across all suppliers?". The answer is a
  property of the whole corpus. Similarity to the *question* is not coverage of the corpus, and
  `k` passages out of `N` cannot become `N`. Reranking cannot fix it either: reranking reorders
  a candidate set, and the candidate set is still `k`.
- **Multi-hop questions** — the answer requires joining facts that never co-occur in any single
  chunk ("which of our vendors share a parent company with a sanctioned entity?"). Each hop may
  be individually retrievable while the conjunction is retrievable nowhere.

Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization"
(v2, February 2025, <https://arxiv.org/abs/2404.16130>) frames the first case sharply: a global
question over a corpus is a **query-focused summarization** task, not a retrieval task, and
prior summarization methods did not scale to corpus sizes that RAG indexes routinely. GraphRAG
exists to sit between those two failures.

| Question shape | Example | Retrieval that fits |
|---|---|---|
| Local lookup | "What is the refund window?" | Vector RAG (`rag-pipeline.md`) |
| Entity-centric detail | "What did we agree with Acme in 2024?" | Vector RAG with metadata filters, or graph local search |
| Multi-hop join | "Which vendors link to a sanctioned parent?" | Graph traversal or text2cypher |
| Global / thematic | "What are the main themes across all incident reports?" | Graph global search |
| Structured aggregation | "How many suppliers ship part X in region Y?" | text2cypher over a real schema |

Diagnose the shape first. A user asking a global question of a vector RAG gets a fluent,
correctly-cited, **wrongly-scoped** answer — synthesized from five passages that were never
representative. That failure is invisible in the transcript, which is what makes it worth
naming here.

## Building the graph: extraction is easy, resolution is hard

The construction pipeline is LLM-driven: chunk the documents, prompt a model to extract entity
instances and the relationships between them, then aggregate and summarize the descriptions
collected for each node and edge.

Extraction is the part everyone demos. **Entity resolution is the part that decides whether the
graph is worth anything**, and it gets a fraction of the attention:

- **Under-merging** — "Acme Corp", "ACME", "the company", and "Acme Corporation" become four
  nodes. The graph fragments, communities split along naming accidents, and multi-hop traversal
  dead-ends because the edge you needed hangs off a different alias.
- **Over-merging** — two genuinely different entities collapse into one node. Every fact about
  one now attaches to the other. This is the more dangerous direction: the graph looks clean,
  the summaries read well, and the corruption is invisible downstream.

A practitioner recipe that holds up (verify against your graph library's current API before
building it): resolve with **deterministic keys wherever they exist** — identifiers, emails,
URLs, ticker symbols beat any similarity heuristic and cost nothing. Only for what remains, use
blocking (cheap candidate grouping) plus embedding similarity to propose pairs, and reserve the
LLM for adjudicating the proposed pairs. Never let a model free-associate merges across the
whole entity set: the cost is quadratic and the errors are silent.

Two more construction decisions worth making on purpose:

- **Constrain the type system, or plan to normalize.** An unconstrained extractor invents a new
  relation type per chunk (`works_at`, `employed_by`, `is_employee_of`) and the graph becomes a
  synonym soup that no query can traverse. Supply an allowed list of entity and relation types,
  or accept free-form extraction and budget a normalization pass. Do not discover this after
  indexing.
- **Chunk size trades recall against cost.** Smaller chunks yield more extracted entity
  references per unit of text — Edge et al. measure this directly in their appendix, and the
  paper's counter-measure is *gleanings*: additional extraction rounds that ask the model
  whether it missed anything. Read the figures there rather than carrying them here; what
  transfers is the direction and the knob, not a number from someone else's corpus.

## The GraphRAG index and its two query modes

The Microsoft GraphRAG indexing pipeline, as described in the paper:

```
source documents
  → text chunks
  → entity + relationship instances (one LLM pass per chunk, plus gleaning rounds)
  → knowledge graph (per-node / per-edge descriptions aggregated and summarized)
  → graph communities (hierarchical community detection)
  → community summaries (a report-like summary per community, at every level)
```

The community step uses **Leiden** community detection applied hierarchically — recursively
finding sub-communities inside each community down to the leaves. Leiden's primary source is
Traag, Waltman & van Eck, "From Louvain to Leiden: guaranteeing well-connected communities"
(*Scientific Reports* 9:5233, 2019, <https://arxiv.org/abs/1810.08473>); its selling point over
Louvain is a guarantee that detected communities are internally connected. The hierarchy is not
decoration: it becomes the cost/detail dial at query time.

### Global search (the paper's mode)

Map-reduce over the pregenerated community summaries. Each community summary produces a partial
answer to the user's question; the partial answers are then reduced into one final response.
Nothing is retrieved by similarity — the whole selected level of the hierarchy is traversed,
which is precisely why it can answer a question about the corpus as a whole.

- **Buys:** answers to global sensemaking questions that vector RAG cannot reach at all.
- **Costs:** the most expensive query mode in this plugin — LLM calls scale with the number of
  community summaries at the chosen level, not with `k`.
- **Fails by:** running over a corpus with no real thematic structure (you get bland summaries
  of summaries); pregenerated summaries going stale as the corpus moves; nobody tuning the
  hierarchy level, so every question pays root-level or leaf-level cost regardless of need.

### Local search (the implementation's mode — not the paper's)

**Attribution matters here.** The paper describes the global map-reduce mode only. *Local
search* is a mode of the Microsoft GraphRAG implementation, documented at
<https://microsoft.github.io/graphrag/query/local_search/> — cite the docs for it, never the
paper.

It is entity-anchored: identify entities semantically related to the question, use them as
entry points into the graph, then pull their connected entities, relationships, covariates and
community reports **together with the raw text chunks associated with those entities**,
prioritizing and filtering all of it to fit a single context window. It suits questions about
specific entities — the graph supplies the neighbourhood a chunk-only retriever would miss,
while the source chunks keep the answer quotable.

Read local search as vector RAG *plus* a structured expansion step, and global search as
something vector RAG has no version of. That difference is the whole reason to keep both.

## text2cypher: natural language into a query language

When the graph has a schema you control, the retrieval question becomes a translation question:
turn the user's sentence into a Cypher query, run it, answer from the rows. This is the same
pattern as NL→SQL and it inherits the same three requirements:

1. **The schema goes in the prompt** — node labels, relationship types, properties. Neo4j's
   GraphRAG package exposes this as a `neo4j_schema` parameter on its `Text2CypherRetriever`.
2. **Few-shot examples carry the dialect** — the same library takes an `examples` parameter of
   question/query pairs. Examples are where you teach the conventions a schema dump cannot show.
3. **A terminology mapping** — users say "customer", the schema says `:Account`. Unmapped
   vocabulary is the most common source of confidently empty results.

Failure modes, in the order they will actually bite:

- **Syntactically invalid output.** The library documents this directly: a generated query is
  not guaranteed to be valid, and an unexecutable one raises `Text2CypherRetrievalError`
  (<https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html>). This is the
  *benign* failure — it is loud.
- **Valid but semantically wrong.** The query runs, returns zero rows, and "no results" is
  indistinguishable from "no such fact in the graph". Never let an empty result set be rendered
  as a negative answer without saying which query produced it.
- **Write capability.** Generated Cypher can contain `DELETE`, `MERGE` or `SET`. Treat the
  generated query as untrusted input — execute it under a **read-only role enforced by the
  database**, not by an instruction in the prompt. This is the tool-permission rule from
  `SKILL.md` applied to a generated query language, and it is the failure with the largest blast
  radius.
- **Schema too large to prompt.** Past a certain size the schema stops fitting usefully; scope
  it to the subgraph the question touches, or route by question type first.

Use text2cypher when the question is a *structured aggregation or join* over a graph whose
schema you own. Do not use it to answer prose questions — a query language cannot summarize.

## Cost honesty: what a graph index actually costs

Indexing cost is not "an embedding pass, slightly more expensive". It is:

- one LLM pass per chunk for extraction, **plus** each gleaning round;
- one summarization call per node/edge description group;
- one summarization call per community, **at every level of the hierarchy**.

Vector ingestion, for comparison, is one cheap embedding call per chunk and no LLM calls at all.
The multiple is large, it is paid again on every full re-index, and it lands before a single
question has been asked.

**Corpus churn is the real bill.** Adding a document does not append neatly: it can change
entity descriptions, edges, community membership and therefore the summaries of every community
it touches. A corpus that changes daily turns the index into a recurring cost, and an index that
is not rebuilt answers global questions from last month's structure while sounding current.

Try the cheaper rungs first and say out loud why they failed:

1. Metadata filters plus aggregation over structured fields you already have.
2. A **summary index** — summarize each document once, retrieve over the summaries. This
   answers a surprising share of "themes" questions at a fraction of graph cost.
3. Hierarchical summarization over document clusters, without entity extraction.

| Situation | Verdict |
|---|---|
| Questions are lookup-shaped | Plain vector RAG. A graph buys nothing |
| Corpus fits in a context window | Summarize it directly; build no index at all |
| Corpus churns faster than you can re-index | Recurring bill; use vector RAG + periodic reports |
| Prose with few stable named entities | Extraction yields a weak graph; communities are noise |
| You already have a curated graph or relational DB | text2cypher / NL→SQL — do not re-derive it with an LLM |
| Global or thematic questions over a large private corpus | Graph global search — the case it exists for |
| Multi-hop joins over real entity relationships | Graph traversal or text2cypher |

Bring this table to the user *before* proposing a graph build. "It cannot answer that class of
question, and here is what the index costs" is the honest version of the pitch.

## Routing between retrievers

A system with more than one retriever needs something to choose between them. That choice is
the **routing** pattern and the answer check is the **evaluator-optimizer** pattern — both are
already specified with their costs and failure modes in `architectures.md`; only the route table
is graph-specific:

| Signal in the question | Route |
|---|---|
| Names a specific entity, asks for its detail | Vector RAG, or graph local search |
| Asks about the corpus as a whole, themes, patterns, "across all" | Graph global search |
| Asks for counts, rankings, or a join over attributes | text2cypher |
| Asks a lookup answerable by one passage | Vector RAG — the cheapest route that works |

One failure mode belongs here rather than in `architectures.md`, because it is specific to this
mix: **a misroute toward vector search is silent**. A global question sent to a vector retriever
returns a well-formed, well-cited answer of the wrong scope, whereas a misroute in the other
direction merely wastes money. Measure routing accuracy on its own labelled set — the routing
pattern's own rule — and bias the default toward the expensive route only for the question
shapes the table above marks global.

## Evaluation hooks

The two-stage discipline from `rag-pipeline.md` still applies, with one adjustment: **a global
question has no single gold passage**, so recall@k is undefined for it. Edge et al. evaluate
head-to-head with an LLM judge on qualities such as comprehensiveness and diversity of the
answers. That is a usable approach and it inherits every judge-bias caveat catalogued in
`evaluate-optimize-models/references/evaluation.md` — position bias, verbosity preference,
self-preference — so calibrate the judge against human ratings on a subsample before trusting a
comparison. For local search and text2cypher, the ordinary retrieval metrics still work, because
those modes do have gold targets.
