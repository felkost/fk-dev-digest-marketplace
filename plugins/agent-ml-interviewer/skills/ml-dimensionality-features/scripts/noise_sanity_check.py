#!/usr/bin/env python3
"""Канарковий аудит важливостей: впорскує шумові ознаки й перевіряє протокол.

Використання:
  python noise_sanity_check.py --csv d.csv --target y
  python noise_sanity_check.py --csv d.csv --target y --n-noise 12 --model l1
  python noise_sanity_check.py --self-test

Відтворює експеримент нотбука курсу (Adult + 12 шумових ознак):
  1. Додає n-noise канарок: normal / uniform / laplace (як у нотбуці).
  2. Фітить RF (або L1-логістику) і рахує важливості.
  3. Червоні прапори:
     a) канарка в топі / реальні ознаки нижче найкращої канарки;
     b) CV-score ЗРІС після додавання сміття -> переоснащення протоколу
        (у нотбуці RF підняв фіктивний fnlwgt на 1-ше місце, і CV зросла).
  4. Ознаки нижче найкращої канарки -- кандидати на виліт.

Вимоги: numpy, pandas, scikit-learn.
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


def add_canaries(X: np.ndarray, n_noise: int, seed: int):
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    kinds = ["normal", "uniform", "laplace"]
    cols, names = [], []
    for i in range(n_noise):
        kind = kinds[i % 3]
        col = {"normal": rng.normal(size=n),
               "uniform": rng.uniform(-1, 1, size=n),
               "laplace": rng.laplace(size=n)}[kind]
        cols.append(col)
        names.append(f"__canary_{kind}_{i}")
    return np.column_stack([X] + cols), names


def make_model(kind: str, seed: int):
    if kind == "rf":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(n_estimators=200, n_jobs=-1,
                                      class_weight="balanced", random_state=seed)
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    return Pipeline([("sc", StandardScaler()),
                     ("lr", LogisticRegression(penalty="l1", solver="liblinear",
                                               C=1.0, class_weight="balanced",
                                               max_iter=500, random_state=seed))])


def importances(model, kind: str, feat_names: list[str]) -> dict[str, float]:
    if kind == "rf":
        vals = model.feature_importances_
    else:
        vals = np.abs(model.named_steps["lr"].coef_).ravel()
    return dict(zip(feat_names, map(float, vals)))


def audit(X: np.ndarray, y: np.ndarray, real_names: list[str], *,
          model_kind: str = "rf", n_noise: int = 12, seed: int = 1,
          use_permutation: bool = False) -> dict:
    from sklearn.model_selection import StratifiedKFold, cross_val_score

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)

    base = make_model(model_kind, seed)
    cv_before = cross_val_score(base, X, y, cv=skf, scoring="roc_auc", n_jobs=-1)

    Xa, canary_names = add_canaries(X, n_noise, seed)
    all_names = real_names + canary_names
    aug = make_model(model_kind, seed)
    cv_after = cross_val_score(aug, Xa, y, cv=skf, scoring="roc_auc", n_jobs=-1)

    aug.fit(Xa, y)
    if use_permutation:
        from sklearn.inspection import permutation_importance
        pi = permutation_importance(aug, Xa, y, n_repeats=5,
                                    random_state=seed, n_jobs=-1)
        imp = dict(zip(all_names, map(float, pi.importances_mean)))
    else:
        imp = importances(aug, model_kind, all_names)

    order = sorted(imp, key=imp.get, reverse=True)
    best_canary = max(canary_names, key=lambda c: imp[c])
    rank_best_canary = order.index(best_canary) + 1
    beaten = [f for f in real_names if imp[f] <= imp[best_canary]]
    d_cv = cv_after.mean() - cv_before.mean()
    se = np.sqrt(cv_before.std(ddof=1) ** 2 + cv_after.std(ddof=1) ** 2) / np.sqrt(len(cv_before))

    return {"cv_before": float(cv_before.mean()), "cv_after": float(cv_after.mean()),
            "cv_delta": float(d_cv), "cv_se": float(se),
            "ranking": [(f, imp[f]) for f in order],
            "best_canary": best_canary, "rank_best_canary": rank_best_canary,
            "beaten_by_canary": beaten, "n_noise": n_noise, "model": model_kind,
            "score_rose_on_noise": bool(d_cv > se)}


def report(r: dict) -> str:
    L = [f"модель = {r['model']}   канарок = {r['n_noise']}",
         f"CV ROC-AUC: до = {r['cv_before']:.4f}   після сміття = {r['cv_after']:.4f}"
         f"   Δ = {r['cv_delta']:+.4f} (SE ≈ {r['cv_se']:.4f})", ""]
    if r["score_rose_on_noise"]:
        L.append("!! CV ЗРОСЛА після додавання шуму понад SE — підпис переоснащення "
                 "протоколу (fnlwgt-сценарій нотбука). Перегляньте спліт/відбір/тюнінг.")
    else:
        L.append("CV не зросла на смітті — протокол цей тест пройшов.")
    L.append(f"Найкраща канарка: {r['best_canary']} на місці {r['rank_best_canary']}.")
    if r["beaten_by_canary"]:
        L.append(f"Реальні ознаки НЕ КРАЩІ за шум ({len(r['beaten_by_canary'])}): "
                 + ", ".join(r["beaten_by_canary"][:12])
                 + (" …" if len(r["beaten_by_canary"]) > 12 else ""))
        L.append("  → кандидати на виліт або на перевірку permutation-важливістю.")
    else:
        L.append("Усі реальні ознаки б'ють найкращу канарку.")
    L.append("")
    L.append("Топ-12 важливостей (канарки позначені __canary_*):")
    for f, v in r["ranking"][:12]:
        L.append(f"   {f:<28} {v:.5f}")
    return "\n".join(L)


def self_test() -> int:
    from sklearn.datasets import make_classification
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'OK ' if cond else 'FAIL'} {label}")

    print("1) Інформативні дані: 5 сигнальних + 5 зайвих ознак, n=2000")
    X, y = make_classification(n_samples=2000, n_features=10, n_informative=5,
                               n_redundant=2, n_repeated=0, shuffle=False,
                               random_state=0)
    names = [f"inf_{i}" for i in range(5)] + [f"noise_orig_{i}" for i in range(5)]
    r = audit(X, y, names, model_kind="rf", n_noise=9, seed=1)
    top5 = [f for f, _ in r["ranking"][:5]]
    check("жодної канарки в топ-5", not any(f.startswith("__canary") for f in top5))
    check("інформативні ознаки б'ють канарку",
          not any(f.startswith("inf_") for f in r["beaten_by_canary"]))
    check(f"CV не зросла на смітті (Δ={r['cv_delta']:+.4f})",
          not r["score_rose_on_noise"])

    print("2) Випадкова ціль: сигналу немає — канарки нероздільні з «ознаками»")
    rng = np.random.default_rng(5)
    Xr = rng.normal(size=(600, 8))
    yr = rng.integers(0, 2, size=600)
    rr = audit(Xr, yr, [f"x{i}" for i in range(8)], model_kind="rf",
               n_noise=6, seed=2)
    check(f"канарка високо (місце {rr['rank_best_canary']} ≤ 6) — «важливість» тут шум",
          rr["rank_best_canary"] <= 6)
    check(f"чимало «ознак» нижче канарки ({len(rr['beaten_by_canary'])} з 8)",
          len(rr["beaten_by_canary"]) >= 3)

    print("3) L1-гілка (стійкість, як у нотбуці) — БЕЗ redundant-ознак:")
    print("   (з redundant L1 законно занулює частину інформативних на користь")
    print("   їхньої комбінації — «близнюкова» нестабільність із ml-linear-regularization)")
    X3, y3 = make_classification(n_samples=2000, n_features=10, n_informative=5,
                                 n_redundant=0, n_repeated=0, shuffle=False,
                                 random_state=0)
    names3 = [f"inf_{i}" for i in range(5)] + [f"pure_noise_{i}" for i in range(5)]
    r3 = audit(X3, y3, names3, model_kind="l1", n_noise=9, seed=1)
    check("жодної канарки в топ-5 у L1",
          not any(f.startswith("__canary") for f, _ in r3["ranking"][:5]))
    check("усі інформативні б'ють найкращу канарку",
          not any(f.startswith("inf_") for f in r3["beaten_by_canary"]))

    print()
    print("УСПІХ" if ok else "ПРОВАЛ")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--target")
    ap.add_argument("--features", help="через кому; без прапорця — всі числові, крім цілі")
    ap.add_argument("--model", choices=["rf", "l1"], default="rf")
    ap.add_argument("--n-noise", type=int, default=12)
    ap.add_argument("--permutation", action="store_true",
                    help="permutation-важливість замість вбудованої (повільніше, чесніше)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.csv and a.target):
        ap.error("потрібні --csv і --target (або --self-test)")
    import pandas as pd
    df = pd.read_csv(a.csv)
    if a.target not in df.columns:
        ap.error(f"цілі '{a.target}' немає; колонки: {list(df.columns)}")
    feats = ([c.strip() for c in a.features.split(",")] if a.features
             else [c for c in df.select_dtypes("number").columns if c != a.target])
    d = df[feats + [a.target]].dropna()
    r = audit(d[feats].to_numpy(dtype=float), d[a.target].to_numpy(),
              feats, model_kind=a.model, n_noise=a.n_noise, seed=a.seed,
              use_permutation=a.permutation)
    print(report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
