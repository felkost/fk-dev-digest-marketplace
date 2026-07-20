"""Offline smoke test for the RAG example's logic and its configuration.

Runs with a bare interpreter: no network, no API keys, no Postgres, no
langchain/langgraph installed. That is possible because the example keeps its
pure logic (chunking.py, retrieval.py, settings.py) free of third-party imports
and puts the framework wiring in ingest.py/agent.py -- check 9 below is what
keeps that property true.

What it pins:
  1-3. the modules import, and import nothing that needs installing;
  4-6. the splitter's window count, overlap and short tail;
  7-9. ranking: a planted chunk is retrieved first, ties are deterministic,
       cosine handles zero vectors and dimension mismatch;
 10-11. settings validation rejects contradictory chunk config;
 12-14. .env.example covers every variable the code reads, ships no filled-in
       secret, and the compose file parses.

Run:  python tests/smoke_test.py     (exit code 0 = all passed)

Console note: this box's console is cp1251, so output is ASCII-safe.
"""

from __future__ import annotations

import ast
import os
import pathlib
import re
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "skills" / "build-ai-examples" / "scripts" / "rag_example"
sys.path.insert(0, str(EXAMPLE))

RESULTS: list[tuple[str, bool, str]] = []


def say(s: str) -> None:
    sys.stdout.write(s.encode("ascii", "replace").decode("ascii") + "\n")


def check(name: str):
    def deco(fn):
        try:
            fn()
            RESULTS.append((name, True, ""))
            say(f"PASS  {name}")
        except Exception as e:  # noqa: BLE001
            RESULTS.append((name, False, f"{type(e).__name__}: {e}"))
            say(f"FAIL  {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
    return deco


# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #

class StubEmbedder:
    """Deterministic bag-of-words vectors. No network, no key, no model.

    This is the seam retrieval.Embedder exists for: the ranking code under test
    is identical in production; only the vector source changes.
    """

    def __init__(self, vocab: list[str]) -> None:
        self.vocab = vocab

    def embed(self, texts):
        out = []
        for t in texts:
            words = re.findall(r"[a-z]+", t.lower())
            out.append([float(words.count(v)) for v in self.vocab])
        return out


# --------------------------------------------------------------------------- #
# 1-3. Imports, and the offline-testability property
# --------------------------------------------------------------------------- #

@check("example directory exists with the expected files")
def _():
    for name in ("chunking.py", "retrieval.py", "settings.py", "ingest.py",
                 "agent.py", "docker-compose.yml", ".env.example", "requirements.txt"):
        assert (EXAMPLE / name).exists(), f"missing {name}"


@check("pure modules import with no third-party packages installed")
def _():
    import chunking  # noqa: F401
    import retrieval  # noqa: F401
    import settings  # noqa: F401


STDLIB_OK = {
    "__future__", "math", "os", "re", "sys", "json", "pathlib", "typing",
    "dataclasses", "collections", "itertools", "functools", "datetime",
}


@check("pure modules import ONLY stdlib (keeps this test runnable offline)")
def _():
    for mod in ("chunking.py", "retrieval.py", "settings.py"):
        tree = ast.parse((EXAMPLE / mod).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for n in names:
                assert n in STDLIB_OK, (
                    f"{mod} imports third-party '{n}'; move it to ingest.py/agent.py "
                    "or this smoke test stops running offline"
                )


# --------------------------------------------------------------------------- #
# 4-6. Splitting
# --------------------------------------------------------------------------- #

@check("splitter produces the expected number of windows")
def _():
    from chunking import split_words
    words = [f"w{i}" for i in range(10)]
    # stride = 4 - 1 = 3 -> windows start at 0, 3, 6
    assert len(split_words(words, chunk_size=4, overlap=1)) == 3


@check("consecutive chunks overlap by exactly `overlap` words")
def _():
    from chunking import split_words
    words = [f"w{i}" for i in range(30)]
    size, overlap = 6, 2
    wins = split_words(words, chunk_size=size, overlap=overlap)
    for a, b in zip(wins, wins[1:]):
        if len(a) < size:
            continue  # short tail has no successor to overlap with
        assert a[-overlap:] == b[:overlap], f"overlap broken between {a} and {b}"


@check("final window is short, not padded; overlap=0 tiles without loss")
def _():
    from chunking import split_words, Chunk  # noqa: F401
    from chunking import split_text
    words = [f"w{i}" for i in range(11)]
    wins = split_words(words, chunk_size=4, overlap=1)
    assert len(wins[-1]) == 2, wins[-1]
    # overlap=0 must reproduce the input exactly, losing nothing
    flat = [w for win in split_words(words, chunk_size=4, overlap=0) for w in win]
    assert flat == words
    # and the public API carries citation metadata through
    chunks = split_text("a b c d e f", source="doc.md", chunk_size=2, overlap=0)
    assert [c.index for c in chunks] == [0, 1, 2]
    assert all(c.source == "doc.md" for c in chunks)


# --------------------------------------------------------------------------- #
# 7-9. Ranking
# --------------------------------------------------------------------------- #

@check("planted relevant chunk is retrieved first")
def _():
    from retrieval import rank
    vocab = ["refund", "policy", "shipping", "warranty", "cat"]
    embedder = StubEmbedder(vocab)
    corpus = [
        "shipping times vary by region",
        "the refund policy allows returns within thirty days",  # planted
        "warranty covers manufacturing defects",
        "a cat sat on a mat",
    ]
    qv = embedder.embed(["what is the refund policy"])[0]
    ranked = rank(qv, embedder.embed(corpus), top_k=2)
    assert ranked[0][0] == 1, f"expected chunk 1 first, got {ranked}"
    assert ranked[0][1] > ranked[1][1], "top hit must outscore the runner-up"


@check("ranking is deterministic on ties and respects top_k")
def _():
    from retrieval import rank
    vecs = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]
    ranked = rank([1.0, 0.0], vecs, top_k=2)
    assert [i for i, _ in ranked] == [0, 1], f"ties must break by index, got {ranked}"
    assert len(rank([1.0, 0.0], vecs, top_k=99)) == 3, "top_k > corpus must not error"


@check("cosine handles zero vectors and rejects dimension mismatch")
def _():
    from retrieval import cosine, recall_at_k
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0, "zero vector must not divide by zero"
    assert abs(cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
    try:
        cosine([1.0], [1.0, 2.0])
    except ValueError:
        pass
    else:
        raise AssertionError("dimension mismatch must raise")
    assert recall_at_k([1, 5], {1, 2}) == 0.5


# --------------------------------------------------------------------------- #
# 10-11. Settings validation
# --------------------------------------------------------------------------- #

@check("settings reject overlap >= chunk_size")
def _():
    import settings as S
    saved = dict(os.environ)
    try:
        os.environ.update(
            OPENROUTER_API_KEY="x", DATABASE_URL="postgresql://x",
            CHUNK_SIZE="10", CHUNK_OVERLAP="10",
        )
        try:
            S.load_settings()
        except RuntimeError:
            pass
        else:
            raise AssertionError("overlap == chunk_size must be rejected")
    finally:
        os.environ.clear()
        os.environ.update(saved)


@check("settings fail loudly on a missing required variable")
def _():
    import settings as S
    saved = dict(os.environ)
    try:
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ["DATABASE_URL"] = "postgresql://x"
        try:
            S.load_settings()
        except RuntimeError as e:
            assert "OPENROUTER_API_KEY" in str(e), "error must name the missing variable"
        else:
            raise AssertionError("missing required variable must raise")
    finally:
        os.environ.clear()
        os.environ.update(saved)


# --------------------------------------------------------------------------- #
# 12-14. Configuration files
# --------------------------------------------------------------------------- #

def _env_example_keys() -> set[str]:
    keys = set()
    for line in (EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


@check(".env.example covers every variable the code reads")
def _():
    read = set()
    for py in sorted(EXAMPLE.glob("*.py")):
        src = py.read_text(encoding="utf-8")
        read |= set(re.findall(r"os\.environ\.get\(\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"os\.environ\[\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"os\.getenv\(\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"_require\(\s*[\"']([A-Z_]+)[\"']", src))
    missing = read - _env_example_keys()
    assert not missing, f".env.example is missing: {sorted(missing)}"


@check(".env.example ships no filled-in secret")
def _():
    for line in (EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (p.strip() for p in line.split("=", 1))
        if any(m in key for m in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            assert value in ("", "not-needed-for-local"), (
                f"{key} looks filled in ({value!r}) -- .env.example must ship blank"
            )


@check("docker-compose.yml parses and exposes a pgvector service")
def _():
    text = (EXAMPLE / "docker-compose.yml").read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        # PyYAML is not guaranteed on every box; fall back to a structural check
        # rather than silently skipping the file entirely.
        assert "services:" in text and "pgvector" in text
        return
    doc = yaml.safe_load(text)
    assert "services" in doc, "compose file has no services"
    images = [s.get("image", "") for s in doc["services"].values()]
    assert any("pgvector" in i for i in images), f"no pgvector image in {images}"
    db = doc["services"]["db"]
    assert "healthcheck" in db, "db needs a healthcheck or ingest.py races the server"


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    say("")
    say("=" * 60)
    say(f"{len(RESULTS) - n_fail}/{len(RESULTS)} checks passed")
    if n_fail:
        say("FAILURES:")
        for name, ok, msg in RESULTS:
            if not ok:
                say(f"  - {name}: {msg}")
        sys.exit(1)
    sys.exit(0)
