"""Latent-factor structure behind a redundancy block (discover step 5).

`clustered_correlation.py` finds *that* a group of columns is redundant; VIF says
*how much* they overlap. Neither answers the question that follows: are these
columns several noisy measurements of one underlying thing (→ build a scale) or
genuinely distinct information that happens to co-move (→ keep them apart)?
That is a common-factor question, and it is not the same question PCA answers.

The distinction is the whole point of this module:

* **PCA** builds composites *out of* the columns. Component scores are an exact,
  closed-form weighted sum, the diagonal of the correlation matrix stays at 1.0,
  and every column contributes all of its variance — including its measurement
  error.
* **The common-factor model** treats the columns as *functions of* latent
  factors, estimates the communality (the shared part) and leaves a uniqueness
  per column. It is the model that matches "these are indicators of a construct".

Both are one eigendecomposition of a correlation matrix, so they agree closely
whenever communalities are high — and diverge exactly where it matters (few
indicators, weak loadings). Measured numbers are in the docstrings below and in
`references/factor-structure.md`.

Fit on train/fold only: every function here reads a correlation matrix estimated
from the data it is given, and that estimate is part of the model.

Core stack only (numpy/scipy); no optional dependencies.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

__all__ = [
    "correlation_matrix",
    "eigenvalue_report",
    "parallel_analysis",
    "principal_axis_factoring",
    "varimax",
    "promax",
    "rotate_loadings",
    "factor_structure_report",
    "pca_vs_fa",
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _as_matrix(X) -> np.ndarray:
    A = np.asarray(getattr(X, "values", X), dtype=float)
    if A.ndim != 2:
        raise ValueError("X must be 2-dimensional (n_rows x n_columns)")
    return A


def _names(X, p: int) -> list[str]:
    cols = getattr(X, "columns", None)
    return [str(c) for c in cols] if cols is not None else [f"x{i}" for i in range(p)]


def correlation_matrix(X, drop_constant: bool = True):
    """Correlation matrix plus the indices of columns that carry no variance.

    A constant column has an undefined correlation and quietly turns the whole
    matrix into NaN, which then surfaces as an unrelated eigen error. Caught here
    instead.
    """
    A = _as_matrix(X)
    sd = A.std(axis=0, ddof=1)
    keep = sd > 0 if drop_constant else np.ones(A.shape[1], bool)
    R = np.corrcoef(A[:, keep], rowvar=False)
    if R.ndim == 0:
        R = R.reshape(1, 1)
    return R, np.flatnonzero(keep), np.flatnonzero(~keep)


# --------------------------------------------------------------------------- #
# eigenvalues
# --------------------------------------------------------------------------- #
def eigenvalue_report(X, scale: bool = True) -> dict:
    """Eigenvalues of the correlation matrix, with the two identities that matter.

    On a correlation matrix of `p` columns the eigenvalues **sum to p** (verified
    to 6.000000000000 on p=6) and their **product is the determinant** (verified
    to 1.11e-16 absolute). The second identity is the useful one: the determinant
    is the generalized variance — the volume the column space still has — so it
    goes to zero exactly when a column becomes a linear combination of the
    others. Making one column an exact duplicate drove the smallest eigenvalue to
    5.55e-17 and the determinant to 0.0. That is the same fact as an infinite VIF
    and as a "matrix is not positive definite" error.

    ``kaiser_count`` (eigenvalues > 1) is reported because it is what most
    software prints, **not** because it is a recommendation: on 300 rows of pure
    independent noise it claimed 4.83 / 9.45 / 18.38 factors at p = 10 / 20 / 40,
    i.e. roughly p/2 dimensions in data with no structure whatsoever. Use
    `parallel_analysis` to decide; see its docstring for the head-to-head.
    """
    R, keep, dropped = correlation_matrix(X)
    p = R.shape[0]
    if p < 2:
        return {"verdict": "insufficient_columns", "n_columns": int(p)}
    w = np.sort(np.linalg.eigvalsh(R))[::-1]
    total = float(w.sum())
    return {
        "n_columns": int(p),
        "dropped_constant_columns": dropped.tolist(),
        "eigenvalues": np.round(w, 6).tolist(),
        "explained_variance_ratio": np.round(w / total, 6).tolist(),
        "cumulative_ratio": np.round(np.cumsum(w) / total, 6).tolist(),
        "sum_eigenvalues": round(total, 10),
        "determinant": float(np.linalg.det(R)),
        "smallest_eigenvalue": round(float(w[-1]), 10),
        "kaiser_count": int(np.sum(w > 1.0)),
        "verdict": ("singular_or_near_singular" if w[-1] < 1e-8
                    else "well_conditioned" if w[-1] > 0.01
                    else "ill_conditioned"),
        "note": ("kaiser_count is reported for orientation only; it over-extracts "
                 "badly (p/2 factors on pure noise) - use parallel_analysis"),
    }


def parallel_analysis(X, n_iter: int = 200, percentile: float = 95,
                      random_state: int = 42, on: str = "correlation") -> dict:
    """Horn's parallel analysis: how many dimensions beat random data of the same shape.

    Simulate `n_iter` datasets of the same n x p shape from independent normals,
    take the `percentile`-th eigenvalue at each position, and keep the leading
    components whose observed eigenvalue exceeds that threshold. Everything below
    is what noise alone produces at this sample size.

    Measured against Kaiser's eigenvalue>1 rule (3 true factors, factor
    correlation 0.30, 50 reps per cell) — the errors point in **opposite**
    directions, which is the reason to prefer this one:

    ==========================  =========================  =========================
    design                      Kaiser                     parallel analysis
    ==========================  =========================  =========================
    load .65, p=15, n=300       3.00 exact 100%            3.00 exact 100%
    load .45, p=15, n=300       4.18 over-extracts 94%     3.00 exact 100%
    load .45, p=12, n=200       4.02 over-extracts 86%     2.58 exact 66%
    load .35, p=12, n=200       4.92 over-extracts 100%    1.98 exact 18%
    load .45, p=24, n=300 (k=4) 7.26 over-extracts 100%    3.98 exact 98%
    pure noise, p=20, n=300     10 factors                 0 factors
    ==========================  =========================  =========================

    Kaiser never under-extracts and is wrong upward in every cell but the
    strongest; parallel analysis never over-extracts in any cell and errs
    downward when the true loadings are weak (0.35 loadings on 200 rows are
    genuinely near the noise floor — under-extraction there is the honest
    answer, not a defect). Both agree when the structure is strong, which is the
    case where the choice does not matter.

    This is a **candidate count**, not a verdict: confirm it against the residual
    matrix (`factor_structure_report`) and against what the columns mean.
    """
    A = _as_matrix(X)
    n, p_raw = A.shape
    R, keep, dropped = correlation_matrix(A)
    p = R.shape[0]
    if p < 2 or n < 3:
        return {"verdict": "insufficient_data", "n_rows": int(n), "n_columns": int(p)}
    obs = np.sort(np.linalg.eigvalsh(R))[::-1]
    rng = np.random.default_rng(random_state)
    sim = np.empty((n_iter, p))
    for i in range(n_iter):
        sim[i] = np.sort(np.linalg.eigvalsh(np.corrcoef(
            rng.standard_normal((n, p)), rowvar=False)))[::-1]
    thr = np.percentile(sim, percentile, axis=0)
    keep_n = 0
    for a, b in zip(obs, thr):
        if a > b:
            keep_n += 1
        else:
            break
    return {
        "n_rows": int(n), "n_columns": int(p),
        "dropped_constant_columns": dropped.tolist(),
        "n_factors": int(keep_n),
        "kaiser_count": int(np.sum(obs > 1.0)),
        "observed_eigenvalues": np.round(obs, 6).tolist(),
        "random_threshold": np.round(thr, 6).tolist(),
        "percentile": float(percentile), "n_iter": int(n_iter),
        "verdict": ("no_structure_beyond_noise" if keep_n == 0
                    else "single_dimension" if keep_n == 1
                    else "multiple_dimensions"),
        "note": (f"kaiser would keep {int(np.sum(obs > 1.0))}; where they differ, "
                 "kaiser is the one that over-extracts"),
    }


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #
def principal_axis_factoring(R, n_factors: int, max_iter: int = 200,
                             tol: float = 1e-6) -> dict:
    """Common-factor extraction with iterated communalities. Heywood cases are reported, never hidden.

    Starts from squared multiple correlations on the diagonal, re-extracts, and
    repeats until the communalities stop moving. Unlike PCA it does **not** put
    1.0 on the diagonal, so it does not credit each column's measurement error to
    the factor.

    A **Heywood case** is a communality that reaches or exceeds 1.0 — the column
    would need more than all of its variance explained, which implies a negative
    uniqueness. It is an improper solution, not a rounding artefact, and it is a
    signal about the *model*, not about that one column: too few indicators, too
    few rows, a misspecified factor count, or an outlier. Measured frequency
    (2 factors, loading 0.70, factor correlation 0.30, 200 reps per cell):

    ================  ======  ======  ======  ======
    indicators/factor n=50    n=100   n=300   n=1000
    ================  ======  ======  ======  ======
    2                 0.240   0.170   0.035   0.000
    3                 0.085   0.005   0.000   0.000
    4                 0.005   0.000   0.000   0.000
    6                 0.000   0.000   0.000   0.000
    ================  ======  ======  ======  ======

    Three indicators per factor is the point where the problem mostly stops; two
    is a design that fails a quarter of the time on 50 rows (26.3% measured at
    n=60 over 300 reps). Two indicators per factor is also *empirically*
    under-identified — the factor correlation is the only thing holding it
    together, and improper solutions rose from 0.010 to 0.070 as that correlation
    fell from 0.60 to 0.05.

    **Do not repair a Heywood case by clipping the communality to 1.0.** That
    silences the warning without changing what caused it, and biases the other
    loadings. Add indicators, add rows, or extract fewer factors.

    Returns ``loadings`` (p x n_factors, unrotated), ``communalities``,
    ``uniquenesses``, ``heywood`` and the per-column ``heywood_columns``.
    """
    R = np.asarray(R, dtype=float)
    p = R.shape[0]
    if R.shape[0] != R.shape[1]:
        raise ValueError("R must be a square correlation matrix")
    if not (1 <= n_factors < p):
        raise ValueError(f"n_factors must be in [1, {p - 1}], got {n_factors}")

    try:
        smc = 1.0 - 1.0 / np.diag(np.linalg.inv(R))
    except np.linalg.LinAlgError:                     # singular: fall back
        smc = 1.0 - 1.0 / np.diag(np.linalg.pinv(R))
    h2 = np.clip(smc, 0.05, 0.99)

    L = np.zeros((p, n_factors))
    converged = False
    for _ in range(max_iter):
        Rr = R.copy()
        np.fill_diagonal(Rr, h2)
        w, V = np.linalg.eigh(Rr)
        idx = np.argsort(w)[::-1][:n_factors]
        L = V[:, idx] * np.sqrt(np.clip(w[idx], 0.0, None))
        h2_new = np.sum(L ** 2, axis=1)
        if np.max(np.abs(h2_new - h2)) < tol:
            h2 = h2_new
            converged = True
            break
        h2 = h2_new

    heywood_cols = np.flatnonzero(h2 >= 1.0)
    return {
        "n_factors": int(n_factors),
        "loadings": L,
        "communalities": np.round(h2, 6).tolist(),
        "uniquenesses": np.round(1.0 - h2, 6).tolist(),
        "converged": bool(converged),
        "heywood": bool(heywood_cols.size),
        "heywood_columns": heywood_cols.tolist(),
        "verdict": ("improper_solution_heywood" if heywood_cols.size
                    else "proper" if converged else "did_not_converge"),
    }


# --------------------------------------------------------------------------- #
# rotation
# --------------------------------------------------------------------------- #
def varimax(loadings, gamma: float = 1.0, max_iter: int = 200, tol: float = 1e-8):
    """Orthogonal rotation maximizing the variance of squared loadings.

    Rotation is a change of basis, not a change of model: it leaves the
    communalities and the reproduced correlation matrix **exactly** where they
    were (measured max abs difference 6.7e-16 and 7.8e-16) while moving the
    loadings themselves a great deal (max abs difference 1.03 on the same data).
    Nothing is gained or lost in fit — only readability. That also means a
    rotation cannot be "wrong" in the way an estimate can be; it can only be
    less interpretable, or dishonestly chosen.

    Varimax keeps the factors at 90 degrees, whose cosine is 0, so it **imposes**
    an uncorrelated-factor answer rather than finding one. See `promax` for what
    that costs when the factors really do correlate.

    Returns ``(rotated_loadings, rotation_matrix)``.
    """
    L = np.asarray(loadings, dtype=float)
    p, k = L.shape
    Rm = np.eye(k)
    if k < 2:
        return L.copy(), Rm
    d = 0.0
    for _ in range(max_iter):
        d_old = d
        Lam = L @ Rm
        u, s, vh = np.linalg.svd(
            L.T @ (Lam ** 3 - (gamma / p) * Lam @ np.diag(np.diag(Lam.T @ Lam))))
        Rm = u @ vh
        d = float(np.sum(s))
        if d_old != 0 and d / d_old < 1 + tol:
            break
    return L @ Rm, Rm


def promax(loadings, k: int = 4):
    """Oblique rotation (varimax, then relax the right angle). The sane default.

    Orthogonal rotation forces the factor correlation to zero and pays for it in
    the loadings, because the relation between the factors has to go *somewhere*.
    Measured on a clean 2-factor design (5 pure indicators each, loading 0.70,
    n=500, 60 reps, factor columns aligned to truth before scoring):

    ==========  ===========================  ===========================
    true r      varimax salient / cross      promax salient / cross
    ==========  ===========================  ===========================
    0.0         0.701 / 0.029                0.701 / 0.026
    0.2         0.698 / 0.066                0.702 / 0.025
    0.4         0.684 / 0.138                0.698 / 0.028
    0.6         0.666 / 0.221                0.696 / 0.037
    0.8         0.625 / 0.312                0.665 / 0.064
    ==========  ===========================  ===========================

    Every one of those cross-loadings is **manufactured**: the items are pure by
    construction. At a true factor correlation of 0.8, varimax reports items
    loading 0.31 on a factor they have nothing to do with — which reads as
    "these columns are double-barrelled" and is entirely an artefact of the right
    angle. Promax keeps them near zero and reports the correlation instead,
    recovering |r| = 0.035 / 0.194 / 0.379 / 0.585 / 0.748 against a truth of
    0.0 / 0.2 / 0.4 / 0.6 / 0.8 (slight shrinkage, 80 reps).

    The first row is the argument for making oblique the default: when the
    factors really are uncorrelated, promax costs nothing (0.026 vs 0.029) and
    reports r = 0.035. An orthogonal rotation cannot return the oblique answer,
    but an oblique rotation can return the orthogonal one.

    Returns ``(pattern, phi)`` — pattern coefficients (each column's relation to
    a factor *controlling for* the other factors, exactly like a partial
    regression coefficient) and the factor correlation matrix.
    """
    Lv, _ = varimax(loadings)
    m = Lv.shape[1]
    if m < 2:
        return Lv, np.eye(m)
    target = np.sign(Lv) * np.abs(Lv) ** k
    W = np.linalg.inv(Lv.T @ Lv) @ Lv.T @ target
    d = np.diag(np.linalg.inv(W.T @ W))
    W = W @ np.diag(np.sqrt(d))
    Wi = np.linalg.inv(W)
    return Lv @ W, Wi @ Wi.T


def rotate_loadings(loadings, method: str = "promax") -> dict:
    """Rotate and report, with the invariance check attached.

    ``method`` is ``promax`` (oblique, default) or ``varimax`` (orthogonal).
    ``fit_preserved_max_diff`` re-derives the reproduced correlation matrix from
    the rotated solution and compares it to the unrotated one; it must be ~0.
    """
    L = np.asarray(loadings, dtype=float)
    method = method.lower()
    if method == "varimax":
        P, _ = varimax(L)
        phi = np.eye(L.shape[1])
    elif method == "promax":
        P, phi = promax(L)
    else:
        raise ValueError("method must be 'promax' or 'varimax'")
    diff = float(np.max(np.abs(L @ L.T - P @ phi @ P.T)))
    return {
        "method": method,
        "pattern": P,
        "phi": phi,
        "communalities": np.round(np.sum(L ** 2, axis=1), 6).tolist(),
        "factor_correlations": np.round(phi[np.triu_indices_from(phi, 1)], 4).tolist(),
        "fit_preserved_max_diff": diff,
        "verdict": "fit_preserved" if diff < 1e-8 else "rotation_changed_fit_BUG",
    }


# --------------------------------------------------------------------------- #
# the orchestrator
# --------------------------------------------------------------------------- #
def factor_structure_report(X, n_factors: Optional[int] = None,
                            rotation: str = "promax", salient: float = 0.40,
                            n_iter: int = 100, random_state: int = 42) -> dict:
    """Full pass: how many factors, what loads where, and what the solution still misses.

    Answers the question that follows a redundancy block: are these columns
    indicators of a smaller number of underlying things, and if so which?

    ``n_factors=None`` takes the count from `parallel_analysis`.

    The output that decides whether to believe any of it is
    ``rms_residual_correlation`` — the RMS of the off-diagonal difference between
    the observed correlations and the ones the factor solution reproduces.
    **Variance explained is not that check.** A pure causal chain
    x1 -> x2 -> ... -> x6 (no common cause anywhere in it) produces a first
    component holding 47.3% / 68.0% / 82.9% of the variance at path
    coefficients 0.6 / 0.8 / 0.9 — numbers any scree or variance-explained read
    would call unidimensional. The residual matrix is what separates it from a
    genuine one-factor dataset at the same first-component share:

    ===================  ==========================  ==========================
    path coefficient     chain, 1-factor RMS resid   true 1-factor, same PC1
    ===================  ==========================  ==========================
    0.6 (PC1 47.3%)      0.1612                      0.0052
    0.8 (PC1 68.0%)      0.1301                      0.0030
    0.9 (PC1 82.9%)      0.0773                      0.0015
    ===================  ==========================  ==========================

    A 25-50x gap. So a large first eigenvalue is *not* evidence of a common
    cause; a small residual matrix is evidence that the factor model reproduces
    the correlations, and even that does not establish the mechanism — it rules
    out one alternative, no more.

    **Where the cutoff runs out**: the 0.08 convention used by ``verdict`` flags
    the 0.6 and 0.8 chains but *not* the 0.9 one (0.0773 sits just under it), so
    the verdict alone reads ``clean_simple_structure`` there. The 50x gap against
    genuine one-factor data is still there, but it is a comparison, not a
    threshold. Read the number, not only the verdict.

    ``orphan_columns`` are columns whose communality falls below
    ``orphan_threshold`` (0.20): they belong to none of the extracted factors. An
    injected pure-noise column landed at communality 0.0129 against a median of
    0.4772 for real indicators. An orphan is a finding, not a defect — it is
    usually either a column measuring something the others do not, or one that
    measures nothing. Do not average it into a scale either way.

    ``complex_columns`` load >= ``salient`` on more than one factor: candidates
    for a column that mixes two things. Check the rotation first — under an
    orthogonal rotation a chunk of those are manufactured (see `promax`).
    """
    A = _as_matrix(X)
    names = _names(X, A.shape[1])
    R, keep, dropped = correlation_matrix(A)
    p = R.shape[0]
    kept_names = [names[i] for i in keep]
    n = A.shape[0]
    if p < 3:
        return {"verdict": "insufficient_columns", "n_columns": int(p)}

    pa = parallel_analysis(A, n_iter=n_iter, random_state=random_state)
    if n_factors is None:
        n_factors = pa.get("n_factors", 0)
        source = "parallel_analysis"
    else:
        source = "user"
    if n_factors < 1:
        return {"n_rows": int(n), "n_columns": int(p), "n_factors": 0,
                "n_factors_source": source, "parallel_analysis": pa,
                "verdict": "no_common_factor_supported",
                "note": "no dimension beat random data of this shape; "
                        "do not build a scale from these columns"}
    if n_factors >= p:
        return {"verdict": "n_factors_must_be_below_n_columns",
                "n_columns": int(p), "n_factors": int(n_factors)}

    ext = principal_axis_factoring(R, n_factors)
    rot = rotate_loadings(ext["loadings"], method=rotation)
    P, phi = rot["pattern"], rot["phi"]
    h2 = np.asarray(ext["communalities"], dtype=float)

    reproduced = P @ phi @ P.T
    off = ~np.eye(p, dtype=bool)
    resid = R - reproduced
    rms = float(np.sqrt(np.mean(resid[off] ** 2)))
    max_resid = float(np.max(np.abs(resid[off])))

    ORPHAN = 0.20
    orphans = [kept_names[i] for i in range(p) if h2[i] < ORPHAN]
    complexity = np.sum(np.abs(P) >= salient, axis=1)
    complex_cols = [kept_names[i] for i in range(p) if complexity[i] > 1]
    silent = [kept_names[i] for i in range(p) if complexity[i] == 0]

    assign: dict[str, list[str]] = {f"factor_{j + 1}": [] for j in range(n_factors)}
    for i in range(p):
        j = int(np.argmax(np.abs(P[i])))
        if abs(P[i, j]) >= salient:
            assign[f"factor_{j + 1}"].append(kept_names[i])

    if ext["heywood"]:
        verdict = "improper_solution_heywood"
    elif rms > 0.08:
        verdict = "factor_model_does_not_reproduce_correlations"
    elif orphans or complex_cols:
        verdict = "structure_found_with_exceptions"
    else:
        verdict = "clean_simple_structure"

    return {
        "n_rows": int(n), "n_columns": int(p),
        "columns": kept_names,
        "dropped_constant_columns": [names[i] for i in dropped],
        "n_factors": int(n_factors), "n_factors_source": source,
        "kaiser_count": pa.get("kaiser_count"),
        "parallel_analysis_n_factors": pa.get("n_factors"),
        "rotation": rotation,
        "pattern": np.round(P, 4).tolist(),
        "factor_correlations": rot["factor_correlations"],
        "communalities": dict(zip(kept_names, np.round(h2, 4).tolist())),
        "assignment": assign,
        "orphan_columns": orphans,
        "complex_columns": complex_cols,
        "unassigned_columns": silent,
        "rms_residual_correlation": round(rms, 6),
        "max_residual_correlation": round(max_resid, 6),
        "heywood": ext["heywood"],
        "heywood_columns": [kept_names[i] for i in ext["heywood_columns"]],
        "fit_preserved_max_diff": rot["fit_preserved_max_diff"],
        "verdict": verdict,
        "note": ("rms_residual_correlation, not variance explained, is the check "
                 "that the factor model reproduces the observed correlations"),
    }


# --------------------------------------------------------------------------- #
# the PCA/FA comparison itself
# --------------------------------------------------------------------------- #
def pca_vs_fa(X, n_factors: int = 1) -> dict:
    """Side-by-side loadings from a component model and a common-factor model.

    PCA puts 1.0 on the diagonal, i.e. assumes every column is measured without
    error, so it credits each column's uniqueness to the component and returns
    **inflated** loadings. Measured on a one-factor design, 9 indicators, n=500,
    60 reps — mean |loading|:

    ============  =======  =======  ==========
    true loading  PCA      PAF      inflation
    ============  =======  =======  ==========
    0.90          0.9118   0.9002   +0.0116
    0.80          0.8236   0.7989   +0.0248
    0.70          0.7382   0.6987   +0.0395
    0.60          0.6555   0.5988   +0.0567
    0.50          0.5758   0.4984   +0.0774
    0.40          0.5023   0.4000   +0.1022
    ============  =======  =======  ==========

    and it gets worse as the block gets smaller — at a fixed true loading of
    0.60, inflation ran +0.1602 / +0.0985 / +0.0562 / +0.0343 / +0.0208 for
    p = 3 / 5 / 9 / 15 / 25 columns. Three noisy indicators is exactly where
    people reach for PCA, and it is the worst case.

    **But the practical scope of this is narrower than it looks.** If what you
    want is a *score* rather than an interpretation of the loadings, the two
    models are interchangeable: factor scores and component scores correlated
    0.9994-0.99997 across every design tested, and both tracked the true latent
    variable equally well (e.g. 0.9362 vs 0.9365 at loading 0.8 with 4
    indicators; 0.6532 vs 0.6588 at loading 0.4). The unit-weighted **mean of the
    z-scored columns** matched them both (0.9366 / 0.6597) — the elaborate
    machinery bought nothing over an average.

    Where weighting does pay is unequal indicators. With loadings
    0.8/0.7/0.6/0.5/0.4/0.3 plus two junk columns at 0.05, correlation with the
    true factor was **0.8915** (factor score) vs 0.8763 (PCA) vs **0.8124**
    (plain mean) — about 8 points, all of it from not letting the junk columns
    vote.

    So: use the common-factor model when you will *interpret* the loadings or
    argue about dimensionality; use PCA when you want compression or
    decorrelation and never intend to call a component a construct; and check
    the plain mean before assuming either is worth the complexity.
    """
    R, keep, dropped = correlation_matrix(X)
    p = R.shape[0]
    if p < 2 or n_factors >= p:
        return {"verdict": "insufficient_columns", "n_columns": int(p)}

    w, V = np.linalg.eigh(R)
    idx = np.argsort(w)[::-1][:n_factors]
    L_pca = V[:, idx] * np.sqrt(np.clip(w[idx], 0.0, None))
    fa = principal_axis_factoring(R, n_factors)
    L_fa = fa["loadings"]

    m_pca = float(np.mean(np.abs(L_pca)))
    m_fa = float(np.mean(np.abs(L_fa)))
    h2_pca = np.sum(L_pca ** 2, axis=1)
    h2_fa = np.asarray(fa["communalities"], dtype=float)

    infl = m_pca - m_fa
    return {
        "n_columns": int(p), "n_factors": int(n_factors),
        "pca_loadings": np.round(L_pca, 4).tolist(),
        "fa_loadings": np.round(L_fa, 4).tolist(),
        "mean_abs_loading_pca": round(m_pca, 4),
        "mean_abs_loading_fa": round(m_fa, 4),
        "loading_inflation": round(infl, 4),
        "mean_communality_pca": round(float(np.mean(h2_pca)), 4),
        "mean_communality_fa": round(float(np.mean(h2_fa)), 4),
        "heywood": fa["heywood"],
        "verdict": ("interchangeable_here" if infl < 0.03
                    else "pca_inflates_loadings" if infl < 0.08
                    else "pca_substantially_inflates_loadings"),
        "note": ("inflation grows as communalities fall and as the block gets "
                 "smaller; it affects loadings you interpret, not scores you compute"),
    }
