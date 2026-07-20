"""Staleness checks for the ai-gen docs and the ChatGPT knowledge package.

Adapted from `plugins/eda-skills/tests/check_docs.py`. The check that earns its
keep here is #5, the skill-list twins: the skill roster is written down in five
places (build script, skills/ on disk, the mentor agent, the README tree, and
the router table) and the roadmap adds two more skills in later rounds. Any one
of the five going stale is silent -- the GPT package simply ships without the
new skill, or the mentor never routes to it.

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
# 1. gpt_instructions.md byte budget.
#    ChatGPT enforces 8000 *bytes*, not characters, and Cyrillic costs 2 bytes
#    per letter -- a comfortable-looking character count can still be rejected.
# --------------------------------------------------------------------------- #
instr = read("chatgpt", "gpt_instructions.md")
n_bytes = len(instr.encode("utf-8"))
LIMIT = 8000
say(f"[1] gpt_instructions.md = {n_bytes} bytes / {len(instr)} chars (limit {LIMIT})")
if n_bytes > LIMIT:
    PROBLEMS.append(f"gpt_instructions.md is {n_bytes} bytes, over the {LIMIT}-byte limit")
elif LIMIT - n_bytes < 100:
    NOTES.append(
        f"only {LIMIT - n_bytes} bytes of headroom in gpt_instructions.md - "
        "compact it before adding another skill"
    )
else:
    say(f"    headroom: {LIMIT - n_bytes} bytes")


# --------------------------------------------------------------------------- #
# 2. Skill-list twins. Five lists must agree; disk is the source of truth.
# --------------------------------------------------------------------------- #
on_disk = {p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").exists()}

script = read("chatgpt", "build_gpt_package.ps1")
m = re.search(r"\$skills\s*=\s*(.+?)(?=\r?\nforeach)", script, re.S)
in_script = set(re.findall(r'"([a-z0-9-]+)"', m.group(1))) if m else set()

mentor = read("agents", "ai-gen-mentor.md")
in_mentor = set(re.findall(r"`ai-gen:([a-z0-9-]+)`", mentor))

readme = read("README.md")
tree = re.search(r"```\n(.*?)```", readme, re.S)
in_readme = set(re.findall(r"^(?:[|├└─\s]*)([a-z][a-z0-9-]+)\s", tree.group(1), re.M)) if tree else set()
in_readme &= on_disk | in_script | in_mentor  # tree also contains prose words

ROUTER = ("skills", "plan-ai-solution", "references", "skill-router.md")
router = read(*ROUTER)
in_router = set(re.findall(r"`([a-z0-9-]+)`", router)) & (on_disk | in_script | in_mentor)

say(f"[2] skills on disk: {len(on_disk)}")
for label, found in (
    ("build_gpt_package.ps1 $skills", in_script),
    ("agents/ai-gen-mentor.md", in_mentor),
    ("README.md tree", in_readme),
    ("skill-router.md", in_router),
):
    if found == on_disk:
        say(f"    {label}: {len(found)} - matches")
        continue
    for missing in sorted(on_disk - found):
        PROBLEMS.append(f"{label} never mentions skill `{missing}` (it exists in skills/)")
    for extra in sorted(found - on_disk):
        PROBLEMS.append(f"{label} lists skill `{extra}` which does not exist in skills/")


# --------------------------------------------------------------------------- #
# 3. Link integrity, both directions, per skill.
#    Every references/*.md must be linked from its owning SKILL.md, and every
#    reference link in a SKILL.md must resolve on disk.
# --------------------------------------------------------------------------- #
linked_total, ref_total = 0, 0
for skill in sorted(on_disk):
    skill_md = read("skills", skill, "SKILL.md")
    refs_dir = ROOT / "skills" / skill / "references"
    on_disk_refs = {p.name for p in refs_dir.glob("*.md")} if refs_dir.exists() else set()
    # `(?<!/)` keeps a CROSS-skill path (`other-skill/references/x.md`) from being
    # read as a link to this skill's own references/. Without it, a SKILL.md that
    # points at a sibling skill's reference is reported as a dangling local link.
    linked = set(re.findall(r"(?<!/)references/([a-z0-9-]+\.md)", skill_md))
    ref_total += len(on_disk_refs)
    linked_total += len(linked & on_disk_refs)
    for orphan in sorted(on_disk_refs - linked):
        PROBLEMS.append(f"{skill}/references/{orphan} is never linked from its SKILL.md")
    for dangling in sorted(linked - on_disk_refs):
        PROBLEMS.append(f"{skill}/SKILL.md links references/{dangling} which is not on disk")
say(f"[3] references on disk: {ref_total}, linked from their SKILL.md: {linked_total}")

# Cross-skill reference links (e.g. `plan-ai-solution/references/handoff.md`) must resolve too.
all_refs = {f"{p.parent.parent.name}/references/{p.name}" for p in ROOT.glob("skills/*/references/*.md")}
for src in sorted(ROOT.glob("skills/*/references/*.md")) + [ROOT / "chatgpt" / "gpt_instructions.md"]:
    text = src.read_text(encoding="utf-8")
    for cited in re.findall(r"`([a-z0-9-]+/references/[a-z0-9-]+\.md)`", text):
        if cited not in all_refs:
            PROBLEMS.append(f"{src.name} cites `{cited}` which does not exist on disk")


# --------------------------------------------------------------------------- #
# 4. Everything gpt_instructions.md cites must exist INSIDE the knowledge zip.
#    The GPT never sees this repo -- only the uploaded archive.
# --------------------------------------------------------------------------- #
zip_path = ROOT / "dist" / "ai_gen_knowledge.zip"
knames: set[str] = set()
if not zip_path.exists():
    PROBLEMS.append("dist/ai_gen_knowledge.zip is missing - run chatgpt/build_gpt_package.ps1")
else:
    knames = {n.replace("\\", "/") for n in zipfile.ZipFile(zip_path).namelist()}

if knames:
    # Only paths with a directory component are real citations. A bare `SKILL.md` or
    # `references/*.md` in the instructions is generic prose ("read the relevant SKILL.md"),
    # not a file the GPT is told to open.
    cited = {p for p in re.findall(r"`([A-Za-z0-9_./-]+\.md)`", instr) if "/" in p and "*" not in p}
    resolvable = 0
    for p in sorted(cited):
        if p in knames:
            resolvable += 1
        else:
            PROBLEMS.append(f"gpt_instructions.md cites `{p}` but it is not in the knowledge zip")
    say(f"[4] paths cited in the instructions that resolve inside the zip: {resolvable}/{len(cited)}")


# --------------------------------------------------------------------------- #
# 5. Zip contents match what the build script promises to stage.
# --------------------------------------------------------------------------- #
if knames:
    n_skill = sum(1 for n in knames if n.endswith("SKILL.md"))
    n_refs = sum(1 for n in knames if "/references/" in n and n.endswith(".md"))
    say(f"[5] zip: {n_skill} SKILL.md, {n_refs} references")
    if n_skill != len(on_disk):
        PROBLEMS.append(f"knowledge zip has {n_skill} SKILL.md files, expected {len(on_disk)}")
    if n_refs != ref_total:
        PROBLEMS.append(f"knowledge zip has {n_refs} references, expected {ref_total}")
    if any(n.startswith("agents/") or "/agents/" in n for n in knames):
        PROBLEMS.append("knowledge zip contains agents/ (should be excluded)")
    for forbidden in ("README", "HANDOFF", "CLAUDE"):
        if any(forbidden in n for n in knames):
            PROBLEMS.append(f"knowledge zip contains {forbidden}* (should be excluded)")


# --------------------------------------------------------------------------- #
# 6. chatgpt/README.md must describe the budget in BYTES, not characters.
#    (The exact confusion that got a paste rejected once in the sibling plugin.)
# --------------------------------------------------------------------------- #
cr = read("chatgpt", "README.md")
say("[6] build-script description in chatgpt/README.md")
if "GetByteCount" in script and "байт" not in cr.lower():
    PROBLEMS.append("chatgpt/README.md never mentions bytes, but the script measures bytes")


# --------------------------------------------------------------------------- #
# 7. A smoke-test check count claimed in prose must match reality.
#    eda-skills' README advertised "30/30 перевірок" for ~14 rounds after the
#    count changed; this is that lesson, scoped to lines that actually talk
#    about the smoke test.
# --------------------------------------------------------------------------- #
smoke_path = ROOT / "tests" / "smoke_test.py"
if smoke_path.exists():
    n_checks = len(re.findall(r"^@check\(", smoke_path.read_text(encoding="utf-8"), re.M))
    say(f"[7] smoke_test.py defines {n_checks} checks")
    # The count must FOLLOW the word "smoke" within a short window. Matching
    # anywhere on the line is too coarse: a sentence naming both test files
    # ("check_docs.py (7 checks) and smoke_test.py (14 checks)") then reads the
    # wrong number as a smoke claim -- which this check did on its first run.
    # Dots must be allowed in the window or "smoke_test.py (14 checks)" never
    # matches -- and HANDOFF.md, the file most likely to go stale, phrases it
    # exactly that way. Keep the window short instead, so the number stays
    # associated with "smoke" rather than with a later clause.
    CLAIM = re.compile(r"smoke[^\n]{0,30}?(\d+)\s*(?:checks|перевірок)", re.I)
    claims = 0
    for md in sorted(ROOT.glob("**/*.md")):
        if "dist" in md.parts:
            continue
        for line in md.read_text(encoding="utf-8").splitlines():
            for claimed in CLAIM.findall(line):
                claims += 1
                if int(claimed) != n_checks:
                    PROBLEMS.append(
                        f"{md.relative_to(ROOT).as_posix()} claims {claimed} smoke checks; "
                        f"smoke_test.py has {n_checks}"
                    )
    say(f"    prose claims about that count checked: {claims}")


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
