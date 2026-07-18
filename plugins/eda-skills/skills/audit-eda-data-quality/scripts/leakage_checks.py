"""Split and leakage checks (audit step 8).

Detect the mechanical leakage classes: duplicate/near-duplicate keys across
splits, group leakage, features that look suspiciously predictive on their own,
and features whose availability time is after the prediction cutoff.

Core-library only (numpy, pandas, scikit-learn).
"""

from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd


def keys_across_splits(df: pd.DataFrame, split_col: str, key_cols: Sequence[str]) -> dict:
    """Count keys (or group keys) that appear in more than one split.

    Use ``key_cols=[primary_key]`` for duplicate leakage and
    ``key_cols=[group_key]`` for entity/group leakage.
    """
    key_cols = list(key_cols)
    g = df.groupby(key_cols, observed=True)[split_col].nunique()
    offending = g[g > 1]
    return {
        "key_cols": key_cols,
        "n_keys_in_multiple_splits": int(offending.size),
        "examples": [tuple(x) if isinstance(x, tuple) else x for x in offending.head(5).index.tolist()],
        "disjoint": bool(offending.empty),
    }


def suspicious_single_features(
    X: pd.DataFrame,
    y: pd.Series,
    cols: Optional[Iterable[str]] = None,
    cv: int = 5,
    auc_threshold: float = 0.9,
    random_state: int = 42,
) -> pd.DataFrame:
    """Rank numeric features by single-feature out-of-fold ROC-AUC.

    A single feature that nearly separates a binary target is a leakage or
    proxy-leakage candidate; confirm against acquisition time and semantics.
    Returns features sorted by AUC descending with a boolean ``suspicious`` flag.
    """
    from sklearn.model_selection import cross_val_predict, StratifiedKFold
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.metrics import roc_auc_score

    if y.nunique() != 2:
        raise ValueError("suspicious_single_features expects a binary target")
    pos = y.max()
    y_bin = (y == pos).astype(int).to_numpy()
    if cols is None:
        cols = X.select_dtypes(include=[np.number]).columns
    skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=random_state)

    rows = []
    for c in cols:
        xc = X[[c]].astype(float)
        xc = xc.fillna(xc.median())
        try:
            proba = cross_val_predict(
                DecisionTreeClassifier(max_depth=3, random_state=random_state),
                xc, y_bin, cv=skf, method="predict_proba",
            )[:, 1]
            auc = roc_auc_score(y_bin, proba)
        except Exception:
            auc = np.nan
        rows.append({"column": c, "oof_auc": round(float(auc), 4) if auc == auc else np.nan})
    out = pd.DataFrame(rows)
    out["suspicious"] = out["oof_auc"] > auc_threshold
    return out.sort_values("oof_auc", ascending=False).reset_index(drop=True)


def composite_target_probe(X: pd.DataFrame, y, cols: Optional[Iterable[str]] = None,
                           exact_tol: float = 1e-6, near_tol: float = 0.05,
                           max_subset_report: int = 12) -> dict:
    """Is the target a (near-)linear combination of the features themselves?

    ``suspicious_single_features`` looks at one column at a time and needs a
    binary target, so it structurally cannot see the case where a **continuous**
    target is *constructed* from several feature columns. That case is common in
    published datasets and index-style targets: the World Happiness Report's
    Happiness Score is exactly ``Economy + Family + Health + Freedom + Trust +
    Generosity + Dystopia Residual``, a credit "risk score" is a weighted sum of
    the bureau columns shipped beside it, and a "total" column is the sum of its
    parts. Correlating such a target with its own components and reporting the
    result as a finding is circular.

    **No single-feature screen can catch it.** Simulated on the Happiness
    structure (n=158, 7 components), the individual correlations with the target
    came out +0.36..+0.45 -- unremarkable, and the published heat map for the
    real dataset shows 0.72..0.78, still nowhere near a leakage threshold. The
    identity only appears when the features are taken *together*:

    - OLS on all 7 components: ``R^2 = 1.000000000000``, relative residual
      ``1.07e-15`` (machine precision).
    - An honest model at a genuine ``R^2`` of 0.99 gives a relative residual of
      **0.0992** -- fifteen orders of magnitude away, so the separation is not
      a matter of threshold tuning.
    - Realistic partial case (one component not exported): dropping any single
      column still leaves ``R^2`` 0.866..0.893.

    **The guard matters more than the statistic.** With ``n <= p+1`` least
    squares reproduces *any* ``y`` exactly, so an unguarded version of this
    probe reports "identity" on pure noise. Measured minimum relative residual
    over 400 pure-noise draws, by ``n/(p+1)``:

    ====  ======  ======  ======  ======  ======
    n/(p+1)  1.0   1.2-1.3   1.5     2.0     3.0
    ====  ======  ======  ======  ======  ======
    p=3   0.0000  0.0008  0.0657  0.2457  0.4075
    p=5   0.0000  0.0133  0.0700  0.3067  0.4927
    p=10  0.0000  0.0720  0.2101  0.4284  0.5549
    ====  ======  ======  ======  ======  ======

    Hence the probe refuses below ``n >= 2*(p+1)``, where the noise floor is
    0.31-0.43 against an ``exact_tol`` of 1e-6 -- five orders of margin.

    Returns ``relative_residual``, ``r2_full``, ``verdict`` (``exact_identity``
    / ``near_identity`` / ``no_identity`` / ``insufficient_rows`` /
    ``degenerate_target``), the ``minimal_subset`` that still reproduces the
    target and its fitted ``weights`` (all-equal weights mean a plain sum), and
    ``best_r2_without_one`` for the partial case. A finding here is a question
    for the data owner -- "how was this column computed?" -- not a licence to
    drop columns automatically: sometimes the components are the real features
    and the target should be replaced by something measured independently.
    """
    Xn = X[list(cols)] if cols is not None else X.select_dtypes(include=[np.number])
    ys = pd.Series(y, dtype=float).reset_index(drop=True)
    Xn = Xn.reset_index(drop=True).astype(float)
    ok = ys.notna() & Xn.notna().all(axis=1)
    Xn, ys = Xn[ok], ys[ok]
    n, p = Xn.shape
    names = list(Xn.columns)

    if p == 0 or n == 0:
        return {"verdict": "insufficient_rows", "n": int(n), "p": int(p)}
    if float(ys.std(ddof=0)) == 0.0:
        return {"verdict": "degenerate_target", "n": int(n), "p": int(p),
                "note": "target is constant; R^2 is undefined"}
    if n < 2 * (p + 1):
        return {"verdict": "insufficient_rows", "n": int(n), "p": int(p),
                "required_rows": int(2 * (p + 1)),
                "note": ("with n <= p+1 least squares reproduces any target "
                         "exactly, so this probe cannot distinguish an identity "
                         "from noise at this shape")}

    yv = ys.to_numpy()
    sd_y = float(yv.std(ddof=0))

    def rel_resid(subset: Sequence[str]) -> tuple:
        M = np.column_stack([np.ones(n)] + [Xn[c].to_numpy() for c in subset])
        beta, *_ = np.linalg.lstsq(M, yv, rcond=None)
        r = yv - M @ beta
        rr = float(np.sqrt((r @ r) / n) / sd_y)
        r2 = float(1 - (r @ r) / (((yv - yv.mean()) ** 2).sum()))
        return rr, r2, beta

    rr_full, r2_full, beta_full = rel_resid(names)

    # partial case: how well does the target survive losing one column?
    best_without = None
    if p > 1:
        drops = [(rel_resid([c for c in names if c != d])[1], d) for d in names]
        best_without = max(drops)

    verdict = ("exact_identity" if rr_full < exact_tol
               else "near_identity" if rr_full < near_tol
               else "no_identity")

    out = {
        "verdict": verdict,
        "relative_residual": rr_full,
        "r2_full": round(r2_full, 12),
        "n": int(n), "p": int(p),
        "noise_floor_ratio": round(n / (p + 1), 2),
    }
    if best_without is not None:
        out["best_r2_without_one"] = round(best_without[0], 6)
        out["most_redundant_column"] = best_without[1]

    if verdict == "no_identity":
        return out

    # greedy backward elimination: smallest subset that still reproduces y
    keep = list(names)
    for c in sorted(names, key=lambda c: abs(float(np.corrcoef(Xn[c], yv)[0, 1]))):
        if len(keep) <= 1:
            break
        trial = [k for k in keep if k != c]
        if n < 2 * (len(trial) + 1):
            continue
        if rel_resid(trial)[0] <= max(rr_full * 10, exact_tol):
            keep = trial
    rr_min, r2_min, beta_min = rel_resid(keep)
    weights = {c: round(float(b), 6) for c, b in zip(keep, beta_min[1:])}
    out["minimal_subset"] = keep[:max_subset_report]
    out["minimal_subset_size"] = len(keep)
    out["weights"] = dict(list(weights.items())[:max_subset_report])
    out["intercept"] = round(float(beta_min[0]), 6)
    nz = np.array(list(weights.values()), dtype=float)
    out["looks_like_plain_sum"] = bool(
        nz.size > 1 and np.allclose(nz, 1.0, atol=1e-4))
    out["note"] = ("the target is reconstructable from these columns; ask how "
                   "it was computed before treating any correlation with them "
                   "as a finding")
    return out


def availability_audit(feature_times: Mapping[str, "float | int"], cutoff: "float | int") -> dict:
    """Given a map feature -> availability time, list features available only
    after the prediction cutoff (temporal leakage risk)."""
    late = {f: t for f, t in feature_times.items() if t is not None and t > cutoff}
    return {"cutoff": cutoff, "leaky_features": sorted(late), "n_leaky": len(late)}


__all__ = ["keys_across_splits", "suspicious_single_features", "availability_audit",
           "composite_target_probe"]
