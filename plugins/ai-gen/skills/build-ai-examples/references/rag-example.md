# Worked example: RAG over your own documents (pgvector + LangGraph)

Runnable code lives in `scripts/rag_example/`. It ingests a directory of
markdown/text files into Postgres/pgvector and answers questions through a LangGraph agent that
calls retrieval **as a tool**. The concepts behind each stage — and the failure mode of each —
are in `design-agent-architecture/references/rag-pipeline.md`; this file covers the build.

## Contents

- Run it
- Layout
- Five decisions worth explaining
- What the smoke test pins (this file's share, offline)
- Production deltas

## Run it

```bash
cd scripts/rag_example
cp .env.example .env          # fill in OPENROUTER_API_KEY -- get one at openrouter.ai
docker compose up -d          # Postgres + pgvector, with a healthcheck
ollama pull nomic-embed-text  # local embeddings; see the provider note below
pip install -r requirements.txt
python ingest.py ./docs       # load -> split -> embed -> store
python agent.py "what does the handbook say about refunds?"
```

**Getting the key:** create an account at <https://openrouter.ai>, open the API Keys section of
the dashboard, and create a key. It draws from your own OpenRouter balance per call — top up a
small amount before running this. Paste it into `.env` yourself; never paste it into a chat with
an AI assistant, and never commit the filled-in file (`.env` is gitignored repo-wide, `.env.example`
is the tracked template).

`ingest.py` and `agent.py` load `.env` themselves via `python-dotenv`, anchored to this
directory regardless of your current working directory — `settings.py` stays stdlib-only (see
"Pure logic is separated from framework wiring" below) and only reads `os.environ`; the
dotenv loading is what populates it. Without `python-dotenv` in `requirements.txt`, a filled-in
`.env` sitting next to the scripts does **nothing** — this was a real bug in an earlier version
of this example, found by actually running it, not by review.

**This has been run end to end against live services** (Ollama, a real Postgres/pgvector
container, and a real OpenRouter key) — not just the database layer. `ingest.py` embedded and
stored a small test corpus; `agent.py` retrieved the right chunk and answered with a citation,
e.g. *"customers may return unopened items within thirty days... [handbook.md#0]"*. One
non-blocking finding from that run: `langgraph.prebuilt.create_react_agent` is deprecated as of
LangGraph V1.0 in favor of `langchain.agents.create_agent`, planned for removal in V2.0. The
example still works today; if you hit a removal, that migration is the fix — verify the new
function's signature against LangChain's current docs before swapping it in, don't assume it's a
drop-in replacement.

**Hybrid retrieval's database layer has also been run against a real, genuinely fresh
`docker compose up` container** — not just reviewed. The fresh-database DDL path (`build_schema`
→ `FTS_COLUMN` → `FTS_INDEX`), an idempotent re-run of the FTS DDL on an already-migrated table,
and the migration path itself (dropping `content_tsv` to simulate a pre-hybrid table with rows
already in it, then re-running `FTS_COLUMN` and confirming all three existing rows backfill
correctly with no data loss) all passed. So did the property that matters: a query vector crafted
to match one synthetic chunk and a keyword query crafted to match a different one produced two
*disagreeing* rankings, and `reciprocal_rank_fusion` correctly surfaced both near the top while
ranking the chunk relevant to neither system last.

That same run found a real, non-obvious limitation, worth stating plainly. A first attempt queried
`search_docs`-style with a full natural-language question and got **zero** rows back from the
lexical side. `websearch_to_tsquery` ANDs every significant word in the query together by default
— confirmed directly against the container: `SELECT websearch_to_tsquery('english', 'What does
the ticket INC-4471 say about the return timeline?')` printed `'ticket' & 'inc' <-> '-4471' &
'say' & 'return' & 'timelin'` — and the target document contained none of "say", "return", or
"timeline", so the AND failed even though the document was an exact match for what the question
was actually asking about. A short, keyword-style query (`"INC-4471"`) found it immediately. This
is why `search_docs`'s docstring now tells the calling model to prefer short, specific phrases: it
is not a style preference, it is what makes the lexical half of the hybrid actually work.

## Layout

```
scripts/rag_example/
├── chunking.py        # pure: windowing with overlap + citation metadata
├── retrieval.py       # pure: cosine, top-k ranking, recall@k, reciprocal rank fusion
├── settings.py        # pure: env validation, fails at startup not first query
├── ingest.py          # framework: OpenAI-compatible embeddings + psycopg/pgvector
├── agent.py           # framework: LangGraph ReAct agent, retrieval as a tool
├── docker-compose.yml # pgvector/pgvector:pg16 with a healthcheck
├── .env.example       # every variable the code reads, none filled in
└── requirements.txt
```

## Five decisions worth explaining

### 1. Chat and embeddings come from different providers

OpenRouter's API reference documents chat completions; it does **not** document a
`/v1/embeddings` endpoint. So it cannot serve the retrieval half of RAG, and an example that
assumed one provider for both would not run. The example therefore takes:

- **chat** from OpenRouter (`ChatOpenAI` + `base_url`, the plugin's reference stack), and
- **embeddings** from any OpenAI-compatible embeddings endpoint, defaulting to a **local**
  Ollama — one paid key instead of two, and the corpus never leaves the host.

Both are env-configurable, so pointing embeddings at a hosted provider is a config change, not a
code change. Verify the endpoint situation against OpenRouter's current API reference before
repeating this claim to a user — provider surfaces change.

### 2. Retrieval is a tool, not a mandatory prefix

`agent.py` gives the model a `search_docs` tool instead of retrieving before every turn. The
difference matters: "hello" should not trigger a vector search, and a follow-up question may
need a second, differently-worded one. Retrieve-then-always-stuff is a RAG pipeline with a chat
skin; this is an agent that has RAG available. The cost is one extra model decision per turn, and
the risk is a model that forgets to search — which is why the system prompt makes the tool
mandatory for corpus questions and the loop is capped with `recursion_limit`.

### 3. Pure logic is separated from framework wiring

`chunking.py`, `retrieval.py` and `settings.py` import **only** the standard library. All
LangChain/psycopg/OpenAI imports live in `ingest.py` and `agent.py`. That is what lets
`plugins/ai-gen/tests/smoke_test.py` run with a bare interpreter — no services, no keys, no
network — and a test in the guard asserts the property so it cannot rot back.

This is the general shape worth teaching: the part with interesting semantics (windowing,
ranking, config validation) should not require a database to test.

### 4. The index is versioned by embedding-model ID

Every row stores `model_id`, and queries filter on it. Query and corpus vectors must come from
the same model and version — mixing them degrades silently to noise rather than erroring.
Changing the embedding model is therefore a planned re-ingestion, and the schema makes that
visible instead of leaving it as folklore.

### 5. Hybrid retrieval fuses two real rankings, not a keyword bolt-on

`search_docs` now runs **two** independent queries per call — the existing dense vector search,
plus a lexical one over a `content_tsv` column PostgreSQL maintains automatically — and merges
them with a real `reciprocal_rank_fusion` function in `retrieval.py` (Cormack, Clarke &
Büttcher, SIGIR 2009). This is a deliberate contrast with
`chapter_06/02_RAG_agent_hybrid.py` in a companion repository this plugin triaged: its book
explains reciprocal rank fusion in prose as the production default, but the script itself
implements an ad-hoc keyword scorer (`+10` exact phrase, `+2` per word) and delegates the merge
to "the agent's judgement" — no fusion function exists. Here, fusion is a tested, pure function,
not a hope, and the Chroma vector store that same script uses is deliberately not ported; this
plugin's store is pgvector throughout.

Four points worth being precise about:

- **This is FTS, not BM25, and the example says so.** `content_tsv tsvector GENERATED ALWAYS AS
  (to_tsvector('english', content)) STORED` plus a GIN index is core PostgreSQL — no extension
  required — ranked by `ts_rank_cd`. PostgreSQL's own documentation calls `ts_rank`/`ts_rank_cd`
  "only examples" of a ranking function, not BM25; BM25-style scoring is a separate extension
  (e.g. `pg_search`), not something core PostgreSQL claims to implement. Never copy one system's
  ranking-parameter vocabulary into the other's — see
  `design-agent-architecture/references/memory-vector-db.md`.
- **RRF needs no score normalization between the two rankings**, which is the entire reason it is
  usable here: a cosine distance and a `ts_rank_cd` score are not on comparable scales, and RRF
  never looks at either value — only the rank position each system assigned. `retrieval.py`'s
  `reciprocal_rank_fusion` is deliberately generic (it fuses ranked id lists, not vectors or
  scores) so the same function fuses two systems today and would fuse a third tomorrow.
- **The search config is baked in at schema time, like the vector dimension is.** `'english'` is
  part of the `GENERATED ALWAYS AS` expression, fixed when the column is created — not something
  an env var can change per query. Changing it is a schema migration (`ALTER TABLE ... ADD COLUMN
  IF NOT EXISTS`, verified against PostgreSQL's current docs to rewrite the table and backfill
  existing rows), the same discipline the embedding-model-ID versioning above already teaches,
  applied to text search instead of vectors.
- **`websearch_to_tsquery` was chosen over `to_tsquery`/`plainto_tsquery` because it takes raw,
  unsanitized text without raising a syntax error** — PostgreSQL's own documentation states this
  explicitly, and `query` here is whatever the calling model decided to search for, not a string
  an operator hand-wrote. The cost of that safety is documented in "Run it" above: it ANDs every
  significant term together, so it rewards a short query and can return nothing for a wordy one.

## What the smoke test pins (this file's share, offline)

`python tests/smoke_test.py` — 47 checks total (all four examples this plugin ships); 18 of them
are this file's own (the other three examples' shares are in `mcp-example.md`,
`reflexion-example.md` and `guardrail-example.md`). Run from the plugin root. Grouped:

| Checks | What breaks if they go |
|---|---|
| Files exist; pure modules import; **imports are stdlib-only** | The example stops being testable without a full install |
| Window count; overlap is exactly `overlap` words; short tail; `overlap=0` tiles losslessly | Chunking drifts and every retrieval number moves with it |
| Planted chunk ranks first; ties deterministic; cosine handles zero vectors and dimension mismatch | Ranking regressions, and unreproducible eval runs |
| Fusion ranks agreement-across-systems above a solo top hit; a lexical-only hit missing from the vector side still surfaces; ties break by id, not by insertion order; `k<=0` rejected | A hybrid retriever that quietly degrades to whichever system happened to run last, or an unreproducible eval |
| Settings reject `overlap >= chunk_size`; name the missing variable | Config errors surface at first query instead of at boot |
| `.env.example` covers every variable read; ships no filled-in secret; compose parses with a healthcheck | Silent misconfiguration, a leaked key, or `ingest.py` racing Postgres |

Each was verified by deliberately breaking it: an env var added to code but not to
`.env.example`, a `numpy` import added to `chunking.py`, and an off-by-one in the stride all
produced the expected failure.

**The Postgres/pgvector half of the live path has been run against a real container** (not just
reviewed): a genuinely fresh `docker compose up` database, the actual `SCHEMA`/`build_schema()`
DDL, the actual insert-with-upsert path, and the actual `<=>` ranking query from `search_docs`.
That exercise caught three real bugs the offline smoke test cannot see (it never touches a
database) — all three are fixed in the shipped code, and are worth naming because each is a
common enough pgvector/psycopg trap to recognize elsewhere:

1. `register_vector(conn)` was called **before** `CREATE EXTENSION IF NOT EXISTS vector` in both
   `ingest.py` and `agent.py`. `register_vector` looks up the `vector` type's OID, so on a
   genuinely fresh database — exactly what a first-time user's `docker compose up` produces — it
   raised `vector type not found in the database`. Fixed by creating the extension first.
2. `vector(%(dim)s)` as a bound parameter inside `CREATE TABLE` failed with `type modifiers must
   be simple constants or identifiers`: Postgres does not allow a server-side bind parameter as a
   DDL type modifier, only as a value. Fixed by building the DDL string with the (int-validated)
   dimension formatted in directly, in `build_schema()`.
3. Passing a plain Python list as the query vector to the `<=>` operator failed with `operator
   does not exist: vector <=> double precision[]`. An `INSERT` can infer the `vector` type from
   the target column, but a comparison has no column to infer from, so psycopg's default list
   adapter sends a bare array instead. Fixed by wrapping the query embedding in
   `pgvector.Vector(...)` before binding it, in `agent.py`.

**Still unverified, because it needs things this session does not have:** the embedding call
(Ollama is not installed here) and the OpenRouter chat call (needs the user's own key, and
spending against it is not this session's call to make). Both are still manual verification, not
CI — document them in the user's README rather than faking them in a test.

The hybrid retrieval layer added on top of this (the FTS column, its GIN index, the migration
path, and the fusion itself) was verified the same live way, against the same kind of genuinely
fresh container — see "Run it" above for what that run found, including a real limitation in how
`websearch_to_tsquery` handles a wordy query.

## Production deltas (state these with the example)

This is a teaching scaffold. Before it carries real traffic:

- **Tokenizer, not words.** The splitter windows on whitespace words so the example runs with
  nothing installed. Real chunk sizes must be measured in the *embedding model's* tokens, or
  chunks silently overflow its max sequence length and get truncated.
- **ANN index.** The example's query does an exact scan, deliberately: on a demo corpus that is
  the correct choice. Add an HNSW or IVFFlat index in pgvector once the scan is the *measured*
  bottleneck, and re-measure recall@k after — approximate search trades recall for speed, and the
  trade must be observed, not assumed. Which family, which build-time versus query-time knobs,
  and pgvector's exact parameter names are in
  `design-agent-architecture/references/memory-vector-db.md`.
- **Cross-encoder reranking on the fused result.** Hybrid retrieval (decision 5 above) fixes
  recall on rare identifiers; it does not rerank. RRF's naive score is still a proxy — for a
  precision-sensitive deployment, rerank the fused top-N with a cross-encoder before generation
  (`design-agent-architecture/references/rag-pipeline.md`'s "Advanced retrieval" section).
- **Read-side authorization.** This demo has one tenant, one trust level, and no ACLs. A corpus
  mixing confidentiality levels needs tenant/role filtering enforced in the SQL itself — a
  permissions problem on the index, not a prompt-injection problem, and this example does not
  implement it. See `design-agent-architecture/references/rag-pipeline.md`'s read-side
  authorization section: it is a different failure class from the retrieval-surface point below,
  and neither defends against the other.
- **A labelled retrieval set** of question→passage pairs, and recall@k measured *before* anyone
  touches the prompt. Without it, every later change is a guess
  (`evaluate-optimize-models/references/evaluation.md`).
- **Re-ingestion as a scheduled job** with a freshness metric; a stale index answers confidently
  from deleted documents.
- **Prompt injection through retrieved text.** Retrieved documents are data, not instructions —
  a corpus a user can write into is an instruction channel into your agent.
- **Ops:** retries with backoff, per-request cost logging, rate limiting, a fallback model chain,
  secrets in a cloud secret manager, and the compose password replaced (see
  `stack-langgraph-openrouter.md` and `deploy-ai-environments`).
