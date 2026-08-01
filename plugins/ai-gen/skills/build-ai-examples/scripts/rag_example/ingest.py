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
from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector

from chunking import Chunk, split_text
from settings import load_settings

# settings.py stays stdlib-only (a smoke_test.py check enforces this) and just
# reads os.environ -- something has to populate it from .env first. Anchored to
# this file's directory, not CWD, so `python ingest.py` works from anywhere.
load_dotenv(pathlib.Path(__file__).parent / ".env")

# Split from SCHEMA and applied first: pgvector.psycopg's register_vector() looks
# up the `vector` type's OID in the connected database, so it must run AFTER the
# extension exists -- on a fresh database, register-before-create raises
# "vector type not found in the database". Verified against a real container.
EXTENSION = "CREATE EXTENSION IF NOT EXISTS vector;"

# Full-text search needs no extension -- tsvector/GIN are core PostgreSQL, unlike the
# vector type above (verified against PostgreSQL's current full text search docs). The
# search config ('english') is baked into the generated column's expression below, the
# same way `dim` is baked into the vector column: a STORED generated column's expression
# is fixed at DDL time, not re-evaluated from an env var per query, so changing the
# language is a schema migration -- add a new column, backfill, cut over -- not a config
# edit, exactly the same discipline the embedding-model-ID comment states two lines down.
# ADD COLUMN IF NOT EXISTS makes this idempotent whether `chunks` is brand new (created
# moments earlier by build_schema) or already existed before this column did; either way
# PostgreSQL's docs are explicit that adding a STORED generated column rewrites the whole
# table, a real cost worth knowing about before running this against a large corpus.
FTS_COLUMN = (
    "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector "
    "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;"
)
FTS_INDEX = "CREATE INDEX IF NOT EXISTS chunks_content_tsv_idx ON chunks USING GIN (content_tsv);"


# The index is versioned by embedding-model ID: changing the model means
# re-embedding the whole corpus, which is a planned migration and not a config
# edit. Mixing vectors from two models degrades silently to noise.
def build_schema(dim: int) -> str:
    """DDL for the chunks table, with the vector dimension baked in.

    Postgres rejects a bound parameter as a type modifier ("vector(%(dim)s)")
    with "type modifiers must be simple constants or identifiers" -- DDL type
    parameters cannot be server-side bind parameters the way DML values can.
    Verified against a real container. `dim` is len(vectors[0]), an int from
    the embedding response, not user input; the isinstance check keeps it that
    way rather than trusting the call site.
    """
    if not isinstance(dim, int) or dim <= 0:
        raise ValueError(f"dim must be a positive int, got {dim!r}")
    return f"""
CREATE TABLE IF NOT EXISTS chunks (
    id          bigserial PRIMARY KEY,
    source      text        NOT NULL,
    chunk_index int         NOT NULL,
    content     text        NOT NULL,
    model_id    text        NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    embedding   vector({dim}) NOT NULL,
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
        conn.execute(EXTENSION)
        register_vector(conn)
        conn.execute(build_schema(len(vectors[0])))
        conn.execute(FTS_COLUMN)
        conn.execute(FTS_INDEX)
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
