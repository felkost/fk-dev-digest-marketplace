"""EDA on a ready-made embeddings matrix (discover stage, high-dim modalities).

You bring the embeddings (e.g., DINOv2/DINOv3 or CLIP for images, a text encoder,
a time-series encoder) as an ``N x D`` array — this module does NOT compute them
(that needs a heavy model). It then runs leakage-relevant EDA on top: near-
duplicate detection (for cross-split leakage), kNN label-noise triage,
clusterability, and a linear-probe estimate of class separability. Everything is
a diagnostic probe, not a final model, and nothing is claimed as causal.

Core is scikit-learn + numpy; clusterability reuses ``cluster_tendency`` from the
same scripts directory.
"""

from __future__ import annotations

from typing import Optional

import numpy as np


def _neighbors(X, k: int, metric: str):
    from sklearn.neighbors import NearestNeighbors

    X = np.asarray(X, dtype=float)
    nn = NearestNeighbors(n_neighbors=min(k + 1, len(X)), metric=metric).fit(X)
    dist, idx = nn.kneighbors(X)
    return dist[:, 1:], idx[:, 1:]  # drop the point itself (column 0)


def near_duplicate_pairs(X, threshold: float = 0.05, metric: str = "cosine", k: int = 3) -> list:
    """Embedding-space near-duplicate ``(i, j, distance)`` pairs.

    Complements the pixel-hash version in ``image_profile``; run it across split
    boundaries too, because near-duplicates in both train and test are leakage.
    ``threshold`` is in the chosen metric (cosine distance by default).
    """
    dist, idx = _neighbors(X, k, metric)
    seen: dict = {}
    for i in range(len(dist)):
        for d, j in zip(dist[i], idx[i]):
            if d <= threshold:
                key = (min(i, int(j)), max(i, int(j)))
                seen[key] = min(seen.get(key, np.inf), float(d))
    return sorted((i, j, round(d, 4)) for (i, j), d in seen.items())


def label_noise_candidates(X, y, k: int = 10, metric: str = "cosine"):
    """Flag points whose label disagrees with their embedding neighbours.

    For each point, measure the fraction of its ``k`` nearest neighbours with a
    different label; when the neighbour majority label differs from the point's
    own label it is a label-noise *candidate* to review (never auto-relabel from
    this alone). Returns a DataFrame sorted by disagreement.
    """
    import pandas as pd

    dist, idx = _neighbors(X, k, metric)
    y = np.asarray(y)
    rows = []
    for i in range(len(idx)):
        neigh = y[idx[i]]
        vals, counts = np.unique(neigh, return_counts=True)
        maj = vals[np.argmax(counts)]
        disagree = float(np.mean(neigh != y[i]))
        rows.append({"index": i, "label": y[i], "neighbor_majority": maj,
                     "disagree_frac": round(disagree, 3),
                     "suspect": bool(maj != y[i] and disagree > 0.5)})
    return (pd.DataFrame(rows)
            .sort_values("disagree_frac", ascending=False)
            .reset_index(drop=True))


def clusterability(X) -> dict:
    """Hopkins + neighbour-distance concentration (reuses ``cluster_tendency``)."""
    try:
        from cluster_tendency import hopkins_statistic, nn_distance_summary
        return {"hopkins": round(hopkins_statistic(X), 3), **nn_distance_summary(X)}
    except Exception:  # pragma: no cover - fallback if run outside the skill dir
        from sklearn.neighbors import NearestNeighbors
        X = np.asarray(X, dtype=float)
        d = NearestNeighbors(n_neighbors=2).fit(X).kneighbors(X)[0][:, 1]
        return {"hopkins": None, "mean_nn": round(float(d.mean()), 4),
                "note": "cluster_tendency unavailable; nearest-neighbour distance only"}


def separability_probe(X, y, cv: int = 5, random_state: int = 42) -> dict:
    """Linear-probe (logistic regression) out-of-fold separability of classes.

    A diagnostic of how separable the classes are *in this representation* — not
    a final model and not a causal statement. High separability can also signal a
    shortcut, so corroborate with the label-noise and confound checks.
    """
    import pandas as pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    X = np.asarray(X, dtype=float)
    y = np.asarray(y)
    min_class = int(pd.Series(y).value_counts().min())
    n_splits = max(2, min(cv, min_class))
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    acc = cross_val_score(pipe, X, y, cv=skf, scoring="accuracy")
    f1 = cross_val_score(pipe, X, y, cv=skf, scoring="f1_macro")
    return {"linear_probe_accuracy": round(float(acc.mean()), 4),
            "accuracy_std": round(float(acc.std()), 4),
            "f1_macro": round(float(f1.mean()), 4),
            "n_splits": n_splits,
            "note": "Diagnostic of separability in this representation, not a final model."}


def summary(X, y=None, k: int = 10, dup_threshold: float = 0.05, metric: str = "cosine") -> dict:
    """One-call embedding EDA: shape, clusterability, near-dup count, and — if
    labels are given — label-noise suspects and linear-probe separability."""
    X = np.asarray(X, dtype=float)
    out = {"n": int(X.shape[0]), "dim": int(X.shape[1]),
           "clusterability": clusterability(X),
           "n_near_duplicate_pairs": len(near_duplicate_pairs(X, dup_threshold, metric))}
    if y is not None:
        ln = label_noise_candidates(X, y, k, metric)
        out["n_label_noise_suspects"] = int(ln["suspect"].sum())
        out["separability"] = separability_probe(X, y)
    return out


__all__ = ["near_duplicate_pairs", "label_noise_candidates", "clusterability",
           "separability_probe", "summary"]
