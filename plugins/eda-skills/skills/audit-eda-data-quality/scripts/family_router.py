"""Route a measured data signature to candidate distribution families (audit step 5).

The Leemis UDR chart holds 76 distributions chosen for *provable connectivity and
a planar layout*; its own FAQ lists ~140 more that did not fit. The omitted ones
are disproportionately the families that messy operational data actually follows
-- zero-inflated counts, compound Poisson-gamma spend, Poisson-binomial totals
from drifting rates, power-law token frequencies.

This module does not fit anything. It measures a signature, names the families
that signature is consistent with, and hands back the reason and a URL to read.
Naming a family is a **hypothesis with an attached verification step**, never a
conclusion: see `suggest_families` for the discipline that applies before any
candidate may be adopted.

Core-library only (numpy, pandas, scipy).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

# --------------------------------------------------------------------------- #
# Catalogue. Curated from the UDR FAQ's "not on the chart" list, indexed by the
# signature that should make you read it. Full list:
# www.math.wm.edu/~leemis/chart/UDR/UDR.html  (FAQ section)
# --------------------------------------------------------------------------- #

CATALOGUE: dict[str, dict] = {
    # ---- counts -----------------------------------------------------------
    "negative_binomial": {
        "url": "https://en.wikipedia.org/wiki/Negative_binomial_distribution",
        "note": "gamma-Poisson mixture; ON the chart as Pascal. Overdispersed counts.",
    },
    "conway_maxwell_poisson": {
        "url": "https://en.wikipedia.org/wiki/Conway-Maxwell-Poisson_distribution",
        "note": "one family covering under- AND overdispersion; the honest answer for VMR < 1.",
    },
    "zero_inflated_poisson": {
        "url": "https://en.wikipedia.org/wiki/Zero-inflated_model",
        "note": "structural zeros mixed with sampling zeros; ZINB if also overdispersed.",
    },
    "delaporte": {
        "url": "https://en.wikipedia.org/wiki/Delaporte_distribution",
        "note": "Poisson + negative-binomial convolution: a fixed base rate plus a varying part.",
    },
    "poisson_binomial": {
        "url": "https://en.wikipedia.org/wiki/Poisson_binomial_distribution",
        "note": "sum of Bernoulli trials with DIFFERING p -- what a binomial total becomes when the rate drifts.",
    },
    "skellam": {
        "url": "https://en.wikipedia.org/wiki/Skellam_distribution",
        "note": "difference of two Poisson counts; day-over-day deltas, count A/B tests.",
    },
    "yule_simon": {
        "url": "https://en.wikipedia.org/wiki/Yule-Simon_distribution",
        "note": "preferential attachment; power-law counts (citations, followers).",
    },
    "zipf_mandelbrot": {
        "url": "https://en.wikipedia.org/wiki/Zipf-Mandelbrot_law",
        "note": "token-frequency tails; fits real text better than plain Zipf, which matches only the head.",
    },
    "logarithmic_series": {
        "url": "http://en.wikipedia.org/wiki/Logarithmic_distribution",
        "note": "species/word abundance; the limit of the negative binomial conditioned on being positive.",
    },
    "borel": {
        "url": "https://en.wikipedia.org/wiki/Borel_distribution",
        "note": "branching-process / queue-busy-period totals.",
    },
    "beta_binomial": {
        "url": "https://en.wikipedia.org/wiki/Beta-binomial_distribution",
        "note": "overdispersed bounded counts (k of n); ON the chart. p varies across units.",
    },
    # ---- non-negative continuous with a zero mass -------------------------
    "tweedie": {
        "url": "https://en.wikipedia.org/wiki/Tweedie_distribution",
        "note": "the power-variance family Var = phi*mu^p; 1<p<2 is compound Poisson-gamma (zero mass + positive part).",
    },
    "compound_poisson": {
        "url": "https://en.wikipedia.org/wiki/Compound_Poisson_distribution",
        "note": "a random number of random-sized events: claims, spend, downtime.",
    },
    # ---- heavy tails ------------------------------------------------------
    "stable": {
        "url": "http://en.wikipedia.org/wiki/Stable_distribution",
        "note": "closed under convolution; the normal is its only finite-variance member, Cauchy is index 1. Generalized CLT limit.",
    },
    "generalized_pareto_evt": {
        "url": "https://en.wikipedia.org/wiki/Generalized_Pareto_distribution",
        "note": "peaks-over-threshold (Pickands, shape xi/scale sigma). NOT the chart's Generalized Pareto(delta,kappa,gamma) -- same name, different distribution.",
    },
    "generalized_extreme_value": {
        "url": "http://en.wikipedia.org/wiki/Generalized_extreme_value_distribution",
        "note": "block maxima (Fisher-Tippett); Frechet/Gumbel/Weibull tails in one family.",
    },
    "burr": {
        "url": "http://en.wikipedia.org/wiki/Burr_distribution",
        "note": "flexible Pareto-type body+tail; income, loss, duration.",
    },
    "dagum": {
        "url": "http://en.wikipedia.org/wiki/Dagum_distribution",
        "note": "income distributions; interior mode with a Pareto tail.",
    },
    "log_cauchy": {
        "url": "https://en.wikipedia.org/wiki/Log-Cauchy_distribution",
        "note": "super-heavy: tail heavier than any lognormal, all moments infinite.",
    },
    "levy": {
        "url": "https://en.wikipedia.org/wiki/Levy_distribution",
        "note": "stable with index 1/2; first-passage times.",
    },
    # ---- bounded on [0,1] -------------------------------------------------
    "kumaraswamy": {
        "url": "https://en.wikipedia.org/wiki/Kumaraswamy_distribution",
        "note": "beta-like on [0,1] with a closed-form CDF and quantile function.",
    },
    "logit_normal": {
        "url": "https://en.wikipedia.org/wiki/Logit-normal_distribution",
        "note": "normal after a logit transform; the natural model for a proportion feature.",
    },
    "beta_rectangular": {
        "url": "https://en.wikipedia.org/wiki/Beta_rectangular_distribution",
        "note": "beta plus a uniform component: heavier shoulders, robust elicitation.",
    },
    "balding_nichols": {
        "url": "https://en.wikipedia.org/wiki/Balding-Nichols_model",
        "note": "beta parameterized by mean and an overdispersion (F) parameter.",
    },
    # ---- bounded on [a,b], elicited ---------------------------------------
    "pert": {
        "url": "http://en.wikipedia.org/wiki/PERT_distribution",
        "note": "min/mode/max expert estimates; project durations.",
    },
    "metalog": {
        "url": "http://www.metalogs.org/",
        "note": "quantile-parameterized; fits a shape directly to elicited or empirical quantiles.",
    },
    "u_quadratic": {
        "url": "http://en.wikipedia.org/wiki/U-quadratic_distribution",
        "note": "bounded and bimodal at the edges -- a genuine U shape, not a mixture artefact.",
    },
    # ---- positive lifetimes / reliability ----------------------------------
    "exponentiated_weibull": {
        "url": "http://en.wikipedia.org/wiki/Exponentiated_Weibull_distribution",
        "note": "non-monotone (bathtub / unimodal) hazard, which plain Weibull cannot express.",
    },
    "phase_type": {
        "url": "https://en.wikipedia.org/wiki/Phase-type_distribution",
        "note": "time to absorption in a Markov chain; multi-stage processes, funnels.",
    },
    "generalized_inverse_gaussian": {
        "url": "http://en.wikipedia.org/wiki/Generalized_inverse_Gaussian_distribution",
        "note": "gamma/inverse-gamma/inverse-Gaussian in one family; mixing weight in heavy-tail models.",
    },
    "gamma_gompertz": {
        "url": "https://en.wikipedia.org/wiki/Gamma/Gompertz_distribution",
        "note": "heterogeneous ageing; churn and survival with frailty.",
    },
    "nakagami": {
        "url": "https://en.wikipedia.org/wiki/Nakagami_distribution",
        "note": "signal amplitude / fading.",
    },
    "rice": {
        "url": "http://en.wikipedia.org/wiki/Rice_distribution",
        "note": "magnitude of a 2D vector with a non-zero mean; MRI, RF envelopes.",
    },
    # ---- truncation and folding -------------------------------------------
    "truncated_normal": {
        "url": "http://en.wikipedia.org/wiki/Truncated_normal_distribution",
        "note": "an observation window cuts the support; the mean/sd of the visible part are biased for the whole.",
    },
    "folded_normal": {
        "url": "http://en.wikipedia.org/wiki/Folded_normal_distribution",
        "note": "|X| of a normal; sign discarded upstream.",
    },
    "half_normal": {
        "url": "http://en.wikipedia.org/wiki/Half-normal_distribution",
        "note": "folded normal with zero mean; magnitudes, absolute deviations.",
    },
    "rectified_gaussian": {
        "url": "https://en.wikipedia.org/wiki/Rectified_Gaussian_distribution",
        "note": "max(0, X): a point mass at zero plus a continuous part -- clipping, ReLU, censored-at-zero sensors.",
    },
    # ---- shaped continuous ------------------------------------------------
    "skew_normal": {
        "url": "https://en.wikipedia.org/wiki/Skew_normal_distribution",
        "note": "normal plus a skewness parameter; mild asymmetry without a transform.",
    },
    "johnson_su": {
        "url": "http://en.wikipedia.org/wiki/Johnson_SU_distribution",
        "note": "unbounded, skew and kurtosis fitted independently; financial returns.",
    },
    "sinh_arcsinh": {
        "url": "https://academic.oup.com/biomet/article/96/4/761/220523",
        "note": "separate tail-weight and skewness parameters, normal as a special case.",
    },
    "tukey_lambda": {
        "url": "http://en.wikipedia.org/wiki/Tukey_lambda_distribution",
        "note": "a shape diagnostic: the lambda that best fits identifies the tail regime.",
    },
    "generalized_normal": {
        "url": "https://en.wikipedia.org/wiki/Generalized_normal_distribution",
        "note": "normal/Laplace/uniform in one family via a shape parameter.",
    },
    "slash": {
        "url": "https://en.wikipedia.org/wiki/Slash_distribution",
        "note": "normal divided by a uniform; a standard robustness stress-test.",
    },
    # ---- circular ---------------------------------------------------------
    "wrapped_normal": {
        "url": "https://en.wikipedia.org/wiki/Wrapped_normal_distribution",
        "note": "angles, hour-of-day, day-of-year: 23:59 and 00:01 are adjacent, not 24h apart.",
    },
    "wrapped_cauchy": {
        "url": "https://en.wikipedia.org/wiki/Wrapped_Cauchy_distribution",
        "note": "heavy-tailed circular data.",
    },
    "circular_uniform": {
        "url": "https://en.wikipedia.org/wiki/Circular_uniform_distribution",
        "note": "the null model for directional data -- test against this before claiming a peak hour.",
    },
    # ---- structural / meta -------------------------------------------------
    "mixture": {
        "url": "https://en.wikipedia.org/wiki/Mixture_distribution",
        "note": "the general mechanism behind multimodality: find the latent group before fitting anything.",
    },
    "categorical": {
        "url": "https://en.wikipedia.org/wiki/Categorical_distribution",
        "note": "the everyday distribution of a nominal column; absent from the chart.",
    },
    "irwin_hall": {
        "url": "http://en.wikipedia.org/wiki/Irwin-Hall_distribution",
        "note": "sum of uniforms (Bates = its mean); a synthetic-data smell when data looks suspiciously bell-shaped.",
    },
    "marchenko_pastur": {
        "url": "https://en.wikipedia.org/wiki/Marchenko-Pastur_distribution",
        "note": "the NULL eigenvalue spectrum of a random correlation matrix -- separates signal PCA components from noise.",
    },
    "maximum_entropy": {
        "url": "https://en.wikipedia.org/wiki/Maximum_entropy_probability_distribution",
        "note": "which family the constraints alone imply; a principled default before fitting shapes.",
    },
}


# --------------------------------------------------------------------------- #
# Signature
# --------------------------------------------------------------------------- #

def tail_index(s, frac: float = 0.10) -> dict:
    """Hill tail index of the upper tail, plus whether a Pareto tail is credible.

    ``alpha < 2`` implies infinite variance and ``alpha < 1`` infinite mean --
    *if* the tail really is Pareto-type. It often is not, and the Hill estimator
    returns a finite number regardless, so two guards are reported:

    - ``loglog_r2`` -- linearity of ``log P(X > x)`` against ``log x`` on the
      tail. Measured: Pareto 0.998, lognormal 0.985, exponential 0.965. Note this
      alone does **not** separate lognormal from Pareto.
    - ``log_skew`` -- skewness of ``log X``, which does. ``log`` of a Pareto is
      exponential (skew ~ +2); ``log`` of a lognormal is normal (skew ~ 0);
      negative skew indicates a stretched-exponential/Weibull tail. Measured:
      Pareto 2.02/2.00, lognormal -0.00, Weibull(0.5) -1.13.

    Verified against known truth: Hill recovers Pareto alpha = 0.79/1.49/2.51/4.00
    for true 0.8/1.5/2.5/4.0. But lognormal(0,2) yields alpha = 1.05, which read
    naively would claim an infinite mean for a distribution whose moments all
    exist -- hence ``tail_family``, not ``alpha``, is the field to act on.
    """
    x = np.sort(np.asarray(pd.Series(s).dropna(), dtype=float))
    x = x[np.isfinite(x)]
    x = x[x > 0]
    if x.size < 100:
        return {"alpha": np.nan, "loglog_r2": np.nan, "log_skew": np.nan,
                "tail_family": "insufficient_data"}
    k = max(20, int(x.size * frac))
    if k >= x.size:
        k = x.size // 2
    tail = x[-k:]
    denom = np.log(tail).mean() - np.log(x[-k - 1])
    alpha = float(1.0 / denom) if denom > 0 else np.nan

    surv = np.arange(k, 0, -1) / x.size
    r2 = float(stats.linregress(np.log(tail), np.log(surv)).rvalue ** 2)
    lsk = float(stats.skew(np.log(x)))
    lku = float(stats.kurtosis(np.log(x)))

    # Kurtosis is checked first on purpose: when the log scale is heavy-tailed the
    # sample skewness of log X is itself unstable (log of a log-Cauchy has no
    # moments), so branching on skew first misclassifies exactly that case.
    #
    # The threshold must clear the Pareto case: log of a Pareto is *exponential*,
    # whose excess kurtosis is exactly 6. Measured over 20 seeds at n=5000 --
    # Pareto reaches 9.9 at most, lognormal sits at ~0, log-Cauchy starts around
    # 200. 20 leaves a wide margin on both sides; 3 would swallow every Pareto.
    if lku > 20.0:
        fam = "log_heavy"
    elif abs(lsk) < 0.5:
        fam = "lognormal_like"
    elif lsk >= 0.5:
        fam = "pareto_like" if r2 > 0.97 else "right_skewed_on_log_scale"
    else:
        fam = "stretched_exponential_like"
    return {"alpha": round(alpha, 4) if np.isfinite(alpha) else np.nan,
            "loglog_r2": round(r2, 4), "log_skew": round(lsk, 4),
            "log_kurtosis": round(lku, 4), "tail_family": fam}


def signature(s: pd.Series, by: Optional[pd.Series] = None) -> dict:
    """Measure the properties that select a candidate family. Fits nothing."""
    x = pd.Series(s).dropna()
    arr = x.to_numpy(dtype=float, na_value=np.nan)
    finite = arr[np.isfinite(arr)]
    n = finite.size
    if n < 10:
        return {"n": int(n), "verdict": "insufficient_data"}

    is_int = bool(np.allclose(finite, np.round(finite)))
    nonneg = bool(finite.min() >= 0)
    sig = {
        "n": int(n),
        "n_unique": int(pd.Series(finite).nunique()),
        "n_non_finite": int(arr.size - n),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "is_integer": is_int,
        "is_nonnegative": nonneg,
        "bounded_01": bool(finite.min() >= 0 and finite.max() <= 1),
        "zero_fraction": round(float((finite == 0).mean()), 4),
        "skew": round(float(stats.skew(finite)), 4),
        "excess_kurtosis": round(float(stats.kurtosis(finite)), 4),
        "verdict": "measured",
    }
    if is_int and nonneg and sig["n_unique"] > 1:
        m, v = finite.mean(), finite.var(ddof=1)
        sig["vmr"] = round(float(v / m), 4) if m > 0 else np.nan
    if nonneg and (finite > 0).sum() >= 100:
        sig.update({f"tail_{k}": v for k, v in tail_index(finite).items()})
    if by is not None:
        from distribution_report import mean_variance_scaling
        d = pd.DataFrame({"_v": x, "_g": pd.Series(by).reindex(x.index)}).dropna()
        sig["mean_variance_b"] = mean_variance_scaling(d, "_v", "_g").get("b")
    return sig


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #

def suggest_families(sig: dict, max_candidates: int = 6) -> pd.DataFrame:
    """Rank candidate families for a measured signature, with reason and URL.

    **A candidate is a hypothesis, not a finding.** Before any of these may be
    written into a report or a model choice:

    1. The mechanism must be plausible in the domain. A family that fits but
       describes a process nobody believes in is a curve, not an explanation.
    2. Fit on **train/fold only** and compare against the simpler baseline family
       on held-out data (Q-Q or PP plot plus a proper scoring rule). "More
       parameters fit better" is not evidence.
    3. Read the source at ``url`` and map its parameterization onto the library's
       before touching any parameter -- scale-vs-rate and argument order differ
       between textbooks, scipy, and numpy.
    4. Record the chosen family, the evidence that selected it, and the
       alternatives rejected. Never adopt a family because it appeared in a list.

    Returns an empty frame when the signature is unremarkable: no candidate is
    the correct answer for well-behaved data.
    """
    if sig.get("verdict") != "measured":
        return pd.DataFrame(columns=["family", "reason", "url", "note"])

    out: list[tuple[float, str, str]] = []   # (priority, family, reason)

    z = sig.get("zero_fraction", 0.0)
    vmr = sig.get("vmr")
    b = sig.get("mean_variance_b")
    tail_fam = sig.get("tail_tail_family")
    alpha = sig.get("tail_alpha")

    # counts
    if sig.get("is_integer") and sig.get("is_nonnegative") and vmr is not None:
        if vmr > 1.25:
            out.append((1.0, "negative_binomial", f"integer counts, VMR={vmr} > 1 (overdispersed)"))
            if z > 0.3:
                out.append((0.9, "zero_inflated_poisson", f"overdispersed AND zero_fraction={z}"))
            out.append((0.4, "delaporte", "overdispersion with a possible fixed base rate"))
        elif vmr < 0.75:
            out.append((1.0, "conway_maxwell_poisson", f"integer counts, VMR={vmr} < 1 (underdispersed)"))
            out.append((0.7, "poisson_binomial", "underdispersion also arises from summing Bernoulli trials with differing p"))
        if sig.get("min", 0) < 0:
            out.append((0.8, "skellam", "integer values below zero: a difference of counts"))
        if tail_fam == "pareto_like":
            out.append((0.8, "yule_simon", "integer counts with a power-law tail"))
            out.append((0.7, "zipf_mandelbrot", "rank-frequency data; plain Zipf fits the head only"))

    # zero mass on a continuous positive variable
    if not sig.get("is_integer") and sig.get("is_nonnegative") and z > 0.05:
        reason = f"continuous non-negative with a {z:.1%} point mass at zero"
        if b is not None and 1.0 < b < 2.6:
            reason += f", mean-variance b={b}"
        out.append((1.0, "tweedie", reason))
        out.append((0.8, "compound_poisson", "a random number of random-sized events"))
        out.append((0.5, "rectified_gaussian", "if the zeros are clipping rather than non-events"))

    # heavy tails
    if tail_fam == "pareto_like":
        out.append((0.9, "generalized_pareto_evt", f"Pareto-type tail (Hill alpha={alpha}); model exceedances over a threshold"))
        out.append((0.6, "burr", "flexible Pareto-type body and tail"))
        if alpha is not None and np.isfinite(alpha) and alpha < 2:
            out.append((1.0, "stable", f"Hill alpha={alpha} < 2: variance may not exist, so CLT intervals are invalid"))
        out.append((0.4, "generalized_extreme_value", "if the question is about block maxima rather than the body"))
    elif tail_fam == "log_heavy" and not sig.get("is_integer"):
        # log X symmetric but itself heavy-tailed -- heavier than any lognormal
        out.append((0.8, "log_cauchy",
                    f"log-scale excess kurtosis={sig.get('tail_log_kurtosis')}: the tail is heavier than lognormal"))

    # bounded [0,1]
    if sig.get("bounded_01") and not sig.get("is_integer"):
        out.append((1.0, "logit_normal", "values confined to [0,1]: model on the logit scale"))
        out.append((0.8, "kumaraswamy", "beta-like on [0,1] with closed-form CDF/quantile"))
        if z > 0.02 or sig.get("max", 0) == 1:
            out.append((0.7, "beta_rectangular", "mass at the boundaries; a plain beta cannot place it"))

    # shape anomalies
    if sig.get("excess_kurtosis", 0) < -1.0:
        out.append((0.7, "u_quadratic", f"excess kurtosis={sig['excess_kurtosis']}: mass at both edges"))
        out.append((0.8, "mixture", "flat or bimodal shape usually means an unmodelled latent group"))
    if abs(sig.get("skew", 0)) > 0.5 and not sig.get("is_nonnegative"):
        out.append((0.6, "skew_normal", f"unbounded and skewed (skew={sig['skew']})"))
        out.append((0.5, "johnson_su", "if tails and skewness need separate parameters"))

    if sig.get("n_non_finite", 0):
        out.append((1.0, "mixture", f"{sig['n_non_finite']} non-finite values: resolve those before fitting any family"))

    out.sort(key=lambda t: -t[0])
    seen, rows = set(), []
    for _, fam, reason in out:
        if fam in seen or fam not in CATALOGUE:
            continue
        seen.add(fam)
        rows.append({"family": fam, "reason": reason,
                     "url": CATALOGUE[fam]["url"], "note": CATALOGUE[fam]["note"]})
        if len(rows) >= max_candidates:
            break
    return pd.DataFrame(rows, columns=["family", "reason", "url", "note"])


def route(s: pd.Series, by: Optional[pd.Series] = None) -> dict:
    """Convenience: measure the signature and return it with ranked candidates."""
    sig = signature(s, by=by)
    return {"signature": sig, "candidates": suggest_families(sig)}


__all__ = ["CATALOGUE", "tail_index", "signature", "suggest_families", "route"]
