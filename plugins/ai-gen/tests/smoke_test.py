"""Offline smoke test for the build-ai-examples scripts' logic and config.

Runs with a bare interpreter: no network, no API keys, no Postgres, no
mcp/langchain/langgraph installed. That is possible because each example
keeps its pure logic free of third-party imports and puts the framework
wiring in separate files -- check 9 below is what keeps rag_example's half
of that property true (mcp_example has no framework-importing pure module to
guard, since journal.py is its only pure module and check 17 covers it).

What it pins, rag_example (pgvector + LangGraph RAG, hybrid vector + full-text):
  1-3. the modules import, and import nothing that needs installing;
  4-6. the splitter's window count, overlap and short tail;
  7-9. ranking: a planted chunk is retrieved first, ties are deterministic,
       cosine handles zero vectors and dimension mismatch;
 10-13. reciprocal_rank_fusion: agreement across systems beats being #1 in
       just one, a lexical-only hit missing from the vector side still
       surfaces, ties break deterministically by ascending id, k<=0 rejected;
 14-15. settings validation rejects contradictory chunk config;
 16-18. .env.example covers every variable the code reads, ships no filled-in
       secret, and the compose file parses.

What it pins, mcp_example (MCP server + LangGraph agent -- the *offline* tier
only; the live stdio round-trip is a separate check, see
references/mcp-example.md, because it needs `mcp` installed and a real
subprocess, which breaks the bare-interpreter promise above):
 19-21. the journal module imports, and imports nothing that needs installing;
 22-24. note logic: sequential ids, blank text rejected, an unknown id reads
       as None rather than raising;
 25.   an empty journal reports itself as empty instead of "";
 26-27. .env.example covers every variable agent.py reads and ships no
       filled-in secret.

What it pins, reflexion_example (solver-critic Reflexion loop in LangGraph --
this example has no free live tier the way mcp_example's subprocess
round-trip does, since the only thing left once the loop's control flow is
pure is an actual model call; see references/reflexion-example.md):
 28.   the directory exists with the expected files;
 29-30. reflexion_core imports, and imports nothing that needs installing;
 31.   numeric extraction avoids the book's "126 contains 26" substring trap;
 32.   the checker does not fall for "incorrect" containing "correct";
 33.   the success predicate is derived from the current task, never a
       leftover global -- two tasks built from the same factory never accept
       each other's answers;
 34.   run_reflexion stops the instant a check passes, not before and not after;
 35.   hints accumulate by exactly one per failed attempt and reach solve();
 36.   run_reflexion halts at max_attempts when the task is never solved;
 37-38. .env.example covers every variable agent.py reads and ships no
       filled-in secret.

What it pins, guardrail_example (deterministic pass-off guardrail gating a
two-agent handoff in LangGraph; see references/guardrail-example.md):
 39.   the directory exists with the expected files;
 40-41. guardrail_core imports, and imports nothing that needs installing;
 42.   the polarity test -- the guardrail blocks a thin plan AND approves a
       detailed one, the one direction chapter_04/09_agent_passoff_guardrails.py
       would have failed;
 43.   a long-enough plan missing one required section still blocks, named
       specifically -- length alone is not sufficient;
 44.   attempt_passoff never leaks next_stage_input on a blocked plan;
 45.   interleaved reviews of different plans never contaminate each other --
       no module-level state to race, unlike chapter_07/06's `_last_context`;
 46-47. .env.example covers every variable agent.py reads and ships no
       filled-in secret.

What it pins, loop_example (Layer-2 research loop harness -- the layered stop
gate agent-loop.md specifies; the published counterpart, chapter_09/04, ships
three of its five promised stop conditions and executes at import time, which
is exactly what checks 48 and 51-55 exist to forbid; see
references/loop-example.md):
 48.   the directory exists with the expected files;
 49.   loop_core imports without executing anything -- no module-level call
       of the loop, no import-time environ read (AST-verified);
 50.   loop_core imports ONLY stdlib;
 51.   two near-identical summaries halt the loop with stop == "stagnation"
       and the third exploration never runs;
 52.   the follow-up queue de-duplicates across case/punctuation and refuses
       re-entry even after the question was popped;
 53.   order="breadth" vs "depth" provably changes traversal order;
 54.   the cost cap stops a never-stagnating, always-branching explorer and
       the run record names "cost_cap";
 55.   the wall-clock cap fires via the injected clock, deterministically;
 56.   the offload log returns an id plus a bounded digest and fetch(id)
       still returns the original;
 57.   the writer receives only accumulated findings -- raw observations
       never cross the explorer/writer boundary;
 58-59. .env.example covers every variable agent.py reads and ships no
       filled-in secret.

What it pins, tdad_example (Test-Driven Agent Development harness -- the
normalizing evaluator, the grounding check that takes context explicitly, and
defect localization evaluate-optimize-models/references/agent-tdad.md
specifies; the motivating bug is chapter_07/06_RAG_grounding_with_
guardrails.py's module-level `_last_context`, reproduced by checks 64-65 and
fixed by the explicit-argument signature; see references/tdad-example.md):
 60.   the directory exists with the expected files;
 61.   harness_core imports without executing anything, and imports ONLY
       stdlib;
 62.   exact_match("Photons.", "photons") is True -- the normalizing-
       evaluator case the reference names by name;
 63.   polarity -- a context-drawn answer is grounded, a distinctively
       off-context answer is not;
 64.   two AccumulatingContext instances never contaminate each other's
       is_grounded result under interleaved add()/snapshot() calls;
 65.   an answer citing only the first of two searches is NOT grounded
       against the second search's content alone, but IS grounded against
       the full accumulated snapshot;
 66.   a stub passing 3/5 times reports pass_rate == 0.6 over n=5, not a
       false clean pass;
 67-69. classify_failure resolves "evaluator_bug", "instruction_bug" and
       "capability_gap" from three synthetic cases;
 70.   escalate_fix_tier moves one ladder step at a time and raises past
       "model";
 71.   retry_ceiling_action returns "retry" under the cap, the named policy
       at the cap, and raises on an unrecognized policy;
 72-73. .env.example covers every variable agent.py reads and ships no
       filled-in secret.

What it pins, reliability_example (the time-budget/fallback/circuit-breaker/
graceful-degradation ladder, and the idempotency contrast
deploy-ai-environments/references/serving-release.md specifies; the
motivating bug is chapter_08/06_idempotent_key_example.py's argument-hash-only
cache, reproduced by check 81 and fixed by ArgHashCache vs IdempotencyCache;
see references/reliability-example.md):
 74.   the directory exists with the expected files;
 75.   reliability_core imports without executing anything, and imports ONLY
       stdlib;
 76.   a successful primary never touches any fallback;
 77.   a primary exceeding its time budget falls back, and the fallback's
       success is what the result reports;
 78.   every rung failing returns outcome == "degraded" with the supplied
       value, never an unhandled exception;
 79.   the circuit breaker opens after the failure threshold and sheds load
       (outcome == "circuit_open") without calling primary while open;
 80.   a successful HALF_OPEN probe closes the breaker; a failed probe
       reopens it immediately, without waiting to re-count failures;
 81.   the idempotency contrast -- two different operation_ids with
       IDENTICAL arguments both execute under IdempotencyCache, but collapse
       into one execution under ArgHashCache, reproducing the book's bug on
       purpose;
 82.   the SAME operation_id called twice executes the underlying function
       once under IdempotencyCache -- the cache hit path;
 83-84. .env.example covers every variable agent.py reads and ships no
       filled-in secret.

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
MCP_EXAMPLE = ROOT / "skills" / "build-ai-examples" / "scripts" / "mcp_example"
REFLEXION_EXAMPLE = ROOT / "skills" / "build-ai-examples" / "scripts" / "reflexion_example"
GUARDRAIL_EXAMPLE = ROOT / "skills" / "build-ai-examples" / "scripts" / "guardrail_example"
LOOP_EXAMPLE = ROOT / "skills" / "build-ai-examples" / "scripts" / "loop_example"
TDAD_EXAMPLE = ROOT / "skills" / "build-ai-examples" / "scripts" / "tdad_example"
RELIABILITY_EXAMPLE = ROOT / "skills" / "build-ai-examples" / "scripts" / "reliability_example"
sys.path.insert(0, str(EXAMPLE))
sys.path.insert(0, str(MCP_EXAMPLE))
sys.path.insert(0, str(REFLEXION_EXAMPLE))
sys.path.insert(0, str(GUARDRAIL_EXAMPLE))
sys.path.insert(0, str(LOOP_EXAMPLE))
sys.path.insert(0, str(TDAD_EXAMPLE))
sys.path.insert(0, str(RELIABILITY_EXAMPLE))

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
# 10-13. Reciprocal rank fusion (hybrid vector + full-text retrieval)
# --------------------------------------------------------------------------- #

@check("fusion ranks a document both systems agree on above one only the vector side likes")
def _():
    from retrieval import reciprocal_rank_fusion
    # doc 9 is #2 in BOTH rankings; doc 7 is #1 in vector only, doc 8 is #1 in
    # FTS only. Agreement across systems must outrank either solo top hit --
    # the property Cormack, Clarke & Buttcher's paper names as RRF's reason to
    # exist ("one or two systems that rank a document highly can substantially
    # improve its rank relative to the more popular documents"). doc 9
    # deliberately has the LARGEST id of the three: a broken fusion that
    # dropped the `k` damping constant makes rank-1-once and rank-2-twice
    # score IDENTICALLY (1/1 == 1/2 + 1/2), which this check would silently
    # pass if the ascending-id tie-break happened to favor 9 anyway -- caught
    # by mutation testing, fixed by picking ids where it cannot.
    vector_ranking = [7, 9, 4]
    fts_ranking = [8, 9, 5]
    fused = reciprocal_rank_fusion([vector_ranking, fts_ranking])
    assert fused[0][0] == 9, f"the doc both systems agree on must win, got {fused}"


@check("fusion surfaces a lexical-only hit the vector ranking never returned")
def _():
    from retrieval import reciprocal_rank_fusion
    # The "our RAG cannot find ticket INC-4471" failure mode hybrid retrieval
    # exists to fix: a rare identifier the dense side never retrieves at all
    # must still reach the fused result through the FTS side alone -- unlike
    # the book's ad-hoc keyword scorer, this is an actual fusion function, not
    # a merge left to the agent's judgement.
    vector_ranking = [100, 200, 300]  # ticket id never retrieved by embedding
    fts_ranking = [777]               # exact keyword match, nothing else
    fused = reciprocal_rank_fusion([vector_ranking, fts_ranking])
    ids = [doc_id for doc_id, _score in fused]
    assert 777 in ids, "a lexical-only hit must still appear in the fused list"


@check("fusion breaks ties by ascending id, not by insertion order")
def _():
    from retrieval import reciprocal_rank_fusion
    # Two disjoint rankings where every position ties in score -- an unstable
    # fusion makes a retrieval eval unreproducible, the same concern rank()'s
    # own tie-break test guards above. The higher ids are listed FIRST on
    # purpose: Python's sorted() is stable, so a fusion that merely forgot the
    # id tie-break (sorting by score alone) would pass a naive version of this
    # check by silently falling back to dict-insertion order -- this ordering
    # was verified by deliberately reverting to a score-only sort and
    # confirming it flips the result to [30, 10, 40, 20] before being fixed.
    fused = reciprocal_rank_fusion([[30, 40], [10, 20]])
    assert [doc_id for doc_id, _ in fused] == [10, 30, 20, 40], fused


@check("fusion rejects a non-positive k")
def _():
    from retrieval import reciprocal_rank_fusion
    try:
        reciprocal_rank_fusion([[1, 2]], k=0)
    except ValueError:
        pass
    else:
        raise AssertionError("k <= 0 must be rejected")


# --------------------------------------------------------------------------- #
# 14-15. Settings validation
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
# 16-18. Configuration files
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
# 19-21. mcp_example: imports, and the offline-testability property
# --------------------------------------------------------------------------- #

@check("mcp_example directory exists with the expected files")
def _():
    for name in ("journal.py", "server.py", "agent.py", "test_live_stdio.py",
                 ".env.example", "requirements.txt"):
        assert (MCP_EXAMPLE / name).exists(), f"missing {name}"


@check("journal module imports with no third-party packages installed")
def _():
    import journal  # noqa: F401


@check("journal module imports ONLY stdlib (keeps this test runnable offline)")
def _():
    tree = ast.parse((MCP_EXAMPLE / "journal.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            continue
        for n in names:
            assert n in STDLIB_OK, (
                f"journal.py imports third-party '{n}'; move it to server.py/agent.py "
                "or this smoke test stops running offline"
            )


# --------------------------------------------------------------------------- #
# 22-25. mcp_example: note logic
# --------------------------------------------------------------------------- #

@check("add() assigns sequential ids and strips whitespace")
def _():
    from journal import Journal
    j = Journal()
    first = j.add("  first note  ")
    second = j.add("second note")
    assert (first.id, first.text) == (1, "first note")
    assert second.id == 2, "ids must be sequential across instances of one journal"


@check("add() rejects blank text")
def _():
    from journal import Journal
    j = Journal()
    try:
        j.add("   ")
    except ValueError:
        pass
    else:
        raise AssertionError("blank text must raise ValueError, not silently store")


@check("get() distinguishes a known id from an unknown one")
def _():
    from journal import Journal
    j = Journal()
    note = j.add("track me")
    assert j.get(note.id) == note
    assert j.get(note.id + 1) is None, "an unknown id must read as None, not raise"


@check("format_all() names emptiness instead of returning an empty string")
def _():
    from journal import Journal
    j = Journal()
    assert j.format_all() == "(journal is empty)"
    j.add("one")
    assert "(journal is empty)" not in j.format_all()
    assert j.list_all() == [j.get(1)]


# --------------------------------------------------------------------------- #
# 26-27. mcp_example: configuration file
# --------------------------------------------------------------------------- #

def _mcp_env_example_keys() -> set[str]:
    keys = set()
    for line in (MCP_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


@check(".env.example (mcp_example) covers every variable agent.py reads")
def _():
    read = set()
    for py in sorted(MCP_EXAMPLE.glob("*.py")):
        src = py.read_text(encoding="utf-8")
        read |= set(re.findall(r"os\.environ\.get\(\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"os\.environ\[\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"os\.getenv\(\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"_require\(\s*[\"']([A-Z_]+)[\"']", src))
    missing = read - _mcp_env_example_keys()
    assert not missing, f".env.example (mcp_example) is missing: {sorted(missing)}"


@check(".env.example (mcp_example) ships no filled-in secret")
def _():
    for line in (MCP_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (p.strip() for p in line.split("=", 1))
        if any(m in key for m in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            assert value in ("", "not-needed-for-local"), (
                f"{key} looks filled in ({value!r}) -- .env.example must ship blank"
            )


# --------------------------------------------------------------------------- #
# 28-30. reflexion_example: files exist, and the offline-testability property
# --------------------------------------------------------------------------- #

@check("reflexion_example directory exists with the expected files")
def _():
    for name in ("reflexion_core.py", "agent.py", ".env.example", "requirements.txt"):
        assert (REFLEXION_EXAMPLE / name).exists(), f"missing {name}"


@check("reflexion_core module imports with no third-party packages installed")
def _():
    import reflexion_core  # noqa: F401


@check("reflexion_core module imports ONLY stdlib (keeps this test runnable offline)")
def _():
    tree = ast.parse((REFLEXION_EXAMPLE / "reflexion_core.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            continue
        for n in names:
            assert n in STDLIB_OK, (
                f"reflexion_core.py imports third-party '{n}'; move it to agent.py "
                "or this smoke test stops running offline"
            )


# --------------------------------------------------------------------------- #
# 31-33. The anti-oracle checker: the two substring traps, and non-leakage
# --------------------------------------------------------------------------- #

@check("numeric extraction avoids the book's '126 contains 26' substring trap")
def _():
    from reflexion_core import make_arithmetic_task
    task = make_arithmetic_task("how many days", expected=26)
    result = task.check("The trip takes 126 days total.")
    assert result.passed is False, "126 must not read as containing 26"
    assert task.check("The trip takes 26 days total.").passed is True


@check("checker does not fall for the book's 'incorrect contains correct' substring trap")
def _():
    from reflexion_core import make_arithmetic_task
    task = make_arithmetic_task("how many widgets", expected=45)
    # A naive `"correct" in answer.lower()` check -- the book's second,
    # leftover condition -- would wrongly pass this: "incorrect" contains
    # "correct" as a substring, and there is no valid number here at all.
    result = task.check("That is incorrect.")
    assert result.passed is False, "'incorrect' must not satisfy a 'correct' in answer check"
    assert "No number found" in result.feedback


@check("success predicate is derived from the current task, never a leftover global")
def _():
    from reflexion_core import make_arithmetic_task
    task_a = make_arithmetic_task("task A", expected=26)
    task_b = make_arithmetic_task("task B", expected=45)
    assert task_a.check("26").passed is True
    assert task_b.check("26").passed is False, "task B must not accept task A's leftover answer"
    assert task_b.check("45").passed is True


# --------------------------------------------------------------------------- #
# 34-36. The loop: stopping condition, hint accumulation, attempt cap
# --------------------------------------------------------------------------- #

@check("run_reflexion stops as soon as a check passes")
def _():
    from reflexion_core import make_arithmetic_task, run_reflexion
    task = make_arithmetic_task("t", expected=10)
    answers = iter(["9", "10", "999"])  # a third call must never happen
    outcome = run_reflexion(task, solve=lambda prompt, hints: next(answers), max_attempts=5)
    assert outcome.succeeded is True
    assert outcome.stop_reason == "solved"
    assert len(outcome.attempts) == 2, "must stop at the passing attempt, not run to the cap"


@check("hints accumulate by exactly one per failed attempt and reach solve()")
def _():
    from reflexion_core import make_arithmetic_task, run_reflexion
    task = make_arithmetic_task("t", expected=999)  # unreachable by the stub below
    seen_hint_counts: list[int] = []

    def solve(prompt: str, hints: tuple[str, ...]) -> str:
        seen_hint_counts.append(len(hints))
        return "0"  # always wrong

    outcome = run_reflexion(task, solve=solve, max_attempts=3)
    assert seen_hint_counts == [0, 1, 2], f"hint count must grow by one each attempt, got {seen_hint_counts}"
    assert len(outcome.attempts) == 3
    assert all(not a.passed for a in outcome.attempts)


@check("run_reflexion halts at max_attempts when the task is never solved")
def _():
    from reflexion_core import make_arithmetic_task, run_reflexion
    task = make_arithmetic_task("t", expected=999)
    outcome = run_reflexion(task, solve=lambda prompt, hints: "0", max_attempts=3)
    assert outcome.succeeded is False
    assert outcome.stop_reason == "attempt_cap"
    assert len(outcome.attempts) == 3


# --------------------------------------------------------------------------- #
# 37-38. reflexion_example: configuration file
# --------------------------------------------------------------------------- #

def _reflexion_env_example_keys() -> set[str]:
    keys = set()
    for line in (REFLEXION_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


@check(".env.example (reflexion_example) covers every variable agent.py reads")
def _():
    read = set()
    for py in sorted(REFLEXION_EXAMPLE.glob("*.py")):
        src = py.read_text(encoding="utf-8")
        read |= set(re.findall(r"os\.environ\.get\(\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"os\.environ\[\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"os\.getenv\(\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"_require\(\s*[\"']([A-Z_]+)[\"']", src))
    missing = read - _reflexion_env_example_keys()
    assert not missing, f".env.example (reflexion_example) is missing: {sorted(missing)}"


@check(".env.example (reflexion_example) ships no filled-in secret")
def _():
    for line in (REFLEXION_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (p.strip() for p in line.split("=", 1))
        if any(m in key for m in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            assert value in ("", "not-needed-for-local"), (
                f"{key} looks filled in ({value!r}) -- .env.example must ship blank"
            )


# --------------------------------------------------------------------------- #
# 39-41. guardrail_example: files exist, and the offline-testability property
# --------------------------------------------------------------------------- #

@check("guardrail_example directory exists with the expected files")
def _():
    for name in ("guardrail_core.py", "agent.py", ".env.example", "requirements.txt"):
        assert (GUARDRAIL_EXAMPLE / name).exists(), f"missing {name}"


@check("guardrail_core module imports with no third-party packages installed")
def _():
    import guardrail_core  # noqa: F401


@check("guardrail_core module imports ONLY stdlib (keeps this test runnable offline)")
def _():
    tree = ast.parse((GUARDRAIL_EXAMPLE / "guardrail_core.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            continue
        for n in names:
            assert n in STDLIB_OK, (
                f"guardrail_core.py imports third-party '{n}'; move it to agent.py "
                "or this smoke test stops running offline"
            )


# --------------------------------------------------------------------------- #
# 42-45. The guardrail itself: polarity, section detection, no leakage
# --------------------------------------------------------------------------- #

_GOOD_PLAN = (
    "Objective: Determine the current adoption rate of renewable energy sources "
    "among commercial shipping fleets operating in the North Atlantic corridor, "
    "and identify the top three barriers preventing wider adoption.\n\n"
    "Steps: (1) Survey fifteen shipping operators about their current fuel mix "
    "and any renewable pilot programs. (2) Review publicly available regulatory "
    "filings from the past two years. (3) Interview two industry analysts about "
    "cost trends for retrofitting versus new-build vessels.\n\n"
    "Success criteria: A ranked list of adoption barriers backed by at least ten "
    "operator responses, and a cost-comparison table covering at least three "
    "vessel classes."
)
_THIN_PLAN = "Look into renewable energy in shipping and report back."


@check("polarity test: the guardrail blocks a thin plan AND approves a detailed one")
def _():
    from guardrail_core import review_plan
    # The exact bug class chapter_04/09_agent_passoff_guardrails.py has: a
    # guardrail wired to the wrong polarity looks like it works in a demo,
    # because the flow just always takes one branch. Testing only one
    # direction would not catch that -- both must be asserted together.
    assert review_plan(_THIN_PLAN).should_block is True, "a thin plan must block"
    assert review_plan(_GOOD_PLAN).should_block is False, "a detailed plan must NOT block"


@check("a long-enough plan missing one required section still blocks, named specifically")
def _():
    from guardrail_core import review_plan
    long_but_incomplete = (
        "Objective: figure out adoption barriers. " + ("Detail. " * 60) +
        "Steps: survey operators, review filings, interview analysts. " + ("More detail. " * 20)
    )
    review = review_plan(long_but_incomplete)
    assert review.detail_chars >= 400, "fixture must actually exceed the length threshold"
    assert review.should_block is True, "length alone must not be enough to pass"
    assert "success criteria" in review.reason.lower()
    assert "success criteria" in review.missing_sections
    assert "objective" not in review.missing_sections and "steps" not in review.missing_sections


@check("attempt_passoff never leaks next_stage_input on a blocked plan")
def _():
    from guardrail_core import attempt_passoff
    blocked = attempt_passoff(_THIN_PLAN)
    assert blocked.approved is False
    assert blocked.next_stage_input is None, "a blocked plan must never reach the next stage"

    approved = attempt_passoff(_GOOD_PLAN)
    assert approved.approved is True
    assert approved.next_stage_input == _GOOD_PLAN


@check("interleaved reviews of different plans never contaminate each other (no shared state)")
def _():
    from guardrail_core import review_plan
    # Mirrors the failure chapter_07/06_RAG_grounding_with_guardrails.py has:
    # a module-level `_last_context` overwritten by every search, so a
    # multi-search answer grounds against only the last one. review_plan
    # takes the plan as its only argument and keeps no module-level state,
    # so interleaving calls cannot leak between them -- pinned here so a
    # future refactor cannot reintroduce that failure shape.
    results = [review_plan(p) for p in (_GOOD_PLAN, _THIN_PLAN, _GOOD_PLAN, _THIN_PLAN)]
    assert [r.should_block for r in results] == [False, True, False, True]
    assert results[0] == results[2], "identical input must give identical output regardless of call order"
    assert results[1] == results[3]


# --------------------------------------------------------------------------- #
# 46-47. guardrail_example: configuration file
# --------------------------------------------------------------------------- #

def _guardrail_env_example_keys() -> set[str]:
    keys = set()
    for line in (GUARDRAIL_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


@check(".env.example (guardrail_example) covers every variable agent.py reads")
def _():
    read = set()
    for py in sorted(GUARDRAIL_EXAMPLE.glob("*.py")):
        src = py.read_text(encoding="utf-8")
        read |= set(re.findall(r"os\.environ\.get\(\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"os\.environ\[\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"os\.getenv\(\s*[\"']([A-Z_]+)[\"']", src))
        read |= set(re.findall(r"_require\(\s*[\"']([A-Z_]+)[\"']", src))
    missing = read - _guardrail_env_example_keys()
    assert not missing, f".env.example (guardrail_example) is missing: {sorted(missing)}"


@check(".env.example (guardrail_example) ships no filled-in secret")
def _():
    for line in (GUARDRAIL_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (p.strip() for p in line.split("=", 1))
        if any(m in key for m in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            assert value in ("", "not-needed-for-local"), (
                f"{key} looks filled in ({value!r}) -- .env.example must ship blank"
            )


# --------------------------------------------------------------------------- #
# 48-59. loop_example: the layered stop gate, offline
# --------------------------------------------------------------------------- #

@check("loop_example directory exists with the expected files")
def _():
    for name in ("loop_core.py", "agent.py", ".env.example", "requirements.txt"):
        assert (LOOP_EXAMPLE / name).is_file(), f"missing {name}"


@check("loop_core imports without executing anything (AST-verified)")
def _():
    tree = ast.parse((LOOP_EXAMPLE / "loop_core.py").read_text(encoding="utf-8"))
    for node in tree.body:
        assert not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call), (
            "module-level call found -- importing must not execute the loop"
        )
    src = (LOOP_EXAMPLE / "loop_core.py").read_text(encoding="utf-8")
    assert "os.environ" not in src, "loop_core must not read the environment"
    import loop_core  # noqa: F401  -- and the import itself must succeed bare


@check("loop_core imports ONLY stdlib (keeps this test runnable offline)")
def _():
    tree = ast.parse((LOOP_EXAMPLE / "loop_core.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    allowed = {"re", "dataclasses", "__future__"}
    assert imported <= allowed, f"non-stdlib or unexpected imports: {imported - allowed}"


def _explorer(script):
    """Build an explore_fn from a list of (summary, follow_ups, cost) tuples."""
    calls = {"n": 0}

    def explore_fn(question):
        i = min(calls["n"], len(script) - 1)
        calls["n"] += 1
        summary, follow_ups, cost = script[i]
        return f"RAW({question})", summary, list(follow_ups), cost

    return explore_fn, calls


@check("two near-identical summaries halt with stop == 'stagnation'")
def _():
    from loop_core import LoopBudget, run_loop
    script = [
        ("the capital of france is paris, a large city", ["q2"], 0.0),
        ("paris is the capital of france -- a large city", ["q3"], 0.0),
        ("something completely different entirely", ["q4"], 0.0),
    ]
    explore_fn, calls = _explorer(script)
    result = run_loop(["q1"], explore_fn, lambda f: "r",
                      budget=LoopBudget(max_iterations=10, max_cost=99, max_wall_clock_s=99))
    assert result.stop == "stagnation", f"stopped by {result.stop}"
    assert calls["n"] == 2, f"third exploration ran ({calls['n']} calls)"


@check("follow-up queue de-duplicates and refuses re-entry after popping")
def _():
    from loop_core import FollowUpQueue
    q = FollowUpQueue()
    assert q.push("What is RRF?") is True
    assert q.push("what is rrf") is False, "case-variant duplicate accepted"
    assert q.push("What is RRF!?") is False, "punctuation-variant duplicate accepted"
    assert len(q) == 1
    q.pop()
    assert q.push("What is RRF?") is False, "popped question re-entered the queue"


@check("order='breadth' vs 'depth' provably changes traversal order")
def _():
    from loop_core import FollowUpQueue
    # breadth (FIFO): siblings of the seed go first; depth (LIFO): the most
    # recently opened thread goes first.
    for order, first, second in (("breadth", "A", "B"), ("depth", "B", "C")):
        q = FollowUpQueue(order=order)
        q.push("A"); q.push("B")
        assert q.pop() == first, f"{order}: wrong first pop"
        q.push("C")  # follow-up opened by the first exploration
        assert q.pop() == second, f"{order}: wrong second pop"


@check("cost cap stops a never-stagnating, always-branching explorer")
def _():
    from loop_core import LoopBudget, run_loop
    counter = {"n": 0}

    def explore_fn(question):
        counter["n"] += 1
        i = counter["n"]
        return f"RAW{i}", f"unique finding number {i} about topic {i}", [f"q{i + 100}"], 0.5

    result = run_loop(["q1"], explore_fn, lambda f: "r",
                      budget=LoopBudget(max_iterations=99, max_cost=1.0, max_wall_clock_s=99))
    assert result.stop == "cost_cap", f"stopped by {result.stop}"
    assert result.iterations == 2 and result.cost_spent == 1.0


@check("wall-clock cap fires via the injected clock, deterministically")
def _():
    from loop_core import LoopBudget, run_loop
    ticks = iter([0.0, 10.0, 20.0, 30.0, 40.0, 50.0])

    def explore_fn(question):
        return "RAW", f"different every time {question}", [f"fu-{question}"], 0.0

    result = run_loop(["q1"], explore_fn, lambda f: "r",
                      budget=LoopBudget(max_iterations=99, max_cost=99, max_wall_clock_s=15.0),
                      clock=lambda: next(ticks))
    assert result.stop == "wall_clock_cap", f"stopped by {result.stop}"


@check("offload log returns id + bounded digest; fetch returns the original")
def _():
    from loop_core import OffloadLog
    log = OffloadLog(digest_chars=20)
    raw = "x" * 5000 + " tail"
    rec_id, digest = log.store(raw)
    assert rec_id == "obs-0001" and len(digest) <= 20
    assert log.fetch(rec_id) == raw, "original must stay addressable"


@check("the writer receives only accumulated findings, never raw output")
def _():
    from loop_core import LoopBudget, run_loop
    seen = {}

    def write_fn(findings):
        seen["findings"] = findings
        return "report"

    def explore_fn(question):
        return "RAW-SECRET", f"summary of {question}", [], 0.0

    run_loop(["q1"], explore_fn, write_fn, budget=LoopBudget(max_iterations=5))
    (question, rec_id, summary), = seen["findings"]
    assert question == "q1" and rec_id.startswith("obs-") and "RAW-SECRET" not in summary


@check("loop_example .env.example covers every variable agent.py reads")
def _():
    env_keys = set()
    for line in (LOOP_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            env_keys.add(line.split("=", 1)[0].strip())
    agent_src = (LOOP_EXAMPLE / "agent.py").read_text(encoding="utf-8")
    read_keys = set(re.findall(r"os\.environ(?:\.get\(|\[)\s*[\"']([A-Z0-9_]+)[\"']", agent_src))
    read_keys |= set(re.findall(r"_require\(\s*[\"']([A-Z0-9_]+)[\"']\s*\)", agent_src))
    missing = read_keys - env_keys
    assert not missing, f"agent.py reads {missing} not present in .env.example"


@check("loop_example .env.example ships no filled-in secret")
def _():
    for line in (LOOP_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (p.strip() for p in line.split("=", 1))
        if any(m in key for m in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            assert value == "", f"{key} looks filled in ({value!r})"


# --------------------------------------------------------------------------- #
# 60-73. tdad_example: the TDAD harness, offline
# --------------------------------------------------------------------------- #

@check("tdad_example directory exists with the expected files")
def _():
    for name in ("harness_core.py", "agent.py", ".env.example", "requirements.txt"):
        assert (TDAD_EXAMPLE / name).is_file(), f"missing {name}"


@check("harness_core imports without executing anything, ONLY stdlib")
def _():
    tree = ast.parse((TDAD_EXAMPLE / "harness_core.py").read_text(encoding="utf-8"))
    for node in tree.body:
        assert not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call), (
            "module-level call found -- importing must not execute anything"
        )
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    allowed = {"re", "dataclasses", "__future__"}
    assert imported <= allowed, f"non-stdlib or unexpected imports: {imported - allowed}"
    import harness_core  # noqa: F401  -- the import itself must succeed bare


@check('exact_match("Photons.", "photons") is True')
def _():
    from harness_core import exact_match
    assert exact_match("Photons.", "photons") is True
    assert exact_match("Photons.", "electrons") is False


@check("grounding polarity: context-drawn answer grounded, off-context answer not")
def _():
    from harness_core import is_grounded
    context = (
        "RRF (Reciprocal Rank Fusion) combines ranked lists from multiple "
        "retrieval systems by summing the reciprocal of each item's rank.",
    )
    grounded_answer = "RRF combines ranked lists by summing reciprocal ranks."
    ungrounded_answer = "RRF was patented in 2003 by satellite engineers for telemetry."
    assert is_grounded(grounded_answer, context) is True
    assert is_grounded(ungrounded_answer, context) is False


@check("two AccumulatingContext instances never contaminate each other")
def _():
    from harness_core import AccumulatingContext, is_grounded
    ctx_a = AccumulatingContext()
    ctx_a.add("Paris is the capital of France.")
    ctx_b = AccumulatingContext()
    ctx_b.add("Tokyo is the capital of Japan.")

    answer_a = "Paris is the capital of France."
    # interleave: check B in between two checks of A
    first = is_grounded(answer_a, ctx_a.snapshot())
    is_grounded("Tokyo is the capital of Japan.", ctx_b.snapshot())
    second = is_grounded(answer_a, ctx_a.snapshot())
    assert first is True and second is True, "A's result changed after checking B"
    assert is_grounded(answer_a, ctx_b.snapshot()) is False, "A grounded against B's context"


@check("grounds against the ACCUMULATED snapshot, not the last piece alone")
def _():
    from harness_core import AccumulatingContext, is_grounded
    ctx = AccumulatingContext()
    search1 = "RRF combines ranked lists by summing reciprocal ranks."
    search2 = "Cosine similarity measures the angle between two embedding vectors."
    ctx.add(search1)
    answer = "RRF combines ranked lists using reciprocal ranks and cosine similarity."
    last_piece_only = (search2,)
    assert is_grounded(answer, last_piece_only) is False, (
        "checking only the latest piece should miss the RRF claim from search 1"
    )
    ctx.add(search2)
    assert is_grounded(answer, ctx.snapshot()) is True, (
        "checking the full accumulated snapshot should find both claims"
    )


@check("run_benchmark reports a rate, not a false clean pass")
def _():
    from harness_core import run_benchmark
    script = iter([True, False, True, False, True])  # 3/5

    def stub():
        return next(script)

    result = run_benchmark(stub, n=5)
    assert result.pass_rate == 0.6 and result.passes == 3 and result.n == 5


@check('classify_failure resolves "evaluator_bug"')
def _():
    from harness_core import classify_failure
    verdict = classify_failure(
        expected="42", raw_output="  42.", evaluator_verdict=False,
        tool_calls=["calculator"], required_tool="calculator",
    )
    assert verdict == "evaluator_bug"


@check('classify_failure resolves "instruction_bug"')
def _():
    from harness_core import classify_failure
    verdict = classify_failure(
        expected="42", raw_output="I don't know", evaluator_verdict=False,
        tool_calls=[], required_tool="calculator",
    )
    assert verdict == "instruction_bug"


@check('classify_failure resolves "capability_gap"')
def _():
    from harness_core import classify_failure
    verdict = classify_failure(
        expected="42", raw_output="41", evaluator_verdict=False,
        tool_calls=["calculator"], required_tool="calculator",
    )
    assert verdict == "capability_gap"


@check("escalate_fix_tier moves one step at a time and raises past 'model'")
def _():
    from harness_core import LADDER, escalate_fix_tier
    assert LADDER == ("word", "clause", "sentence", "section", "tool", "model")
    assert escalate_fix_tier("word") == "clause"
    assert escalate_fix_tier("section") == "tool"
    try:
        escalate_fix_tier("model")
        raise AssertionError("escalating past the last tier should raise")
    except ValueError:
        pass
    try:
        escalate_fix_tier("bogus-tier")
        raise AssertionError("an unknown tier should raise")
    except ValueError:
        pass


@check("retry_ceiling_action: retry under cap, named policy at cap, rejects unknown policy")
def _():
    from harness_core import retry_ceiling_action
    assert retry_ceiling_action(2, 5) == "retry"
    assert retry_ceiling_action(5, 5, policy="escalate_human") == "escalate_human"
    assert retry_ceiling_action(5, 5, policy="fail") == "fail"
    try:
        retry_ceiling_action(5, 5, policy="bogus-policy")
        raise AssertionError("an unrecognized policy should raise")
    except ValueError:
        pass


@check("tdad_example .env.example covers every variable agent.py reads")
def _():
    env_keys = set()
    for line in (TDAD_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            env_keys.add(line.split("=", 1)[0].strip())
    agent_src = (TDAD_EXAMPLE / "agent.py").read_text(encoding="utf-8")
    read_keys = set(re.findall(r"os\.environ(?:\.get\(|\[)\s*[\"']([A-Z0-9_]+)[\"']", agent_src))
    read_keys |= set(re.findall(r"_require\(\s*[\"']([A-Z0-9_]+)[\"']\s*\)", agent_src))
    missing = read_keys - env_keys
    assert not missing, f"agent.py reads {missing} not present in .env.example"


@check("tdad_example .env.example ships no filled-in secret")
def _():
    for line in (TDAD_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (p.strip() for p in line.split("=", 1))
        if any(m in key for m in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            assert value == "", f"{key} looks filled in ({value!r})"


# --------------------------------------------------------------------------- #
# 74-84. reliability_example: the ladder and the idempotency contrast, offline
# --------------------------------------------------------------------------- #

@check("reliability_example directory exists with the expected files")
def _():
    for name in ("reliability_core.py", "agent.py", ".env.example", "requirements.txt"):
        assert (RELIABILITY_EXAMPLE / name).is_file(), f"missing {name}"


@check("reliability_example reliability_core imports without executing anything, ONLY stdlib")
def _():
    tree = ast.parse((RELIABILITY_EXAMPLE / "reliability_core.py").read_text(encoding="utf-8"))
    for node in tree.body:
        assert not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call), (
            "module-level call found -- importing must not execute anything"
        )
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    allowed = {"hashlib", "json", "dataclasses", "enum", "__future__"}
    assert imported <= allowed, f"non-stdlib or unexpected imports: {imported - allowed}"
    import reliability_core  # noqa: F401  -- the import itself must succeed bare


def _ladder_stub(elapsed: float, value):
    return lambda: (elapsed, value)


def _ladder_stub_raises():
    def _fn():
        raise RuntimeError("boom")
    return _fn


@check("a successful primary never touches any fallback")
def _():
    from reliability_core import CircuitBreaker, run_ladder
    fallback_called = {"n": 0}

    def fallback():
        fallback_called["n"] += 1
        return 0.1, "fallback-value"

    result = run_ladder(
        _ladder_stub(0.1, "primary-value"), [("secondary", fallback)],
        breaker=CircuitBreaker(), time_budget=1.0, now=0,
    )
    assert result.outcome == "primary" and result.value == "primary-value"
    assert fallback_called["n"] == 0


@check("a primary exceeding its time budget falls back, reporting the fallback's success")
def _():
    from reliability_core import CircuitBreaker, run_ladder
    result = run_ladder(
        _ladder_stub(5.0, "too-slow"), [("secondary", _ladder_stub(0.1, "fast-enough"))],
        breaker=CircuitBreaker(), time_budget=1.0, now=0,
    )
    assert result.outcome == "fallback:secondary" and result.value == "fast-enough"


@check("every rung failing returns outcome == 'degraded', never an unhandled exception")
def _():
    from reliability_core import CircuitBreaker, run_ladder
    result = run_ladder(
        _ladder_stub_raises(), [("secondary", _ladder_stub_raises())],
        breaker=CircuitBreaker(), time_budget=1.0, now=0, degraded_value="sorry",
    )
    assert result.outcome == "degraded" and result.value == "sorry"
    assert result.attempts == ("primary", "fallback:secondary", "degraded")


@check("circuit breaker opens after the threshold and sheds load without calling primary")
def _():
    from reliability_core import CircuitBreaker, run_ladder
    breaker = CircuitBreaker(failure_threshold=2, cooldown=100)
    for now in (0, 1):
        run_ladder(_ladder_stub_raises(), [], breaker=breaker, time_budget=1.0, now=now,
                   degraded_value=None)
    assert breaker.state.value == "open"

    primary_called = {"n": 0}

    def primary():
        primary_called["n"] += 1
        return 0.1, "should-not-run"

    result = run_ladder(primary, [], breaker=breaker, time_budget=1.0, now=2, degraded_value="x")
    assert result.outcome == "circuit_open" and primary_called["n"] == 0


@check("a successful HALF_OPEN probe closes the breaker; a failed one reopens immediately")
def _():
    from reliability_core import BreakerState, CircuitBreaker

    closing = CircuitBreaker(failure_threshold=1, cooldown=5)
    closing.record_failure(now=0)
    assert closing.state == BreakerState.OPEN
    assert closing.allow(now=5) is True and closing.state == BreakerState.HALF_OPEN
    closing.record_success()
    assert closing.state == BreakerState.CLOSED

    reopening = CircuitBreaker(failure_threshold=1, cooldown=5)
    reopening.record_failure(now=0)
    assert reopening.allow(now=5) is True and reopening.state == BreakerState.HALF_OPEN
    reopening.record_failure(now=5)
    assert reopening.state == BreakerState.OPEN, "a failed probe must reopen, not stay half-open"


@check("idempotency contrast: distinct operation_ids both execute under IdempotencyCache, "
       "collapse into one under ArgHashCache")
def _():
    from reliability_core import ArgHashCache, IdempotencyCache
    args = {"amount": 10, "customer": "cust_1"}

    calls = {"n": 0}

    def execute():
        calls["n"] += 1
        return calls["n"]

    good = IdempotencyCache()
    r1, cached1 = good.call("op-1", execute)
    r2, cached2 = good.call("op-2", execute)
    assert cached1 is False and cached2 is False
    assert r1 != r2, "two distinct operation_ids must both actually execute"
    assert calls["n"] == 2

    calls["n"] = 0
    broken = ArgHashCache()
    b1, bcached1 = broken.call("charge", args, execute)
    b2, bcached2 = broken.call("charge", args, execute)
    assert bcached1 is False and bcached2 is True, (
        "the argument-hash cache should silently treat the second distinct "
        "operation as a cache hit -- reproducing chapter_08/06's bug"
    )
    assert b1 == b2 and calls["n"] == 1, "the bug: only one real execution happened"


@check("the SAME operation_id called twice executes the function once (the cache-hit path)")
def _():
    from reliability_core import IdempotencyCache
    calls = {"n": 0}

    def execute():
        calls["n"] += 1
        return "result"

    cache = IdempotencyCache()
    _, cached1 = cache.call("op-1", execute)
    _, cached2 = cache.call("op-1", execute)
    assert cached1 is False and cached2 is True
    assert calls["n"] == 1


@check("reliability_example .env.example covers every variable agent.py reads")
def _():
    env_keys = set()
    for line in (RELIABILITY_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            env_keys.add(line.split("=", 1)[0].strip())
    agent_src = (RELIABILITY_EXAMPLE / "agent.py").read_text(encoding="utf-8")
    read_keys = set(re.findall(r"os\.environ(?:\.get\(|\[)\s*[\"']([A-Z0-9_]+)[\"']", agent_src))
    read_keys |= set(re.findall(r"_require\(\s*[\"']([A-Z0-9_]+)[\"']\s*\)", agent_src))
    missing = read_keys - env_keys
    assert not missing, f"agent.py reads {missing} not present in .env.example"


@check("reliability_example .env.example ships no filled-in secret")
def _():
    for line in (RELIABILITY_EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (p.strip() for p in line.split("=", 1))
        if any(m in key for m in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            assert value == "", f"{key} looks filled in ({value!r})"


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
