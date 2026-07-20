# Worked example: RAG over your own documents (pgvector + LangGraph)

Runnable code lives in `scripts/rag_example/`. It ingests a directory of
markdown/text files into Postgres/pgvector and answers questions through a LangGraph agent that
calls retrieval **as a tool**. The concepts behind each stage — and the failure mode of each —
are in `design-agent-architecture/references/rag-pipeline.md`; this file covers the build.

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

## Layout

```
scripts/rag_example/
├── chunking.py        # pure: windowing with overlap + citation metadata
├── retrieval.py       # pure: cosine, top-k ranking, recall@k
├── settings.py        # pure: env validation, fails at startup not first query
├── ingest.py          # framework: OpenAI-compatible embeddings + psycopg/pgvector
├── agent.py           # framework: LangGraph ReAct agent, retrieval as a tool
├── docker-compose.yml # pgvector/pgvector:pg16 with a healthcheck
├── .env.example       # every variable the code reads, none filled in
└── requirements.txt
```

## Four decisions worth explaining

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

## What the smoke test pins (14 checks, offline)

`python tests/smoke_test.py` from the plugin root. Grouped:

| Checks | What breaks if they go |
|---|---|
| Files exist; pure modules import; **imports are stdlib-only** | The example stops being testable without a full install |
| Window count; overlap is exactly `overlap` words; short tail; `overlap=0` tiles losslessly | Chunking drifts and every retrieval number moves with it |
| Planted chunk ranks first; ties deterministic; cosine handles zero vectors and dimension mismatch | Ranking regressions, and unreproducible eval runs |
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

## Production deltas (state these with the example)

This is a teaching scaffold. Before it carries real traffic:

- **Tokenizer, not words.** The splitter windows on whitespace words so the example runs with
  nothing installed. Real chunk sizes must be measured in the *embedding model's* tokens, or
  chunks silently overflow its max sequence length and get truncated.
- **ANN index.** The example's query does an exact scan. Add an HNSW or IVFFlat index in
  pgvector once the corpus grows, and re-measure recall@k after — approximate search trades
  recall for speed, and the trade must be observed, not assumed.
- **Hybrid search.** Dense vectors miss exact identifiers and rare terms; add keyword/BM25 and
  fuse (see `design-agent-architecture/references/memory-vector-db.md`).
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
