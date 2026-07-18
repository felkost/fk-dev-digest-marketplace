#!/usr/bin/env python3
"""Діагностика механізму пропусків: MCAR проти MAR, за передбачуваністю індикатора.

Ідея (references/derivations.md): різниця між MCAR і MAR лежить цілком у
спостережених даних. Якщо індикатор пропуску колонки j передбачається рештою
колонок — механізм MAR, і ті предиктори зобов'язані бути в моделі імпутації.
Якщо не передбачається (AUC ~ 0.5) — це сумісно з MCAR (не доводить його).

MNAR цим способом НЕ виявляється в принципі — залежність від самого пропущеного
значення не має спостережних наслідків. Непрямий сигнал (індикатор пов'язаний
із ціллю сильніше, ніж з ознаками) рахується окремо, якщо передано --target.

Використання:
  python missingness_report.py --csv data.csv [--target y] [--min-auc 0.65]
  python missingness_report.py --self-test
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

RANDOM_STATE = 0
# Поріг умовний, як VIF 5/10: нижче — немає доказу залежності, вище — є.
# Обґрунтування саме 0.65: на n~1000 AUC випадкової моделі має розкид ~±0.03,
# тож 0.65 — це впевнено поза шумом, але не вимагає сильного зв'язку.
DEFAULT_MIN_AUC = 0.65


def missingness_auc(X: np.ndarray, col: int, random_state: int = RANDOM_STATE) -> float:
    """ROC-AUC передбачення індикатора пропуску колонки `col` за рештою колонок.

    Решта колонок сама може мати пропуски, тому імпутується медіаною ВСЕРЕДИНІ
    крос-валідації (Pipeline) — інакше витік з валідаційних фолдів у діагностику.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.pipeline import Pipeline

    y = np.isnan(X[:, col]).astype(int)
    if y.sum() == 0 or y.sum() == len(y):
        return float("nan")  # немає пропусків або всі — питання не стоїть

    rest = np.delete(X, col, axis=1)
    if rest.shape[1] == 0:
        return float("nan")

    # Мінімум 2 приклади кожного класу на фолд
    n_splits = min(5, int(y.sum()), int((1 - y).sum()))
    if n_splits < 2:
        return float("nan")

    pipe = Pipeline([
        ("imp", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("clf", RandomForestClassifier(n_estimators=200, random_state=random_state,
                                       n_jobs=1)),
    ])
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    scores = cross_val_score(pipe, rest, y, cv=cv, scoring="roc_auc")
    return float(np.mean(scores))


def report(X: np.ndarray, names: list[str], target: np.ndarray | None = None,
           min_auc: float = DEFAULT_MIN_AUC) -> list[dict]:
    rows = []
    for j, name in enumerate(names):
        miss = np.isnan(X[:, j])
        frac = float(miss.mean())
        if frac == 0:
            continue
        auc = missingness_auc(X, j)
        verdict = ("MAR (пропуск передбачається)" if auc == auc and auc >= min_auc
                   else "сумісно з MCAR")
        row = {"col": name, "frac": frac, "auc": auc, "verdict": verdict}
        if target is not None:
            # непрямий сигнал MNAR: індикатор пов'язаний із ціллю
            t = target[~np.isnan(target)] if np.issubdtype(target.dtype, np.floating) else target
            if len(t) == len(miss):
                grp1 = t[miss]
                grp0 = t[~miss]
                if len(grp1) > 1 and len(grp0) > 1:
                    pooled = np.sqrt((grp1.var(ddof=1) + grp0.var(ddof=1)) / 2)
                    row["target_d"] = float(abs(grp1.mean() - grp0.mean()) / pooled) \
                        if pooled > 0 else 0.0
        rows.append(row)
    return rows


def print_report(rows: list[dict], min_auc: float) -> None:
    if not rows:
        print("Пропусків не знайдено — діагностика механізму не потрібна.")
        return
    has_t = any("target_d" in r for r in rows)
    hdr = f"{'колонка':<20}{'частка':>9}{'AUC':>8}   вердикт"
    if has_t:
        hdr += "   |d| до цілі"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        auc_s = "  н/д" if r["auc"] != r["auc"] else f"{r['auc']:.3f}"
        line = f"{r['col']:<20}{r['frac']:>8.1%}{auc_s:>8}   {r['verdict']}"
        if has_t:
            line += f"   {r.get('target_d', float('nan')):.2f}"
        print(line)
    print()
    print(f"Поріг AUC = {min_auc} (конвенція, не теорема).")
    print("MAR -> предиктори, що дали AUC, МАЮТЬ бути в моделі імпутації.")
    print("Сумісно з MCAR -> це НЕ доказ MCAR, лише відсутність знайденої залежності.")
    if has_t:
        print("|d| до цілі — непрямий сигнал MNAR; великий |d| при низькій AUC")
        print("  означає: пропуск пов'язаний із ціллю, але не з ознаками -> не")
        print("  імпутувати наївно, додати індикатор. Доказом MNAR це не є.")


def self_test() -> int:
    """Перевірка проти синтетичної істини: механізм відомий за побудовою."""
    rng = np.random.default_rng(0)
    n = 1500
    ok = True

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        print(("OK   " if cond else "FAIL ") + label + (f" -- {detail}" if detail else ""))
        if not cond:
            ok = False

    # Спільна основа: три корельовані ознаки
    age = rng.normal(40, 12, n)
    income = 0.5 * age + rng.normal(0, 10, n)
    score = rng.normal(0, 1, n)

    # --- 1. MCAR: маска незалежна від усього ---------------------------------
    X_mcar = np.column_stack([age, income.copy(), score])
    mask_mcar = rng.random(n) < 0.25
    X_mcar[mask_mcar, 1] = np.nan
    auc_mcar = missingness_auc(X_mcar, 1)
    check(f"MCAR: AUC ~ 0.5 (отримано {auc_mcar:.3f})", 0.42 <= auc_mcar <= 0.58,
          f"{auc_mcar:.3f}")

    # --- 2. MAR: маска залежить від СПОСТЕРЕЖЕНОЇ age -------------------------
    X_mar = np.column_stack([age, income.copy(), score])
    p_mar = 1 / (1 + np.exp(-(age - 40) / 5))          # старші частіше пропускають
    mask_mar = rng.random(n) < p_mar
    X_mar[mask_mar, 1] = np.nan
    auc_mar = missingness_auc(X_mar, 1)
    check(f"MAR: AUC помітно > 0.5 (отримано {auc_mar:.3f})", auc_mar >= 0.75,
          f"{auc_mar:.3f}")
    check("MAR відрізняється від MCAR щонайменше на 0.2 AUC",
          (auc_mar - auc_mcar) >= 0.20, f"різниця {auc_mar - auc_mcar:.3f}")

    # --- 3. MNAR: маска залежить від САМОГО income, і це НЕ видно -------------
    # income корелює з age (r~0.5), тож слабкий слід лишиться; ключове —
    # AUC помітно нижча, ніж при MAR тієї ж сили, бо прямої причини в даних немає.
    X_mnar = np.column_stack([age, income.copy(), score])
    p_mnar = 1 / (1 + np.exp(-(income - income.mean()) / 5))
    mask_mnar = rng.random(n) < p_mnar
    X_mnar[mask_mnar, 1] = np.nan
    auc_mnar = missingness_auc(X_mnar, 1)
    check(f"MNAR: AUC нижча за MAR (MNAR {auc_mnar:.3f} < MAR {auc_mar:.3f})",
          auc_mnar < auc_mar, f"MNAR {auc_mnar:.3f} vs MAR {auc_mar:.3f}")

    # --- 4. Середнє занижує дисперсію (вивід derivations.md) -----------------
    col = X_mcar[:, 1]
    obs = col[~np.isnan(col)]
    filled = np.where(np.isnan(col), obs.mean(), col)
    ratio = filled.var(ddof=1) / obs.var(ddof=1)
    expected = (len(obs) - 1) / (len(col) - 1)
    check(f"імпутація середнім занижує дисперсію: {ratio:.3f} ~ {expected:.3f}",
          abs(ratio - expected) < 0.02, f"{ratio:.4f} проти {expected:.4f}")

    # --- 5. Жива пастка: add_indicator не бачить колонок, чистих у train ------
    from sklearn.impute import SimpleImputer
    Xtr = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    Xte = np.array([[np.nan, 2.0], [3.0, np.nan]])
    si = SimpleImputer(add_indicator=True).fit(Xtr)
    check("add_indicator: жодного індикатора при чистому train",
          len(si.indicator_.features_) == 0 and si.transform(Xte).shape[1] == 2,
          f"features_={si.indicator_.features_}, shape={si.transform(Xte).shape}")

    # --- 6. Жива пастка: None в object-колонці не заповнюється ---------------
    Xo = np.array([["a"], [None], ["b"], ["a"]], dtype=object)
    out_default = SimpleImputer(strategy="most_frequent").fit_transform(Xo)
    out_fixed = SimpleImputer(missing_values=None,
                              strategy="most_frequent").fit_transform(Xo)
    check("None не чіпається дефолтом, але лікується missing_values=None",
          any(v is None for v in out_default.ravel())
          and not any(v is None for v in out_fixed.ravel()))

    # --- 7. Жива пастка: колонка з суцільних NaN зникає ----------------------
    Xe = np.array([[1.0, np.nan], [2.0, np.nan]])
    n_default = SimpleImputer().fit_transform(Xe).shape[1]
    n_keep = SimpleImputer(keep_empty_features=True).fit_transform(Xe).shape[1]
    check(f"порожня колонка: дефолт {n_default}, keep_empty_features {n_keep}",
          n_default == 1 and n_keep == 2)

    print()
    print("УСПІХ — усі перевірки пройдено." if ok else "Є розбіжності.")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--target", help="назва колонки цілі (для непрямого сигналу MNAR)")
    ap.add_argument("--min-auc", type=float, default=DEFAULT_MIN_AUC)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if not a.csv:
        ap.error("потрібен --csv або --self-test")

    import pandas as pd
    df = pd.read_csv(a.csv)
    target = None
    if a.target:
        if a.target not in df.columns:
            ap.error(f"колонки {a.target!r} немає у файлі")
        target = pd.to_numeric(df[a.target], errors="coerce").to_numpy()
        df = df.drop(columns=[a.target])

    num = df.select_dtypes(include="number")
    skipped = [c for c in df.columns if c not in num.columns]
    if skipped:
        print(f"Пропущено нечислові колонки: {', '.join(skipped)}")
        print("(діагностика механізму рахується лише на числових)\n")

    rows = report(num.to_numpy(dtype=float), list(num.columns), target, a.min_auc)
    print_report(rows, a.min_auc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
