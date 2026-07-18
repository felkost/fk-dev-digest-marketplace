#!/usr/bin/env python3
"""Звіт про якість мітки: згода анотаторів, стеля метрики, підозрілі мітки.

Використання:
    python label_quality_report.py --csv d.csv --labels ann1,ann2,ann3
    python label_quality_report.py --csv d.csv --target y --noise-rate 0.12
    python label_quality_report.py --self-test

`--self-test` звіряє з АНАЛІТИЧНОЮ основною істиною: стеля = 1−p,
precision_виміряна = (1−α)·precision_істинна, κ = (p_o−p_e)/(1−p_e).
"""
from __future__ import annotations

import argparse
import itertools
import sys

import numpy as np

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


# --------------------------------------------------------------------------
def ceiling(noise_rate: float) -> float:
    """Стеля будь-якої метрики точності при симетричному шумі p."""
    return 1.0 - noise_rate


def kappa_pair(a: np.ndarray, b: np.ndarray) -> float:
    from sklearn.metrics import cohen_kappa_score
    return float(cohen_kappa_score(a, b))


def percent_agreement(a: np.ndarray, b: np.ndarray) -> float:
    return float((np.asarray(a) == np.asarray(b)).mean())


def fleiss(labels: np.ndarray) -> float | None:
    """labels: (n_обʼєктів, n_анотаторів). None, якщо statsmodels недоступний."""
    try:
        from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa
    except ImportError:
        return None
    table, _ = aggregate_raters(np.asarray(labels))
    return float(fleiss_kappa(table))


def suspect_labels(X, y, est=None, cv=5, thresh=0.95):
    """Confident learning без cleanlab: out-of-fold упевнена незгода з міткою."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict
    est = est or LogisticRegression(max_iter=1000)
    proba = cross_val_predict(est, X, y, cv=cv, method="predict_proba")
    pred = proba.argmax(1)
    conf = proba.max(1)
    mask = (conf > thresh) & (pred != np.asarray(y))
    order = np.argsort(-conf[mask])
    return np.flatnonzero(mask)[order], conf


# --------------------------------------------------------------------------
def report(labels=None, y=None, X=None, noise_rate=None, metric_value=None) -> None:
    if labels is not None:
        labels = np.asarray(labels)
        n_ann = labels.shape[1]
        print(f"--- ЗГОДА АНОТАТОРІВ ({n_ann}) ---")
        base = np.bincount(labels.ravel()) / labels.size
        rare = base.min()
        print(f"частки категорій: {np.round(base, 4).tolist()}  "
              f"(найрідкісніша {rare:.4f})")
        for i, j in itertools.combinations(range(n_ann), 2):
            pa = percent_agreement(labels[:, i], labels[:, j])
            kp = kappa_pair(labels[:, i], labels[:, j])
            print(f"  анотатори {i}-{j}: % згоди={pa:.3f}, κ={kp:.4f}")
        if n_ann >= 3:
            fk = fleiss(labels)
            print(f"  Fleiss κ (усі {n_ann}): "
                  f"{'недоступно (немає statsmodels)' if fk is None else f'{fk:.4f}'}")
        if rare < 0.15:
            print("  ! рідкісний клас: відсоток згоди НЕ звітувати — "
                  "він завищує враження (κ його коригує)")
        ks = [kappa_pair(labels[:, i], labels[:, j])
              for i, j in itertools.combinations(range(n_ann), 2)]
        mk = float(np.mean(ks))
        if mk < 0.40:
            print(f"  ! середня κ={mk:.3f} < 0.40 — мітка непридатна як основна "
                  "істина; спершу інструкція анотування")
        elif mk > 0.80:
            print(f"  ! середня κ={mk:.3f} > 0.80 — перевірте незалежність "
                  "анотаторів (не бачили роботи одне одного / виходу однієї моделі)")

    if noise_rate is not None:
        c = ceiling(noise_rate)
        print(f"\n--- СТЕЛЯ ---")
        print(f"частка хибних міток p={noise_rate:.4f} → стеля точності "
              f"1−p = {c:.4f}")
        if metric_value is not None:
            print(f"досягнуто {metric_value:.4f} = {metric_value / c:.1%} "
                  f"доступного під стелею")
            if metric_value / c > 0.97:
                print("  ! ви фактично вперлись у стелю: далі — не тюнінг, "
                      "а якість міток")

    if X is not None and y is not None:
        idx, conf = suspect_labels(X, y)
        print(f"\n--- ПІДОЗРІЛІ МІТКИ (out-of-fold, впевненість > 0.95) ---")
        print(f"знайдено {len(idx)} з {len(y)} ({len(idx) / len(y):.2%})")
        print(f"перші індекси на аудит: {idx[:15].tolist()}")
        print("  це ЧЕРГА НА РУЧНИЙ АУДИТ, а не список помилок: автоматично "
              "перекидати мітки за передбаченням моделі заборонено")


# --------------------------------------------------------------------------
def self_test() -> int:
    print("=== self-test: звірка з АНАЛІТИЧНОЮ основною істиною ===")
    ok = total = 0

    def chk(label, cond, detail=""):
        nonlocal ok, total
        total += 1
        if cond:
            ok += 1
            print(f"OK   {label}")
        else:
            print(f"FAIL {label} -- {detail}")

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import precision_score, recall_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    rng = np.random.default_rng(11)
    N = 20_000
    X = rng.normal(size=(N, 6))
    ytrue = ((X[:, 0] + 0.7 * X[:, 1] - 0.5 * X[:, 2]) > 0).astype(int)

    def flip(y, p, g):
        y2 = y.copy()
        y2[g.choice(len(y), int(p * len(y)), replace=False)] ^= 1
        return y2

    # 1. стеля 1−p відтворюється точно
    worst = 0.0
    for p in (0.05, 0.15, 0.30):
        yn = flip(ytrue, p, np.random.default_rng(3))
        worst = max(worst, abs((ytrue == yn).mean() - ceiling(p)))
    chk(f"стеля 1−p відтворена (макс. відхилення {worst:.5f})", worst < 0.005)

    # 2-3. асиметрія: шум у train майже не шкодить, у test — знищує
    Xtr, Xte, ytr, yte = train_test_split(X, ytrue, test_size=0.4, random_state=0)
    g = np.random.default_rng(5)
    ytr_n, yte_n = flip(ytr, 0.20, g), flip(yte, 0.20, g)
    clean = LogisticRegression().fit(Xtr, ytr)
    noisy = LogisticRegression().fit(Xtr, ytr_n)
    a_clean = clean.score(Xte, yte)
    a_trnoise = noisy.score(Xte, yte)
    a_tenoise = clean.score(Xte, yte_n)
    chk(f"шум у TRAIN майже не шкодить: {a_clean:.4f} → {a_trnoise:.4f}",
        a_clean - a_trnoise < 0.02, f"падіння {a_clean - a_trnoise:.4f}")
    chk(f"шум у TEST руйнує вимір: {a_clean:.4f} → {a_tenoise:.4f} (стеля 0.80)",
        abs(a_tenoise - 0.80) < 0.02, f"{a_tenoise:.4f}")

    # 4. AUC чистої моделі теж зрізається шумом у test
    auc_c = roc_auc_score(yte, clean.predict_proba(Xte)[:, 1])
    auc_n = roc_auc_score(yte_n, clean.predict_proba(Xte)[:, 1])
    chk(f"AUC: {auc_c:.4f} на чистому test → {auc_n:.4f} на зашумленому",
        auc_c > 0.99 and auc_n < 0.85)

    # 5. асиметричний шум: precision = (1−α)·precision_істинна
    alpha = 0.30
    ya = ytrue.copy()
    pos = np.flatnonzero(ytrue == 1)
    ya[rng.choice(pos, int(alpha * len(pos)), replace=False)] = 0
    Xtr2, Xte2, ytr2, yte2, _, yte2_t = train_test_split(
        X, ya, ytrue, test_size=0.4, random_state=0)
    m2 = LogisticRegression().fit(Xtr2, ytr2)
    p2 = m2.predict(Xte2)
    pr_obs, pr_true = precision_score(yte2, p2), precision_score(yte2_t, p2)
    rc_obs, rc_true = recall_score(yte2, p2), recall_score(yte2_t, p2)
    chk(f"precision {pr_obs:.4f} ≈ (1−α)·{pr_true:.4f} = {(1 - alpha) * pr_true:.4f}",
        abs(pr_obs - (1 - alpha) * pr_true) < 0.02)
    chk(f"recall майже не зачеплений: {rc_obs:.4f} проти {rc_true:.4f}",
        abs(rc_obs - rc_true) < 0.02)

    # 6-7. каппа: той самий % згоди дає різну κ
    g = np.random.default_rng(0)
    a = g.integers(0, 2, 500)
    b = a.copy()
    b[g.choice(500, 100, replace=False)] ^= 1
    k_bal, pa_bal = kappa_pair(a, b), percent_agreement(a, b)
    a2 = (g.random(500) < 0.95).astype(int)
    b2 = a2.copy()
    b2[g.choice(500, 100, replace=False)] ^= 1
    k_rare, pa_rare = kappa_pair(a2, b2), percent_agreement(a2, b2)
    chk(f"збалансовано: %згоди={pa_bal:.3f} → κ={k_bal:.4f} (теорія 0.60)",
        abs(k_bal - 0.60) < 0.05)
    chk(f"рідкісний клас: %згоди={pa_rare:.3f} → κ={k_rare:.4f} — той самий "
        f"відсоток, каппа втричі менша", k_rare < k_bal / 2)

    # 8. κ з формули збігається з sklearn
    po = pa_bal
    pe = sum((a == k).mean() * (b == k).mean() for k in (0, 1))
    chk(f"κ вручну (p_o−p_e)/(1−p_e)={((po - pe) / (1 - pe)):.4f} = sklearn "
        f"{k_bal:.4f}", abs((po - pe) / (1 - pe) - k_bal) < 1e-9)

    # 9. Fleiss на випадкових мітках ≈ 0
    fk = fleiss(np.random.default_rng(1).integers(0, 2, (300, 3)))
    chk(f"Fleiss κ на випадкових мітках = {fk if fk is None else f'{fk:.4f}'} ≈ 0",
        fk is None or abs(fk) < 0.10)

    # 10. проксі: зміщення по групах при однаковій істинній потребі
    g = np.random.default_rng(21)
    n = 20_000
    grp = g.integers(0, 2, n)
    need = g.normal(0, 1, n)
    proxy = need - 0.8 * grp + g.normal(0, 0.3, n)
    feat = np.c_[need + g.normal(0, 0.5, n), grp, g.normal(size=n)]
    from sklearn.linear_model import LinearRegression
    pred = LinearRegression().fit(feat, proxy).predict(feat)
    sel = pred >= np.quantile(pred, 0.90)
    share_pop, share_sel = grp.mean(), grp[sel].mean()
    need0, need1 = need[sel & (grp == 0)].mean(), need[sel & (grp == 1)].mean()
    chk(f"проксі відсіює групу: частка {share_pop:.3f} → {share_sel:.3f} "
        f"серед відібраних", share_sel < share_pop / 2)
    chk(f"а відібрані з неї мають ВИЩУ істинну потребу: {need1:.3f} проти "
        f"{need0:.3f}", need1 > need0 + 0.3)

    # 11. confident learning знаходить внесені помилки
    g = np.random.default_rng(31)
    Xs = g.normal(size=(2000, 4))
    ys = ((Xs[:, 0] + Xs[:, 1]) > 0).astype(int)
    bad = g.choice(2000, 60, replace=False)
    yc = ys.copy()
    yc[bad] ^= 1
    idx, _ = suspect_labels(Xs, yc)
    hit = len(set(idx.tolist()) & set(bad.tolist())) / max(len(idx), 1)
    chk(f"confident learning: {len(idx)} кандидатів, влучність у внесені "
        f"помилки {hit:.1%}", hit > 0.60, f"влучність {hit:.1%}")

    print(f"\n=== {ok}/{total} {'УСПІХ' if ok == total else 'Є ПОМИЛКИ'} ===")
    return 0 if ok == total else 1


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--labels", help="колонки анотаторів через кому: ann1,ann2,ann3")
    ap.add_argument("--target", help="колонка мітки (для пошуку підозрілих)")
    ap.add_argument("--features", help="колонки ознак через кому (з --target)")
    ap.add_argument("--noise-rate", type=float, help="оцінка p з аудиту підвибірки")
    ap.add_argument("--metric", type=float, help="досягнуте значення метрики")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if not a.csv:
        ap.error("потрібен --csv (або --self-test)")

    import pandas as pd
    df = pd.read_csv(a.csv)
    labels = df[a.labels.split(",")].to_numpy() if a.labels else None
    X = y = None
    if a.target:
        y = df[a.target].to_numpy()
        cols = a.features.split(",") if a.features else [
            c for c in df.columns
            if c != a.target and np.issubdtype(df[c].dtype, np.number)]
        X = df[cols].to_numpy(dtype=float)
    report(labels=labels, y=y, X=X, noise_rate=a.noise_rate, metric_value=a.metric)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
