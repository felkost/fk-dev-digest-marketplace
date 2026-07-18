"""Outlier and anomaly signals (audit step 6).

Provide univariate (IQR, robust MAD-z, domain bounds) and multivariate
(IsolationForest / LOF) signals. Everything *flags*; nothing is removed. The
multivariate detectors fit on the training partition only.

Do not define "share of outliers" as points beyond the 1st/99th percentile --
that construction labels ~2% of any distribution by design.

Core-library only (numpy, pandas, scikit-learn).
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd


def iqr_flags(s: pd.Series, k: float = 1.5) -> pd.Series:
    x = s.astype(float)
    q1, q3 = np.nanpercentile(x, [25, 75])
    iqr = q3 - q1
    return (x < q1 - k * iqr) | (x > q3 + k * iqr)


def robust_z_flags(s: pd.Series, thresh: float = 3.5) -> pd.Series:
    """MAD-based robust z-score flags (Iglewicz-Hoaglin)."""
    x = s.astype(float)
    med = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - med))
    if mad == 0:
        return pd.Series(False, index=s.index)
    rz = 0.6745 * (x - med) / mad
    return rz.abs() > thresh


def domain_bound_flags(s: pd.Series, low: Optional[float] = None, high: Optional[float] = None) -> pd.Series:
    x = s.astype(float)
    flags = pd.Series(False, index=s.index)
    if low is not None:
        flags |= x < low
    if high is not None:
        flags |= x > high
    return flags


def multivariate_outliers(
    train_df: pd.DataFrame,
    cols: Iterable[str],
    score_df: Optional[pd.DataFrame] = None,
    method: str = "iforest",
    contamination="auto",
    random_state: int = 42,
) -> pd.DataFrame:
    """Fit an anomaly detector on train and score ``score_df`` (default: train).

    Returns a DataFrame with a boolean ``is_outlier`` and a continuous
    ``anomaly_score`` (higher = more anomalous). Imputation medians and scaling
    are learned on train only.
    """
    from sklearn.ensemble import IsolationForest
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.preprocessing import StandardScaler

    cols = list(cols)
    med = train_df[cols].astype(float).median()
    Xtr = train_df[cols].astype(float).fillna(med)
    scaler = StandardScaler().fit(Xtr)
    tgt = train_df if score_df is None else score_df
    Xte = scaler.transform(tgt[cols].astype(float).fillna(med))

    if method == "lof":
        model = LocalOutlierFactor(novelty=True, contamination=contamination)
        model.fit(scaler.transform(Xtr))
        pred = model.predict(Xte)
        score = -model.decision_function(Xte)
    else:
        model = IsolationForest(contamination=contamination, random_state=random_state)
        model.fit(scaler.transform(Xtr))
        pred = model.predict(Xte)
        score = -model.decision_function(Xte)

    return pd.DataFrame(
        {"is_outlier": pred == -1, "anomaly_score": score},
        index=tgt.index,
    )


def univariate_report(df: pd.DataFrame, cols: Optional[Iterable[str]] = None, k: float = 1.5) -> pd.DataFrame:
    """Per-column count of IQR and robust-z flags (compare, do not auto-drop)."""
    if cols is None:
        cols = df.select_dtypes(include=[np.number]).columns
    rows = []
    for c in cols:
        s = df[c]
        rows.append(
            {
                "column": c,
                "n_iqr_flags": int(iqr_flags(s, k).sum()),
                "n_robust_z_flags": int(robust_z_flags(s).sum()),
            }
        )
    return pd.DataFrame(rows).set_index("column")


__all__ = [
    "iqr_flags",
    "robust_z_flags",
    "domain_bound_flags",
    "multivariate_outliers",
    "univariate_report",
]
