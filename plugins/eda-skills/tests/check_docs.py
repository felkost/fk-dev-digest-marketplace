"""Staleness checks for the user-facing docs and the ChatGPT package.

The smoke test covers the code; nothing covered the docs, and they drifted
silently -- `README.md` advertised "30/30 перевірок" for ~14 rounds after the
count changed, and `chatgpt/README.md` described the instruction budget in
characters after the build script had switched to bytes (the exact confusion
that got a paste rejected once: Cyrillic is 2 bytes/letter, so 5563 chars =
8498 bytes).

Run:  python tests/check_docs.py      (exit code 0 = all clear)

Console note: this box's console is cp1251, so output is forced ASCII-safe --
never print raw Cyrillic from a script here.
"""

from __future__ import annotations

import pathlib
import re
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROBLEMS: list[str] = []
NOTES: list[str] = []


def say(s: str) -> None:
    """cp1251-safe stdout."""
    sys.stdout.write(s.encode("ascii", "replace").decode("ascii") + "\n")


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# 1. A smoke-test count claimed in any doc must match reality
# --------------------------------------------------------------------------- #
smoke = read("tests", "smoke_test.py")
n_checks = len(re.findall(r"^@check\(", smoke, re.M))
say(f"[1] smoke_test.py defines {n_checks} checks")
for doc in ("README.md", "README-beginner.md", "chatgpt/README.md"):
    text = read(*doc.split("/"))
    for a, b in re.findall(r"(\d+)\s*/\s*(\d+)\s*(?:перевірок|checks)", text):
        if int(b) != n_checks:
            PROBLEMS.append(f"{doc} claims {a}/{b} checks; smoke_test.py has {n_checks}")
        else:
            say(f"    {doc}: {a}/{b} - matches")


# --------------------------------------------------------------------------- #
# 2. gpt_instructions.md: byte budget, and paths resolvable IN THE ZIP
#    (the GPT never sees the repo -- only the uploaded knowledge archive)
# --------------------------------------------------------------------------- #
instr = read("chatgpt", "gpt_instructions.md")
n_bytes = len(instr.encode("utf-8"))
LIMIT = 8000
say(f"[2] gpt_instructions.md = {n_bytes} bytes / {len(instr)} chars (limit {LIMIT})")
if n_bytes > LIMIT:
    PROBLEMS.append(f"gpt_instructions.md is {n_bytes} bytes, over the {LIMIT}-byte limit")
elif LIMIT - n_bytes < 20:
    NOTES.append(f"only {LIMIT - n_bytes} bytes of headroom in gpt_instructions.md")

zip_path = ROOT / "dist" / "eda_skills_knowledge.zip"
knames: set[str] = set()
if not zip_path.exists():
    PROBLEMS.append("dist/eda_skills_knowledge.zip is missing - run chatgpt/build_gpt_package.ps1")
else:
    knames = set(zipfile.ZipFile(zip_path).namelist())

RUNTIME_FILES = {"insights.md"}          # created by insights.py, deliberately not shipped
cited_paths = set(re.findall(r"`([A-Za-z0-9_./-]+\.(?:md|py))`", instr))
resolvable = 0
for p in sorted(cited_paths):
    if p in RUNTIME_FILES:
        continue
    if p in knames:
        resolvable += 1
    else:
        PROBLEMS.append(f"gpt_instructions.md cites `{p}` but it is not in the knowledge zip")
say(f"    cited paths resolvable in the zip: {resolvable}")


# --------------------------------------------------------------------------- #
# 3. Function names cited in the instructions must exist in the source
# --------------------------------------------------------------------------- #
src = ""
for skill in ("audit-eda-data-quality", "discover-eda-structure",
              "engineer-select-eda-features", "plan-eda-dataset"):
    for f in sorted((ROOT / "skills" / skill / "scripts").glob("*.py")):
        src += f.read_text(encoding="utf-8")

modules = {f.stem for skill in ("audit-eda-data-quality", "discover-eda-structure",
                                "engineer-select-eda-features", "plan-eda-dataset")
           for f in (ROOT / "skills" / skill / "scripts").glob("*.py")}
# Tokens that legitimately look like identifiers but are not code: the readiness
# verdicts from contracts.py and the knowledge archive's filename.
NON_FUNCTIONS = {"ready", "not_ready", "ready_with_accepted_limitations",
                 "eda_skills_knowledge.zip", "insights.md"}

resolved, unresolved = 0, []
for name in sorted(re.findall(r"`([a-z_]+(?:\.[a-z_]+)?)`", instr)):
    if name in NON_FUNCTIONS or re.search(r"\.(md|py|zip|ipynb|txt)$", name):
        continue
    head, _, _attr = name.partition(".")
    if head in modules:                      # e.g. family_router.route
        resolved += 1
    elif f"def {name}" in src:
        resolved += 1
    elif "_" in name and len(name) > 6:      # looks like a function, but is not one
        unresolved.append(name)
say(f"[3] symbols cited in instructions that resolve to real code: {resolved}")
for u in sorted(set(unresolved)):
    PROBLEMS.append(f"gpt_instructions.md cites `{u}` which is not a function or module")


# --------------------------------------------------------------------------- #
# 4. chatgpt/README.md must describe the budget in BYTES, not characters
# --------------------------------------------------------------------------- #
cr = read("chatgpt", "README.md")
script = read("chatgpt", "build_gpt_package.ps1")
say("[4] build-script description in chatgpt/README.md")
if "GetByteCount" in script and "байт" not in cr.lower():
    PROBLEMS.append("chatgpt/README.md never mentions bytes, but the script measures bytes")
if re.search(r"довжину[^.]{0,40}у символах", cr):
    PROBLEMS.append("chatgpt/README.md still says the instruction length is measured 'у символах'")


# --------------------------------------------------------------------------- #
# 5. Knowledge zip contents match what chatgpt/README.md promises
# --------------------------------------------------------------------------- #
if knames:
    n_skill = sum(1 for n in knames if n.endswith("SKILL.md"))
    say(f"[5] zip: {n_skill} SKILL.md, "
        f"{sum(1 for n in knames if '/references/' in n)} references, "
        f"{sum(1 for n in knames if '/scripts/' in n and n.endswith('.py'))} scripts")
    if n_skill != 4:
        PROBLEMS.append(f"knowledge zip has {n_skill} SKILL.md files, expected 4")
    if any(n.startswith("agents/") or "/agents/" in n for n in knames):
        PROBLEMS.append("knowledge zip contains agents/ (should be excluded)")
    if any("README" in n for n in knames):
        PROBLEMS.append("knowledge zip contains a README (should be excluded)")
    if not any(n.endswith(".ipynb") for n in knames):
        PROBLEMS.append("knowledge zip is missing the workflow notebook")


# --------------------------------------------------------------------------- #
# 6. Modality routing is deliberately duplicated: the expanded table lives in
#    plan-eda-dataset/references/modality-routing.md (which the ChatGPT package
#    points at, because its 8000-byte instruction budget cannot hold the table)
#    and a condensed twin lives in plan-eda-dataset/SKILL.md for Claude. Keeping
#    both was an explicit decision; this check is what makes it safe. It has
#    already caught one real drift: the graph branch was added to SKILL.md while
#    the ChatGPT copy silently stayed on five modalities.
# --------------------------------------------------------------------------- #
ROUTING = ROOT / "skills" / "plan-eda-dataset" / "references" / "modality-routing.md"
SKILL = ROOT / "skills" / "plan-eda-dataset" / "SKILL.md"
REF_RE = re.compile(r"`?([A-Za-z0-9_./-]*references/([a-z0-9-]+\.md))`?")


def cited_refs(text: str) -> set[str]:
    return {m.group(2) for m in REF_RE.finditer(text)}


if not ROUTING.exists():
    PROBLEMS.append("plan-eda-dataset/references/modality-routing.md is missing")
else:
    routing_txt = ROUTING.read_text(encoding="utf-8")
    skill_txt = SKILL.read_text(encoding="utf-8")
    # the SKILL.md twin is the "Маршрутизація ..." section only
    sec = re.search(r"(?ms)^## Маршрутизація за модальністю.*?(?=^## |\Z)", skill_txt)
    skill_refs = cited_refs(sec.group(0)) if sec else set()
    routing_refs = cited_refs(routing_txt)
    say(f"[6] modality routing: {len(routing_refs)} references in the table, "
        f"{len(skill_refs)} in the SKILL.md twin")
    if sec is None:
        PROBLEMS.append("plan-eda-dataset/SKILL.md has no 'Маршрутизація за модальністю' section")
    for missing in sorted(skill_refs - routing_refs):
        PROBLEMS.append(f"modality-routing.md never routes to `{missing}`, but SKILL.md does")
    for extra in sorted(routing_refs - skill_refs):
        PROBLEMS.append(f"modality-routing.md routes to `{extra}`, but the SKILL.md twin does not")

    all_refs = {p.name for p in ROOT.glob("skills/*/references/*.md")}
    for dangling in sorted(routing_refs - all_refs):
        PROBLEMS.append(f"modality-routing.md cites `{dangling}` which does not exist on disk")


# --------------------------------------------------------------------------- #
say("")
say("=" * 60)
for n in NOTES:
    say(f"NOTE    {n}")
if PROBLEMS:
    say(f"{len(PROBLEMS)} problem(s) found:")
    for p in PROBLEMS:
        say(f"  - {p}")
    sys.exit(1)
say("docs OK")
sys.exit(0)
