#!/usr/bin/env python3
"""Вердикт про перенавчання за порогами курсу (15-20% насторожує, 20-30% overfit).

Використання:
  python overfit_report.py --metric r2   --train 0.95 --test 0.60
  python overfit_report.py --metric rmse --train 1.1  --test 7.8
  python overfit_report.py --metric rmse --train 5.9  --cv 6.1,6.3,6.2,6.4,6.2
  python overfit_report.py --self-test

Розрив: score-метрики (більше=краще): gap=(train-test)/train;
        error-метрики (менше=краще):  gap=(test-train)/train.
CV-список замість --test дає mean±std і 1-SE коридор.
"""

from __future__ import annotations

import argparse
import math
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

SCORE = {"r2", "accuracy", "auc", "roc_auc", "f1", "ba", "balanced_accuracy",
         "average_precision", "mcc", "score"}
ERROR = {"rmse", "mse", "mae", "medae", "logloss", "log_loss", "deviance", "error"}

# Пороги курсу (Л2-3, Подскребко): відносний розрив
T_CONCERN, T_OVERFIT, T_SEVERE = 0.15, 0.20, 0.30


def gap(metric: str, train: float, test: float) -> float:
    m = metric.lower()
    if m in SCORE:
        kind = "score"
    elif m in ERROR:
        kind = "error"
    else:
        raise ValueError(f"невідома метрика '{metric}': додайте у SCORE/ERROR")
    if train == 0:
        raise ValueError("train == 0: відносний розрив невизначений")
    g = (train - test) / abs(train) if kind == "score" else (test - train) / abs(train)
    return g


def verdict(g: float) -> tuple[str, str]:
    if g < 0:
        return ("АНОМАЛІЯ: test кращий за train",
                "перевірити витік у препроцесингу, спліт, розмір вибірки — не радіти")
    if g < T_CONCERN:
        return ("норма", "розрив у межах шуму; перевірити, чи не underfit (обидва погані?)")
    if g < T_OVERFIT:
        return ("НАСТОРОЖУЄ (15–20%)",
                "перевірити стабільність по фолдах; крок у бік простішої моделі")
    if g < T_SEVERE:
        return ("ПЕРЕНАВЧАННЯ (20–30%)",
                "різати ємність: дерева -> ml-tree-ensemble-params, лінійні -> ml-linear-regularization")
    return ("СИЛЬНЕ ПЕРЕНАВЧАННЯ (>30%)",
            "ємність + регуляризація + дані; перевірити канарками, чи train не вивчив шум")


def report(metric: str, train: float, test: float | None,
           cv: list[float] | None) -> str:
    L = []
    if cv:
        n = len(cv)
        mean = sum(cv) / n
        var = sum((x - mean) ** 2 for x in cv) / (n - 1) if n > 1 else 0.0
        sd = math.sqrt(var)
        se = sd / math.sqrt(n) if n > 1 else float("nan")
        L.append(f"CV ({n} фолдів): mean = {mean:.4f}   std = {sd:.4f}   SE = {se:.4f}")
        L.append(f"  1-SE коридор: [{mean - se:.4f}, {mean + se:.4f}] — конфігурації "
                 "всередині нього еквівалентні; беріть найпростішу")
        test = mean
    g = gap(metric, train, test)
    v, action = verdict(g)
    L.insert(0, f"метрика = {metric}   train = {train:.4f}   test = {test:.4f}"
                f"   розрив = {g:+.1%}")
    L.append(f"Вердикт: {v}")
    L.append(f"Дія: {action}")
    return "\n".join(L)


def self_test() -> int:
    ok = True
    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'OK ' if cond else 'FAIL'} {label}")

    print("Приклади курсу:")
    g = gap("r2", 0.95, 0.60)
    check(f"R² 0.95/0.60 -> gap {g:.1%} -> перенавчання (>30%)",
          abs(g - 0.3684) < 1e-3 and verdict(g)[0].startswith("СИЛЬНЕ"))
    g = gap("rmse", 1.1, 7.8)
    check(f"RMSE 1.1/7.8 -> gap {g:.0%} -> сильне", g > 6 and verdict(g)[0].startswith("СИЛЬНЕ"))
    g = gap("rmse", 6.2, 6.4)
    check(f"RMSE 6.2/6.4 -> gap {g:.1%} -> норма", g < T_CONCERN and verdict(g)[0] == "норма")
    print("Межові й аномальні:")
    check("gap 17% -> насторожує", verdict(0.17)[0].startswith("НАСТОРОЖУЄ"))
    check("gap 25% -> перенавчання", verdict(0.25)[0].startswith("ПЕРЕНАВЧАННЯ"))
    check("test кращий за train -> аномалія", verdict(gap("r2", 0.80, 0.86))[0].startswith("АНОМАЛІЯ"))
    # 1-SE: перевіримо арифметику
    cv = [6.1, 6.3, 6.2, 6.4, 6.2]
    mean = sum(cv)/5
    check("CV mean 6.24", abs(mean - 6.24) < 1e-9)
    print()
    print("УСПІХ" if ok else "ПРОВАЛ")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metric", default="score",
                    help="r2/accuracy/auc/... або rmse/mae/logloss/...")
    ap.add_argument("--train", type=float)
    ap.add_argument("--test", type=float)
    ap.add_argument("--cv", help="скори валідації через кому (замість --test)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.train is None or (a.test is None and not a.cv):
        ap.error("потрібні --train і (--test або --cv)")
    cv = [float(x) for x in a.cv.split(",")] if a.cv else None
    print(report(a.metric, a.train, a.test, cv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
