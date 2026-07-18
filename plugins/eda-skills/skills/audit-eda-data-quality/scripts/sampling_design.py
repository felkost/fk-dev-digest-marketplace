"""Sampling design: how many independent observations do you actually have?

Almost every statistic this project computes -- a confidence interval, a
bootstrap, a PSI reliability guard, a chi-square, a correlation p-value --
assumes rows are independent draws. Real datasets are rarely collected that
way: pupils sit inside classes, readings inside sensors, sessions inside users,
households inside census tracts, and rows may carry unequal selection weights.

The consequence is measurable and large. With 60 clusters x 25 rows and an
intraclass correlation of 0.30, a nominal 95% CI for the mean covers the truth
**48.8%** of the time; the same data hold the information of ~183 independent
rows, not 1500. This module quantifies that so downstream stages can either
correct or, at minimum, caveat.

What it does NOT do: re-weighted estimation, survey-package linearisation, or
mixed models. Those are modelling. The audit's job is to state the effective
sample size and flag which later claims are affected.

Definitions used (all verified by simulation against injected ground truth):

- ``icc`` -- one-way random-effects intraclass correlation (ANOVA estimator,
  unequal cluster sizes handled via the standard ``m0`` correction).
- ``deff_mean = 1 + (m0 - 1) * icc`` -- Kish's design effect for a MEAN or a
  RATE. Recovered empirical variance inflation to within ~10% at icc
  0.05/0.15/0.30 (predicted 1.95/3.85/6.70, measured 1.93/4.35/7.06) when
  clusters are near-equal in size. With strongly unequal cluster sizes it is a
  **lower bound**: at icc=0.30 the empirical/predicted ratio grew 1.03 -> 1.14
  -> 1.27 -> 1.35 as cluster sizes spread from 18-22 to 10-30, 2-40, 1-60.
- ``deff_weights = n * sum(w^2) / (sum w)^2`` -- Kish's weight design effect.
  Predicted 1.11/1.67/2.78 vs measured 1.10/1.62/2.81 across weight patterns.
- ``deff_pair = 1 + (m0 - 1) * icc_x * icc_y`` -- the design effect for an
  ASSOCIATION between two columns. **This is not the same quantity as
  ``deff_mean`` and substituting one for the other is a real error**: using the
  mean's deff to correct a correlation test drove the false-positive rate to
  0.002 against a nominal 0.05, while the product rule held 0.045-0.052 across
  eight configurations.

Core-library only (numpy, pandas).
"""

from __future__ import annotations

from typing import Iterable, Optional, Union

import numpy as np
import pandas as pd

_NEGLIGIBLE = 1.2
_SUBSTANTIAL = 2.0


def _verdict(deff: float) -> str:
    if not np.isfinite(deff):
        return "undetermined"
    if deff < _NEGLIGIBLE:
        return "negligible"
    if deff < _SUBSTANTIAL:
        return "moderate"
    return "substantial"


def _f_test_p(ms_b: float, ms_w: float, df_b: int, df_w: int) -> float:
    """p-value of the one-way ANOVA F test that between-cluster variance is 0.

    scipy is optional here on purpose: this module is core-stack, and a missing
    scipy must degrade to "no guard" rather than raise.
    """
    if not (np.isfinite(ms_b) and np.isfinite(ms_w)) or ms_w <= 0:
        return float("nan")
    try:
        from scipy import stats as _st
    except Exception:  # pragma: no cover - scipy is present in the core stack
        return float("nan")
    return float(_st.f.sf(ms_b / ms_w, df_b, df_w))


def _mean_cluster_size(counts: np.ndarray) -> float:
    """Kish's ``m0``: the cluster size that makes the deff formula exact under
    unequal counts. Equals the plain mean when all clusters are the same size."""
    n = float(counts.sum())
    k = counts.size
    if k <= 1:
        return float(n)
    return float((n - np.sum(counts.astype(float) ** 2) / n) / (k - 1))


def intraclass_correlation(
    df: pd.DataFrame,
    group: Union[str, pd.Series],
    columns: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Per-column ICC and the design effect it implies for a mean or a rate.

    ``group`` is the cluster identifier -- the thing rows are nested in (user,
    school, sensor, session, household). Binary 0/1 columns are fine: the same
    estimator gives the ICC of a rate.

    A negative ICC estimate is a real possibility under a true ICC of zero
    (the ANOVA estimator is unbiased, not non-negative); ``icc`` is clipped at
    0 for the deff calculation and the raw value is kept in ``icc_raw``.

    The ``verdict`` is gated by an ANOVA F test (``icc_p_value``), because the
    point estimate alone cries wolf: on truly independent rows the estimator
    returns icc~0.003, which (m0-1)=19 multiplies into deff>1.2 in **10-22%**
    of samples. With the gate, the non-negligible rate on independent rows is
    5.2 / 3.0 / 0.5 / 4.5% across four cluster layouts -- i.e. the nominal 5%.
    The cost is at the very bottom: true icc of 0.01/0.02 is flagged only
    30%/63% of the time, where deff is 1.20/1.36 and barely consequential;
    from icc=0.05 upward detection was 100%.

    Returns one row per column with ``icc``, ``icc_p_value``, ``n_clusters``,
    ``mean_cluster_size``, ``deff_mean``, ``n_eff_mean`` and a ``verdict``.
    """
    g = df[group] if isinstance(group, str) else pd.Series(group, index=df.index)
    if columns is None:
        columns = [c for c in df.select_dtypes(include=[np.number]).columns
                   if not (isinstance(group, str) and c == group)]
    columns = list(columns)

    rows = []
    for col in columns:
        sub = pd.DataFrame({"y": pd.to_numeric(df[col], errors="coerce"), "g": g.values}).dropna()
        if sub.empty or sub["g"].nunique() < 2 or sub["y"].nunique() < 2:
            rows.append({
                "column": col, "icc": np.nan, "icc_raw": np.nan, "icc_p_value": np.nan,
                "n_rows": int(sub.shape[0]), "n_clusters": int(sub["g"].nunique()),
                "mean_cluster_size": np.nan, "deff_mean": np.nan,
                "n_eff_mean": np.nan, "verdict": "undetermined",
            })
            continue

        labs, inv = np.unique(sub["g"].to_numpy(), return_inverse=True)
        y = sub["y"].to_numpy(dtype=float)
        k, n = labs.size, y.size
        counts = np.bincount(inv).astype(float)
        means = np.bincount(inv, weights=y) / counts
        ss_b = float(np.sum(counts * (means - y.mean()) ** 2))
        ss_w = float(np.sum((y - means[inv]) ** 2))
        df_b, df_w = k - 1, n - k

        m0 = _mean_cluster_size(counts)

        # One row per cluster carries no clustering at all: deff is exactly 1,
        # whatever the (undefined) ICC. This is the common case where an ID
        # column is passed as ``group`` by mistake -- answer it cleanly.
        if m0 <= 1.0 + 1e-9:
            rows.append({
                "column": col, "icc": 0.0, "icc_raw": np.nan, "icc_p_value": np.nan,
                "n_rows": int(n), "n_clusters": int(k), "mean_cluster_size": float(m0),
                "deff_mean": 1.0, "n_eff_mean": float(n), "verdict": "negligible",
            })
            continue

        if df_b <= 0 or df_w <= 0:
            icc_raw, p_value = np.nan, np.nan
        else:
            ms_b, ms_w = ss_b / df_b, ss_w / df_w
            var_b = (ms_b - ms_w) / m0 if m0 > 0 else np.nan
            denom = var_b + ms_w
            icc_raw = float(var_b / denom) if denom and np.isfinite(denom) and denom > 0 else np.nan
            # One-way ANOVA F test for "between-cluster variance is zero".
            # Without this guard a sampling fluctuation of icc=0.011 on truly
            # independent rows is multiplied by (m0-1)=19 into deff=1.22 and
            # reported as real clustering -- measured false-alarm rate 44%.
            p_value = _f_test_p(ms_b, ms_w, df_b, df_w)

        icc = float(np.clip(icc_raw, 0.0, 1.0)) if np.isfinite(icc_raw) else np.nan
        deff = 1.0 + (m0 - 1.0) * icc if np.isfinite(icc) else np.nan
        verdict = _verdict(deff)
        if np.isfinite(p_value) and p_value > 0.05:
            verdict = "negligible"
        rows.append({
            "column": col, "icc": icc, "icc_raw": icc_raw, "icc_p_value": p_value,
            "n_rows": int(n), "n_clusters": int(k),
            "mean_cluster_size": float(m0),
            "deff_mean": float(deff) if np.isfinite(deff) else np.nan,
            "n_eff_mean": float(n / deff) if np.isfinite(deff) and deff > 0 else np.nan,
            "verdict": verdict,
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("deff_mean", ascending=False, na_position="last").reset_index(drop=True)
    return out


def weight_design_effect(weights: Iterable[float]) -> dict:
    """Kish's design effect from unequal selection weights.

    ``deff = n * sum(w^2) / (sum w)^2``; scale-invariant, so raw weights,
    normalized weights and inverse selection probabilities all give the same
    answer. Only the *variability* of the weights costs precision.
    """
    w_all = np.asarray(list(weights), dtype=float)
    w = w_all[np.isfinite(w_all)]
    n_dropped = int(w_all.size - w.size)
    if w.size == 0 or np.all(w <= 0):
        return {"n": 0, "n_dropped": int(w_all.size), "deff_weights": np.nan,
                "n_eff": np.nan, "cv_weights": np.nan, "max_min_ratio": np.nan,
                "verdict": "undetermined"}
    n_dropped += int(np.sum(w <= 0))
    w = w[w > 0]
    n = w.size
    deff = float(n * np.sum(w ** 2) / np.sum(w) ** 2)
    return {
        "n": int(n),
        "n_dropped": n_dropped,
        "deff_weights": deff,
        "n_eff": float(n / deff),
        "cv_weights": float(w.std(ddof=1) / w.mean()) if n > 1 else 0.0,
        "max_min_ratio": float(w.max() / w.min()),
        "verdict": _verdict(deff),
    }


def overlapping_label_deff(horizon: int, n: int) -> dict:
    """Design effect when each label is built from a FORWARD WINDOW of length h.

    Any label defined over a span -- "return over the next 20 days", "churn
    within 90 days", "readmission within 30 days", a rolling-sum or
    rolling-max target -- makes row ``t`` and row ``t+1`` share ``h-1`` of
    their ``h`` ingredients. The rows are not independent, and ``n`` stops
    being the amount of information present.

    Two different quantities, and conflating them is the trap:

    - **uniqueness = 1/h** is the right *sample weight* (Lopez de Prado): how
      much of a label is its own. Verified exactly -- measured mean uniqueness
      0.202 / 0.052 / 0.022 against 1/h = 0.200 / 0.050 / 0.020 for h=5/20/50.
    - **deff = 1 + (h-1)(2h-1)/(3h)** is the right *variance inflation* for an
      estimate computed on those rows. It is the Bartlett sum of the squared
      triangular autocorrelation (``rho_k = 1 - k/h``) that a rectangular
      window induces, and it tends to ``2h/3``, NOT to ``h``.

    Using ``1/h`` as if it were the variance inflation over-corrects badly:
    measured false-positive rates for a correlation between two *independent*
    forward-window series (alpha = 0.05, n = 1000) were

    ====  ========  =============  ===============
    h     naive     deff = h       deff = 2h/3
    ====  ========  =============  ===============
    1     0.049     0.049          0.049
    5     0.290     0.017          0.053
    20    0.580     0.012          0.045
    50    0.740     0.011          0.040
    ====  ========  =============  ===============

    -- i.e. uncorrected, three-quarters of independent pairs read as
    "significant" at h=50, while the ``h`` correction pushes alpha down to
    0.011. Measured deff tracked the formula closely (3.41 / 13.05 / 32.80
    against 3.40 / 13.35 / 33.34 for h=5/20/50).

    The formula assumes a *rectangular* window of constant length. For
    irregular spans, decayed weights, or a label whose horizon varies per row,
    treat it as an approximation and prefer a block bootstrap.
    """
    h = int(max(horizon, 1))
    deff = 1.0 + (h - 1) * (2 * h - 1) / (3.0 * h)
    deff = max(deff, 1.0)
    return {
        "horizon": h,
        "n": int(n),
        "uniqueness": 1.0 / h,
        "deff_overlap": float(deff),
        "deff_large_h_limit": 2.0 * h / 3.0,
        "n_eff": float(n / deff),
        "verdict": _verdict(deff),
    }


def label_concurrency(start: Iterable[float], end: Iterable[float]) -> dict:
    """Concurrency and average uniqueness for labels with EXPLICIT spans.

    Use when horizons vary per row (an event-driven label, a variable holding
    period, a case open until it closes). ``start``/``end`` are the inclusive
    bounds of each label's span on a common index.

    ``uniqueness_mean`` is the sample-weight quantity; the implied variance
    inflation is reported as ``deff_implied`` using the same Bartlett logic
    with the mean span, and is an approximation when spans are ragged.
    """
    s = np.asarray(list(start), dtype=float)
    e = np.asarray(list(end), dtype=float)
    if s.size == 0 or s.size != e.size:
        return {"n": int(s.size), "uniqueness_mean": np.nan,
                "mean_span": np.nan, "max_concurrency": np.nan,
                "deff_implied": np.nan, "verdict": "undetermined"}
    ok = np.isfinite(s) & np.isfinite(e) & (e >= s)
    s, e = s[ok], e[ok]
    if s.size == 0:
        return {"n": 0, "uniqueness_mean": np.nan, "mean_span": np.nan,
                "max_concurrency": np.nan, "deff_implied": np.nan,
                "verdict": "undetermined"}
    lo, hi = s.min(), e.max()
    grid = np.arange(int(np.floor(lo)), int(np.ceil(hi)) + 2)
    conc = np.zeros(grid.size, dtype=float)
    for a, b in zip(s, e):
        i0 = int(np.searchsorted(grid, a, side="left"))
        i1 = int(np.searchsorted(grid, b, side="right"))
        conc[i0:i1] += 1.0
    uniq = []
    for a, b in zip(s, e):
        i0 = int(np.searchsorted(grid, a, side="left"))
        i1 = int(np.searchsorted(grid, b, side="right"))
        seg = conc[i0:i1]
        seg = seg[seg > 0]
        uniq.append(float(np.mean(1.0 / seg)) if seg.size else 1.0)
    mean_span = float(np.mean(e - s + 1))
    d = overlapping_label_deff(int(round(mean_span)), s.size)
    return {
        "n": int(s.size),
        "uniqueness_mean": float(np.mean(uniq)),
        "mean_span": mean_span,
        "max_concurrency": float(conc.max()),
        "deff_implied": d["deff_overlap"],
        "n_eff": float(s.size / d["deff_overlap"]),
        "verdict": _verdict(d["deff_overlap"]),
    }


def effective_n_for_association(
    icc_x: float,
    icc_y: float,
    mean_cluster_size: float,
    n: int,
) -> dict:
    """Design effect for a correlation/association between two clustered columns.

    Uses ``deff = 1 + (m0 - 1) * icc_x * icc_y`` -- the PRODUCT of the two
    ICCs, not either one alone. Two consequences worth internalising:

    - If only one of the two columns is clustered, the product is ~0 and the
      association test needs **no** correction. Measured: icc_x=0.60 with
      icc_y=0.00 gave a false-positive rate of 0.047 uncorrected.
    - If both are clustered the naive test is badly wrong: icc_x=icc_y=0.30 at
      m0=25 gave a false-positive rate of **0.272** against a nominal 0.05,
      restored to 0.047 by this correction.
    """
    icc_x = float(np.clip(icc_x, 0.0, 1.0)) if np.isfinite(icc_x) else 0.0
    icc_y = float(np.clip(icc_y, 0.0, 1.0)) if np.isfinite(icc_y) else 0.0
    m0 = float(mean_cluster_size)
    deff = 1.0 + (m0 - 1.0) * icc_x * icc_y
    deff = max(deff, 1.0)
    return {
        "icc_x": icc_x,
        "icc_y": icc_y,
        "mean_cluster_size": m0,
        "deff_pair": deff,
        "n_eff_pair": float(n / deff),
        "verdict": _verdict(deff),
    }


def design_effect_report(
    df: pd.DataFrame,
    group: Optional[Union[str, pd.Series]] = None,
    weights: Optional[Union[str, Iterable[float]]] = None,
    columns: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """One-call summary combining clustering and unequal weights.

    The combined design effect is reported as ``deff_mean * deff_weights``.
    Measured behaviour of that product (weights held fixed as a property of the
    sample, 3 independent weight draws per case, 4000+ replicates each) --
    note this is the **opposite** of the intuition that the product needs
    weights to be independent of clusters:

    - weights that are a **cluster-level** property (one weight per school):
      the product is essentially exact, empirical/predicted = 1.05 / 0.99 / 0.99;
    - weights varying **within** clusters: the product **overstates** the design
      effect, empirical/predicted = 0.70 / 0.70 / 0.67, i.e. it is conservative
      by roughly 1.4x. Averaging many weights inside a cluster makes the
      cluster totals more nearly equal than the raw weight spread suggests.

    So: treat ``deff_total`` as accurate for cluster-level weights and as a
    safe upper bound for within-cluster weights.

    ``.attrs`` carries ``weights`` (the full weight dict) and ``notes``.
    """
    notes: list[str] = []
    if group is not None:
        out = intraclass_correlation(df, group, columns=columns)
    else:
        cols = list(columns) if columns is not None else list(
            df.select_dtypes(include=[np.number]).columns)
        out = pd.DataFrame({
            "column": cols, "icc": np.nan, "icc_raw": np.nan,
            "n_rows": len(df), "n_clusters": np.nan, "mean_cluster_size": np.nan,
            "deff_mean": 1.0, "n_eff_mean": float(len(df)), "verdict": "negligible",
        })
        notes.append("No cluster column supplied; clustering deff assumed 1.0 (unverified).")

    wdict = None
    if weights is not None:
        wvals = df[weights] if isinstance(weights, str) else weights
        wdict = weight_design_effect(wvals)
        dw = wdict["deff_weights"]
        if np.isfinite(dw):
            out["deff_weights"] = dw
            out["deff_total"] = out["deff_mean"].fillna(1.0) * dw
            out["n_eff_total"] = out["n_rows"] / out["deff_total"]
            out["verdict"] = [_verdict(v) for v in out["deff_total"]]
            notes.append("deff_total = deff_mean * deff_weights (approximation; "
                         "exact only if weights are independent of cluster membership).")
    else:
        out["deff_weights"] = 1.0
        out["deff_total"] = out["deff_mean"]
        out["n_eff_total"] = out["n_eff_mean"]

    notes.append("deff_mean applies to means/rates/CIs. For an association between two "
                 "columns use effective_n_for_association (product of ICCs), never this number.")
    out.attrs["weights"] = wdict
    out.attrs["notes"] = notes
    return out


__all__ = [
    "intraclass_correlation",
    "weight_design_effect",
    "overlapping_label_deff",
    "label_concurrency",
    "effective_n_for_association",
    "design_effect_report",
]
