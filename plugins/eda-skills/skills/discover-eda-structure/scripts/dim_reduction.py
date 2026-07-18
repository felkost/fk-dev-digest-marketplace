"""Dimensionality reduction with train-only fit (discover step 5).

Linear methods (PCA, TruncatedSVD, NMF) expose ``transform`` for out-of-sample
data; t-SNE/UMAP are visualization-only and do not transform new points, so we
never derive a cluster count from their 2D embedding. Fit only on train/fold.

Core is scikit-learn (incl. t-SNE); UMAP and MCA/FAMD (prince) are optional.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

_HAS_TRANSFORM = {"pca", "svd", "nmf"}


def fit_reduce(X_train, method: str = "pca", n_components: int = 2,
               scale: bool = True, random_state: int = 42, **kw) -> dict:
    """Fit a reducer on training data and return a state dict.

    Returns ``{'method', 'reducer', 'scaler', 'embedding', 'explained_variance'}``.
    For t-SNE/UMAP the embedding is the train fit only and ``reducer`` is None
    (no out-of-sample transform).
    """
    from sklearn.preprocessing import StandardScaler

    X = np.asarray(X_train, dtype=float)
    method = method.lower()
    scaler = None
    if scale and method != "nmf":  # NMF needs non-negative input; don't standardize
        scaler = StandardScaler().fit(X)
        Xs = scaler.transform(X)
    else:
        Xs = X

    reducer = None
    explained = None
    if method == "pca":
        from sklearn.decomposition import PCA
        reducer = PCA(n_components=n_components, random_state=random_state).fit(Xs)
        emb = reducer.transform(Xs)
        explained = reducer.explained_variance_ratio_.round(4).tolist()
    elif method == "svd":
        from sklearn.decomposition import TruncatedSVD
        reducer = TruncatedSVD(n_components=n_components, random_state=random_state).fit(Xs)
        emb = reducer.transform(Xs)
        explained = reducer.explained_variance_ratio_.round(4).tolist()
    elif method == "nmf":
        from sklearn.decomposition import NMF
        reducer = NMF(n_components=n_components, random_state=random_state,
                      init="nndsvda", max_iter=kw.get("max_iter", 400)).fit(Xs)
        emb = reducer.transform(Xs)
    elif method == "tsne":
        from sklearn.manifold import TSNE
        emb = TSNE(n_components=n_components, random_state=random_state,
                   perplexity=kw.get("perplexity", 30)).fit_transform(Xs)
    elif method == "umap":
        try:
            import umap
        except ImportError as e:  # pragma: no cover
            raise ImportError("umap-learn is optional; `pip install umap-learn`") from e
        reducer = umap.UMAP(n_components=n_components, random_state=random_state).fit(Xs)
        emb = reducer.transform(Xs)
    else:
        raise ValueError(f"unknown method: {method}")

    return {"method": method, "reducer": reducer, "scaler": scaler,
            "embedding": emb, "explained_variance": explained}


def apply_reduce(state: dict, X_new) -> np.ndarray:
    """Transform new (validation/test) data with a fitted linear reducer."""
    method = state["method"]
    if method not in _HAS_TRANSFORM and method != "umap":
        raise ValueError(f"{method} has no out-of-sample transform; refit is not valid EDA")
    X = np.asarray(X_new, dtype=float)
    if state["scaler"] is not None:
        X = state["scaler"].transform(X)
    return state["reducer"].transform(X)


__all__ = ["fit_reduce", "apply_reduce"]
