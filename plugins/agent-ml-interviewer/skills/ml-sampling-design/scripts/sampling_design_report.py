#!/usr/bin/env python3
"""Звіт про дизайн вибірки: ICC, design effect, ефективний n, вплив ваг.

Використання:
    python sampling_design_report.py --csv d.csv --target y --cluster school_id
    python sampling_design_report.py --csv d.csv --target y --weight w --strata region
    python sampling_design_report.py --self-test

`--self-test` звіряє кожну величину з АНАЛІТИЧНОЮ основною істиною
(deff = 1+(m-1)·ICC, SE_ratio = sqrt(deff), незміщеність зваженого середнього),
а не з попереднім прогоном самого скрипта.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


# --------------------------------------------------------------------------
def icc_oneway(y: np.ndarray, groups: np.ndarray) -> tuple[float, float, float]:
    """ICC за однофакторним ANOVA-розкладом. Повертає (ICC, m_середнє, k)."""
    y = np.asarray(y, dtype=float)
    codes, inv = np.unique(groups, return_inverse=True)
    k = len(codes)
    if k < 2:
        raise ValueError("потрібно щонайменше 2 кластери")
    sizes = np.bincount(inv)
    means = np.bincount(inv, weights=y) / sizes
    grand = y.mean()
    msb = (sizes * (means - grand) ** 2).sum() / (k - 1)
    within = ((y - means[inv]) ** 2).sum()
    dfw = len(y) - k
    msw = within / dfw if dfw > 0 else 0.0
    # m0 — «ефективний» розмір кластера для незбалансованих даних
    n = len(y)
    m0 = (n - (sizes ** 2).sum() / n) / (k - 1)
    denom = msb + (m0 - 1) * msw
    icc = (msb - msw) / denom if denom > 0 else 0.0
    return float(np.clip(icc, 0.0, 1.0)), float(m0), int(k)


def design_effect(icc: float, m: float) -> float:
    return 1.0 + (m - 1.0) * icc


def weighted_mean(y: np.ndarray, w: np.ndarray) -> float:
    return float(np.average(y, weights=w))


def cluster_se_mean(y: np.ndarray, groups: np.ndarray) -> float:
    """Кластерна SE середнього (sandwich) без statsmodels."""
    y = np.asarray(y, dtype=float)
    codes, inv = np.unique(groups, return_inverse=True)
    k, n = len(codes), len(y)
    resid = y - y.mean()
    sums = np.bincount(inv, weights=resid)          # сума залишків у кластері
    meat = (sums ** 2).sum()
    var = meat / (n ** 2)
    corr = (k / (k - 1)) * ((n - 1) / max(n - 1, 1))  # мала поправка на df
    return float(np.sqrt(var * corr))


def naive_se_mean(y: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    return float(y.std(ddof=1) / np.sqrt(len(y)))


# --------------------------------------------------------------------------
def report(y, groups=None, weights=None, strata=None) -> None:
    y = np.asarray(y, dtype=float)
    n = len(y)
    print(f"n рядків: {n}")
    print(f"наївне середнє: {y.mean():.4f}   наївна SE: {naive_se_mean(y):.5f}")

    if weights is not None:
        w = np.asarray(weights, dtype=float)
        wm = weighted_mean(y, w)
        print(f"\n--- ВАГИ ---")
        print(f"зважене середнє: {wm:.4f}   (наївне {y.mean():.4f}, "
              f"різниця {wm - y.mean():+.4f})")
        cv_w = w.std() / w.mean()
        print(f"розкид ваг CV={cv_w:.3f}; Kish n_eff = "
              f"{w.sum() ** 2 / (w ** 2).sum():.1f} з {n}")
        if cv_w > 0.5:
            print("  ! ваги дуже нерівні — оцінки нестабільні, розгляньте "
                  "обрізання (trimming) верхніх ваг")
        print("  НАГАДУВАННЯ: ваги мають бути подані і у fit, і в scorer — "
              "без metadata routing метрика лишиться незваженою МОВЧКИ")

    if groups is not None:
        icc, m0, k = icc_oneway(y, groups)
        deff = design_effect(icc, m0)
        se_c, se_n = cluster_se_mean(y, groups), naive_se_mean(y)
        print(f"\n--- КЛАСТЕРИ ---")
        print(f"кластерів k={k}, середній розмір m={m0:.2f}")
        print(f"ICC={icc:.4f}   deff=1+(m-1)·ICC={deff:.3f}")
        print(f"ефективний n = n/deff = {n / deff:.1f}  (з {n})")
        print(f"SE: наївна={se_n:.5f}, кластерна={se_c:.5f}, "
              f"відношення={se_c / se_n:.3f} (теорія sqrt(deff)={np.sqrt(deff):.3f})")
        if k < 40:
            print(f"  ! кластерів лише {k}: кластерні SE самі зміщені вниз "
                  "(виміряне покриття 95% ДІ при k=10 — 0.937)")
        if deff > 2:
            print(f"  ! у звіті вказуйте n_eff={n / deff:.0f}, не n={n}; "
                  "групування у CV обов'язкове (GroupKFold)")

    if strata is not None:
        st = np.asarray(strata)
        print(f"\n--- СТРАТИ ---")
        for s in np.unique(st):
            msk = st == s
            print(f"  {s}: n={msk.sum():5d} ({msk.mean():6.1%}), "
                  f"середнє y={y[msk].mean():.4f}")
        print("  якщо частки страт у вибірці ≠ часток у популяції — потрібні ваги")


# --------------------------------------------------------------------------
def self_test() -> int:
    print("=== self-test: звірка з АНАЛІТИЧНОЮ основною істиною ===")
    ok = 0
    total = 0

    def chk(label, cond, detail=""):
        nonlocal ok, total
        total += 1
        if cond:
            ok += 1
            print(f"OK   {label}")
        else:
            print(f"FAIL {label} -- {detail}")

    # 1-3. deff і SE на трьох розмірах: збіг із sqrt(deff) має РОСТИ з k
    for k, tol in ((40, 0.05), (200, 0.02), (500, 0.01)):
        g = np.random.default_rng(1)
        m, icc_true = 25, 0.20
        u = g.normal(0, np.sqrt(icc_true), k)
        y = np.repeat(u, m) + g.normal(0, np.sqrt(1 - icc_true), k * m)
        gid = np.repeat(np.arange(k), m)
        icc, m0, kk = icc_oneway(y, gid)
        deff = design_effect(icc, m0)
        ratio = cluster_se_mean(y, gid) / naive_se_mean(y)
        chk(f"k={k}: SE_ratio={ratio:.3f} ≈ sqrt(deff)={np.sqrt(deff):.3f}",
            abs(ratio - np.sqrt(deff)) < tol,
            f"розбіжність {abs(ratio - np.sqrt(deff)):.4f} > {tol}")

    # 4. ICC відновлюється з великої кількості кластерів
    g = np.random.default_rng(2)
    u = g.normal(0, np.sqrt(0.20), 800)
    y = np.repeat(u, 20) + g.normal(0, np.sqrt(0.80), 800 * 20)
    icc, _, _ = icc_oneway(y, np.repeat(np.arange(800), 20))
    chk(f"ICC={icc:.4f} відновлює задану 0.20 (±0.02)", abs(icc - 0.20) < 0.02)

    # 5. крайній випадок ICC=0 → deff=1
    g = np.random.default_rng(3)
    y = g.normal(size=2000)
    icc0, m0, _ = icc_oneway(y, np.repeat(np.arange(100), 20))
    chk(f"незалежні дані: ICC={icc0:.4f}→0, deff={design_effect(icc0, m0):.3f}→1",
        design_effect(icc0, m0) < 1.15)

    # 6. крайній випадок ICC=1 → n_eff = k
    y_id = np.repeat(np.arange(50, dtype=float), 20)   # усередині кластера — константа
    icc1, m1, k1 = icc_oneway(y_id, np.repeat(np.arange(50), 20))
    deff1 = design_effect(icc1, m1)
    chk(f"ідентичні всередині кластера: ICC={icc1:.3f}→1, n_eff={1000 / deff1:.1f}→k={k1}",
        abs(1000 / deff1 - k1) < 2, f"n_eff={1000 / deff1:.2f} проти k={k1}")

    # 7. зважене середнє незміщене, наївне — ні
    g = np.random.default_rng(4)
    N = 200_000
    strat = g.integers(0, 2, N)
    val = np.where(strat == 1, 10.0, 0.0) + g.normal(0, 1, N)
    p = np.where(strat == 1, 0.50, 0.05)
    sel = g.random(N) < p
    wt = 1.0 / p[sel]
    truth, naive, wmean = val.mean(), val[sel].mean(), weighted_mean(val[sel], wt)
    chk(f"зважене {wmean:.4f} ≈ істина {truth:.4f} (наївне {naive:.4f} — зміщене)",
        abs(wmean - truth) < 0.05 and abs(naive - truth) > 1.0)

    # 8. вага=const не змінює середнього
    g = np.random.default_rng(5)
    yy = g.normal(size=500)
    chk("сталі ваги не змінюють середнього",
        abs(weighted_mean(yy, np.full(500, 3.7)) - yy.mean()) < 1e-12)

    print(f"\n=== {ok}/{total} {'УСПІХ' if ok == total else 'Є ПОМИЛКИ'} ===")
    return 0 if ok == total else 1


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--target", help="числова колонка, за якою рахувати ICC/середнє")
    ap.add_argument("--cluster", help="колонка-ідентифікатор кластера")
    ap.add_argument("--weight", help="колонка з вагами вибірки")
    ap.add_argument("--strata", help="колонка страти")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if not a.csv or not a.target:
        ap.error("потрібні --csv і --target (або --self-test)")

    import pandas as pd
    df = pd.read_csv(a.csv)
    report(
        df[a.target].to_numpy(dtype=float),
        groups=df[a.cluster].to_numpy() if a.cluster else None,
        weights=df[a.weight].to_numpy(dtype=float) if a.weight else None,
        strata=df[a.strata].to_numpy() if a.strata else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
