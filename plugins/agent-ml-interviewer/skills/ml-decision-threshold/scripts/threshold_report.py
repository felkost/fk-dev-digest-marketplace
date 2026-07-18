#!/usr/bin/env python3
"""Підбір порогу рішення для бінарного класифікатора за чотирма критеріями Лекції 2.

Правило рішення: передбачаємо клас 1, якщо score >= t.

Критерії:
  closest01      мінімізує sqrt((1-TPR)^2 + FPR^2)   -- найближча точка до (0,1)
  youden         максимізує J = TPR - FPR            -- Youden 1950; J = 2*BA - 1
  balanced       мінімізує |Sensitivity - Specificity|  -- Fkih & Omri 2012
  min-precision  максимізує recall за умови precision >= P_min  -- доменне обмеження
  fbeta          максимізує F_beta                   -- beta задається через --beta

Використання:
  python threshold_report.py --csv scores.csv --score-col y_score --label-col y_true
  python threshold_report.py --csv s.csv --criterion min-precision --min-precision 0.90
  python threshold_report.py --self-test          # звірка з аналітикою Лекції 2

Вимоги: numpy, pandas. scikit-learn >= 1.5 -- лише щоб надрукувати еквівалентний виклик
TunedThresholdClassifierCV (не обов'язково для самого розрахунку).
"""

from __future__ import annotations

import argparse
import math
import sys

import numpy as np

# Консоль Windows за замовчуванням не в UTF-8 -- без цього кирилиця виводиться кракозябрами.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

CRITERIA = ("closest01", "youden", "balanced", "min-precision", "fbeta")


def sweep(y_true: np.ndarray, y_score: np.ndarray) -> dict[str, np.ndarray]:
    """Перебір усіх змістовних порогів. Повертає масиви метрик, вирівняні за thresholds.

    Кандидати -- унікальні значення score плюс +inf (нікого не відносимо до класу 1).
    Це саме та побудова, яку Лекція 2 виконує вручну: сортування за b(x) і рух порогу.
    Зв'язані (однакові) значення score обробляються коректно, бо поріг береться на
    унікальних значеннях, а не на позиціях -- об'єкти з рівним score завжди потрапляють
    в один бік від порогу.
    """
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score, dtype=float)
    if set(np.unique(y_true)) - {0, 1}:
        raise ValueError("label-col має містити лише 0 і 1")

    P = int(y_true.sum())
    N = int((1 - y_true).sum())
    if P == 0 or N == 0:
        raise ValueError("потрібні обидва класи; знайдено лише один")

    thresholds = np.unique(y_score)
    # +inf -> нікого не позначаємо позитивним (TP=FP=0). Дає ліву точку ROC (0,0).
    thresholds = np.concatenate([thresholds, [np.inf]])

    # Векторизовано: для кожного t рахуємо, скільки score >= t.
    order = np.argsort(-y_score, kind="mergesort")
    s_sorted = y_score[order]
    y_sorted = y_true[order]
    cum_tp = np.concatenate([[0], np.cumsum(y_sorted)])
    cum_fp = np.concatenate([[0], np.cumsum(1 - y_sorted)])
    # k = кількість об'єктів зі score >= t
    k = np.searchsorted(-s_sorted, -thresholds, side="right")

    TP = cum_tp[k].astype(float)
    FP = cum_fp[k].astype(float)
    FN = P - TP
    TN = N - FP

    tpr = TP / P
    fpr = FP / N
    spec = 1.0 - fpr

    with np.errstate(invalid="ignore", divide="ignore"):
        precision = np.where(TP + FP > 0, TP / np.maximum(TP + FP, 1), np.nan)

    return {
        "threshold": thresholds,
        "TP": TP, "FP": FP, "FN": FN, "TN": TN,
        "tpr": tpr, "fpr": fpr, "recall": tpr, "specificity": spec,
        "precision": precision,
        "youden_J": tpr - fpr,
        "balanced_accuracy": (tpr + spec) / 2.0,
    }


def fbeta(precision: np.ndarray, recall: np.ndarray, beta: float) -> np.ndarray:
    """F_beta з коректною обробкою 0/0: якщо P і R обидва 0 (або P невизначена), F = 0."""
    b2 = beta * beta
    p = np.nan_to_num(precision, nan=0.0)
    denom = b2 * p + recall
    with np.errstate(invalid="ignore", divide="ignore"):
        f = np.where(denom > 0, (1 + b2) * p * recall / np.maximum(denom, 1e-300), 0.0)
    return f


def pick(sw: dict[str, np.ndarray], criterion: str, *,
         beta: float = 1.0, min_precision: float = 0.9) -> int:
    """Індекс обраного порогу для заданого критерію."""
    tpr, fpr = sw["tpr"], sw["fpr"]
    if criterion == "closest01":
        return int(np.argmin(np.sqrt((1 - tpr) ** 2 + fpr ** 2)))
    if criterion == "youden":
        return int(np.argmax(sw["youden_J"]))
    if criterion == "balanced":
        return int(np.argmin(np.abs(sw["specificity"] - tpr)))
    if criterion == "fbeta":
        return int(np.argmax(fbeta(sw["precision"], sw["recall"], beta)))
    if criterion == "min-precision":
        ok = np.nan_to_num(sw["precision"], nan=-1.0) >= min_precision
        if not ok.any():
            raise ValueError(
                f"жоден поріг не дає precision >= {min_precision:.3f}; "
                f"максимум досяжний = {np.nanmax(sw['precision']):.3f}"
            )
        masked = np.where(ok, sw["recall"], -np.inf)
        return int(np.argmax(masked))
    raise ValueError(f"невідомий критерій: {criterion}")


def auc_roc(sw: dict[str, np.ndarray]) -> float:
    """AUC-ROC трапеціями по (fpr, tpr), відсортованих за fpr."""
    o = np.argsort(sw["fpr"], kind="mergesort")
    return float(np.trapezoid(sw["tpr"][o], sw["fpr"][o]))


def report(y_true, y_score, *, criteria, beta, min_precision) -> str:
    sw = sweep(y_true, y_score)
    rows = []
    for c in criteria:
        try:
            i = pick(sw, c, beta=beta, min_precision=min_precision)
        except ValueError as e:
            rows.append((c, None, str(e)))
            continue
        rows.append((c, i, None))

    out = []
    n_pos, n_neg = int(np.sum(y_true)), int(len(y_true) - np.sum(y_true))
    out.append(f"n = {len(y_true)}   позитивних = {n_pos}   негативних = {n_neg}"
               f"   частка позитивних = {n_pos / len(y_true):.4f}")
    out.append(f"AUC-ROC = {auc_roc(sw):.4f}   (Gini = 2*AUC - 1 = {2 * auc_roc(sw) - 1:.4f})")
    out.append("")
    hdr = f"{'критерій':<16}{'поріг t':>10}{'TPR/Recall':>12}{'FPR':>9}{'Spec':>9}{'Precision':>11}{'F1':>9}{'J':>9}{'BA':>9}"
    out.append(hdr)
    out.append("-" * len(hdr))
    f1_all = fbeta(sw["precision"], sw["recall"], 1.0)
    for c, i, err in rows:
        if err is not None:
            out.append(f"{c:<16}  -- {err}")
            continue
        p = sw["precision"][i]
        out.append(
            f"{c:<16}{sw['threshold'][i]:>10.4f}{sw['tpr'][i]:>12.4f}{sw['fpr'][i]:>9.4f}"
            f"{sw['specificity'][i]:>9.4f}{(float('nan') if np.isnan(p) else p):>11.4f}"
            f"{f1_all[i]:>9.4f}{sw['youden_J'][i]:>9.4f}{sw['balanced_accuracy'][i]:>9.4f}"
        )
    out.append("")
    out.append("Еквівалент у scikit-learn (>=1.5):")
    out.append("  from sklearn.model_selection import TunedThresholdClassifierCV")
    out.append("  # youden -> це ДЕФОЛТ, бо J = 2*BA - 1 (максимізація BA тотожна максимізації J)")
    out.append("  TunedThresholdClassifierCV(est, scoring='balanced_accuracy')")
    out.append("  # fbeta:")
    out.append("  from sklearn.metrics import make_scorer, fbeta_score")
    out.append(f"  TunedThresholdClassifierCV(est, scoring=make_scorer(fbeta_score, beta={beta}))")
    out.append("  # фіксований поріг з доменних вимог:")
    out.append("  from sklearn.model_selection import FixedThresholdClassifier")
    out.append("  from sklearn.frozen import FrozenEstimator")
    out.append("  FixedThresholdClassifier(FrozenEstimator(est), threshold=t)")
    return "\n".join(out)


# ---------------------------------------------------------------- self-test

def _analytic_sample(n_per_class: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Вибірка з модельної задачі Лекції 2: f0(x)=2-2x, f1(x)=2x на [0,1].

    Обернене перетворення:
      клас 1: F1(x)=x^2      -> x = sqrt(u)
      клас 0: F0(x)=2x-x^2   -> x = 1 - sqrt(1-u)
    Рівні апріорні ймовірності (по n_per_class на клас) -- формула P=(1+t)/2
    виводиться саме за цієї умови.
    """
    rng = np.random.default_rng(seed)
    x1 = np.sqrt(rng.random(n_per_class))
    x0 = 1.0 - np.sqrt(rng.random(n_per_class))
    y = np.concatenate([np.ones(n_per_class, int), np.zeros(n_per_class, int)])
    s = np.concatenate([x1, x0])
    return y, s


def self_test() -> int:
    """Звірка з аналітикою Лекції 2. Основна істина:
        t* = (3-sqrt(5))/2 ~ 0.381966   (аргмакс F1)
        F1_max = 3 - sqrt(5) ~ 0.763932
        AUC-ROC = AUC-PRC = 5/6 ~ 0.833333
    """
    t_star = (3 - math.sqrt(5)) / 2
    f1_star = 3 - math.sqrt(5)
    auc_star = 5 / 6

    print("Звірка з аналітичною моделлю Лекції 2 (f0=2-2x, f1=2x, рівні апріорні)")
    print(f"  очікуємо: t* = {t_star:.6f}   F1_max = {f1_star:.6f}   AUC = {auc_star:.6f}\n")

    ok = True
    for n in (2_000, 20_000, 200_000):
        y, s = _analytic_sample(n, seed=12345)
        sw = sweep(y, s)
        i = pick(sw, "fbeta", beta=1.0)
        t_hat = sw["threshold"][i]
        f1_hat = fbeta(sw["precision"], sw["recall"], 1.0)[i]
        auc_hat = auc_roc(sw)
        # похибка вибірки ~ 1/sqrt(n); допуск щедрий на малих n, жорсткий на великих
        tol_t = max(0.02, 6.0 / math.sqrt(n))
        tol_f = max(0.01, 3.0 / math.sqrt(n))
        tol_a = max(0.005, 3.0 / math.sqrt(n))
        good = (abs(t_hat - t_star) < tol_t and abs(f1_hat - f1_star) < tol_f
                and abs(auc_hat - auc_star) < tol_a)
        ok &= good
        print(f"  n={2*n:>7}  t={t_hat:.6f} (dt={t_hat-t_star:+.4f}, tol={tol_t:.4f})"
              f"  F1={f1_hat:.6f} (dF={f1_hat-f1_star:+.4f})"
              f"  AUC={auc_hat:.6f} (dA={auc_hat-auc_star:+.4f})"
              f"   {'OK' if good else 'FAIL'}")

    # Youden на цій моделі має давати t=1/2 (BA максимальна = 3/4 при t=1/2)
    y, s = _analytic_sample(200_000, seed=7)
    sw = sweep(y, s)
    j = pick(sw, "youden")
    t_j, ba_j = sw["threshold"][j], sw["balanced_accuracy"][j]
    good_j = abs(t_j - 0.5) < 0.02 and abs(ba_j - 0.75) < 0.01
    ok &= good_j
    print(f"\n  Youden: t={t_j:.6f} (очікуємо 0.5)   BA={ba_j:.6f} (очікуємо 0.75)"
          f"   {'OK' if good_j else 'FAIL'}")

    # J = 2*BA - 1 має виконуватись тотожно на всій сітці
    ident = np.allclose(sw["youden_J"], 2 * sw["balanced_accuracy"] - 1)
    ok &= ident
    print(f"  Тотожність J = 2*BA - 1 на всій сітці порогів: {'OK' if ident else 'FAIL'}")

    print("\n" + ("УСПІХ -- скрипт відтворює аналітику Лекції 2" if ok else "ПРОВАЛ"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--score-col", default="y_score")
    ap.add_argument("--label-col", default="y_true")
    ap.add_argument("--criterion", default="all",
                    choices=("all",) + CRITERIA)
    ap.add_argument("--beta", type=float, default=1.0,
                    help="beta для fbeta: 0.5 коли дорожча хибна тривога, 2 коли дорожчий пропуск")
    ap.add_argument("--min-precision", type=float, default=0.90)
    ap.add_argument("--self-test", action="store_true",
                    help="звірити з аналітикою Лекції 2 і вийти")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if not a.csv:
        ap.error("потрібен --csv (або --self-test)")

    import pandas as pd
    df = pd.read_csv(a.csv)
    for col in (a.score_col, a.label_col):
        if col not in df.columns:
            ap.error(f"колонки '{col}' немає у {a.csv}; наявні: {list(df.columns)}")

    criteria = CRITERIA if a.criterion == "all" else (a.criterion,)
    print(report(df[a.label_col].to_numpy(), df[a.score_col].to_numpy(),
                 criteria=criteria, beta=a.beta, min_precision=a.min_precision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
