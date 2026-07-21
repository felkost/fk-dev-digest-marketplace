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
sys.path.insert(0, str(EXAMPLE))
sys.path.insert(0, str(MCP_EXAMPLE))
sys.path.insert(0, str(REFLEXION_EXAMPLE))
sys.path.insert(0, str(GUARDRAIL_EXAMPLE))

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
