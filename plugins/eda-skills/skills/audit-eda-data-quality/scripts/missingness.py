"""Missingness analysis (audit step 4).

Measure missing rates by column and by slice (source/time/target/split), find
co-missing patterns, and test whether missingness itself relates to the target.
Includes low-rank (iterative-PCA) imputation and a mask-and-recover probe that
scores ANY imputation strategy on cells whose truth is known.
MCAR/MAR/MNAR are hypotheses, never auto-proved here.

Core-library only (numpy, pandas).
"""

from __future__ import annotations

from typing import Callable, Optional, Union

import numpy as np
import pandas as pd


def missingness_summary(df: pd.DataFrame, by: Optional[str] = None) -> pd.DataFrame:
    """Per-column missing rate, optionally broken down by a slice column ``by``."""
    if by is None:
        s = df.isna().mean().sort_values(ascending=False)
        return s.rename("missing_rate").to_frame()
    grp = df.drop(columns=[by]).isna().groupby(df[by], observed=True).mean()
    return grp.T  # columns are slice values, rows are features


def co_missing_matrix(df: pd.DataFrame, min_rate: float = 0.0) -> pd.DataFrame:
    """Correlation of missingness indicators -- features that go missing together.

    Only columns with missing rate > ``min_rate`` are included.
    """
    mask = df.isna()
    keep = mask.columns[mask.mean() > min_rate]
    mask = mask[keep].astype(float)
    if mask.shape[1] < 2:
        return pd.DataFrame()
    # drop indicators with no variance (all-present or all-missing)
    mask = mask.loc[:, mask.std() > 0]
    return mask.corr()


def missingness_vs_target(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """For each feature, compare the target rate/mean between missing vs present.

    A large gap suggests missingness is informative (MAR/MNAR hypothesis) and
    that an explicit missing-indicator feature may help. This does not prove a
    mechanism.
    """
    y = df[target]
    numeric_target = pd.api.types.is_numeric_dtype(y)
    rows = []
    for c in df.columns:
        if c == target:
            continue
        m = df[c].isna()
        if m.nunique() < 2:
            continue
        if numeric_target:
            miss_stat = float(y[m].mean())
            pres_stat = float(y[~m].mean())
        else:
            # positive-class rate assuming the max label is "positive"
            pos = y.max()
            miss_stat = float((y[m] == pos).mean())
            pres_stat = float((y[~m] == pos).mean())
        rows.append(
            {
                "column": c,
                "missing_rate": round(float(m.mean()), 4),
                "target_when_missing": round(miss_stat, 4),
                "target_when_present": round(pres_stat, 4),
                "gap": round(miss_stat - pres_stat, 4),
            }
        )
    out = pd.DataFrame(rows)
    return out.reindex(out["gap"].abs().sort_values(ascending=False).index) if not out.empty else out


def lowrank_impute(df: pd.DataFrame, cols=None, n_components: int = 1,
                   max_iter: int = 100, tol: float = 1e-6,
                   standardize: bool = True) -> dict:
    """Iterative low-rank (PCA) imputation -- ISLP Algorithm 12.1.

    Initialize missing cells with column means, then alternate: fit a rank-M
    SVD to the filled matrix, replace the missing cells with the rank-M
    reconstruction, until the objective on OBSERVED cells stops decreasing.
    Exploits between-column correlation, so it beats column means exactly when
    the correlation structure is real; with near-independent columns it
    reduces to means. Choose ``n_components`` with
    :func:`imputation_quality_probe` (mask known cells, score recovery) --
    the validation-set approach to imputation.

    Run on the TRAIN partition. The procedure is transductive (it fits the
    matrix it is given); a persisted inference-time imputer must be refit on
    train and saved like any other transformer.
    """
    cols = list(cols) if cols is not None else list(df.select_dtypes(include=[np.number]).columns)
    X = df[cols].to_numpy(dtype=float)
    mask = np.isnan(X)
    if not mask.any():
        return {"imputed": df[cols].copy(), "n_iter": 0, "objective": []}
    mu = np.nanmean(X, axis=0)
    sd = np.nanstd(X, axis=0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd if standardize else X - mu
    Z[mask] = 0.0  # column mean in standardized space

    objective = []
    prev = np.inf
    n_iter = 0
    for n_iter in range(1, max_iter + 1):
        U, S, Vt = np.linalg.svd(Z, full_matrices=False)
        M = min(n_components, len(S))
        recon = U[:, :M] @ np.diag(S[:M]) @ Vt[:M]
        Z[mask] = recon[mask]
        obj = float(((Z - recon)[~mask] ** 2).sum())
        objective.append(round(obj, 6))
        if prev - obj < tol * max(prev, 1e-12):
            break
        prev = obj

    filled = Z * sd + mu if standardize else Z + mu
    out = df[cols].copy()
    out.loc[:, :] = filled
    return {"imputed": out, "n_iter": n_iter, "objective": objective,
            "n_components": n_components}


def imputation_quality_probe(df: pd.DataFrame, cols=None,
                             strategy: Union[str, Callable] = "median",
                             mask_frac: float = 0.1, n_repeats: int = 5,
                             random_state: int = 42, **strategy_kw) -> pd.DataFrame:
    """Score an imputation strategy by masking OBSERVED cells and recovering them.

    The validation-set approach to imputation (ISLP par. 12.3): hide a random
    ``mask_frac`` of known cells, impute, compare with the hidden truth.
    Use it to choose between mean/median/group/low-rank/model imputers and to
    pick the low-rank ``n_components`` -- instead of trusting any imputer by
    default. Run on the TRAIN partition only.

    ``strategy``: ``"mean"`` | ``"median"`` | ``"lowrank"`` (extra kwargs pass
    to :func:`lowrank_impute`) | callable ``fn(df_masked, cols) -> DataFrame``.
    Returns per-column MAE (in raw units and relative to the column MAD) and
    the truth-vs-imputed correlation, averaged over repeats.
    """
    rng = np.random.default_rng(random_state)
    cols = list(cols) if cols is not None else list(df.select_dtypes(include=[np.number]).columns)
    X = df[cols]
    results: dict[str, list] = {c: [] for c in cols}
    for _ in range(n_repeats):
        masked = X.copy()
        hidden: dict[str, pd.Index] = {}
        for c in cols:
            obs = X.index[X[c].notna()]
            k = max(1, int(round(mask_frac * len(obs))))
            if len(obs) <= k:
                continue
            drop = pd.Index(rng.choice(obs, size=k, replace=False))
            masked.loc[drop, c] = np.nan
            hidden[c] = drop
        if strategy == "lowrank":
            imputed = lowrank_impute(masked, cols, **strategy_kw)["imputed"]
        elif strategy in ("mean", "median"):
            fill = masked[cols].mean() if strategy == "mean" else masked[cols].median()
            imputed = masked[cols].fillna(fill)
        elif callable(strategy):
            imputed = strategy(masked, cols)
        else:
            raise ValueError(f"unknown strategy: {strategy!r}")
        for c, idx in hidden.items():
            true = X.loc[idx, c].to_numpy(dtype=float)
            got = imputed.loc[idx, c].to_numpy(dtype=float)
            mae = float(np.mean(np.abs(true - got)))
            med = float(X[c].median())
            mad = float(np.median(np.abs(X[c].dropna() - med))) or np.nan
            corr = float(np.corrcoef(true, got)[0, 1]) if len(idx) > 2 and np.std(got) > 0 else np.nan
            results[c].append((mae, mae / mad if mad else np.nan, corr))
    rows = []
    for c, vals in results.items():
        if not vals:
            continue
        arr = np.array(vals, dtype=float)
        corr_col = arr[:, 2]
        corr = float(np.nanmean(corr_col)) if not np.all(np.isnan(corr_col)) else np.nan
        rows.append({"column": c, "mae": round(float(np.nanmean(arr[:, 0])), 6),
                     "mae_over_mad": round(float(np.nanmean(arr[:, 1])), 4),
                     "truth_corr": round(corr, 4) if not np.isnan(corr) else np.nan,
                     "n_repeats": len(vals)})
    return pd.DataFrame(rows)


__all__ = ["missingness_summary", "co_missing_matrix", "missingness_vs_target",
           "lowrank_impute", "imputation_quality_probe"]
