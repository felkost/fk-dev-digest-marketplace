"""Association measures with the right test for each variable-type pair
(discover step 1).

Includes linear/monotonic correlations, chi-square/Cramer's V with a per-cell
Quetelet decomposition (which cells drive the association, and in which
direction), a tabular-regression summary with the correlation ratio,
a numpy distance-correlation (no ``dcor`` dependency), mutual information
with a permutation null, and Benjamini-Hochberg FDR. Report effect size and
uncertainty, not only a p-value; association is not causation.

Core-library only (numpy, pandas, scipy, scikit-learn).
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import pdist, squareform


def benjamini_hochberg(pvalues) -> np.ndarray:
    """Return BH-adjusted q-values for a family of p-values."""
    p = np.asarray(pvalues, dtype=float)
    n = p.size
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(q, 0, 1)
    return out


def cramers_v(x, y) -> float:
    """Bias-corrected Cramer's V for two categorical vectors."""
    tab = pd.crosstab(pd.Series(x), pd.Series(y))
    if tab.size == 0 or min(tab.shape) < 2:
        return 0.0
    chi2 = stats.chi2_contingency(tab, correction=False)[0]
    n = tab.to_numpy().sum()
    r, k = tab.shape
    phi2 = chi2 / n
    phi2corr = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    rcorr = r - (r - 1) ** 2 / (n - 1)
    kcorr = k - (k - 1) ** 2 / (n - 1)
    denom = min(kcorr - 1, rcorr - 1)
    return float(np.sqrt(phi2corr / denom)) if denom > 0 else 0.0


def correlation_ratio(categories, values) -> float:
    """Eta: strength of a categorical -> numeric relationship (0..1)."""
    cats = pd.Series(categories)
    vals = pd.Series(values, dtype=float)
    ok = cats.notna() & vals.notna()
    cats, vals = cats[ok], vals[ok]
    if vals.size == 0:
        return 0.0
    grand = vals.mean()
    ss_between = sum(len(g) * (g.mean() - grand) ** 2 for _, g in vals.groupby(cats.values))
    ss_total = ((vals - grand) ** 2).sum()
    return float(np.sqrt(ss_between / ss_total)) if ss_total > 0 else 0.0


def quetelet_table(x, y) -> dict:
    """Per-cell decomposition of a contingency table via Quetelet indices.

    ``q(l/k) = P(l|k)/P(l) - 1`` is the relative change in the probability of
    category ``l`` once ``k`` is known (symmetric: q(l/k) == q(k/l)).
    Chi-square is the Quetelet-weighted average: ``chi2/N = sum p_kl * q_kl``
    (Pearson's phi^2), so a scalar chi-square/Cramer's V says *whether* the
    features are related while this table says *which* cells drive it and in
    which direction. Cells whose |contribution| exceeds twice the mean deviate
    strongly and are flagged in ``highlight``.

    Caveat: the lift is relative to the *whole-table* base rate. If the
    meaningful comparison population is different (e.g. convicted rather than
    the general population in the stop-and-search debate), the sign of the
    conclusion can flip -- state the reference population explicitly.
    """
    tab = pd.crosstab(pd.Series(x, name="row"), pd.Series(y, name="col"))
    n = tab.to_numpy().sum()
    p = tab / n
    pr = p.sum(axis=1).to_numpy()[:, None]  # row marginals
    pc = p.sum(axis=0).to_numpy()[None, :]  # column marginals
    expected = pr * pc  # outer product of marginals: p_k+ * p_+l
    with np.errstate(divide="ignore", invalid="ignore"):
        q = p.to_numpy() / expected - 1.0
    q = np.where(np.isfinite(q), q, 0.0)
    contrib = p.to_numpy() * q                      # sums to chi2 / N
    resid = (p.to_numpy() - expected) / np.sqrt(expected)  # signed Pearson residuals
    phi2 = float(contrib.sum())
    mean_abs = np.abs(contrib).mean()
    frame = lambda m: pd.DataFrame(m, index=tab.index, columns=tab.columns)
    return {
        "counts": tab,
        "quetelet": frame(np.round(q, 4)),
        "contribution": frame(np.round(contrib, 6)),
        "pearson_residuals": frame(np.round(resid, 4)),
        "highlight": frame(np.abs(contrib) > 2 * mean_abs),
        "chi2": round(phi2 * n, 4),
        "phi2": round(phi2, 6),
        "mean_relative_lift": round(phi2, 6),
        "cramers_v": round(cramers_v(x, y), 4),
        "n": int(n),
    }


def tabular_regression(categories, values) -> pd.DataFrame:
    """Piecewise-constant ('tabular') regression of a numeric on a nominal.

    One row per category with ``n``, within-category ``mean`` (the least-squares
    prediction) and ``std`` (its error), plus an ``(all)`` marginal row -- the
    prediction quality without knowing the category. ``eta_squared`` in
    ``attrs`` is the explained-variance share (ANOVA decomposition); it is
    asymmetric: eta(y|x) != eta(x|y). Within-group *means* do not affect eta --
    only the variance reduction does.
    """
    cats = pd.Series(categories).reset_index(drop=True)
    vals = pd.Series(values, dtype=float).reset_index(drop=True)
    ok = cats.notna() & vals.notna()
    cats, vals = cats[ok], vals[ok]
    rows = []
    for level, g in vals.groupby(cats.values):
        rows.append({"category": level, "n": int(g.size),
                     "mean": round(float(g.mean()), 4),
                     "std": round(float(g.std(ddof=1)) if g.size > 1 else 0.0, 4)})
    rows.append({"category": "(all)", "n": int(vals.size),
                 "mean": round(float(vals.mean()), 4),
                 "std": round(float(vals.std(ddof=1)) if vals.size > 1 else 0.0, 4)})
    out = pd.DataFrame(rows).set_index("category")
    eta = correlation_ratio(cats, vals)
    out.attrs["eta"] = float(eta)
    out.attrs["eta_squared"] = float(eta ** 2)
    return out


def distance_correlation(x, y) -> float:
    """Distance correlation (detects nonlinear/nonmonotonic dependence), 0..1."""
    x = np.asarray(x, dtype=float).reshape(-1, 1)
    y = np.asarray(y, dtype=float).reshape(-1, 1)
    a = squareform(pdist(x))
    b = squareform(pdist(y))
    A = a - a.mean(0) - a.mean(1)[:, None] + a.mean()
    B = b - b.mean(0) - b.mean(1)[:, None] + b.mean()
    dcov2 = (A * B).mean()
    dvarx, dvary = (A * A).mean(), (B * B).mean()
    denom = np.sqrt(dvarx * dvary)
    return float(np.sqrt(max(dcov2, 0) / denom)) if denom > 0 else 0.0


def mutual_information(x, y, y_discrete: Optional[bool] = None, random_state: int = 42) -> float:
    """MI between one feature ``x`` and ``y`` via scikit-learn estimators."""
    from sklearn.feature_selection import mutual_info_classif, mutual_info_regression

    x = np.asarray(x, dtype=float).reshape(-1, 1)
    y = np.asarray(y)
    if y_discrete is None:
        y_discrete = (y.dtype.kind in "iOSU") or (np.unique(y).size <= 20)
    if y_discrete:
        return float(mutual_info_classif(x, y, random_state=random_state)[0])
    return float(mutual_info_regression(x, y, random_state=random_state)[0])


def mi_permutation_pvalue(x, y, n_perm: int = 200, y_discrete: Optional[bool] = None,
                          random_state: int = 42) -> dict:
    """MI with a permutation null: returns observed MI, null mean, and p-value."""
    rng = np.random.default_rng(random_state)
    obs = mutual_information(x, y, y_discrete=y_discrete, random_state=random_state)
    y = np.asarray(y)
    null = np.array([
        mutual_information(x, rng.permutation(y), y_discrete=y_discrete, random_state=random_state)
        for _ in range(n_perm)
    ])
    p = float((1 + np.sum(null >= obs)) / (1 + n_perm))
    return {"mi": round(obs, 5), "null_mean": round(float(null.mean()), 5), "p_value": round(p, 4)}


def auto_association(df: pd.DataFrame, a: str, b: str) -> dict:
    """Pick a measure by the variable-type pair and return effect size + p."""
    sa, sb = df[a], df[b]
    num_a = pd.api.types.is_numeric_dtype(sa) and sa.nunique() > 2
    num_b = pd.api.types.is_numeric_dtype(sb) and sb.nunique() > 2
    ok = sa.notna() & sb.notna()
    sa, sb = sa[ok], sb[ok]

    if num_a and num_b:
        r, p = stats.spearmanr(sa, sb)
        pear, _ = stats.pearsonr(sa, sb)
        return {"measure": "spearman", "value": round(float(r), 4),
                "pearson": round(float(pear), 4), "p_value": float(p)}
    if num_a ^ num_b:
        cat, val = (sb, sa) if num_a else (sa, sb)
        return {"measure": "correlation_ratio(eta)", "value": round(correlation_ratio(cat, val), 4),
                "p_value": float(stats.kruskal(*[g.to_numpy() for _, g in val.groupby(cat.values)])[1])
                if cat.nunique() > 1 else np.nan}
    v = cramers_v(sa, sb)
    tab = pd.crosstab(sa, sb)
    p = stats.chi2_contingency(tab)[1] if min(tab.shape) > 1 else np.nan
    return {"measure": "cramers_v", "value": round(v, 4), "p_value": float(p)}


def leverage_diagnostics(df: pd.DataFrame, cols: Optional[Sequence[str]] = None,
                         top_n: int = 10) -> dict:
    """Design balance of the predictor matrix: hat values and their concentration.

    Leverage `h_ii` is row *i*'s diagonal of the hat matrix `X(X'X)^-1 X'`. It
    depends on **X only** -- no outcome is involved -- and measures how much
    room a single row has to pull a fitted surface toward itself. The average
    hat value is always `p/n`; the usual flag is `2p/n` or `3p/n`.

    **Why this and not a normality test on residuals.** Gauss-Markov never
    assumes normally distributed errors: least-squares estimates are unbiased
    and BLUE without it. Normality only enters when the *sampling distribution*
    is needed for an interval or a p-value, and even there the CLT usually
    rescues it. Measured 95% CI coverage over 6000 replicates:

    ======================  ======  ======  ======
    design / errors         n=10    n=30    n=200
    ======================  ======  ======  ======
    balanced x, normal      0.953   0.952   0.951
    balanced x, lognormal   0.947   0.947   0.954
    leveraged x, normal     0.950   0.950   0.950
    leveraged x, lognormal  0.925   0.940   0.959
    ======================  ======  ======  ======

    The coefficient was unbiased in every cell. Coverage only degraded where
    small `n`, a heavy-tailed `x` design and non-normal errors coincided --
    because a few high-leverage rows let individual errors dominate the
    estimator, so no averaging happens and the CLT never engages. That makes
    **leverage the diagnostic worth running**, and a residual normality test
    largely beside the point.

    Returns ``n``, ``p``, ``mean_leverage`` (= p/n), counts above the 2p/n and
    3p/n rules, ``max_leverage``, ``leverage_gini`` (concentration of design
    influence, 0 = perfectly balanced), the ``top`` rows, and ``clt_safe`` --
    False when the design is concentrated enough that interval coverage should
    be checked by bootstrap rather than assumed.

    **Leverage says who *could* move the estimate, never who *does*** -- which
    is exactly what "no outcome is involved" costs. A row can sit at seven times
    the leverage flag and move the fitted slope by 0.02 because its outcome
    happens to fall on the line. Use `influence_diagnostics` for the half of the
    question that needs `y`.
    """
    num = df[list(cols)] if cols is not None else df.select_dtypes(include=[np.number])
    X = num.dropna().to_numpy(dtype=float)
    n, p_raw = X.shape
    if n <= p_raw + 1:
        return {"n": int(n), "p": int(p_raw + 1), "verdict": "insufficient_rows"}
    X = np.column_stack([np.ones(n), X])          # intercept: leverage is defined for the design
    p = X.shape[1]
    try:
        H_diag = np.einsum("ij,jk,ik->i", X, np.linalg.pinv(X.T @ X), X)
    except np.linalg.LinAlgError:
        return {"n": int(n), "p": int(p), "verdict": "singular_design"}

    h = np.clip(H_diag, 0.0, 1.0)
    mean_h = p / n
    order = np.argsort(-h)[:top_n]
    srt = np.sort(h)
    gini = float((2 * np.arange(1, n + 1) - n - 1).dot(srt) / (n * srt.sum())) if srt.sum() > 0 else 0.0
    n_2p = int((h > 2 * mean_h).sum())

    return {
        "n": int(n), "p": int(p),
        "mean_leverage": round(float(mean_h), 6),
        "max_leverage": round(float(h.max()), 6),
        "n_above_2p_over_n": n_2p,
        "n_above_3p_over_n": int((h > 3 * mean_h).sum()),
        "leverage_gini": round(gini, 4),
        "top": [{"index": int(num.dropna().index[i]), "leverage": round(float(h[i]), 6)}
                for i in order],
        # a single row holding >20% of the design, or a very concentrated profile,
        # means the estimator is an average of too few things for the CLT to help
        "clt_safe": bool(h.max() < 0.2 and gini < 0.6),
        "verdict": "measured",
    }


def semipartial_correlations(df: pd.DataFrame, target: str,
                             predictors: Optional[Sequence[str]] = None,
                             dropna: bool = True) -> pd.DataFrame:
    """Per-predictor share of the outcome: raw slope, standardized slope, sr2, pr2.

    A coefficient table reports the *same* unique effect on four scales. For
    predictor `j`, all four rest on the part of `x_j` left after the other
    predictors are projected out:

    ==========  =============================================================
    ``b``       rise over run in raw units
    ``b_star``  rise over run in SD units
    ``sr2``     unique share of the **total** variance of the target
    ``pr2``     unique share of the target variance **left unexplained** by
                the other predictors
    ==========  =============================================================

    They are rescalings of one quantity, so they cannot disagree about
    significance -- measured on a two-predictor design, the t from ``b``, the t
    from ``b_star`` and ``sqrt(F)`` built from ``sr2`` were all 30.420713.

    **``sr2`` is the increment in R-squared** when the predictor is added last;
    ``pr2`` divides that same increment by ``1 - R2_without``. Verified against
    both definitions: increment 0.096826 vs ``corr(y, e_xj)**2`` 0.096826, and
    0.129630 vs ``corr(e_y, e_xj)**2`` 0.129630. Hence ``pr2 >= sr2`` always --
    over 100 random designs the ratio ranged 1.0000 to 1.6262, reaching exactly
    1 when the other predictors explain nothing, since the two denominators
    then coincide. Prefer ``sr2`` for reporting: "x_j uniquely accounts for 6%
    of the variance in y" is a statement about the outcome the reader cares
    about, whereas ``pr2`` is a share of a residual that changes whenever the
    predictor set changes.

    **Two sanity anchors, both measured.** With a single predictor ``b_star``
    equals Pearson r exactly, in either direction (0.550031 for x->y, y->x and
    r alike) though the raw slopes differ (0.672714 vs 0.449721). With exactly
    uncorrelated predictors the multiple-regression slopes equal the simple
    ones, so nothing is gained by the joint fit.

    **Do not residualize the outcome instead of the predictor.** The standard
    semipartial correlates `y` with `x_j` purged of the others. Purging the
    others out of `y` and correlating with raw `x_j` is a different number:
    on one design the three shared an identical covariance (0.251731) while
    the denominators ``sd(y)*sd(e_xj)``, ``sd(x_j)*sd(e_y)`` and
    ``sd(e_y)*sd(e_xj)`` gave 0.286242, 0.237252 and 0.335046. Only the first
    squares to the R-squared increment.

    Association only: a large ``sr2`` says the column carries information the
    others do not, never that it acts on the target. See
    ``references/associations.md`` on when conditioning on a column destroys
    the effect you meant to measure.
    """
    cols = list(predictors) if predictors is not None else [
        c for c in df.select_dtypes(include=[np.number]).columns if c != target]
    if not cols:
        return pd.DataFrame(columns=["feature", "b", "b_star", "sr", "sr2", "pr", "pr2",
                                     "r_zero_order"])

    work = df[[target] + cols]
    work = work.dropna() if dropna else work.fillna(work.mean(numeric_only=True))
    y = work[target].to_numpy(dtype=float)
    X = work[cols].to_numpy(dtype=float)
    n = len(y)
    if n <= len(cols) + 1:
        out = pd.DataFrame({"feature": cols})
        out.attrs["verdict"] = "insufficient_rows"
        return out

    def _r2(mat: np.ndarray) -> float:
        if mat.shape[1] == 0:
            return 0.0
        A = np.column_stack([np.ones(n), mat])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        resid = y - A @ coef
        ss_tot = ((y - y.mean()) ** 2).sum()
        return float(1 - (resid @ resid) / ss_tot) if ss_tot > 0 else np.nan

    A_full = np.column_stack([np.ones(n), X])
    coef_full, *_ = np.linalg.lstsq(A_full, y, rcond=None)
    r2_full = _r2(X)
    sd_y = y.std(ddof=1)

    rows = []
    for j, name in enumerate(cols):
        r2_drop = _r2(np.delete(X, j, axis=1))
        inc = max(r2_full - r2_drop, 0.0)
        denom = 1 - r2_drop
        pr2 = inc / denom if denom > 1e-12 else np.nan
        sign = np.sign(coef_full[j + 1]) or 1.0
        sd_j = X[:, j].std(ddof=1)
        rows.append({
            "feature": name,
            "b": round(float(coef_full[j + 1]), 6),
            "b_star": round(float(coef_full[j + 1] * sd_j / sd_y), 6) if sd_y > 0 else np.nan,
            "sr": round(float(sign * np.sqrt(inc)), 6),
            "sr2": round(float(inc), 6),
            "pr": round(float(sign * np.sqrt(pr2)), 6) if pr2 == pr2 else np.nan,
            "pr2": round(float(pr2), 6) if pr2 == pr2 else np.nan,
            "r_zero_order": round(float(np.corrcoef(X[:, j], y)[0, 1]), 6) if sd_j > 0 else np.nan,
        })

    out = pd.DataFrame(rows).sort_values("sr2", ascending=False).reset_index(drop=True)
    out.attrs["r2_full"] = round(float(r2_full), 6)
    out.attrs["sum_sr2"] = round(float(out["sr2"].sum()), 6)
    # shared variance: R2 minus the unique parts. Large => the predictors
    # overlap heavily and no single column owns the explained variance.
    out.attrs["shared_r2"] = round(float(r2_full - out["sr2"].sum()), 6)
    out.attrs["n"] = int(n)
    out.attrs["verdict"] = "measured"
    return out


def holm_bonferroni(pvalues) -> np.ndarray:
    """Return Holm-adjusted p-values (step-down FWER control).

    Uniformly at least as powerful as Bonferroni and valid under any dependence
    structure, so there is no reason to prefer plain Bonferroni. Use this when
    the claim is "*this particular pair* differs"; use ``benjamini_hochberg``
    when the claim is "*some* of these are worth following up" -- FWER and FDR
    answer different questions and the choice belongs to the analyst.
    """
    p = np.clip(np.asarray(pvalues, dtype=float), 0.0, 1.0)
    k = p.size
    order = np.argsort(p)
    adj = np.empty(k)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (k - rank) * p[idx])
        adj[idx] = min(running, 1.0)
    return adj


def pairwise_group_differences(categories, values, correction: str = "holm",
                               alpha: float = 0.05, min_group: int = 3) -> pd.DataFrame:
    """Which levels of a nominal actually differ on a numeric, with FWER control.

    The routine EDA question "does the target differ across the levels of this
    feature, and between which levels" is a *family* of ``g(g-1)/2`` tests, and
    the textbook recipe -- run a one-way ANOVA, then, if it is significant, run
    uncorrected pairwise t-tests (Fisher's LSD) -- does not control the
    familywise rate beyond three groups. Measured under a **complete** null
    (all groups identical, n=30 each, 20 000 replicates, alpha=0.05):

    ======  =====  ===========  ========  ======  ==========  ======
    groups  pairs  uncorrected  LSD       Holm    Bonferroni  BH
    ======  =====  ===========  ========  ======  ==========  ======
    3        3     0.1197       0.0481    0.0411  0.0411      0.0439
    4        6     0.2039       0.0507    0.0418  0.0418      0.0449
    5       10     0.2887       0.0489    0.0388  0.0388      0.0418
    6       15     0.3623       0.0500    0.0379  0.0379      0.0425
    8       28     0.5068       0.0478    0.0390  0.0390      0.0428
    ======  =====  ===========  ========  ======  ==========  ======

    Read that table and LSD looks fine -- it holds 0.05 at every ``g``. That is
    the trap: under the complete null the omnibus itself only fires 5% of the
    time, so the gate does all the work. Re-measured under a **partial** null
    (one group genuinely shifted by 3 sd, the rest identical; false positives
    counted only among the truly-equal pairs), the omnibus is significant in
    **100%** of replicates, the gate stops gating, and LSD lands exactly on the
    uncorrected rate:

    ======  ===========  ========  ======  ==========  ======
    groups  uncorrected  LSD       Holm    Bonferroni  BH
    ======  ===========  ========  ======  ==========  ======
    3       0.0488       0.0488    0.0488  0.0149      0.0488
    4       0.1224       0.1224    0.0444  0.0235      0.0863
    5       0.2036       0.2036    0.0401  0.0246      0.1150
    6       0.2843       0.2843    0.0406  0.0278      0.1363
    8       0.4374       0.4374    0.0381  0.0295      0.1752
    ======  ===========  ========  ======  ==========  ======

    Three things follow. (1) The partial null is the realistic EDA case -- you
    rarely screen a feature where *nothing* differs -- so LSD is protection
    that evaporates exactly when it is needed. It survives only at ``g=3``
    (0.0488), which is the classical result, and breaks from ``g=4`` on.
    (2) **BH does not control the familywise rate** (0.0863 -> 0.1752 as ``g``
    grows) and is not a drop-in substitute: it controls the false *discovery*
    rate, a different guarantee. Use it when the output is a shortlist to
    follow up, Holm when the claim is "*this* pair differs".
    (3) Holm holds ~0.04-0.05 in both regimes and is uniformly more powerful
    than Bonferroni, at no cost (g=4, n=30, detection of the truly-different
    pair): 0.2377 vs 0.2210 at delta=0.5, 0.6701 vs 0.6388 at 0.8, 0.8866 vs
    0.8637 at 1.0. Hence Holm is the default here.

    Welch's t is used unconditionally rather than after a variance pre-test:
    the pooled statistic is wrong in *both* directions under unequal variance
    with unequal group sizes, and the pre-test is itself a data-dependent
    choice (see ``associations.md``, "Do not choose a test by first testing its
    assumption").

    Returns one row per pair with ``n_a``/``n_b``, group means, ``diff``, a
    Welch confidence interval for the difference, Hedges' g, the raw and
    adjusted p, and ``significant``. ``attrs`` carries the omnibus (Welch
    ANOVA is not used; the classical F and its p are reported as context
    only), ``eta_squared``, ``n_pairs``, and ``fwer_uncorrected_upper_bound``
    = ``1-(1-alpha)**n_pairs`` -- an upper bound, since the pairs share
    groups and are therefore correlated.

    The output is a list of *candidates*. A pair that survives correction on
    the data that suggested it is a hypothesis, not a finding.
    """
    if correction not in ("holm", "fdr_bh", "bonferroni", "none"):
        raise ValueError("correction must be holm, fdr_bh, bonferroni or none")
    cats = pd.Series(categories).reset_index(drop=True)
    vals = pd.Series(values, dtype=float).reset_index(drop=True)
    ok = cats.notna() & vals.notna()
    cats, vals = cats[ok], vals[ok]

    groups, dropped = {}, []
    for level, g in vals.groupby(cats.values):
        if g.size >= min_group and float(g.std(ddof=1)) >= 0:
            groups[level] = g.to_numpy(dtype=float)
        else:
            dropped.append(level)
    levels = sorted(groups, key=lambda k: str(k))
    if len(levels) < 2:
        out = pd.DataFrame(columns=["group_a", "group_b", "n_a", "n_b", "mean_a",
                                    "mean_b", "diff", "ci_low", "ci_high",
                                    "hedges_g", "t", "p_raw", "p_adj",
                                    "significant"])
        out.attrs["verdict"] = "too_few_usable_groups"
        out.attrs["dropped_levels"] = dropped
        return out

    rows = []
    for i, a in enumerate(levels):
        for b in levels[i + 1:]:
            xa, xb = groups[a], groups[b]
            na, nb = xa.size, xb.size
            va, vb = xa.var(ddof=1), xb.var(ddof=1)
            se = np.sqrt(va / na + vb / nb)
            res = stats.ttest_ind(xa, xb, equal_var=False)
            # Welch-Satterthwaite df for the interval
            if se > 0:
                df = (va / na + vb / nb) ** 2 / (
                    (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
                half = stats.t.ppf(1 - alpha / 2, df) * se
            else:
                df, half = np.nan, np.nan
            diff = float(xa.mean() - xb.mean())
            # Hedges' g: pooled sd with the small-sample correction
            sp = np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
            d = diff / sp if sp > 0 else np.nan
            j = 1 - 3 / (4 * (na + nb) - 9) if na + nb > 3 else 1.0
            rows.append({
                "group_a": a, "group_b": b, "n_a": int(na), "n_b": int(nb),
                "mean_a": round(float(xa.mean()), 6),
                "mean_b": round(float(xb.mean()), 6),
                "diff": round(diff, 6),
                "ci_low": round(diff - half, 6) if np.isfinite(half) else np.nan,
                "ci_high": round(diff + half, 6) if np.isfinite(half) else np.nan,
                "hedges_g": round(float(d * j), 4) if np.isfinite(d) else np.nan,
                "t": round(float(res.statistic), 4),
                "p_raw": float(res.pvalue),
            })

    out = pd.DataFrame(rows)
    p = out["p_raw"].to_numpy()
    k = p.size
    if correction == "holm":
        adj = holm_bonferroni(p)
    elif correction == "fdr_bh":
        adj = benjamini_hochberg(p)
    elif correction == "bonferroni":
        adj = np.clip(p * k, 0, 1)
    else:
        adj = p.copy()
    out["p_adj"] = np.round(adj, 6)
    out["p_raw"] = np.round(p, 6)
    out["significant"] = adj < alpha
    out = out.sort_values("p_adj").reset_index(drop=True)

    f = stats.f_oneway(*[groups[l] for l in levels])
    eta = correlation_ratio(
        np.concatenate([[l] * groups[l].size for l in levels]).astype(object),
        np.concatenate([groups[l] for l in levels]))
    out.attrs["levels"] = levels
    out.attrs["dropped_levels"] = dropped
    out.attrs["n_pairs"] = int(k)
    out.attrs["correction"] = correction
    out.attrs["alpha"] = float(alpha)
    out.attrs["omnibus_f"] = round(float(f.statistic), 4)
    out.attrs["omnibus_p"] = round(float(f.pvalue), 6)
    out.attrs["eta_squared"] = round(float(eta ** 2), 6)
    out.attrs["fwer_uncorrected_upper_bound"] = round(1 - (1 - alpha) ** k, 4)
    out.attrs["verdict"] = ("candidates" if bool(out["significant"].any())
                            else "no_pair_survives_correction")
    out.attrs["note"] = ("Do not gate these on the omnibus: ANOVA-protected "
                         "uncorrected pairwise (Fisher's LSD) loses FWER "
                         "control as soon as any one group really differs.")
    return out


def range_restriction(r_observed: float, sd_selected: float, sd_reference: float) -> dict:
    """What would this correlation be if the sample were not pre-filtered?

    Selecting on a variable shrinks its variance, and a correlation shrinks with
    it — *without any change in the underlying relation*. This is why "SAT score
    does not predict college GPA" computed on admitted students, or "tenure does
    not predict performance" computed on people who were not fired, are usually
    arithmetic rather than findings.

    Thorndike Case II, for direct selection on `x` (``u = sd_selected /
    sd_reference``)::

        r_unrestricted = (r/u) / sqrt(1 + r^2/u^2 - r^2)

    Measured against a known truth of 0.50 on 200 000 rows, keeping only the top
    quantile of `x`: observed r fell to 0.3261 / 0.2695 / 0.2253 / **0.1959** at
    the top 50% / 25% / 10% / 5%, matching the forward formula to within 0.015;
    inverting it recovered 0.4944 and 0.4892 from the top-25% and top-10%
    samples. So the correction works, but treat it as a **sensitivity
    statement**, not a measurement: it assumes selection was on `x` alone, the
    relation is linear and homoscedastic, and `sd_reference` genuinely describes
    the population you want to talk about.

    ``sd_reference`` has to come from outside the filtered data — a published
    norm, an earlier unfiltered extract, the pre-filter table. If you do not
    have one, the honest output is "this r is a lower bound", which is what
    ``verdict`` says when ``u`` is not supplied credibly.

    Returns ``u``, ``r_unrestricted``, ``attenuation_factor`` and a verdict.
    """
    if not (0 < sd_selected) or not (0 < sd_reference):
        return {"verdict": "invalid_sd"}
    if not (-1 <= r_observed <= 1):
        return {"verdict": "invalid_r"}
    u = float(sd_selected) / float(sd_reference)
    if u >= 1.0:
        return {"u": round(u, 4), "r_unrestricted": round(float(r_observed), 4),
                "attenuation_factor": 1.0,
                "verdict": "no_restriction",
                "note": "selected spread is not below the reference; nothing to correct"}
    r = float(r_observed)
    denom = np.sqrt(1.0 + (r ** 2) / (u ** 2) - r ** 2)
    r_unres = (r / u) / denom if denom > 0 else np.nan
    r_unres = float(np.clip(r_unres, -1.0, 1.0))
    return {
        "u": round(u, 4),
        "r_observed": round(r, 4),
        "r_unrestricted": round(r_unres, 4),
        "attenuation_factor": round(r / r_unres, 4) if r_unres not in (0.0,) else np.nan,
        "verdict": "restricted",
        "note": ("Thorndike Case II, assumes direct selection on x, linearity and "
                 "homoscedasticity. A sensitivity estimate, not a measurement."),
    }


def influence_diagnostics(df: pd.DataFrame, target: str,
                          predictors: Optional[Sequence[str]] = None,
                          top_n: int = 10, dropna: bool = True) -> pd.DataFrame:
    """Which rows actually move the fit -- outlier, leverage and influence separated.

    `leverage_diagnostics` answers "who could?" from `X` alone. This answers
    "who does?", which needs the outcome. **Three different things wear the name
    "outlier"** and they come apart completely:

    ==============================  ===============================================
    ``outlier``                     a large studentized deleted residual: the row
                                    is far from the fitted surface
    ``leverage``                    a large hat value: the row sits far out in `X`
                                    and has room to pull the surface
    ``influence``                   a large Cook's D or DFFITS: removing the row
                                    actually changes the estimate
    ==============================  ===============================================

    Measured on one clean base (n=60, ``x ~ U(0,3)``, ``y = 2 + 1*x + N(0,1)``,
    clean slope 1.0979) with **exactly one planted point per dataset** -- flags
    at 2p/n = 0.0656, 4/n = 0.0656, 2*sqrt(p/n) = 0.3621, |r_del| > 3:

    =========================  ======  ========  =======  =======  =====  ===========
    planted point              h       stud.del  Cook D   DFFITS   shift  flags
    =========================  ======  ========  =======  =======  =====  ===========
    A x at the mean, y off +6  0.0166  +5.449    0.1685   +0.708   +0.013 out+infl
    B x=6, on the true line    0.3081  -0.183    0.0076   -0.122   +0.017 lev
    C x=6, y off -9            0.3081  -6.826    5.8510   -4.554   +0.623 all three
    =========================  ======  ========  =======  =======  =====  ===========

    Only C matters, and only C carries all three flags. Swept over 60 seeds of
    the same design, the separation is total: A's leverage stays in
    [0.0164, 0.0193], always *below* the flag; B's studentized deleted residual
    stays in [-1.16, +1.54], never near 3; C's Cook's D never falls below 3.76.

    **The thresholds are scale-free and do not know what is material.** A is
    flagged ``influence`` in 60 seeds out of 60 -- its Cook's D (0.126-0.265)
    and DFFITS (0.58-1.06) clear their conventional flags every time -- while
    the slope it actually moves has a 60-seed **median of -0.0007** against a
    coefficient of 1.10. It is a real outlier that changes nothing, because a
    point at the centre of `x` moves the intercept and not the slope. That is
    why ``slope_shift_if_top_dropped`` carries the actual refit: it is the only
    number here denominated in the units of the answer.

    **B is not reliably "clean" either, and the honest version says so:** with
    its outcome on the *true* line but not on the *fitted* one, 5x leverage
    amplifies a small residual enough to trip Cook's D in **27 of 60 seeds**.
    What holds across every seed is the pair of facts the trichotomy is about --
    B is a leverage point (h at 4-6x the flag) and B is not an outlier.

    **These are screening rules, not tests.** On perfectly clean normal data
    with no influential structure whatsoever, **8-13% of all rows are flagged**,
    and the share of datasets containing at least one flagged row is 0.9985 at
    n=30 and **1.0000 at every n from 50 to 1000** (p in {2,4,8}, 2000 reps).
    "My data has influential points" is the normal condition, not a finding.

    A briefed expectation died here: heavy-tailed errors were supposed to raise
    the flag rate, and **they do not**. Lognormal errors give 0.1190 of rows
    flagged at n=100/p=2 against 0.1203 for normal errors -- indistinguishable.
    The rules are studentized, so inflating the error spread inflates the
    estimated scale with it and the rate self-normalizes.

    **Masking, measured rather than assumed.** Duplicating point C (two copies
    at x-separation 0 to 2) drops the largest single-deletion Cook's D from
    5.8510 to 1.76-2.23 -- a real 3x dilution, since deleting either copy leaves
    the other holding the fit. But 1.76 is still **27x the 4/n flag**, so the
    points are not hidden; only the magnitude is. Meanwhile the damage doubles:
    the slope falls to 0.146 with two copies against 0.475 with one, from a
    clean 1.0979. So masking here costs accuracy in the *diagnostic*, not the
    detection -- which is the opposite of the usual warning, and is what this
    design actually produced.

    Returns one row per flagged observation (at most ``top_n``, ordered by
    Cook's D). ``.attrs`` carries the thresholds, per-flag counts, the full
    per-predictor DFBETAS frame, and the refit.
    """
    cols = list(predictors) if predictors is not None else [
        c for c in df.select_dtypes(include=[np.number]).columns if c != target]
    empty = pd.DataFrame(columns=["index", "leverage", "residual",
                                  "studentized_deleted_residual", "cooks_d",
                                  "dffits", "dfbetas_max", "dfbetas_argmax", "flags"])
    if not cols:
        empty.attrs["verdict"] = "no_predictors"
        return empty

    work = df[[target] + cols]
    work = work.dropna() if dropna else work.fillna(work.mean(numeric_only=True))
    y = work[target].to_numpy(dtype=float)
    n = len(y)
    X = np.column_stack([np.ones(n), work[cols].to_numpy(dtype=float)])
    p = X.shape[1]
    if n <= p + 2:
        empty.attrs["verdict"] = "insufficient_rows"
        empty.attrs["n"], empty.attrs["p"] = int(n), int(p)
        return empty

    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    h = np.clip(np.einsum("ij,jk,ik->i", X, XtX_inv, X), 0.0, 1.0 - 1e-12)
    dof = n - p
    s2 = float(e @ e) / dof
    if s2 <= 0:
        empty.attrs["verdict"] = "perfect_fit_no_residual_variance"
        return empty

    # every quantity below is closed-form from the one pinv above: no refit loop
    r_int = e / np.sqrt(s2 * (1.0 - h))
    s2_i = np.clip((dof * s2 - e ** 2 / (1.0 - h)) / (dof - 1), 1e-300, None)
    r_del = e / np.sqrt(s2_i * (1.0 - h))
    cooks = (r_int ** 2 / p) * (h / (1.0 - h))
    dffits = r_del * np.sqrt(h / (1.0 - h))
    # beta - beta_(i) = (X'X)^-1 x_i e_i / (1 - h_i), standardized by s_(i)
    delta = (XtX_inv @ X.T) * (e / (1.0 - h))
    dfbetas = delta / (np.sqrt(np.diag(XtX_inv))[:, None] * np.sqrt(s2_i)[None, :])

    thr_lev, thr_cook = 2.0 * p / n, 4.0 / n
    thr_dffits, thr_dfbetas = 2.0 * np.sqrt(p / n), 2.0 / np.sqrt(n)
    THR_RESID = 3.0                      # a screening cutoff, not a 5%-level test

    is_out = np.abs(r_del) > THR_RESID
    is_lev = h > thr_lev
    is_inf = (cooks > thr_cook) | (np.abs(dffits) > thr_dffits)

    coef_names = ["intercept"] + cols
    idx = work.index.to_numpy()
    abs_db = np.abs(dfbetas)
    db_argmax = np.argmax(abs_db, axis=0)

    rows = []
    for i in np.flatnonzero(is_out | is_lev | is_inf):
        flags = [nm for nm, on in (("outlier", is_out[i]), ("leverage", is_lev[i]),
                                   ("influence", is_inf[i])) if on]
        rows.append({
            "index": idx[i],
            "leverage": round(float(h[i]), 6),
            "residual": round(float(e[i]), 6),
            "studentized_deleted_residual": round(float(r_del[i]), 4),
            "cooks_d": round(float(cooks[i]), 6),
            "dffits": round(float(dffits[i]), 4),
            "dfbetas_max": round(float(abs_db[db_argmax[i], i]), 4),
            "dfbetas_argmax": coef_names[int(db_argmax[i])],
            "flags": "+".join(flags),
        })

    out = (pd.DataFrame(rows).sort_values("cooks_d", ascending=False)
           .head(top_n).reset_index(drop=True)) if rows else empty

    # the refit: what dropping the single most influential row actually costs
    top_i = int(np.argmax(cooks))
    keep = np.ones(n, dtype=bool)
    keep[top_i] = False
    beta_drop = np.linalg.pinv(X[keep].T @ X[keep]) @ X[keep].T @ y[keep]
    shifts = {nm: round(float(b1 - b0), 6)
              for nm, b0, b1 in zip(coef_names, beta, beta_drop)}

    out.attrs["n"], out.attrs["p"] = int(n), int(p)
    out.attrs["thresholds"] = {
        "leverage_2p_over_n": round(float(thr_lev), 6),
        "cooks_d_4_over_n": round(float(thr_cook), 6),
        "dffits_2_sqrt_p_over_n": round(float(thr_dffits), 6),
        "dfbetas_2_over_sqrt_n": round(float(thr_dfbetas), 6),
        "studentized_deleted_residual": THR_RESID,
    }
    out.attrs["n_outlier"] = int(is_out.sum())
    out.attrs["n_leverage"] = int(is_lev.sum())
    out.attrs["n_influence"] = int(is_inf.sum())
    out.attrs["n_flagged_total"] = int((is_out | is_lev | is_inf).sum())
    out.attrs["dfbetas"] = pd.DataFrame(dfbetas.T, columns=coef_names, index=idx).round(4)
    out.attrs["slope_shift_if_top_dropped"] = {
        "dropped_index": idx[top_i],
        "dropped_cooks_d": round(float(cooks[top_i]), 6),
        "coefficients": {nm: round(float(b), 6) for nm, b in zip(coef_names, beta)},
        "shifts": shifts,
        "max_abs_shift": round(float(max(abs(v) for v in shifts.values())), 6),
    }
    out.attrs["verdict"] = ("influential_rows_present" if bool(is_inf.any())
                            else "flagged_rows_are_not_influential" if rows
                            else "no_flagged_observations")
    out.attrs["note"] = ("conventional flags are scale-free and fire routinely on "
                         "clean data; slope_shift_if_top_dropped is the number "
                         "denominated in the units of the answer")
    return out


__all__ = [
    "benjamini_hochberg", "cramers_v", "correlation_ratio", "distance_correlation",
    "mutual_information", "mi_permutation_pvalue", "auto_association",
    "quetelet_table", "tabular_regression", "leverage_diagnostics",
    "influence_diagnostics",
    "semipartial_correlations", "range_restriction",
    "holm_bonferroni", "pairwise_group_differences",
]
