"""Split design (audit step 8).

Build a train/test split whose mechanism matches how new data appear, and emit
a split manifest (plain dict matching ``plan-eda-dataset`` ``SplitManifest``)
plus overlap checks. This designs the split; it does not touch a holdout in
response to results.

Core-library only (numpy, pandas, scikit-learn).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def make_split(
    df: pd.DataFrame,
    strategy: str = "stratified_random",
    target: Optional[str] = None,
    group: Optional[str] = None,
    time_col: Optional[str] = None,
    test_size: float = 0.2,
    seed: int = 42,
) -> dict:
    """Return ``{'train_idx', 'test_idx', 'manifest'}`` for the chosen strategy.

    strategy:
      - ``stratified_random`` : approx-IID classification (needs ``target``)
      - ``group``             : repeated entities (needs ``group``)
      - ``chronological``     : forecasting / point-in-time (needs ``time_col``)
      - ``spatial``           : region holdout (pass region id as ``group``)
    """
    n = len(df)
    pos = np.arange(n)
    manifest = {
        "strategy": strategy,
        "seed": seed,
        "group_key": group,
        "time_boundaries": {},
        "rationale": None,
    }

    if strategy == "stratified_random":
        from sklearn.model_selection import train_test_split

        strat = df[target] if (target and df[target].nunique() > 1) else None
        tr, te = train_test_split(pos, test_size=test_size, random_state=seed, stratify=strat)
        manifest["rationale"] = "Approximately IID rows; stratified on target."

    elif strategy in ("group", "spatial"):
        from sklearn.model_selection import GroupShuffleSplit

        if not group:
            raise ValueError(f"strategy '{strategy}' requires a group column")
        gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        tr, te = next(gss.split(pos, groups=df[group].to_numpy()))
        manifest["rationale"] = "Whole groups/regions held out to test generalization."

    elif strategy in ("chronological", "rolling"):
        if not time_col:
            raise ValueError("chronological split requires time_col")
        order = np.argsort(df[time_col].to_numpy(), kind="stable")
        cut = int(round(n * (1 - test_size)))
        tr, te = order[:cut], order[cut:]
        t = df[time_col].to_numpy()
        manifest["time_boundaries"] = {
            "train_end": str(t[order[cut - 1]]) if cut > 0 else None,
            "test_start": str(t[order[cut]]) if cut < n else None,
        }
        manifest["rationale"] = "Past predicts future; test is strictly later."

    else:
        raise ValueError(f"unknown strategy: {strategy}")

    tr = np.asarray(tr)
    te = np.asarray(te)

    # ---- overlap checks -------------------------------------------------- #
    checks: dict = {"index_overlap": int(len(set(tr) & set(te)))}
    if group:
        gtr = set(df.iloc[tr][group])
        gte = set(df.iloc[te][group])
        checks["group_overlap"] = int(len(gtr & gte))
    if time_col and strategy in ("chronological", "rolling") and len(tr) and len(te):
        checks["time_ordered"] = bool(
            df.iloc[tr][time_col].max() <= df.iloc[te][time_col].min()
        )

    manifest["row_counts"] = {"train": int(len(tr)), "test": int(len(te))}
    if target and df[target].nunique() <= 20:
        manifest["class_rates"] = {
            "train": df.iloc[tr][target].value_counts(normalize=True).round(4).to_dict(),
            "test": df.iloc[te][target].value_counts(normalize=True).round(4).to_dict(),
        }
    manifest["overlap_checks"] = checks
    return {"train_idx": tr, "test_idx": te, "manifest": manifest}


def purge_and_embargo(
    train_idx,
    test_idx,
    horizon: int,
    embargo: Optional[int] = None,
) -> dict:
    """Drop training rows whose forward-looking LABEL reaches into the test block.

    When a label spans ``horizon`` steps forward (return over the next 20 days,
    churn within 90 days, readmission within 30 days), a training row at ``t``
    carries information from ``t+1 .. t+horizon``. If that span touches the test
    block, the training label literally contains the test period's outcome --
    a leak no feature-side check can see, because the offending column is the
    target. Purging removes those rows; the embargo additionally drops training
    rows just *after* the test block, where serial dependence still bites.

    Returns the kept training indices plus a manifest of what was dropped.

    **Measured honestly, because the result was not what the technique's
    reputation implies.** On a design where true skill is exactly zero (label =
    sum of the next h innovations, features = past only), apparent skill was:

    ====  ================  ==================  ======================
    h     shuffled k-fold   contiguous k-fold   purged+embargo k-fold
    ====  ================  ==================  ======================
    5     **+0.151**        -0.026              -0.027
    20    **+0.203**        -0.048              -0.047
    50    **+0.205**        -0.116              -0.127
    ====  ================  ==================  ======================

    So: **shuffling is the catastrophic error**, inventing 0.15-0.21 of
    correlation out of nothing, and simply keeping folds contiguous removes
    essentially all of it. Explicit purging changed nothing measurable beyond
    contiguity in that design, because shuffling's damage comes from placing
    training rows *interleaved with* every test row, not from the fold
    boundary. Purging is still the correct guard -- it costs a few rows and it
    is the only thing that removes the boundary leak when folds are many and
    small -- but do not expect it to rescue a shuffled split, and do not skip
    contiguity because you purged.

    Note also the negative bias of contiguous k-fold at large ``h`` (-0.116 at
    h=50): with a persistent label, held-out blocks sit systematically opposite
    the training mean. On overlapping labels a single CV number is unreliable
    in **both** directions; see ``sampling_design.overlapping_label_deff``.
    """
    tr = np.asarray(list(train_idx))
    te = np.asarray(list(test_idx))
    h = int(max(horizon, 0))
    emb = int(h if embargo is None else max(embargo, 0))
    if te.size == 0 or tr.size == 0:
        return {"train_idx": tr, "n_purged": 0, "n_embargoed": 0,
                "manifest": {"horizon": h, "embargo": emb, "note": "empty split"}}
    lo, hi = int(te.min()), int(te.max())
    # label of training row i spans [i+1, i+h]; it leaks if that span reaches lo
    leaks_forward = (tr + h >= lo) & (tr < lo)
    in_embargo = (tr > hi) & (tr <= hi + emb)
    drop = leaks_forward | in_embargo
    kept = tr[~drop]
    return {
        "train_idx": kept,
        "n_purged": int(leaks_forward.sum()),
        "n_embargoed": int(in_embargo.sum()),
        "manifest": {
            "horizon": h,
            "embargo": emb,
            "test_span": [lo, hi],
            "n_train_before": int(tr.size),
            "n_train_after": int(kept.size),
            "fraction_dropped": float(drop.sum() / tr.size),
            "rationale": ("Training labels spanning into the test block were removed "
                          "(purge); rows just after the block were removed (embargo)."),
        },
    }


__all__ = ["make_split", "purge_and_embargo"]
