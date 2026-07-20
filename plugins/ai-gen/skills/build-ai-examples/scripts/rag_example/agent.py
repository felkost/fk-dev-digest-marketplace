"""Serving: a LangGraph agent with retrieval exposed as a tool.

Retriever-as-tool, not retrieve-then-always-stuff: the model decides whether a
question needs the corpus at all. That is the difference between an agent with
RAG and a RAG pipeline with a chat skin -- "hello" should not trigger a vector
search, and a follow-up may need a second, differently-worded one.

Run:  python agent.py "your question"
"""

from __future__ import annotations

import sys

import psycopg
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from openai import OpenAI
from pgvector.psycopg import register_vector

from settings import load_settings

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
    """Search the ingested corpus. Use for any question about its content."""
    vector = embed_client.embeddings.create(
        model=settings.embedding_model, input=[query]
    ).data[0].embedding

    with psycopg.connect(settings.database_url) as conn:
        register_vector(conn)
        rows = conn.execute(
            """
            SELECT source, chunk_index, content
            FROM chunks
            WHERE model_id = %s
            ORDER BY embedding <=> %s          -- pgvector cosine distance
            LIMIT %s
            """,
            (settings.embedding_model, vector, settings.top_k),
        ).fetchall()

    if not rows:
        # An explicit empty result, not an empty string: the model must be able
        # to tell "nothing matched" from "the tool broke".
        return "NO_RESULTS: the corpus returned nothing for this query."
    return "\n\n".join(f"[{src}#{idx}]\n{content}" for src, idx, content in rows)


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
