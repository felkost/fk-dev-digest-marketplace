"""Serving: a LangGraph agent with retrieval exposed as a tool.

Retriever-as-tool, not retrieve-then-always-stuff: the model decides whether a
question needs the corpus at all. That is the difference between an agent with
RAG and a RAG pipeline with a chat skin -- "hello" should not trigger a vector
search, and a follow-up may need a second, differently-worded one.

Run:  python agent.py "your question"
"""

from __future__ import annotations

import pathlib
import sys

import psycopg
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from openai import OpenAI
from pgvector import Vector
from pgvector.psycopg import register_vector

from retrieval import reciprocal_rank_fusion
from settings import load_settings

# settings.py stays stdlib-only (a smoke_test.py check enforces this) and just
# reads os.environ -- something has to populate it from .env first. Anchored to
# this file's directory, not CWD, so `python agent.py` works from anywhere.
# Must run before load_settings() below, which reads os.environ immediately.
load_dotenv(pathlib.Path(__file__).parent / ".env")

settings = load_settings()

# Embeddings and chat are separate clients against separate providers -- see the
# note in settings.py. Query and corpus must share one embedding model/version.
embed_client = OpenAI(base_url=settings.embedding_base_url, api_key=settings.embedding_api_key)

SYSTEM_PROMPT = """You answer strictly from the retrieved sources.

Rules:
- Use search_docs before answering anything about the corpus.
- Cite the source label in brackets after each claim, e.g. [handbook.md#3].
- If the sources do not contain the answer, say so plainly. Do not fill the gap
  from memory: an unsupported answer next to real citations is the worst
  failure mode this system has.
"""


@tool
def search_docs(query: str) -> str:
    """Search the ingested corpus. Use for any question about its content.

    Prefer a short, specific phrase (names, ids, key terms) over a full
    question: the lexical side of this search ANDs every significant word
    together, so a wordy query can fail to match a document that a short one
    would find.
    """
    vector = embed_client.embeddings.create(
        model=settings.embedding_model, input=[query]
    ).data[0].embedding

    with psycopg.connect(settings.database_url) as conn:
        # register_vector() looks up the `vector` type's OID -- must run after the
        # extension exists. Cheap no-op once ingest.py has already created it; kept
        # here too so agent.py does not depend on ingest.py having run first.
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        register_vector(conn)

        # Two independent rankings over the same rows. reciprocal_rank_fusion
        # (retrieval.py) needs no normalization between them despite the wholly
        # different scales of a cosine distance and a ts_rank_cd score -- that
        # is RRF's whole point, and why it is safe to fuse dense and lexical
        # results without inventing a way to compare the two scores directly.
        vector_rows = conn.execute(
            """
            SELECT id, source, chunk_index, content
            FROM chunks
            WHERE model_id = %s
            ORDER BY embedding <=> %s          -- pgvector cosine distance
            LIMIT %s
            """,
            # Vector(...) is required here, not optional: an INSERT can infer
            # `vector` from the target column's type, but this parameter has no
            # target column to infer from. An un-wrapped list is sent as
            # double precision[], and Postgres has no `vector <=> double
            # precision[]` operator -- verified against a real container.
            (settings.embedding_model, Vector(vector), settings.top_k),
        ).fetchall()

        # websearch_to_tsquery is PostgreSQL's own recommended constructor for
        # raw, unsanitized user text: unlike to_tsquery/plainto_tsquery it never
        # raises a syntax error, which matters because `query` here is whatever
        # the model decided to search for. ts_rank_cd additionally weighs how
        # close the matching lexemes sit together ("cover density"); PostgreSQL's
        # docs call both ts_rank and ts_rank_cd "only examples" of a ranking
        # function -- this is NOT BM25, and does not need to be, since fusion
        # below only consumes the resulting ORDER, never the score itself.
        fts_rows = conn.execute(
            """
            SELECT id, source, chunk_index, content
            FROM chunks
            WHERE model_id = %s
              AND content_tsv @@ websearch_to_tsquery('english', %s)
            ORDER BY ts_rank_cd(content_tsv, websearch_to_tsquery('english', %s)) DESC
            LIMIT %s
            """,
            (settings.embedding_model, query, query, settings.top_k),
        ).fetchall()

    by_id: dict[int, tuple[str, int, str]] = {}
    for doc_id, source, chunk_index, content in (*vector_rows, *fts_rows):
        by_id[doc_id] = (source, chunk_index, content)

    fused = reciprocal_rank_fusion(
        [[row[0] for row in vector_rows], [row[0] for row in fts_rows]]
    )
    if not fused:
        # An explicit empty result, not an empty string: the model must be able
        # to tell "nothing matched" from "the tool broke".
        return "NO_RESULTS: the corpus returned nothing for this query."
    return "\n\n".join(
        f"[{by_id[doc_id][0]}#{by_id[doc_id][1]}]\n{by_id[doc_id][2]}"
        for doc_id, _score in fused[: settings.top_k]
    )


def build_agent():
    model = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        model=settings.chat_model,
        temperature=0,
        timeout=30,
    )
    return create_react_agent(model, [search_docs], prompt=SYSTEM_PROMPT)


def main(question: str) -> None:
    agent = build_agent()
    result = agent.invoke(
        {"messages": [("user", question)]},
        # Cap the loop. An agent that can call a tool can loop forever calling it.
        config={"recursion_limit": 8},
    )
    print(result["messages"][-1].content)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "What is in this corpus?")
