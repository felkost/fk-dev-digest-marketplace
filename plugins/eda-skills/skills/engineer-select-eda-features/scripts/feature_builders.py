"""Leakage-safe feature construction (engineer steps 1-2).

Transformers learn their parameters on train/folds only:
- ``EmpiricalCDF`` / normal-CDF features from the training distribution;
- out-of-fold target encoding for training rows, train-fitted map for val/test;
- multi-hot encoding of mixed ``(a, b)`` category cells with a train vocabulary.
Plus stateless domain builders (ratios, diffs, signed-log, rank, flags).

Core-library only (numpy, pandas, scipy, scikit-learn).
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import MultiLabelBinarizer


# --------------------------------------------------------------------------- #
# Distributional features
# --------------------------------------------------------------------------- #

class EmpiricalCDF(BaseEstimator, TransformerMixin):
    """Map values to their training-distribution percentile P(X <= x) in [0,1].

    Fitted on train only; out-of-range values map toward 0 or 1.
    """

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        self.sorted_ = [np.sort(X[~np.isnan(X[:, j]), j]) for j in range(X.shape[1])]
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        out = np.empty_like(X)
        for j, sv in enumerate(self.sorted_):
            n = max(len(sv), 1)
            out[:, j] = np.searchsorted(sv, X[:, j], side="right") / n
        return out


def normal_cdf_features(train: pd.DataFrame, cols: Iterable[str]) -> dict:
    """Fit (mu, sigma) on train; returns a state usable on val/test."""
    params = {c: (float(train[c].mean()), float(train[c].std(ddof=1) or 1.0)) for c in cols}
    return {"params": params}


def apply_normal_cdf(state: dict, df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for c, (mu, sigma) in state["params"].items():
        out[f"{c}_ncdf"] = stats.norm.cdf(df[c].to_numpy(dtype=float), mu, sigma)
    return out


# --------------------------------------------------------------------------- #
# Mixed / multi-label categories
# --------------------------------------------------------------------------- #

def parse_multi_value(value) -> list[str]:
    """Parse ``a`` / ``(a, b)`` / ``[a; b]`` cells into a normalized list."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    s = str(value).strip()
    if not s:
        return []
    s = re.sub(r"^[\(\[\{]|[\)\]\}]$", "", s).strip()
    parts = re.split(r"[;,|]", s)
    return [p.strip().lower() for p in parts if p.strip()]


class MixedCategoryMultiHot(BaseEstimator, TransformerMixin):
    """Multi-hot encode mixed single/multi category cells; vocab fitted on train.

    Unseen categories at transform time are ignored (no new columns) but counted
    into an ``<name>__unknown`` indicator, and a ``<name>__count`` set-size
    feature is added.
    """

    def __init__(self, name: str = "cat"):
        self.name = name

    def fit(self, X, y=None):
        lists = [parse_multi_value(v) for v in np.asarray(X).ravel()]
        self.mlb_ = MultiLabelBinarizer().fit(lists)
        self.classes_ = set(self.mlb_.classes_)
        return self

    def transform(self, X):
        raw = [parse_multi_value(v) for v in np.asarray(X).ravel()]
        known = [[c for c in row if c in self.classes_] for row in raw]
        mat = self.mlb_.transform(known)
        cols = [f"{self.name}__{c}" for c in self.mlb_.classes_]
        out = pd.DataFrame(mat, columns=cols)
        out[f"{self.name}__count"] = [len(row) for row in raw]
        out[f"{self.name}__unknown"] = [
            int(any(c not in self.classes_ for c in row)) for row in raw
        ]
        return out


# --------------------------------------------------------------------------- #
# Out-of-fold target encoding
# --------------------------------------------------------------------------- #

def oof_target_encode(x: pd.Series, y: pd.Series, cv, smoothing: float = 10.0):
    """Return (oof_encoded_train, mapping_for_val_test, global_mean).

    Training rows get out-of-fold encodings; val/test use a map fitted on all
    training rows. Never fit this on validation/test.
    """
    x = x.reset_index(drop=True)
    y = y.reset_index(drop=True)
    global_mean = float(y.mean())
    oof = np.full(len(y), global_mean, dtype=float)
    for tr, va in cv.split(x, y):
        g = y.iloc[tr].groupby(x.iloc[tr])
        agg = g.agg(["mean", "count"])
        smooth = (agg["mean"] * agg["count"] + global_mean * smoothing) / (agg["count"] + smoothing)
        oof[va] = x.iloc[va].map(smooth).fillna(global_mean).to_numpy()
    g = y.groupby(x)
    agg = g.agg(["mean", "count"])
    mapping = (agg["mean"] * agg["count"] + global_mean * smoothing) / (agg["count"] + smoothing)
    return oof, mapping, global_mean


# --------------------------------------------------------------------------- #
# Text: pooled word embeddings
# --------------------------------------------------------------------------- #

class PooledTextEmbedding(BaseEstimator, TransformerMixin):
    """Document vectors by pooling pretrained word embeddings.

    ``weighting="mean"`` is the baseline; ``"tfidf"`` weights each token by a
    smooth idf **fitted on the training texts only** (idf is a learned
    statistic like any other) and typically beats plain mean by a small but
    real margin.

    ``embeddings`` is a dict-like ``token -> vector`` or a gensim
    ``KeyedVectors``-style object (``key_to_index`` + ``vectors``). The
    tokenizer must match the one used for the vocabulary audit (case included;
    see audit references/text-nlp.md on case mismatch).

    OOV policy is explicit: documents whose every token is OOV (or that are
    NaN/empty) get a **zero vector plus an ``all_oov`` flag column** — never a
    silent arbitrary constant. ``oov_policy="error"`` raises instead, for
    pipelines where such documents must not exist.
    """

    def __init__(self, embeddings, weighting: str = "mean", tokenizer=None,
                 lowercase: bool = True, oov_policy: str = "zeros_flag",
                 name: str = "txt"):
        self.embeddings = embeddings
        self.weighting = weighting
        self.tokenizer = tokenizer
        self.lowercase = lowercase
        self.oov_policy = oov_policy
        self.name = name

    def _tokens(self, text) -> list[str]:
        if pd.isna(text):
            return []
        s = str(text)
        if self.lowercase:
            s = s.lower()
        if self.tokenizer is not None:
            return list(self.tokenizer(s))
        return re.findall(r"[\w'-]+", s)

    def _vector(self, token):
        emb = self.embeddings
        if hasattr(emb, "key_to_index"):  # gensim KeyedVectors
            idx = emb.key_to_index.get(token)
            return None if idx is None else emb.vectors[idx]
        return emb.get(token) if hasattr(emb, "get") else None

    def fit(self, texts, y=None):
        probe = self._vector(next(iter(
            self.embeddings.key_to_index if hasattr(self.embeddings, "key_to_index")
            else self.embeddings
        )))
        self.dim_ = int(np.asarray(probe).shape[0])
        if self.weighting == "tfidf":
            texts = pd.Series(texts)
            n_docs = int(texts.notna().sum())
            df_counts: dict[str, int] = {}
            for t in texts.dropna():
                for tok in set(self._tokens(t)):
                    df_counts[tok] = df_counts.get(tok, 0) + 1
            # smooth idf (sklearn convention): log((1+n)/(1+df)) + 1
            self.idf_ = {t: np.log((1 + n_docs) / (1 + c)) + 1.0
                         for t, c in df_counts.items()}
        elif self.weighting != "mean":
            raise ValueError(f"unknown weighting: {self.weighting!r}")
        return self

    def transform(self, texts) -> pd.DataFrame:
        texts = pd.Series(texts)
        vecs = np.zeros((len(texts), self.dim_), dtype=float)
        all_oov = np.zeros(len(texts), dtype=int)
        for i, text in enumerate(texts):
            num = np.zeros(self.dim_)
            wsum = 0.0
            for tok in self._tokens(text):
                v = self._vector(tok)
                if v is None:
                    continue
                w = self.idf_.get(tok, 1.0) if self.weighting == "tfidf" else 1.0
                num += w * np.asarray(v, dtype=float)
                wsum += w
            if wsum > 0:
                vecs[i] = num / wsum
            else:
                if self.oov_policy == "error":
                    raise ValueError(f"document {texts.index[i]!r} has no in-vocabulary "
                                     "tokens (all-OOV / empty / NaN)")
                all_oov[i] = 1  # zero vector + explicit flag, not a magic constant
        out = pd.DataFrame(vecs, index=texts.index,
                           columns=[f"{self.name}_emb{j}" for j in range(self.dim_)])
        out[f"{self.name}_all_oov"] = all_oov
        return out


# --------------------------------------------------------------------------- #
# Stateless domain builders
# --------------------------------------------------------------------------- #

def add_ratio(df, num, den, name=None, eps=1e-9):
    out = df.copy()
    out[name or f"{num}_per_{den}"] = out[num] / (out[den].replace(0, np.nan)).fillna(eps)
    return out


def signed_log1p(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    return np.sign(s) * np.log1p(np.abs(s))


def rank_transform(s: pd.Series) -> pd.Series:
    """Rank to [0,1] -- monotone, outlier-robust. Fit-free but rank uses only
    the rows given; for strict safety rank train and map val/test by interp."""
    return s.rank(pct=True)


def missing_indicator(df, cols) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for c in cols:
        out[f"{c}_isna"] = df[c].isna().astype(int)
    return out


__all__ = [
    "EmpiricalCDF", "normal_cdf_features", "apply_normal_cdf",
    "parse_multi_value", "MixedCategoryMultiHot", "oof_target_encode",
    "PooledTextEmbedding",
    "add_ratio", "signed_log1p", "rank_transform", "missing_indicator",
]
