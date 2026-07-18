"""Clustering routing and validation (discover steps 3-4).

Route to an algorithm by data shape, compute internal indices, and -- most
importantly -- measure stability with bootstrap ARI. Do not pick an algorithm by
the highest silhouette alone; prefer a simpler stable partition over a brittle
complex one.

Core is scikit-learn; HDBSCAN / K-Modes / K-Prototypes are optional (lazy).
"""

from __future__ import annotations

from typing import Optional, Union

import numpy as np
import pandas as pd


def _scale_matrix(X, scale: Union[bool, str]):
    """Scale a numeric matrix for distance-based clustering.

    ``True``/``'standard'`` -> z-score; ``'range'`` -> min-max; ``'robust'`` ->
    median/IQR; ``False``/``None`` -> as-is. Note that z-scoring divides by the
    standard deviation, which is *inflated* exactly for multimodal
    (cluster-bearing) features, so it suppresses the features that carry the
    cluster structure; range scaling often preserves that structure better
    (Mirkin). Compare partitions under both before trusting either.
    """
    Xarr = np.asarray(X, dtype=float)
    if scale is False or scale is None:
        return Xarr
    if scale is True or scale == "standard":
        from sklearn.preprocessing import StandardScaler
        return StandardScaler().fit_transform(Xarr)
    if scale == "range":
        from sklearn.preprocessing import MinMaxScaler
        return MinMaxScaler().fit_transform(Xarr)
    if scale == "robust":
        from sklearn.preprocessing import RobustScaler
        return RobustScaler().fit_transform(Xarr)
    raise ValueError(f"unknown scale: {scale!r}")


def run_clustering(X, algorithm: str = "kmeans", k: Optional[int] = None,
                   scale: Union[bool, str] = True, random_state: int = 42, **kw) -> dict:
    """Fit a clustering and return ``{'labels', 'model', 'X'}``.

    algorithm: kmeans | gmm | dbscan | agglomerative | hdbscan | kmodes | kprototypes
    scale: True/'standard' | 'range' | 'robust' | False (see :func:`_scale_matrix`)
    """
    Xarr = np.asarray(X, dtype=float)
    Xs = _scale_matrix(Xarr, scale)
    algo = algorithm.lower()

    if algo in ("kmeans", "minibatch"):
        from sklearn.cluster import KMeans, MiniBatchKMeans
        cls = MiniBatchKMeans if algo == "minibatch" else KMeans
        model = cls(n_clusters=k or 3, random_state=random_state, n_init=10)
        labels = model.fit_predict(Xs)
    elif algo in ("gmm", "gaussian_mixture"):
        from sklearn.mixture import GaussianMixture
        model = GaussianMixture(n_components=k or 3, random_state=random_state,
                                covariance_type=kw.get("covariance_type", "full"))
        labels = model.fit_predict(Xs)
    elif algo == "dbscan":
        from sklearn.cluster import DBSCAN
        model = DBSCAN(eps=kw.get("eps", 0.5), min_samples=kw.get("min_samples", 5))
        labels = model.fit_predict(Xs)
    elif algo in ("agglomerative", "hierarchical"):
        from sklearn.cluster import AgglomerativeClustering
        model = AgglomerativeClustering(n_clusters=k or 3, linkage=kw.get("linkage", "ward"))
        labels = model.fit_predict(Xs)
    elif algo == "hdbscan":
        try:
            import hdbscan
        except ImportError as e:  # pragma: no cover
            raise ImportError("hdbscan is optional; `pip install hdbscan`") from e
        model = hdbscan.HDBSCAN(min_cluster_size=kw.get("min_cluster_size", 15))
        labels = model.fit_predict(Xs)
    elif algo in ("kmodes", "kprototypes"):
        try:
            from kmodes.kmodes import KModes
            from kmodes.kprototypes import KPrototypes
        except ImportError as e:  # pragma: no cover
            raise ImportError("kmodes is optional; `pip install kmodes`") from e
        if algo == "kmodes":
            model = KModes(n_clusters=k or 3, random_state=random_state)
            labels = model.fit_predict(np.asarray(X))
        else:
            model = KPrototypes(n_clusters=k or 3, random_state=random_state)
            labels = model.fit_predict(np.asarray(X), categorical=kw.get("categorical", []))
    else:
        raise ValueError(f"unknown algorithm: {algorithm}")

    return {"labels": np.asarray(labels), "model": model, "X": Xs}


def k_scan(X, k_range=range(2, 16), algorithm: str = "kmeans",
           scale: Union[bool, str] = True, random_state: int = 42,
           hartigan_threshold: float = 10.0, **kw) -> pd.DataFrame:
    """Scan candidate ``k`` and collect complementary signals per k.

    Columns: inertia/SSE (kmeans-family), silhouette, calinski_harabasz,
    davies_bouldin, and bic/aic for GMM. ``elbow_candidate`` marks the knee of
    the SSE curve (max distance to the chord -- a dependency-free Kneedle).
    ``hartigan`` is Hartigan's rule-of-thumb index
    ``H_K = (W_K / W_{K+1} - 1)(N - K - 1)``; ``hartigan_candidate`` marks the
    first k with ``H_K < hartigan_threshold`` (default 10; the result is not
    sensitive to 10-20% threshold changes, and the rule was the best of nine
    k-selection criteria in Chiang & Mirkin's experiments). It needs a
    contiguous k range and inertia, so it appears for the kmeans family only.
    The elbow/Hartigan are heuristics: read them together with silhouette,
    DB/CH, BIC/AIC and :func:`cluster_stability`, and prefer domain utility
    over any single curve. More clusters than semantic classes is a legitimate
    outcome (within-class styles/modes).
    """
    Xarr = np.asarray(X, dtype=float)
    Xs = _scale_matrix(Xarr, scale)
    rows = []
    for k in k_range:
        res = run_clustering(Xs, algorithm=algorithm, k=int(k), scale=False,
                             random_state=random_state, **kw)
        row = {"k": int(k), **internal_indices(Xs, res["labels"])}
        model = res["model"]
        if hasattr(model, "inertia_"):
            row["inertia"] = round(float(model.inertia_), 2)
        if hasattr(model, "bic"):
            row["bic"] = round(float(model.bic(Xs)), 2)
            row["aic"] = round(float(model.aic(Xs)), 2)
        rows.append(row)
    out = pd.DataFrame(rows)

    curve = ("inertia" if "inertia" in out else "bic" if "bic" in out else None)
    out["elbow_candidate"] = False
    if curve and out[curve].notna().all() and len(out) >= 3:
        # Kneedle-style knee: farthest point from the first-last chord.
        x = out["k"].to_numpy(dtype=float)
        yv = out[curve].to_numpy(dtype=float)
        x_n = (x - x[0]) / (x[-1] - x[0])
        y_n = (yv - yv.min()) / (yv.max() - yv.min() + 1e-12)
        dist = np.abs(y_n - (y_n[0] + (y_n[-1] - y_n[0]) * x_n))
        out.loc[int(np.argmax(dist)), "elbow_candidate"] = True

    if "inertia" in out and len(out) >= 2 and out["k"].diff().dropna().eq(1).all():
        w = out["inertia"].to_numpy(dtype=float)
        kv = out["k"].to_numpy(dtype=float)
        n_obj = Xarr.shape[0]
        with np.errstate(divide="ignore", invalid="ignore"):
            h = (w[:-1] / w[1:] - 1.0) * (n_obj - kv[:-1] - 1.0)
        out["hartigan"] = np.append(np.round(h, 2), np.nan)
        out["hartigan_candidate"] = False
        below = np.where(h < hartigan_threshold)[0]
        if below.size:
            out.loc[out.index[int(below[0])], "hartigan_candidate"] = True
    return out


def silhouette_profile(X, labels) -> pd.DataFrame:
    """Per-cluster silhouette table (the tabular version of silhouette 'knives').

    The average silhouette hides weak clusters: inspect each cluster's mean,
    minimum, share of negative-silhouette points, and size. Clusters with a low
    mean or many negative points are merge/split/noise candidates.
    """
    from sklearn.metrics import silhouette_samples

    X = np.asarray(X, dtype=float)
    labels = np.asarray(labels)
    mask = labels != -1
    if np.unique(labels[mask]).size < 2:
        return pd.DataFrame()
    sil = silhouette_samples(X[mask], labels[mask])
    df = pd.DataFrame({"cluster": labels[mask], "sil": sil})
    prof = df.groupby("cluster")["sil"].agg(
        size="count", mean_sil="mean", min_sil="min",
        frac_negative=lambda s: float((s < 0).mean()),
    ).reset_index()
    prof["weak"] = (prof["mean_sil"] < df["sil"].mean()) & (prof["frac_negative"] > 0.1)
    return prof.round(4)


def k_distance(X, k: int = 5, scale: Union[bool, str] = True) -> dict:
    """Sorted k-th nearest-neighbor distances -- the k-distance graph for
    choosing DBSCAN ``eps`` (knee = eps candidate; ``min_samples`` = k, with the
    rule of thumb min_samples >= n_dims + 1). Returns the sorted distances and
    the knee estimate; always inspect the curve, not just the number."""
    from sklearn.neighbors import NearestNeighbors

    Xarr = np.asarray(X, dtype=float)
    Xs = _scale_matrix(Xarr, scale)
    nn = NearestNeighbors(n_neighbors=k + 1).fit(Xs)
    dist, _ = nn.kneighbors(Xs)
    kd = np.sort(dist[:, k])
    x_n = np.linspace(0, 1, kd.size)
    y_n = (kd - kd.min()) / (kd.max() - kd.min() + 1e-12)
    knee = int(np.argmax(np.abs(y_n - x_n)))
    return {"k": k, "sorted_k_distances": kd,
            "eps_candidate": round(float(kd[knee]), 4)}


def label_alignment(labels, y) -> dict:
    """Diagnostic cross-check of clusters against existing labels.

    Maps each cluster to its majority label and reports purity, homogeneity,
    and the per-cluster majority table. This validates *data structure*
    (labels only as an independent check, never as clustering input); it is not
    a model accuracy claim. Low purity with high stability may mean clusters
    encode a different-but-real factor (style, source, regime), and several
    clusters mapping to one label is normal.
    """
    from sklearn.metrics import homogeneity_score

    labels = np.asarray(labels)
    y = np.asarray(y)
    mask = labels != -1
    ct = pd.crosstab(pd.Series(labels[mask], name="cluster"),
                     pd.Series(y[mask], name="label"))
    majority = ct.idxmax(axis=1)
    purity = float(ct.max(axis=1).sum() / ct.to_numpy().sum())
    return {
        "purity": round(purity, 4),
        "homogeneity": round(float(homogeneity_score(y[mask], labels[mask])), 4),
        "cluster_to_label": majority.to_dict(),
        "contingency": ct,
        "n_clusters": int(ct.shape[0]), "n_labels": int(ct.shape[1]),
    }


def internal_indices(X, labels) -> dict:
    """Silhouette / Calinski-Harabasz / Davies-Bouldin, ignoring DBSCAN noise."""
    from sklearn.metrics import (
        calinski_harabasz_score, davies_bouldin_score, silhouette_score,
    )

    X = np.asarray(X, dtype=float)
    labels = np.asarray(labels)
    mask = labels != -1
    uniq = np.unique(labels[mask])
    if uniq.size < 2 or mask.sum() < 3:
        return {"n_clusters": int(uniq.size), "silhouette": np.nan,
                "calinski_harabasz": np.nan, "davies_bouldin": np.nan,
                "noise_frac": float((labels == -1).mean())}
    return {
        "n_clusters": int(uniq.size),
        "silhouette": round(float(silhouette_score(X[mask], labels[mask])), 4),
        "calinski_harabasz": round(float(calinski_harabasz_score(X[mask], labels[mask])), 2),
        "davies_bouldin": round(float(davies_bouldin_score(X[mask], labels[mask])), 4),
        "noise_frac": round(float((labels == -1).mean()), 4),
    }


def cluster_stability(X, algorithm: str = "kmeans", k: int = 3, n_boot: int = 20,
                      subsample: float = 0.8, random_state: int = 42) -> dict:
    """Bootstrap-ARI stability: cluster a reference, then re-cluster subsamples
    and compare on the shared points. Mean ARI near 1 = stable."""
    from sklearn.metrics import adjusted_rand_score

    rng = np.random.default_rng(random_state)
    Xarr = np.asarray(X, dtype=float)
    n = Xarr.shape[0]
    ref = run_clustering(Xarr, algorithm=algorithm, k=k, random_state=random_state)["labels"]

    aris = []
    for _ in range(n_boot):
        idx = rng.choice(n, int(subsample * n), replace=False)
        lab = run_clustering(Xarr[idx], algorithm=algorithm, k=k,
                             random_state=int(rng.integers(1e6)))["labels"]
        aris.append(adjusted_rand_score(ref[idx], lab))
    aris = np.array(aris)
    return {"mean_ari": round(float(aris.mean()), 4), "std_ari": round(float(aris.std()), 4),
            "n_boot": n_boot}


def anomalous_clusters(X, t: int = 1, scale: Union[bool, str] = "range",
                       reference=None, max_groups: int = 50,
                       max_iter: int = 100) -> dict:
    """Mirkin's anomalous-pattern extraction: deterministic K and centers.

    Repeatedly (1) take the point farthest from a fixed reference point
    (default: grand mean of the scaled data), (2) grow its 'anomalous group'
    with a two-center K-Means in which the reference center never moves
    (a point joins the group when it is closer to the group center than to the
    reference), (3) remove the group and repeat on the rest. The K-Means
    criterion prefers exactly such large far-from-center clusters, so the
    groups of size > ``t`` provide both the number of clusters and the initial
    centers for :func:`ik_means` -- no random restarts.

    Groups of size <= ``t`` are set aside (``is_kept=False``): anomalous
    singletons are frequent *data-error* candidates (an age of 5000) and are
    worth routing back to the audit rather than clustering. ``contribution``
    is the group's share of the data scatter around the reference -- report it
    per cluster; a steep drop is a natural stopping signal.

    Returns ``{'groups', 'labels', 'centers', 'K', 'reference', 'X'}``;
    ``labels`` has -1 for points in discarded small groups.
    """
    Xs = _scale_matrix(np.asarray(X, dtype=float), scale)
    n = Xs.shape[0]
    a = Xs.mean(axis=0) if reference is None else np.asarray(reference, dtype=float)
    total_scatter = float(((Xs - a) ** 2).sum())
    if total_scatter <= 0:
        raise ValueError("all points coincide with the reference; nothing to extract")

    remaining = np.ones(n, dtype=bool)
    labels = np.full(n, -1, dtype=int)
    groups = []
    order = 0
    while remaining.any() and order < max_groups:
        idx = np.where(remaining)[0]
        d_ref = ((Xs[idx] - a) ** 2).sum(axis=1)
        c = Xs[idx[int(np.argmax(d_ref))]].copy()
        members = None
        for _ in range(max_iter):
            d_c = ((Xs[idx] - c) ** 2).sum(axis=1)
            new_members = idx[d_c < d_ref]  # ties go to the reference
            if new_members.size == 0:
                new_members = idx[[int(np.argmax(d_ref))]]
            if members is not None and np.array_equal(new_members, members):
                break
            members = new_members
            c = Xs[members].mean(axis=0)
        contribution = members.size * float(((c - a) ** 2).sum()) / total_scatter
        groups.append({"order": order, "size": int(members.size),
                       "contribution": round(contribution, 4),
                       "is_kept": bool(members.size > t),
                       "indices": members})
        remaining[members] = False
        order += 1

    kept = [g for g in groups if g["is_kept"]]
    centers = np.array([Xs[g["indices"]].mean(axis=0) for g in kept])
    for cluster_id, g in enumerate(kept):
        labels[g["indices"]] = cluster_id
    table = pd.DataFrame([{k: v for k, v in g.items() if k != "indices"}
                          for g in groups])
    return {"groups": table, "labels": labels, "centers": centers,
            "K": len(kept), "reference": a, "X": Xs,
            "discarded_indices": np.concatenate(
                [g["indices"] for g in groups if not g["is_kept"]]
            ) if any(not g["is_kept"] for g in groups) else np.array([], dtype=int)}


def ik_means(X, t: int = 1, scale: Union[bool, str] = "range",
             random_state: int = 42) -> dict:
    """Intelligent K-Means: K-Means initialized by :func:`anomalous_clusters`.

    The anomalous-pattern pass fixes both K and the starting centers
    deterministically (``n_init=1``); small groups (size <= t) are excluded
    from initialization and reported for outlier/data-error triage -- set
    ``t=0`` to keep every group. Validate the partition exactly like any other
    clustering (stability, silhouette profile, domain profiling).
    """
    ac = anomalous_clusters(X, t=t, scale=scale)
    if ac["K"] < 1:
        raise ValueError("no anomalous group is larger than t; lower t or "
                         "treat the data as unclustered")
    from sklearn.cluster import KMeans

    km = KMeans(n_clusters=ac["K"], init=ac["centers"], n_init=1,
                random_state=random_state)
    labels = km.fit_predict(ac["X"])
    return {"labels": labels, "model": km, "K": ac["K"],
            "anomalous": ac, "X": ac["X"]}


def profile_clusters(df: pd.DataFrame, labels, cols=None) -> pd.DataFrame:
    """Per-cluster means on original variables (name clusters only after domain
    validation)."""
    cols = list(cols) if cols is not None else df.select_dtypes(include=[np.number]).columns
    tmp = df[cols].copy()
    tmp["_cluster"] = np.asarray(labels)
    return tmp.groupby("_cluster").agg(["mean", "count"])


__all__ = ["run_clustering", "internal_indices", "cluster_stability", "profile_clusters",
           "k_scan", "silhouette_profile", "k_distance", "label_alignment",
           "anomalous_clusters", "ik_means"]
