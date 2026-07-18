"""Cluster tendency checks (discover step 2).

Before clustering, test whether there is any reason to expect clusters. A
Hopkins statistic near 0.5 means the data look uniformly random (no tendency);
values toward 1 suggest clusterable structure. "No stable clusters found" is a
valid conclusion and does not require forcing a `k`.

Core-library only (numpy, pandas, scikit-learn).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def hopkins_statistic(X, sample_ratio: float = 0.1, random_state: int = 42) -> float:
    """Hopkins statistic on scaled data. ~0.5 = random, ->1 = clustered."""
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import StandardScaler

    X = StandardScaler().fit_transform(np.asarray(X, dtype=float))
    n, d = X.shape
    m = max(2, int(sample_ratio * n))
    rng = np.random.default_rng(random_state)

    nn = NearestNeighbors(n_neighbors=2).fit(X)
    # distances from real sampled points to their nearest *other* real point
    idx = rng.choice(n, m, replace=False)
    u_dist = nn.kneighbors(X[idx], return_distance=True)[0][:, 1]
    # distances from uniform random points to the nearest real point
    mins, maxs = X.min(0), X.max(0)
    synth = rng.uniform(mins, maxs, size=(m, d))
    w_dist = nn.kneighbors(synth, n_neighbors=1, return_distance=True)[0][:, 0]

    denom = u_dist.sum() + w_dist.sum()
    return float(w_dist.sum() / denom) if denom > 0 else 0.5


def nn_distance_summary(X, k: int = 5) -> dict:
    """Nearest-neighbour distance summary -- concentration of distances in high
    dimensions can make naive distance clustering uninformative."""
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import StandardScaler

    X = StandardScaler().fit_transform(np.asarray(X, dtype=float))
    nn = NearestNeighbors(n_neighbors=k + 1).fit(X)
    dist = nn.kneighbors(X, return_distance=True)[0][:, 1:]
    kth = dist[:, -1]
    return {
        "k": k,
        "mean_kth_nn": round(float(kth.mean()), 4),
        "cv_kth_nn": round(float(kth.std() / kth.mean()), 4) if kth.mean() > 0 else 0.0,
        "note": "low CV of neighbour distances suggests distance concentration",
    }


__all__ = ["hopkins_statistic", "nn_distance_summary"]
