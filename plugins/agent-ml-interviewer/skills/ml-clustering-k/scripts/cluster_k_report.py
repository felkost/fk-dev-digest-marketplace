#!/usr/bin/env python3
"""Вибір k: elbow (inertia+KneeLocator) + silhouette + Davies-Bouldin разом.

Використання:
  python cluster_k_report.py --csv d.csv --k-min 2 --k-max 12
  python cluster_k_report.py --csv d.csv --features a,b,c --minibatch
  python cluster_k_report.py --self-test

Уроки нотбука курсу, вшиті сюди:
  - повний silhouette-свіп по MNIST зайняв ~106 хв: silhouette О(n²), тому
    рахується на підвибірці (--silhouette-cap, дефолт 5000); inertia -- на всіх;
  - init='k-means++', n_init>=10, random_state фіксований;
  - розбіжність сигналів -- інформація: скрипт її НЕ ховає.

Вимоги: numpy, pandas, scikit-learn; kneed -- опційно (без нього коліно
шукається максимальною відстанню до хорди).
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


def knee_convex_decreasing(ks: list[int], sse: list[float]):
    """Коліно опуклої спадної кривої. kneed, як є; інакше -- відстань до хорди."""
    try:
        from kneed import KneeLocator
        kl = KneeLocator(ks, sse, curve="convex", direction="decreasing")
        return kl.elbow
    except ImportError:
        x = np.asarray(ks, float); y = np.asarray(sse, float)
        x0, y0, x1, y1 = x[0], y[0], x[-1], y[-1]
        num = np.abs((y1 - y0) * x - (x1 - x0) * y + x1 * y0 - y1 * x0)
        d = num / np.hypot(y1 - y0, x1 - x0)
        i = int(np.argmax(d))
        return ks[i] if 0 < i < len(ks) - 1 else None


def sweep(X: np.ndarray, k_min: int, k_max: int, *, minibatch: bool = False,
          sil_cap: int = 5000, seed: int = 1) -> dict:
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans, MiniBatchKMeans
    from sklearn.metrics import silhouette_score, davies_bouldin_score

    if k_min < 2:
        k_min = 2                      # silhouette для k=1 не визначений
    Xs = StandardScaler().fit_transform(np.asarray(X, dtype=float))
    rng = np.random.default_rng(seed)
    idx = (rng.choice(len(Xs), sil_cap, replace=False)
           if len(Xs) > sil_cap else np.arange(len(Xs)))

    ks, sse, sil, db = [], [], [], []
    for k in range(k_min, k_max + 1):
        if minibatch:
            km = MiniBatchKMeans(n_clusters=k, init="k-means++", n_init=10,
                                 batch_size=4096, max_iter=300, random_state=seed)
        else:
            km = KMeans(n_clusters=k, init="k-means++", n_init=10,
                        max_iter=300, random_state=seed)
        labels = km.fit_predict(Xs)
        ks.append(k)
        sse.append(float(km.inertia_))                       # на ВСІХ даних
        sub = labels[idx]
        if len(np.unique(sub)) < 2:                          # вироджена підвибірка
            sil.append(float("nan")); db.append(float("nan")); continue
        sil.append(float(silhouette_score(Xs[idx], sub)))    # на підвибірці: O(n²)
        db.append(float(davies_bouldin_score(Xs[idx], sub)))

    return {
        "ks": ks, "sse": sse, "silhouette": sil, "davies_bouldin": db,
        "k_elbow": knee_convex_decreasing(ks, sse),
        "k_silhouette": ks[int(np.nanargmax(sil))],
        "k_db": ks[int(np.nanargmin(db))],
        "n": len(Xs), "n_sil": len(idx),
    }


def report(r: dict) -> str:
    L = [f"n = {r['n']}   silhouette на підвибірці {r['n_sil']} (O(n²): урок «106 хвилин»)",
         "",
         f"{'k':>4}{'inertia':>14}{'silhouette':>12}{'DaviesB':>10}"]
    for k, s, si, d in zip(r["ks"], r["sse"], r["silhouette"], r["davies_bouldin"]):
        marks = "".join([" ←elbow" if k == r["k_elbow"] else "",
                         " ←sil" if k == r["k_silhouette"] else "",
                         " ←DB" if k == r["k_db"] else ""])
        L.append(f"{k:>4}{s:>14.1f}{si:>12.4f}{d:>10.4f}{marks}")
    L.append("")
    votes = [v for v in (r["k_elbow"], r["k_silhouette"], r["k_db"]) if v]
    L.append(f"Голоси: elbow={r['k_elbow']}  silhouette={r['k_silhouette']}  DB={r['k_db']}")
    if len(set(votes)) == 1:
        L.append(f"Сигнали ЗГОДНІ: k = {votes[0]}")
    else:
        L.append("Сигнали РОЗХОДЯТЬСЯ — це інформація: перевірте silhouette-ножі "
                 "по кластерах, стабільність на іншому random_state, і форму "
                 "кластерів (можливо, потрібен не k-means).")
    L.append("Запуск для відтворення: KMeans(init='k-means++', n_init=10, random_state=1) "
             "після StandardScaler.")
    return "\n".join(L)


def self_test() -> int:
    from sklearn.datasets import make_blobs
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'OK ' if cond else 'FAIL'} {label}")

    print("1) 4 добре розділені блоби, n=1500")
    X, _ = make_blobs(n_samples=1500, centers=4, cluster_std=0.8, random_state=3)
    r = sweep(X, 2, 9)
    check(f"silhouette голосує 4 (дав {r['k_silhouette']})", r["k_silhouette"] == 4)
    check(f"elbow голосує 4 (дав {r['k_elbow']})", r["k_elbow"] == 4)
    check(f"Davies-Bouldin голосує 4 (дав {r['k_db']})", r["k_db"] == 4)

    print("2) Масштабна пастка: та сама структура, одна ознака ×1000 — скейлер рятує")
    X2 = X.copy(); X2[:, 0] *= 1000.0
    r2 = sweep(X2, 2, 9)
    check(f"після StandardScaler досі 4 (дав sil={r2['k_silhouette']})",
          r2["k_silhouette"] == 4)

    print("3) Підвибірка silhouette не міняє переможця (cap=400)")
    r3 = sweep(X, 2, 9, sil_cap=400)
    check(f"cap=400 -> той самий k={r3['k_silhouette']}", r3["k_silhouette"] == 4)

    print("4) MiniBatch-гілка працює і згодна")
    r4 = sweep(X, 2, 9, minibatch=True)
    check(f"minibatch sil k={r4['k_silhouette']}", r4["k_silhouette"] == 4)

    print()
    print("УСПІХ" if ok else "ПРОВАЛ")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--features", help="через кому; без прапорця — всі числові")
    ap.add_argument("--k-min", type=int, default=2)
    ap.add_argument("--k-max", type=int, default=12)
    ap.add_argument("--silhouette-cap", type=int, default=5000)
    ap.add_argument("--minibatch", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.csv:
        ap.error("потрібен --csv (або --self-test)")
    import pandas as pd
    df = pd.read_csv(a.csv)
    cols = ([c.strip() for c in a.features.split(",")] if a.features
            else df.select_dtypes("number").columns.tolist())
    X = df[cols].dropna().to_numpy(dtype=float)
    r = sweep(X, a.k_min, a.k_max, minibatch=a.minibatch,
              sil_cap=a.silhouette_cap, seed=a.seed)
    print(report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
