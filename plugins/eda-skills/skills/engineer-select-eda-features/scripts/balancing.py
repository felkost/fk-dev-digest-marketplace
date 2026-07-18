"""Class-imbalance handling, applied inside the training fold only (engineer
step 6).

Resample only the training partition; keep validation/test at the natural
deployment prevalence and never synthesize across split boundaries. Do not force
50/50 by default -- prefer class weights + threshold tuning, then a moderate
target ratio. Every call returns a sampling manifest with provenance.

Core is scikit-learn + numpy; SMOTE/SMOTENC/ADASYN/Tomek/ENN need
imbalanced-learn (optional, lazy).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def class_duplicate_report(X, y) -> dict:
    """Is the imbalance real, or a duplication artifact? Per-class duplicate-row
    rates and class counts before/after deduplication.

    Run this before choosing any balancing strategy: duplicated majority rows
    exaggerate imbalance (and duplicated minority rows hide it); after
    deduplication the ratio may change enough to change the decision. Duplicates
    inside the minority also mean fewer *effective* independent positives than
    the raw count suggests.
    """
    Xdf = pd.DataFrame(X).copy()
    y = pd.Series(np.asarray(y), index=Xdf.index, name="_y")
    out_classes = {}
    for cls, grp in Xdf.groupby(y, observed=True):
        n, n_unique = len(grp), len(grp.drop_duplicates())
        out_classes[cls] = {"count": int(n), "unique": int(n_unique),
                            "duplicate_rate": round(float(1 - n_unique / n), 4)}
    counts = {c: v["count"] for c, v in out_classes.items()}
    uniques = {c: v["unique"] for c, v in out_classes.items()}

    def ratio(d):
        lo, hi = min(d.values()), max(d.values())
        return round(float(lo / hi), 4) if hi else np.nan

    return {"classes": out_classes,
            "minority_ratio_raw": ratio(counts),
            "minority_ratio_dedup": ratio(uniques)}


def compute_class_weights(y) -> dict:
    """Balanced class weights (a leakage-free alternative to resampling)."""
    from sklearn.utils.class_weight import compute_class_weight

    classes = np.unique(y)
    w = compute_class_weight("balanced", classes=classes, y=np.asarray(y))
    return {c: round(float(wi), 4) for c, wi in zip(classes, w)}


def prevalence_metric_report(y_true, scores, recalls=(0.5, 0.8)) -> dict:
    """What a headline AUC is worth at this class balance.

    ROC-AUC is **invariant to prevalence**: it is built from TPR and FPR, each
    normalised within its own class, so subsampling negatives leaves it
    unchanged. Measured on one fixed scorer while only the negative class was
    thinned -- ROC-AUC 0.873 / 0.874 / 0.866 / 0.871 / 0.868 at prevalence
    0.500 / 0.200 / 0.050 / 0.010 / 0.002, while average precision on the very
    same scores collapsed 0.869 -> 0.679 -> 0.371 -> 0.147 -> **0.041**.

    That invariance does **not** make ROC-AUC invalid for imbalanced data -- it
    makes it an answer to a different question. ROC-AUC is the probability that
    a random positive outranks a random negative, which is well defined at any
    prevalence and is the *right* metric for comparing models across datasets
    or periods with different base rates. The mirror-image trap is that average
    precision, the usual "use this instead" recommendation, is **not** portable
    that way: identical ranking quality above produced AP from 0.869 down to
    0.041 purely because prevalence moved. Report both and name the population. The
    baseline for average precision is the prevalence itself, so AP must be read
    against it (the lift ``ap/prevalence`` actually *rises* as the class gets
    rarer -- measured 1.7 / 3.4 / 7.4 / 14.7 / 20.6 -- which is a real signal
    and still compatible with a useless alert queue).

    The operational translation, measured at a fixed ROC-AUC of ~0.95:

    ==========  =========  ===============  ===============
    prevalence  ROC-AUC    precision@0.8    alerts per TP
    ==========  =========  ===============  ===============
    0.500       0.951      0.919            1.1
    0.100       0.949      0.546            1.8
    0.010       0.953      0.111            9.0
    0.001       0.951      0.012            **80.6**
    ==========  =========  ===============  ===============

    Same model quality by AUC; at a 0.1% base rate someone must review ~81
    alerts per true case. Decide capacity from ``alerts_per_true_positive``,
    not from AUC. This is the ranking-side counterpart of the base-rate
    arithmetic in ``consistency.proxy_label_diagnostics``.

    Optional dependency: scikit-learn. Returns ``verdict`` =
    ``good_ranking_unusable_operating_point`` when AUC looks strong but
    precision at the requested recall is weak.
    """
    y = np.asarray(list(y_true)).astype(float)
    s = np.asarray(list(scores)).astype(float)
    ok = np.isfinite(y) & np.isfinite(s)
    y, s = y[ok], s[ok]
    n = int(y.size)
    pos = int((y == 1).sum())
    if n == 0 or pos == 0 or pos == n:
        return {"n": n, "n_positive": pos, "prevalence": float(pos / n) if n else float("nan"),
                "roc_auc": float("nan"), "average_precision": float("nan"),
                "ap_baseline": float("nan"), "ap_lift": float("nan"),
                "precision_at_recall": {}, "alerts_per_true_positive": {},
                "verdict": "single_class_or_empty"}

    try:
        from sklearn.metrics import (average_precision_score, precision_recall_curve,
                                     roc_auc_score)
    except Exception:
        return {"n": n, "n_positive": pos, "prevalence": float(pos / n),
                "roc_auc": float("nan"), "average_precision": float("nan"),
                "ap_baseline": float(pos / n), "ap_lift": float("nan"),
                "precision_at_recall": {}, "alerts_per_true_positive": {},
                "verdict": "sklearn_unavailable"}

    prev = float(pos / n)
    auc = float(roc_auc_score(y, s))
    ap = float(average_precision_score(y, s))
    prec, rec, _ = precision_recall_curve(y, s)

    p_at, alerts = {}, {}
    for r in recalls:
        m = rec >= float(r)
        p = float(prec[m].max()) if m.any() else float("nan")
        p_at[float(r)] = p
        alerts[float(r)] = float(1.0 / p) if p and np.isfinite(p) and p > 0 else float("inf")

    worst = min((v for v in p_at.values() if np.isfinite(v)), default=float("nan"))
    # Deliberately NOT called "auc is wrong here": the ranking really is good.
    # The name states the gap between a valid ranking metric and the operating
    # point a reviewer will experience.
    verdict = ("good_ranking_unusable_operating_point"
               if auc >= 0.85 and np.isfinite(worst) and worst < 0.25
               else "read_precision_alongside_auc" if auc >= 0.85
               else "weak_ranking")
    return {
        "n": n,
        "n_positive": pos,
        "prevalence": prev,
        "roc_auc": auc,
        "average_precision": ap,
        "ap_baseline": prev,
        "ap_lift": float(ap / prev) if prev > 0 else float("nan"),
        "precision_at_recall": p_at,
        "alerts_per_true_positive": alerts,
        "verdict": verdict,
    }


def _as_manifest(algorithm, params, y0, y1, provenance) -> dict:
    def counts(y):
        v, c = np.unique(np.asarray(y), return_counts=True)
        return {int(k) if np.issubdtype(type(k), np.integer) else k: int(n) for k, n in zip(v, c)}

    return {
        "algorithm": algorithm,
        "params": params,
        "fold_scope": "train_partition_within_fold",
        "original_counts": counts(y0),
        "resampled_counts": counts(y1),
        "synthetic_provenance": provenance,
        "validation_test_prevalence": "natural/deployment (unchanged)",
    }


def random_resample(X_train, y_train, kind: str = "over", target_ratio: float = 0.2,
                    random_state: int = 42):
    """Random over/under-sampling of the *training* partition (binary target).

    ``target_ratio`` is the desired minority:majority ratio (e.g. 0.2), not 0.5.
    Returns ``(X_res, y_res, manifest)``.
    """
    rng = np.random.default_rng(random_state)
    y = np.asarray(y_train)
    classes, counts = np.unique(y, return_counts=True)
    if classes.size != 2:
        raise ValueError("random_resample supports a binary target")
    minority, majority = classes[np.argmin(counts)], classes[np.argmax(counts)]
    idx_min, idx_maj = np.where(y == minority)[0], np.where(y == majority)[0]
    n_min, n_maj = idx_min.size, idx_maj.size

    if kind == "over":
        target = int(target_ratio * n_maj)
        extra = rng.choice(idx_min, max(target - n_min, 0), replace=True)
        keep = np.sort(np.concatenate([np.arange(y.size), extra]))
    elif kind == "under":
        target = int(n_min / target_ratio) if target_ratio > 0 else n_maj
        sel_maj = rng.choice(idx_maj, min(target, n_maj), replace=False)
        keep = np.sort(np.concatenate([idx_min, sel_maj]))
    else:
        raise ValueError("kind must be 'over' or 'under'")

    Xr = X_train.iloc[keep] if hasattr(X_train, "iloc") else np.asarray(X_train)[keep]
    yr = y[keep]
    manifest = _as_manifest(f"random_{kind}", {"target_ratio": target_ratio}, y, yr,
                            "duplicated real rows" if kind == "over" else "subset of real rows")
    return Xr, yr, manifest


def imblearn_resample(X_train, y_train, method: str = "smote", random_state: int = 42, **kw):
    """SMOTE / SMOTENC / ADASYN / Tomek / ENN via imbalanced-learn (lazy import).

    Apply to the training partition only. ``sampling_strategy`` defaults to a
    moderate ratio, not 1.0. Returns ``(X_res, y_res, manifest)``.
    """
    try:
        from imblearn.over_sampling import ADASYN, SMOTE, SMOTENC
        from imblearn.under_sampling import EditedNearestNeighbours, TomekLinks
    except ImportError as e:  # pragma: no cover
        raise ImportError("imbalanced-learn is optional; `pip install imbalanced-learn`") from e

    method = method.lower()
    strat = kw.pop("sampling_strategy", 0.2)
    if method == "smote":
        sampler = SMOTE(sampling_strategy=strat, random_state=random_state, **kw)
    elif method == "smotenc":
        sampler = SMOTENC(categorical_features=kw.pop("categorical_features"),
                          sampling_strategy=strat, random_state=random_state, **kw)
    elif method == "adasyn":
        sampler = ADASYN(sampling_strategy=strat, random_state=random_state, **kw)
    elif method == "tomek":
        sampler = TomekLinks(**kw)
    elif method == "enn":
        sampler = EditedNearestNeighbours(**kw)
    else:
        raise ValueError(f"unknown method: {method}")

    Xr, yr = sampler.fit_resample(X_train, y_train)
    provenance = "synthetic minority rows" if method in ("smote", "smotenc", "adasyn") else "cleaned overlap"
    manifest = _as_manifest(method, {"sampling_strategy": strat, **kw}, y_train, yr, provenance)
    return Xr, yr, manifest


__all__ = ["class_duplicate_report", "compute_class_weights", "random_resample",
           "imblearn_resample", "prevalence_metric_report"]
