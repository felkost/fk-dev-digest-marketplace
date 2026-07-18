#!/usr/bin/env python3
"""VIF-аудит мультиколінеарності за драбиною курсу: heatmap-скринінг -> VIF -> прунінг.

Використання:
  python collinearity_report.py --csv data.csv --features x1,x2,x3,x4
  python collinearity_report.py --csv data.csv            # усі числові колонки
  python collinearity_report.py --self-test

Правила курсу (Л2-3): |r|>0.8 -> рахувати VIF; VIF>5 сильна; VIF>10 -- втручання.
Дві пастки, які скрипт закриває:
  1) variance_inflation_factor БЕЗ константного стовпця тихо хибний на даних із
     ненульовим середнім (регресія без інтерсепта мусить моделювати рівень).
  2) Блокова колінеарність (x3 ~ x1 + x2) невидима попарній кореляції:
     всі |r| ~ 0.7 < 0.8, а VIF -- десятки. Тому VIF рахуємо завжди.

Вимоги: numpy, pandas, statsmodels.
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

T_CORR, T_STRONG, T_SEVERE = 0.8, 5.0, 10.0


def vif_table(X: np.ndarray, names: list[str]) -> list[tuple[str, float]]:
    """VIF з обов'язковою константою (пастка №1)."""
    import statsmodels.api as sm
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    Xc = sm.add_constant(np.asarray(X, dtype=float), has_constant="add")
    # індекси 1..k: константу не звітуємо, але вона в матриці ОБОВ'ЯЗКОВА
    return [(names[j], float(variance_inflation_factor(Xc, j + 1)))
            for j in range(len(names))]


def vif_manual(X: np.ndarray, j: int) -> float:
    """Незалежна перевірка визначення: VIF_j = 1/(1-R²_j) через sklearn."""
    from sklearn.linear_model import LinearRegression
    y = X[:, j]
    Z = np.delete(X, j, axis=1)
    r2 = LinearRegression().fit(Z, y).score(Z, y)   # з інтерсептом
    return float("inf") if r2 >= 1 else 1.0 / (1.0 - r2)


def corr_screen(X: np.ndarray, names: list[str]) -> list[tuple[str, str, float]]:
    C = np.corrcoef(np.asarray(X, dtype=float), rowvar=False)
    out = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if abs(C[i, j]) > T_CORR:
                out.append((names[i], names[j], float(C[i, j])))
    return sorted(out, key=lambda t: -abs(t[2]))


def prune(X: np.ndarray, names: list[str], threshold: float = T_SEVERE):
    """Ітеративно видаляє найгірший VIF > threshold; повертає (лишились, послідовність)."""
    X = np.asarray(X, dtype=float).copy()
    names = list(names)
    dropped = []
    while len(names) >= 2:
        tab = vif_table(X, names)
        worst_name, worst_v = max(tab, key=lambda t: t[1])
        if not np.isfinite(worst_v) or worst_v > threshold:
            k = names.index(worst_name)
            dropped.append((worst_name, worst_v))
            X = np.delete(X, k, axis=1)
            names.pop(k)
        else:
            break
    return names, dropped


def report(X: np.ndarray, names: list[str]) -> str:
    L = [f"n = {X.shape[0]}   ознак = {len(names)}", ""]
    pairs = corr_screen(X, names)
    L.append(f"1) Скринінг кореляцій (|r| > {T_CORR}):")
    if pairs:
        for a, b, r in pairs:
            L.append(f"   {a} ~ {b}: r = {r:+.3f}")
    else:
        L.append("   пар немає — але це НЕ виправдання пропустити VIF (блокова колінеарність невидима попарно)")
    L.append("")
    tab = vif_table(X, names)
    L.append("2) VIF (з константою; пороги курсу: >5 сильна, >10 втручання):")
    for name, v in sorted(tab, key=lambda t: -t[1]):
        mark = "  << ВТРУЧАННЯ" if v > T_SEVERE else ("  << сильна" if v > T_STRONG else "")
        L.append(f"   {name:<20} VIF = {v:>10.2f}{mark}")
    L.append("")
    kept, dropped = prune(X, names)
    L.append(f"3) Ітеративний прунінг (поріг {T_SEVERE}):")
    if dropped:
        for name, v in dropped:
            L.append(f"   видалено {name} (VIF був {v:.1f})")
        L.append(f"   лишилось: {', '.join(kept)}")
    else:
        L.append("   видаляти нічого")
    L.append("")
    L.append("Правило курсу: оптимізуєте точність RF/XGB — колінеарність можна лишити;")
    L.append("оптимізуєте інтерпретацію/коефіцієнти — пруньте за списком вище.")
    return "\n".join(L)


def self_test() -> int:
    rng = np.random.default_rng(7)
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'OK ' if cond else 'FAIL'} {label}")

    n = 800
    print("1) Незалежні ознаки з НЕнульовим середнім (демо пастки константи)")
    X = rng.normal(loc=5.0, scale=1.0, size=(n, 3))
    names = ["a", "b", "c"]
    tab = dict(vif_table(X, names))
    check("з константою всі VIF ~ 1", all(v < 1.2 for v in tab.values()))
    # відтворюємо ПОМИЛКОВИЙ виклик без константи:
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    bad = [variance_inflation_factor(X, j) for j in range(3)]
    check(f"БЕЗ константи VIF роздуті (min={min(bad):.1f} >> 1) — пастка реальна",
          min(bad) > 5)

    print("2) Блокова колінеарність x3 = x1 + x2 + шум (невидима попарно)")
    x1, x2 = rng.normal(size=n), rng.normal(size=n)
    x3 = x1 + x2 + rng.normal(scale=0.35, size=n)
    Xb = np.column_stack([x1, x2, x3])
    r = np.corrcoef(Xb, rowvar=False)
    max_pair = max(abs(r[0, 2]), abs(r[1, 2]), abs(r[0, 1]))
    check(f"усі попарні |r| < 0.8 (max = {max_pair:.2f}) — скринінг мовчить",
          max_pair < T_CORR)
    tabb = dict(vif_table(Xb, ["x1", "x2", "x3"]))
    check(f"а VIF ловить (max = {max(tabb.values()):.1f} > {T_SEVERE})",
          max(tabb.values()) > T_SEVERE)

    print("3) Звірка з визначенням 1/(1-R²) через sklearn")
    v_sm = dict(vif_table(Xb, ["x1", "x2", "x3"]))["x3"]
    v_man = vif_manual(Xb, 2)
    check(f"statsmodels {v_sm:.3f} == manual {v_man:.3f} (до 1e-6)",
          abs(v_sm - v_man) < 1e-6)
    r2 = 1 - 1 / v_man
    check(f"таблиця курсу: VIF {v_man:.1f} <-> R² {r2:.3f} (1/(1-R²) тотожно)", 0 < r2 < 1)

    print("4) Прунінг повертає блок під поріг одним видаленням")
    kept, dropped = prune(Xb, ["x1", "x2", "x3"])
    check(f"видалено рівно одну ({dropped[0][0] if dropped else '—'}), лишилось 2",
          len(dropped) == 1 and len(kept) == 2)
    tab_after = vif_table(Xb[:, [0, 1]] if dropped and dropped[0][0] == "x3"
                          else Xb[:, [i for i in range(3) if ["x1","x2","x3"][i] in kept]], kept)
    check("після прунінгу всі VIF < 5", all(v < T_STRONG for _, v in tab_after))

    print()
    print("УСПІХ" if ok else "ПРОВАЛ")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--features", help="через кому; без прапорця — всі числові")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.csv:
        ap.error("потрібен --csv (або --self-test)")
    import pandas as pd
    df = pd.read_csv(a.csv)
    if a.features:
        names = [c.strip() for c in a.features.split(",")]
        missing = [c for c in names if c not in df.columns]
        if missing:
            ap.error(f"немає колонок: {missing}")
    else:
        names = df.select_dtypes("number").columns.tolist()
        if len(names) < 2:
            ap.error("менше двох числових колонок")
    X = df[names].dropna().to_numpy(dtype=float)
    print(report(X, names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
