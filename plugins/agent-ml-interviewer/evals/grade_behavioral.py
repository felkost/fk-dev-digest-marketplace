#!/usr/bin/env python3
"""Маркерний грейдер поведінкових evals: базлайн проти зі-скілом.

Використання:
  python evals/grade_behavioral.py --answers <answers.md> [--answers2 <other.md>]

Логіка: для кожної пастки з evals/behavioral-traps.json відповідь ПРОЙШЛА, якщо
збігся хоч один correct_any-маркер і жоден ДІЙСНИЙ wrong_any. Wrong-маркер
рахується дійсним, лише якщо в ±200 символах навколо збігу НЕМАЄ заперечної
лексики (не/видалено/застаріле/deprecated/removed/…) — інакше це застереження
«не робіть так», а не рекомендація (перевірено на реальних відповідях:
«Явно НЕ додавайте gamma=…» — правильна відповідь, наївний маркер її валив).
Розділи відповідей — '## <id>'. Грейдер детермінований; друкує і сирі збіги.

УВАГА (виправлено 2026-07-18, під час додавання пасток b9/b10): у списку
NEGATION бракувало меж слова, через що "ні\\s"/"не\\s" збігались із
закінченнями прикметників ("унікальні ", "сильне ") — тобто заперечний контекст
знаходився майже завжди й wrong-маркери масово глушились. Записаний прогін
базлайну 6/8 від 2026-07-18 отримано ще за старим, м'якшим правилом; після
цього виправлення грейдер строгіший, і той прогін відтворити один-в-один не
можна (файли відповідей не збережені). Числа з нової матриці не змішувати зі
старими.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parents[1]


def split_sections(text: str) -> dict[str, str]:
    parts = re.split(r"^##\s+(\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


# \b обов'язкові: без них "не\s|ні\s" ловлять ЗАКІНЧЕННЯ прикметників
# ("унікальні ефекти", "сильне перекриття") — а такі слова є майже в кожному
# вікні ±200 символів українського тексту, тож wrong-маркери глушилися завжди.
# "прибер" свідомо ПРИБРАНО зі списку: в API-пастках це коректне застереження
# ("приберіть gamma="), але в b10 "приберіть предиктор" — сама хибна порада,
# тобто маркер глушив сам себе. Заперечення там і так ловиться через "не".
NEGATION = re.compile(
    r"\bне\s|\bні\s|\bжодн|видален|застаріл|deprecated|removed|перейменован|"
    r"\bзамін|\bзамість|don'?t|do\s+not|instead|avoid|no\s+longer|уникай", re.I)
WINDOW = 200


def _real_wrong_hits(pattern: str, ans: str,
                     negation_extra: list[str] | None = None) -> list[str]:
    """Збіги wrong-маркера ПОЗА заперечним контекстом (±WINDOW символів).

    `negation_extra` — додаткові заперечні стеми ДЛЯ ОДНІЄЇ пастки. Потрібні,
    бо та сама лексема буває застереженням в одній пастці й хибною порадою в
    іншій: "приберіть algorithm=" (b8) — правильно, "приберіть предиктор"
    (b10) — саме та помилка, яку ловимо. Глобальним списком це не розв'язати.
    """
    neg = NEGATION
    if negation_extra:
        neg = re.compile(NEGATION.pattern + "|" + "|".join(negation_extra), re.I)
    hits = []
    for m in re.finditer(pattern, ans, re.I):
        ctx = ans[max(0, m.start() - WINDOW): m.end() + WINDOW]
        if not neg.search(ctx):
            hits.append(m.group(0))
    return hits


def grade_file(path: Path, traps: list[dict]) -> dict:
    sections = split_sections(path.read_text(encoding="utf-8"))
    out = {}
    for t in traps:
        ans = sections.get(t["id"], "")
        hit_c = [m for m in t["correct_any"] if re.search(m, ans, re.I)]
        raw_w = [m for m in t["wrong_any"] if re.search(m, ans, re.I)]
        extra = t.get("negation_extra")
        hit_w = [m for m in t["wrong_any"] if _real_wrong_hits(m, ans, extra)]
        out[t["id"]] = {
            "present": bool(ans.strip()),
            "passed": bool(hit_c) and not hit_w,
            "correct_hits": hit_c, "wrong_hits": hit_w, "raw_wrong_hits": raw_w,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", required=True)
    ap.add_argument("--answers2")
    ap.add_argument("--labels", default="baseline,with-skill")
    a = ap.parse_args()

    traps = json.load(open(ROOT / "evals" / "behavioral-traps.json",
                           encoding="utf-8"))["items"]
    labels = a.labels.split(",")
    files = [Path(a.answers)] + ([Path(a.answers2)] if a.answers2 else [])
    results = {lab: grade_file(f, traps) for lab, f in zip(labels, files)}

    hdr = f"{'пастка':<8}" + "".join(f"{lab:>14}" for lab in results) + "   нотатка"
    print(hdr)
    print("-" * len(hdr))
    score = {lab: 0 for lab in results}
    for t in traps:
        row = f"{t['id']:<8}"
        for lab in results:
            r = results[lab][t["id"]]
            mark = "PASS" if r["passed"] else ("FAIL" if r["present"] else "нема")
            if r["wrong_hits"]:
                mark += "(пастка!)"
            score[lab] += r["passed"]
            row += f"{mark:>14}"
        print(row + f"   {t['note']}")
    print("-" * len(hdr))
    print(f"{'разом':<8}" + "".join(f"{score[lab]}/{len(traps):>7}" if False else f"{str(score[lab]) + '/' + str(len(traps)):>14}" for lab in results))
    if len(results) == 2:
        l1, l2 = labels
        print(f"\nДельта ({l2} − {l1}): {score[l2] - score[l1]:+d} з {len(traps)}")
    # машиночитне
    print("\nJSON:", json.dumps({lab: {k: v["passed"] for k, v in r.items()}
                                 for lab, r in results.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
