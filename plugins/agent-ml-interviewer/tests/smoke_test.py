#!/usr/bin/env python3
"""Смоук-тест пака: структура, конвенції, junction-и, самотести скриптів, байти GPT.

Запуск із кореня пака:  python tests/smoke_test.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parents[1]
SKILLS = [
    "ml-metric-choice", "ml-decision-threshold", "ml-distribution-choice",
    "ml-overfitting-diagnosis", "ml-search-strategy",
    "ml-tree-ensemble-params", "ml-linear-regularization",
    "ml-clustering-k", "ml-dimensionality-features",
    "rl-hyperparameters", "llm-parameter-choice", "ml-tuning-workflow",
    "ml-task-framing", "ml-model-selection", "ml-validation-design",
    "nn-training-params", "ml-bayesian-inference", "ml-missing-data",
    "ml-sampling-design", "ml-label-quality", "ml-forecasting-model",
]

passed, failed = 0, 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"OK   {label}")
    else:
        failed += 1
        print(f"FAIL {label}" + (f" -- {detail}" if detail else ""))


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


# --- 1. Структура і конвенції кожного скіла --------------------------------
for s in SKILLS:
    d = ROOT / s
    skill_md = d / "SKILL.md"
    check(f"{s}/SKILL.md існує", skill_md.is_file())
    if not skill_md.is_file():
        continue
    text = skill_md.read_text(encoding="utf-8")
    fm = frontmatter(text)
    check(f"{s}: frontmatter name == тека", fm.get("name") == s,
          f"name={fm.get('name')!r}")
    desc = fm.get("description", "")
    check(f"{s}: description містить 'Use when'", "Use when" in desc)
    check(f"{s}: description містить негативне обмеження", "Does NOT" in desc)
    body_lines = len(text.splitlines())
    check(f"{s}: SKILL.md ≤ 500 рядків", body_lines <= 500, f"{body_lines}")
    # усі згадані ЛОКАЛЬНІ references/* існують (крос-пакові шляхи виду
    # `інший-скіл/references/...` мають префікс і не рахуються)
    refs = set(re.findall(r"(?<![\w/-])references/[A-Za-z0-9._-]+\.(?:md|txt)", text))
    for r in sorted(refs):
        check(f"{s}: посилання {r} існує", (d / r).is_file())
    # api-2026 має бути дато-штампований
    api = d / "references" / "api-2026.md"
    if api.is_file():
        check(f"{s}: api-2026.md має дату перевірки",
              re.search(r"20\d\d-\d\d-\d\d", api.read_text(encoding="utf-8")[:400]) is not None)
    check(f"{s}: agents/openai.yaml існує", (d / "agents" / "openai.yaml").is_file())

# --- 2. Junction-и для Claude Code -----------------------------------------
for s in SKILLS:
    j = ROOT / ".claude" / "skills" / s / "SKILL.md"
    c = ROOT / s / "SKILL.md"
    ok = j.is_file() and c.is_file() and \
        j.read_text(encoding="utf-8") == c.read_text(encoding="utf-8")
    check(f".claude/skills/{s} читається крізь junction і збігається", ok)

# --- 3. Самотести скриптів (аналітична основна істина) ---------------------
# Скрипти шукаються ГЛОБОМ, а не списком: інакше новий скіл мовчки лишається
# неперевіреним (саме так ml-sampling-design і ml-label-quality спершу й
# випали з прогону, показавши зелені 206 OK).
_scripts = sorted(
    (s, p.name)
    for s in SKILLS
    for p in sorted((ROOT / s / "scripts").glob("*.py"))
    if p.name != "__init__.py"
)
check("знайдено скрипти для самотестів", len(_scripts) >= 10,
      f"знайдено лише {len(_scripts)}")
for s, script in _scripts:
    p = ROOT / s / "scripts" / script
    r = subprocess.run([sys.executable, str(p), "--self-test"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    tail = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
    check(f"{script} --self-test", r.returncode == 0 and "УСПІХ" in (r.stdout or ""),
          tail)

# --- 4. Байтовий бюджет інструкцій GPT --------------------------------------
instr = ROOT / "chatgpt" / "gpt_instructions.md"
if instr.is_file():
    # СИРІ байти: read_text().encode() недораховує ~56 байтів, бо текстовий
    # режим згортає CRLF у LF — перевірка була м'якшою за реальний бюджет.
    n = len(instr.read_bytes())
    check(f"gpt_instructions.md ≤ 8000 сирих байтів (зараз {n})", n <= 8000)

# --- 5. UDR-індекс узгоджений ------------------------------------------------
idx = ROOT / "ml-distribution-choice" / "references" / "udr-index.md"
if idx.is_file():
    t = idx.read_text(encoding="utf-8")
    n_dist = len(re.findall(r"^- ", t[t.find("## Картки"):t.find("## Докази стрілок")], re.M))
    check(f"udr-index: рівно 76 карток розподілів (зараз {n_dist})", n_dist == 76)
    check("udr-index: колізія ExponentialForgetfulness задокументована",
          "ExponentialForgetfulness" in t)

print()
print(f"{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
