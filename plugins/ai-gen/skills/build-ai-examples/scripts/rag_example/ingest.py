"""Offline ingestion: load -> split -> embed -> store into Postgres/pgvector.

Run once per corpus change:  python ingest.py ./docs

Third-party imports live here rather than in chunking.py/retrieval.py so the
pure logic stays testable with nothing installed. Pin exact versions in
requirements.txt at build time -- look them up, do not trust remembered ones.
"""

from __future__ import annotations

import pathlib
import sys

import psycopg
from openai import OpenAI
from pgvector.psycopg import register_vector

from chunking import Chunk, split_text
from settings import load_settings

# The index is versioned by embedding-model ID: changing the model means
# re-embedding the whole corpus, which is a planned migration and not a config
# edit. Mixing vectors from two models degrades silently to noise.
SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks (
    id          bigserial PRIMARY KEY,
    source      text        NOT NULL,
    chunk_index int         NOT NULL,
    content     text        NOT NULL,
    model_id    text        NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    embedding   vector(%(dim)s) NOT NULL,
    UNIQUE (source, chunk_index, model_id)
);
"""


def load_documents(root: pathlib.Path) -> list[tuple[str, str]]:
    """Read a directory of .md/.txt files as (source, text) pairs.

    Deliberately the simplest possible loader. Real corpora are PDFs, HTML and
    tables, where extraction loses content *silently* -- eyeball the extracted
    text for every source type before building on top of it.
    """
    docs = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() in {".md", ".txt"} and path.is_file():
            docs.append((str(path.relative_to(root)), path.read_text(encoding="utf-8")))
    if not docs:
        raise SystemExit(f"no .md/.txt files found under {root}")
    return docs


def embed_batch(client: OpenAI, model: str, texts: list[str]) -> list[list[float]]:
    """Embed a batch. Query and corpus MUST use this same model and version."""
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def main(corpus_dir: str) -> None:
    settings = load_settings()
    client = OpenAI(base_url=settings.embedding_base_url, api_key=settings.embedding_api_key)

    chunks: list[Chunk] = []
    for source, text in load_documents(pathlib.Path(corpus_dir)):
        chunks.extend(
            split_text(
                text,
                source=source,
                chunk_size=settings.chunk_size,
                overlap=settings.chunk_overlap,
            )
        )
    print(f"{len(chunks)} chunks to embed")

    vectors: list[list[float]] = []
    for start in range(0, len(chunks), 64):
        batch = chunks[start : start + 64]
        vectors.extend(embed_batch(client, settings.embedding_model, [c.text for c in batch]))
        print(f"  embedded {min(start + 64, len(chunks))}/{len(chunks)}")

    with psycopg.connect(settings.database_url) as conn:
        register_vector(conn)
        conn.execute(SCHEMA, {"dim": len(vectors[0])})
        with conn.cursor() as cur:
            for chunk, vector in zip(chunks, vectors):
                cur.execute(
                    """
                    INSERT INTO chunks (source, chunk_index, content, model_id, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (source, chunk_index, model_id)
                    DO UPDATE SET content = EXCLUDED.content,
                                  embedding = EXCLUDED.embedding,
                                  ingested_at = now()
                    """,
                    (chunk.source, chunk.index, chunk.text, settings.embedding_model, vector),
                )
        conn.commit()
    print(f"stored {len(chunks)} chunks under model_id={settings.embedding_model}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "./docs")
