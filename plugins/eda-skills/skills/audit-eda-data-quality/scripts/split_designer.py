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


def graph_split(
    edges: pd.DataFrame,
    src: str = "src",
    dst: str = "dst",
    mode: str = "inductive",
    test_size: float = 0.2,
    seed: int = 42,
) -> dict:
    """Split an edge list so the split matches the question being asked.

    A random split of *edges* is not automatically wrong -- but it answers a
    different question from a split of *nodes*, and the usual error is not
    knowing which one was answered:

    - ``transductive`` -- edges are held out, every node stays visible. This is
      "a new link appears among people we already know" (friend recommendation,
      a new transaction between existing accounts). Legitimate, and it must be
      declared, because node-level features computed on the training graph
      legitimately see both endpoints of every test edge.
    - ``inductive`` -- whole nodes are held out; a test edge has **both**
      endpoints unseen. This is "a new user/device/account arrives". It is the
      only honest setting when the model must generalise to new entities.

    The arithmetic nobody expects, and the reason this needs a function: hold
    out a fraction ``q`` of nodes and the edges divide as ``(1-q)^2`` train,
    ``q^2`` test, ``2q(1-q)`` **cross-boundary and unusable**. At ``q = 0.2``
    that is 64% / 4% / **32%** -- holding out a fifth of the nodes yields a test
    set of 4% of the edges while discarding a third of them. To reach a 20% edge
    test share you must hold out ``sqrt(0.2) ~ 45%`` of nodes and throw away
    ~49% of the edges. Cross edges are dropped rather than assigned: an edge
    with one endpoint in train and one in test belongs to neither question.

    ``test_size`` is the fraction of **nodes** in ``inductive`` mode and the
    fraction of **edges** in ``transductive`` mode; the achieved shares of both
    are reported either way, so the trade is visible instead of assumed.

    Returns ``{'train_idx', 'test_idx', 'dropped_idx', 'manifest'}`` with
    positional indices into ``edges``.
    """
    if mode not in ("inductive", "transductive"):
        raise ValueError(f"unknown mode: {mode} (use 'inductive' or 'transductive')")

    rng = np.random.default_rng(seed)
    s = edges[src].to_numpy()
    d = edges[dst].to_numpy()
    pos = np.arange(len(edges))
    node_labels = pd.Index(pd.unique(np.concatenate([s, d])))
    n_nodes = len(node_labels)

    manifest: dict = {"strategy": f"graph_{mode}", "seed": seed,
                      "n_nodes": int(n_nodes), "n_edges": int(len(edges))}

    if mode == "transductive":
        te_mask = np.zeros(len(edges), bool)
        te_mask[rng.choice(len(edges), size=int(round(len(edges) * test_size)), replace=False)] = True
        tr, te, dropped = pos[~te_mask], pos[te_mask], pos[:0]
        train_nodes = set(np.concatenate([s[~te_mask], d[~te_mask]]).tolist())
        both_seen = float(np.mean([
            (u in train_nodes) and (v in train_nodes) for u, v in zip(s[te_mask], d[te_mask])
        ])) if te.size else float("nan")
        manifest["endpoints_seen_in_train"] = both_seen
        manifest["rationale"] = (
            "New links among known nodes. Node-level features see both endpoints of "
            "every test edge by design - this is the assumption, not a leak, and it "
            "is only valid if deployment also scores known nodes.")
    else:
        held = np.zeros(n_nodes, bool)
        held[rng.choice(n_nodes, size=int(round(n_nodes * test_size)), replace=False)] = True
        is_held = pd.Series(held, index=node_labels)
        s_held = is_held.reindex(s).to_numpy()
        d_held = is_held.reindex(d).to_numpy()
        te_mask = s_held & d_held
        tr_mask = ~s_held & ~d_held
        cross = ~te_mask & ~tr_mask
        tr, te, dropped = pos[tr_mask], pos[te_mask], pos[cross]
        manifest["held_out_node_share"] = float(held.mean())
        manifest["cross_edges_dropped"] = int(cross.sum())
        manifest["cross_edge_share"] = float(cross.mean())
        manifest["endpoints_seen_in_train"] = 0.0
        manifest["rationale"] = (
            "New entities arrive: both endpoints of every test edge are unseen. "
            "Cross-boundary edges are discarded because they answer neither question.")

    manifest["row_counts"] = {"train": int(tr.size), "test": int(te.size),
                              "dropped": int(dropped.size)}
    manifest["edge_test_share"] = float(te.size / len(edges)) if len(edges) else float("nan")
    manifest["overlap_checks"] = {
        "index_overlap": int(len(set(tr.tolist()) & set(te.tolist()))),
        "node_overlap": int(len(
            set(np.concatenate([s[tr], d[tr]]).tolist()) &
            set(np.concatenate([s[te], d[te]]).tolist())
        )) if tr.size and te.size else 0,
    }
    return {"train_idx": tr, "test_idx": te, "dropped_idx": dropped, "manifest": manifest}


__all__ = ["make_split", "purge_and_embargo", "graph_split"]
