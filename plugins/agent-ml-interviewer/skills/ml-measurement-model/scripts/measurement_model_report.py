#!/usr/bin/env python3
"""Аудит композитної ознаки: надійність, огрублення, інваріантність, допустимість.

Використання:
    python measurement_model_report.py --csv d.csv --items q1,q2,q3,q4
    python measurement_model_report.py --csv d.csv --items q1,q2,q3 --group grp
    python measurement_model_report.py --csv d.csv --items q1,q2,q3 --outcome y
    python measurement_model_report.py --disattenuate 0.42 --rel-x 0.8 --rel-y 0.7
    python measurement_model_report.py --self-test

`--self-test` звіряє з АНАЛІТИЧНОЮ основною істиною: формула послаблення
r_obs = r_true·sqrt(rel_x·rel_y); omega = (Σλ)²/((Σλ)²+Σψ); alpha ≤ omega з
рівністю лише при рівних навантаженнях; поліхорична відновлює r_true.
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
# Надійність
# --------------------------------------------------------------------------
def cronbach_alpha(X: np.ndarray) -> float:
    """Alpha Кронбаха. НИЖНЯ МЕЖА надійності; точна лише при тау-еквівалентності."""
    X = np.asarray(X, dtype=float)
    k = X.shape[1]
    if k < 2:
        return float("nan")
    return float(k / (k - 1) * (1 - X.var(axis=0, ddof=1).sum()
                                / X.sum(axis=1).var(ddof=1)))


def omega_total(loadings: np.ndarray, psi: np.ndarray) -> float:
    """Omega Макдональда для конженеричної моделі (не вимагає рівних λ)."""
    s = float(np.sum(loadings))
    return s ** 2 / (s ** 2 + float(np.sum(psi)))


def omega_from_data(X: np.ndarray, random_state: int = 0) -> tuple[float, np.ndarray]:
    """Оцінити omega через однофакторну модель на стандартизованих ознаках."""
    from sklearn.decomposition import FactorAnalysis
    X = np.asarray(X, dtype=float)
    Xz = (X - X.mean(0)) / X.std(0, ddof=1)
    fa = FactorAnalysis(n_components=1, random_state=random_state).fit(Xz)
    lam = fa.components_[0]
    if lam.sum() < 0:          # знак фактора довільний
        lam = -lam
    psi = np.clip(1.0 - lam ** 2, 1e-9, None)
    return omega_total(lam, psi), lam


def disattenuate(r_obs: float, rel_x: float, rel_y: float = 1.0) -> float:
    """Корекція за послаблення: r_true = r_obs / sqrt(rel_x·rel_y)."""
    return float(r_obs / np.sqrt(rel_x * rel_y))


def attenuate(r_true: float, rel_x: float, rel_y: float = 1.0) -> float:
    """Пряма формула послаблення."""
    return float(r_true * np.sqrt(rel_x * rel_y))


# --------------------------------------------------------------------------
# Огрублення і поліхорична кореляція
# --------------------------------------------------------------------------
def _thresholds(x: np.ndarray, k: int) -> np.ndarray:
    from scipy import stats
    counts = np.bincount(x, minlength=k).astype(float)
    cum = np.cumsum(counts / counts.sum())[:-1]
    return stats.norm.ppf(np.clip(cum, 1e-9, 1 - 1e-9))


def polychoric(x, y, kx: int | None = None, ky: int | None = None) -> float:
    """ML-оцінка поліхоричної кореляції, двокроковий метод Олссона (1979).

    Крок 1 — пороги з маргінальних часток; крок 2 — максимізація
    правдоподібності таблиці спряженості за rho при фіксованих порогах.
    При k=2 з обох боків це тетрахорична кореляція.
    """
    from scipy import optimize, stats
    x = np.asarray(x).astype(int)
    y = np.asarray(y).astype(int)
    x = x - x.min()
    y = y - y.min()
    kx = kx or int(x.max()) + 1
    ky = ky or int(y.max()) + 1
    tab = np.zeros((kx, ky))
    for i, j in zip(x, y):
        tab[i, j] += 1
    ax = np.concatenate([[-np.inf], _thresholds(x, kx), [np.inf]])
    ay = np.concatenate([[-np.inf], _thresholds(y, ky), [np.inf]])

    def negll(rho: float) -> float:
        rho = float(np.clip(rho, -0.999, 0.999))
        mvn = stats.multivariate_normal(mean=[0, 0], cov=[[1, rho], [rho, 1]])
        ll = 0.0
        for i in range(kx):
            for j in range(ky):
                if tab[i, j] == 0:
                    continue
                p = (mvn.cdf([ax[i + 1], ay[j + 1]]) - mvn.cdf([ax[i], ay[j + 1]])
                     - mvn.cdf([ax[i + 1], ay[j]]) + mvn.cdf([ax[i], ay[j]]))
                ll += tab[i, j] * np.log(max(p, 1e-12))
        return -ll

    return float(optimize.minimize_scalar(
        negll, bounds=(-0.99, 0.99), method="bounded").x)


# --------------------------------------------------------------------------
# Допустимість розв'язку
# --------------------------------------------------------------------------
def check_positive_definite(corr: np.ndarray) -> dict:
    """Чи є кореляційна матриця допустимою (усі власні значення > 0)."""
    ev = np.linalg.eigvalsh(np.asarray(corr, dtype=float))
    return {
        "lambda_min": float(ev.min()),
        "det": float(np.linalg.det(np.asarray(corr, dtype=float))),
        "positive_definite": bool(ev.min() > 0),
        "n_negative": int((ev < 0).sum()),
    }


def gmm_degeneracy(gm, X, tol: float = 10.0) -> dict:
    """Чи сіла компонента GaussianMixture на жменю точок (вироджений розв'язок).

    Відбиток виродження: det(Σ) ≈ reg_covar**d — це і є підлога, яку
    reg_covar тихо підставляє замість помилки.
    """
    X = np.asarray(X)
    d = X.shape[1]
    dets = np.array([np.linalg.det(np.atleast_2d(c)) for c in gm.covariances_])
    floor = gm.reg_covar ** d
    return {
        "min_det": float(dets.min()),
        "reg_covar_floor": float(floor),
        "at_floor": bool(dets.min() <= floor * tol),
        "min_component_n": float(gm.weights_.min() * len(X)),
    }


# --------------------------------------------------------------------------
# Інваріантність і парселі
# --------------------------------------------------------------------------
def invariance_probe(X: np.ndarray, group: np.ndarray) -> dict:
    """Груба перевірка: чи тримається різниця композита без кожної окремої ознаки.

    Не заміна формального тесту інваріантності — детектор того, що ВСЯ
    різниця груп тримається на одній ознаці.
    """
    X = np.asarray(X, dtype=float)
    g = np.asarray(group)
    levels = np.unique(g)
    if len(levels) != 2:
        raise ValueError("invariance_probe очікує рівно дві групи")
    a, b = X[g == levels[0]], X[g == levels[1]]
    full = b.mean(1).mean() - a.mean(1).mean()
    per_item = []
    for j in range(X.shape[1]):
        keep = [c for c in range(X.shape[1]) if c != j]
        per_item.append(b[:, keep].mean(1).mean() - a[:, keep].mean(1).mean())
    per_item = np.array(per_item)
    return {
        "diff_full": float(full),
        "diff_drop_one": per_item,
        "max_swing": float(np.abs(per_item - full).max()),
        "worst_item": int(np.argmax(np.abs(per_item - full))),
    }


def parcel_allocation_variability(X: np.ndarray, y: np.ndarray,
                                  n_parcels: int = 2, max_alloc: int = 200) -> dict:
    """Розкид кореляції парселя з outcome по всіх способах розбиття (Sterba PAV)."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    p = X.shape[1]
    size = p // n_parcels
    corrs, seen = [], set()
    for combo in itertools.combinations(range(p), size):
        key = frozenset([combo, tuple(sorted(set(range(p)) - set(combo)))])
        if key in seen:
            continue
        seen.add(key)
        corrs.append(abs(np.corrcoef(X[:, list(combo)].mean(1), y)[0, 1]))
        if len(corrs) >= max_alloc:
            break
    corrs = np.array(corrs)
    mean_r = float(corrs.mean())
    return {
        "n_allocations": len(corrs),
        "min": float(corrs.min()), "max": float(corrs.max()),
        "spread": float(corrs.max() - corrs.min()),
        "sd": float(corrs.std(ddof=1)),
        "sampling_se": float((1 - mean_r ** 2) / np.sqrt(len(y) - 1)),
    }


# --------------------------------------------------------------------------
# Самотест
# --------------------------------------------------------------------------
def self_test() -> int:
    ok = fail = 0

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"OK   {label}")
        else:
            fail += 1
            print(f"FAIL {label}" + (f" -- {detail}" if detail else ""))

    rng = np.random.default_rng(20260719)
    N = 200_000

    # 1. Формула послаблення проти емпірики
    print("\n1) Послаблення надійністю: r_obs = r_true·sqrt(rel_x·rel_y)")
    r_true = 0.60
    T = rng.multivariate_normal([0, 0], [[1, r_true], [r_true, 1]], size=N)
    for rel_x, rel_y in [(0.9, 0.9), (0.8, 0.5), (0.7, 1.0)]:
        ex = rng.normal(0, np.sqrt(1 / rel_x - 1), N) if rel_x < 1 else 0.0
        ey = rng.normal(0, np.sqrt(1 / rel_y - 1), N) if rel_y < 1 else 0.0
        obs = np.corrcoef(T[:, 0] + ex, T[:, 1] + ey)[0, 1]
        theo = attenuate(r_true, rel_x, rel_y)
        check(f"   rel=({rel_x},{rel_y}): вим. {obs:.4f} проти теор. {theo:.4f}",
              abs(obs - theo) < 0.005, f"|Δ|={abs(obs-theo):.4f}")
        check(f"   корекція повертає r_true з {obs:.4f}",
              abs(disattenuate(obs, rel_x, rel_y) - r_true) < 0.01)

    # 2. Стеля R² = надійність цілі
    print("\n2) Стеля R² моделі = надійність цілі (звʼязок детермінований)")
    for rel_y in (0.9, 0.6):
        ey = rng.normal(0, np.sqrt(1 / rel_y - 1), N)
        r2 = np.corrcoef(T[:, 0], T[:, 0] + ey)[0, 1] ** 2
        check(f"   rel_y={rel_y}: max R² = {r2:.4f}", abs(r2 - rel_y) < 0.01)

    # 3. alpha ≤ omega, рівність лише при рівних навантаженнях
    print("\n3) Alpha — нижня межа; збігається з omega лише при рівних λ")
    n = 100_000
    F = rng.normal(0, 1, n)
    for tag, lam in [("рівні λ", np.full(6, 0.70)),
                     ("різкі λ", np.array([0.90, 0.85, 0.80, 0.35, 0.25, 0.20]))]:
        psi = 1 - lam ** 2
        X = np.column_stack([lam[j] * F + rng.normal(0, np.sqrt(psi[j]), n)
                             for j in range(len(lam))])
        a, w = cronbach_alpha(X), omega_total(lam, psi)
        true_rel = lam.sum() ** 2 / X.sum(axis=1).var(ddof=1)
        check(f"   {tag}: alpha={a:.4f} <= omega={w:.4f}", a <= w + 1e-3)
        check(f"   {tag}: omega={w:.4f} відповідає істинній {true_rel:.4f}",
              abs(w - true_rel) < 0.01)
        if tag == "рівні λ":
            check(f"   {tag}: alpha≈omega (розрив {abs(a-w):.4f})", abs(a - w) < 0.005)
        else:
            check(f"   {tag}: alpha ЗАНИЖУЄ на {true_rel-a:.4f}", true_rel - a > 0.02)

    # 4. Незважене середнє програє при нерівних λ і НЕ програє при рівних
    print("\n4) Середнє по колонках оптимальне лише при рівних навантаженнях")
    for tag, lam in [("нерівні λ", np.array([0.9, 0.8, 0.7, 0.4, 0.2])),
                     ("рівні λ", np.full(5, 0.7))]:
        X = np.column_stack([lam[j] * F + rng.normal(0, np.sqrt(1 - lam[j] ** 2), n)
                             for j in range(len(lam))])
        r_mean = abs(np.corrcoef(X.mean(1), F)[0, 1])
        w = lam / (1 - lam ** 2)
        r_w = abs(np.corrcoef(X @ w / w.sum(), F)[0, 1])
        if tag == "нерівні λ":
            check(f"   {tag}: середнє {r_mean:.4f} гірше за зважене {r_w:.4f}",
                  r_w - r_mean > 0.02)
        else:
            check(f"   {tag}: середнє {r_mean:.4f} ≈ зважене {r_w:.4f}",
                  abs(r_w - r_mean) < 0.005)

    # 5. Поліхорична відновлює те, що зруйнувало огрублення
    print("\n5) Поліхорична кореляція відновлює огрублений звʼязок")
    from scipy import stats as _st
    Z = rng.multivariate_normal([0, 0], [[1, 0.6], [0.6, 1]], size=20_000)

    def _cut(z, k):
        return np.digitize(z, _st.norm.ppf(np.linspace(0, 1, k + 1)[1:-1]))

    for k in (2, 5):
        a_, b_ = _cut(Z[:, 0], k), _cut(Z[:, 1], k)
        pear, poly = np.corrcoef(a_, b_)[0, 1], polychoric(a_, b_, k, k)
        check(f"   k={k}: Пірсон {pear:.4f} занижений, поліхорична {poly:.4f}",
              abs(poly - 0.6) < 0.03 and pear < 0.58, f"poly={poly:.4f}")

    # 6. Непозитивно визначена матриця розпізнається
    print("\n6) Розпізнавання недопустимої кореляційної матриці")
    good = np.array([[1, .5, .3], [.5, 1, .4], [.3, .4, 1]])
    bad = np.array([[1, .9, -.9], [.9, 1, .9], [-.9, .9, 1]])
    check("   допустима визнана допустимою", check_positive_definite(good)["positive_definite"])
    r_bad = check_positive_definite(bad)
    check(f"   недопустима спіймана (λ_min={r_bad['lambda_min']:.4f})",
          not r_bad["positive_definite"])

    # 7. Виродження GMM ловиться за відбитком reg_covar**d
    print("\n7) Виродження GaussianMixture за відбитком det(Σ)≈reg_covar**d")
    from sklearn.mixture import GaussianMixture
    import warnings
    Xg = rng.normal(0, 1, (120, 2))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gm_bad = GaussianMixture(n_components=25, reg_covar=1e-6,
                                 random_state=1, max_iter=500).fit(Xg)
        gm_ok = GaussianMixture(n_components=3, reg_covar=1e-6,
                                random_state=1, max_iter=500).fit(Xg)
    d_bad, d_ok = gmm_degeneracy(gm_bad, Xg), gmm_degeneracy(gm_ok, Xg)
    check(f"   k=25 вироджена (min det={d_bad['min_det']:.2e}, "
          f"n компоненти={d_bad['min_component_n']:.1f})", d_bad["at_floor"])
    check(f"   k=3 допустима (min det={d_ok['min_det']:.2e})", not d_ok["at_floor"])

    # 8. Проба інваріантності знаходить саме зсунуту ознаку
    print("\n8) Проба інваріантності вказує на ознаку, що тримає різницю")
    n_g = 50_000
    Fa, Fb = rng.normal(0, 1, n_g), rng.normal(0, 1, n_g)
    A = np.column_stack([0.8 * Fa + rng.normal(0, 0.6, n_g) for _ in range(5)])
    B = np.column_stack([0.8 * Fb + rng.normal(0, 0.6, n_g) for _ in range(5)])
    B[:, 2] += 0.8
    X_all = np.vstack([A, B])
    g_all = np.r_[np.zeros(n_g), np.ones(n_g)]
    res = invariance_probe(X_all, g_all)
    check(f"   повна різниця {res['diff_full']:+.4f} без істинної різниці",
          res["diff_full"] > 0.1)
    check(f"   винуватець — ознака №{res['worst_item']} (очікувано 2)",
          res["worst_item"] == 2)
    check(f"   без неї різниця зникає ({res['diff_drop_one'][2]:+.4f})",
          abs(res["diff_drop_one"][2]) < 0.05)

    # 9. Розкид від розбиття на парселі порівнюваний із вибірковою похибкою
    print("\n9) Parcel allocation variability")
    n_p = 3000
    Fp = rng.normal(0, 1, n_p)
    lam_p = np.array([0.85, 0.80, 0.75, 0.70, 0.45, 0.40, 0.35, 0.30])
    Xp = np.column_stack([lam_p[j] * Fp + rng.normal(0, np.sqrt(1 - lam_p[j] ** 2), n_p)
                          for j in range(8)])
    yp = 0.5 * Fp + rng.normal(0, np.sqrt(0.75), n_p)
    pav = parcel_allocation_variability(Xp, yp)
    check(f"   {pav['n_allocations']} розбиттів, розмах {pav['spread']:.4f}",
          pav["n_allocations"] == 35 and pav["spread"] > 0.03)
    check(f"   sd розбиття {pav['sd']:.4f} не менша за вибіркову SE "
          f"{pav['sampling_se']:.4f}", pav["sd"] >= pav["sampling_se"] * 0.8)

    print(f"\n{'=' * 60}\nПідсумок: {ok} OK, {fail} FAIL")
    print("УСПІХ" if fail == 0 else "ПРОВАЛ")
    return 0 if fail == 0 else 1


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--items", help="колонки композита через кому")
    ap.add_argument("--group", help="колонка групи для проби інваріантності")
    ap.add_argument("--outcome", help="колонка outcome для парселів")
    ap.add_argument("--disattenuate", type=float, metavar="R_OBS")
    ap.add_argument("--rel-x", type=float, default=1.0)
    ap.add_argument("--rel-y", type=float, default=1.0)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    if a.disattenuate is not None:
        r_t = disattenuate(a.disattenuate, a.rel_x, a.rel_y)
        print(f"r спостережена   : {a.disattenuate:.4f}")
        print(f"надійності       : rel_x={a.rel_x:.3f}  rel_y={a.rel_y:.3f}")
        print(f"r виправлена     : {r_t:.4f}")
        if abs(r_t) > 1:
            print("УВАГА: |r| > 1 — надійності занижені або модель не тримається.")
        return 0

    if not (a.csv and a.items):
        ap.error("потрібні --csv і --items (або --self-test, або --disattenuate)")

    import pandas as pd
    df = pd.read_csv(a.csv)
    cols = [c.strip() for c in a.items.split(",")]
    X = df[cols].to_numpy(dtype=float)

    print(f"Композит із {len(cols)} ознак, n={len(X)}")
    print("=" * 60)

    alpha = cronbach_alpha(X)
    om, lam = omega_from_data(X)
    print(f"alpha Кронбаха      : {alpha:.4f}   (нижня межа; точна лише при рівних λ)")
    print(f"omega Макдональда   : {om:.4f}   (конженерична — беріть це)")
    print(f"навантаження        : {np.round(lam, 3)}")
    spread = float(lam.max() - lam.min())
    print(f"розкид навантажень  : {spread:.3f}", end="  ")
    print("-> середнє НЕ оптимальне, зважте" if spread > 0.25 else "-> середнє прийнятне")
    print(f"стеля |r| з будь-чим : {np.sqrt(max(om, 0)):.4f}   (= sqrt(надійності))")

    ncat = [len(np.unique(X[:, j])) for j in range(X.shape[1])]
    coarse = [cols[j] for j in range(len(cols)) if ncat[j] < 5]
    if coarse:
        print(f"\nОгрублені ознаки (<5 рівнів): {coarse}")
        print("  Пірсон між ними занижений — рахуйте поліхоричну (див. SKILL.md Крок 3).")

    corr = np.corrcoef(X, rowvar=False)
    pd_res = check_positive_definite(corr)
    print(f"\nМатриця кореляцій   : λ_min={pd_res['lambda_min']:+.4f}  "
          f"{'ДОПУСТИМА' if pd_res['positive_definite'] else 'НЕДОПУСТИМА'}")
    if not pd_res["positive_definite"]:
        print("  Причина №1 — попарне видалення пропусків. Використайте dropna()")
        print("  або імпутацію (ml-missing-data), не pandas .corr() на дірявих даних.")

    if a.group:
        res = invariance_probe(X, df[a.group].to_numpy())
        print(f"\nПроба інваріантності за '{a.group}'")
        print(f"  різниця композитів      : {res['diff_full']:+.4f}")
        print(f"  найбільший зсув без 1   : {res['max_swing']:.4f} "
              f"(ознака '{cols[res['worst_item']]}')")
        if res["max_swing"] > abs(res["diff_full"]) * 0.5:
            print("  УВАГА: різницю груп тримає переважно одна ознака —")
            print("  це підпис неінваріантності, а не змістовної різниці.")

    if a.outcome:
        pav = parcel_allocation_variability(X, df[a.outcome].to_numpy(dtype=float))
        print(f"\nParcel allocation variability ({pav['n_allocations']} розбиттів)")
        print(f"  r з outcome: {pav['min']:.4f}..{pav['max']:.4f}  "
              f"розмах {pav['spread']:.4f}")
        print(f"  sd розбиття {pav['sd']:.4f} проти вибіркової SE {pav['sampling_se']:.4f}")
        if pav["sd"] > pav["sampling_se"]:
            print("  Вибір розбиття вносить більше варіативності, ніж вибірка.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
