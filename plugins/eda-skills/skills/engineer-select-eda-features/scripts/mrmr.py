"""minimum Redundancy - Maximum Relevance selection (engineer step 3).

At each step pick the candidate with high relevance to ``y`` and low redundancy
with already-selected features (MIQ / difference scheme). Fit estimators inside
training folds only; re-run across folds and report selection frequency, since
the estimator and discretization can change the ranking. mRMR does not prove
causation.

Core-library only (numpy, pandas, scikit-learn).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def _relevance(X: pd.DataFrame, y: pd.Series, task: str, random_state: int) -> pd.Series:
    from sklearn.feature_selection import mutual_info_classif, mutual_info_regression

    f = mutual_info_classif if task == "classification" else mutual_info_regression
    vals = f(X.fillna(X.median()), y, random_state=random_state)
    return pd.Series(vals, index=X.columns)


def mrmr_select(X: pd.DataFrame, y: pd.Series, k: int = 10, task: str = "classification",
                scheme: str = "difference", corr_method: str = "spearman",
                random_state: int = 42) -> dict:
    """Select up to ``k`` features by mRMR. Returns order and per-step scores.

    scheme: ``difference`` (relevance - mean redundancy) or ``quotient``.
    Redundancy uses absolute correlation as a fast MI proxy among numeric cols.
    """
    num = X.select_dtypes(include=[np.number])
    rel = _relevance(num, y, task, random_state)
    corr = num.corr(method=corr_method).abs().fillna(0.0)

    selected: list[str] = []
    remaining = list(num.columns)
    steps = []
    k = min(k, len(remaining))
    for _ in range(k):
        best, best_score = None, -np.inf
        for c in remaining:
            red = float(corr.loc[c, selected].mean()) if selected else 0.0
            if scheme == "quotient":
                score = rel[c] / (red + 1e-9)
            else:
                score = rel[c] - red
            if score > best_score:
                best, best_score = c, score
        selected.append(best)
        remaining.remove(best)
        steps.append({"feature": best, "score": round(float(best_score), 5),
                      "relevance": round(float(rel[best]), 5)})
    return {"selected": selected, "steps": steps, "scheme": scheme}


def mrmr_stability(X: pd.DataFrame, y: pd.Series, k: int = 10, task: str = "classification",
                   n_folds: int = 5, random_state: int = 42) -> pd.DataFrame:
    """Run mRMR per fold and report selection frequency across folds."""
    from sklearn.model_selection import KFold, StratifiedKFold

    splitter = (StratifiedKFold(n_folds, shuffle=True, random_state=random_state)
                if task == "classification"
                else KFold(n_folds, shuffle=True, random_state=random_state))
    counts: dict[str, int] = {}
    for tr, _ in splitter.split(X, y):
        sel = mrmr_select(X.iloc[tr], y.iloc[tr], k=k, task=task, random_state=random_state)["selected"]
        for f in sel:
            counts[f] = counts.get(f, 0) + 1
    return (
        pd.DataFrame({"feature": list(counts), "selected_in_folds": list(counts.values())})
        .assign(frequency=lambda d: (d["selected_in_folds"] / n_folds).round(3))
        .sort_values("selected_in_folds", ascending=False)
        .reset_index(drop=True)
    )


__all__ = ["mrmr_select", "mrmr_stability"]
