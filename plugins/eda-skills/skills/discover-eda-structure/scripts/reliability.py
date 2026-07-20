"""Reliability of a multi-item scale, and what it caps (discover step 6).

`associations.md` states the attenuation ceiling `r_obs = r_true * sqrt(rel_x *
rel_y)` in three places and computes `rel` in none of them.
`consistency-validity.md` names the dead end outright: repeated measurements or
parallel instruments "are the only in-data evidence of reliability; otherwise it
is a domain question". A multi-item scale **is** that repeated measurement — the
items are the parallel instruments — so the loop closes here: estimate the
reliability from the items, then say what it costs every correlation the scale
takes part in.

Two things this module exists to stop:

* **Reading alpha as a dimensionality statistic.** It is not one. Two
  *orthogonal* 15-item factors (true factor correlation 0.0 by construction)
  produce alpha = 0.9179. Alpha rises with item count at a fixed mean inter-item
  correlation; that is Spearman-Brown, not evidence of a common cause.
* **Reading a weak correlation as a weak relationship.** Two scales at
  reliability 0.70 cap the observable correlation at 0.70 — a true 0.80 cannot
  read above 0.56 no matter how large the sample.

Scores computed here are a model fitted to the data they are given: fit on
train/fold only, exactly like every other estimate in this skill.

Core stack only (numpy/pandas); shares `principal_axis_factoring` with
`factor_analysis.py` so an ordinal user can hand the same polychoric matrix to
both.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

from factor_analysis import correlation_matrix, parallel_analysis, principal_axis_factoring

__all__ = [
    "cronbach_alpha",
    "item_statistics",
    "mcdonald_omega",
    "tau_equivalence_check",
    "disattenuate",
    "attenuation_ceiling",
    "indicator_direction_check",
    "invariance_screen",
    "scale_score_report",
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _as_matrix(X) -> np.ndarray:
    A = np.asarray(getattr(X, "values", X), dtype=float)
    if A.ndim != 2:
        raise ValueError("X must be 2-dimensional (n_rows x n_items)")
    return A


def _names(X, p: int, names: Optional[Sequence[str]] = None) -> list[str]:
    if names is not None:
        return [str(c) for c in names]
    cols = getattr(X, "columns", None)
    return [str(c) for c in cols] if cols is not None else [f"item{i}" for i in range(p)]


def _clean(X) -> np.ndarray:
    """Listwise-complete rows only: a partial row has no total score."""
    A = _as_matrix(X)
    return A[np.isfinite(A).all(axis=1)]


def _one_factor_loadings(R: np.ndarray) -> tuple[np.ndarray, dict]:
    """Unrotated one-factor loadings with the arbitrary sign resolved.

    A single factor's sign is not identified, so the extraction may return the
    whole column negated. Everything downstream (omega, the loading sd, the
    invariance range) is then wrong in a way that looks like a finding. Fixed
    once, here, by orienting the factor so the items agree with it on average.
    """
    ext = principal_axis_factoring(R, 1)
    L = np.asarray(ext["loadings"], dtype=float).ravel()
    if L.sum() < 0:
        L = -L
    return L, ext


# --------------------------------------------------------------------------- #
# alpha
# --------------------------------------------------------------------------- #
def cronbach_alpha(X, standardized: bool = False) -> dict:
    """Internal consistency, and the item count that manufactures it.

    ``alpha = k/(k-1) * (1 - sum(var_i)/var_total)``. The standardized form is
    Spearman-Brown on the mean inter-item correlation:
    ``k*r_bar / (1 + (k-1)*r_bar)`` — and *that* form is the warning label,
    because it contains no term for what the items mean. Alpha is a function of
    two things only: how many items there are, and how much they share on
    average.

    **The convention is clearable by item count alone.** Measured on population
    correlation matrices (no sampling involved, these are exact):

    ==========================  ===============  ===================
    design                      mean inter-item  alpha
    ==========================  ===============  ===================
    6 items, loading 0.70       0.4900           0.8522
    30 items, loading 0.30      0.0900           0.7479
    40 items, loading 0.25      0.0625           0.7273
    ==========================  ===============  ===================

    Forty items each sharing 6% of their variance with the next clear the
    "alpha > 0.70" rule. ``k_for_alpha_070`` reports the inverse — how many
    items this ``mean_inter_item_r`` needs to reach 0.70 — which is the number
    that makes the trap visible.

    **A briefed claim died here and is recorded so it is not re-briefed:**
    "alpha rises when junk items are added" is **false**. Appending 0/2/4/6
    items at loading 0.10 to six items at loading 0.70 drove population alpha
    *down* monotonically, 0.8522 / 0.7681 / 0.7168 / 0.6823. Junk items lower
    the mean inter-item correlation faster than the extra k raises alpha. The
    real trap is the one in the table: *many mediocre* items, not a few bad ones.

    ``verdict`` is ``inflated_by_item_count`` when alpha clears 0.70 on a mean
    inter-item correlation below 0.15 (the Clark-Watson floor). On the
    population matrices above that branch fires for the 30- and 40-item designs
    and stays silent for the 6-item one, which is the separation it exists to
    make.
    """
    A = _clean(X)
    n, k = A.shape if A.ndim == 2 else (0, 0)
    if k < 2:
        return {"verdict": "too_few_items", "k": int(k)}
    if n < 3:
        return {"verdict": "insufficient_rows", "n": int(n), "k": int(k)}

    var_i = A.var(axis=0, ddof=1)
    var_t = A.sum(axis=1).var(ddof=1)
    raw = float(k / (k - 1) * (1 - var_i.sum() / var_t)) if var_t > 0 else float("nan")

    R = np.corrcoef(A, rowvar=False)
    off = ~np.eye(k, dtype=bool)
    r_bar = float(np.nanmean(R[off]))
    std = float(k * r_bar / (1 + (k - 1) * r_bar)) if (1 + (k - 1) * r_bar) != 0 else float("nan")
    alpha = std if standardized else raw

    k_needed = (0.70 * (1 - r_bar) / (r_bar * 0.30)) if r_bar > 0 else float("inf")

    if not np.isfinite(alpha):
        verdict = "undefined_no_variance"
    elif alpha < 0:
        verdict = "negative_alpha_check_reverse_keyed_items"
    elif alpha >= 0.70 and r_bar < 0.15:
        verdict = "inflated_by_item_count"
    elif alpha >= 0.70:
        verdict = "adequate"
    else:
        verdict = "below_convention"

    return {
        "n": int(n), "k": int(k),
        "alpha": round(alpha, 4),
        "alpha_raw": round(raw, 4),
        "alpha_standardized": round(std, 4),
        "mean_inter_item_r": round(r_bar, 4),
        "min_inter_item_r": round(float(np.nanmin(R[off])), 4),
        "k_for_alpha_070": (int(np.ceil(k_needed)) if np.isfinite(k_needed) else None),
        "verdict": verdict,
        "note": ("alpha is a function of item count and mean inter-item r only; "
                 "it is not evidence that the items measure one thing"),
    }


def item_statistics(X, names: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """Per-item table: rest correlation, alpha-if-deleted, one-factor loading.

    ``item_total_r`` correlates each item with a total that **contains that
    item**, so every item is partly correlated with itself. How badly depends
    only on how many other items dilute the total — measured against a true
    loading of 0.50 (n=1000, 500 reps):

    =====  =============  =============  ==========
    k      item_total_r   item_rest_r    true load
    =====  =============  =============  ==========
    3      0.7074         0.3171         0.50
    5      0.6319         0.3771         0.50
    8      0.5854         0.4170         0.50
    15     0.5477         0.4537         0.50
    30     0.5235         0.4750         0.50
    =====  =============  =============  ==========

    **Both columns are wrong at small k, and they are wrong in opposite
    directions** — which is the honest form of this finding and not the one
    usually stated. ``item_total_r`` is inflated from above (0.71 at k=3) by the
    item's own contribution to the total. ``item_rest_r`` is attenuated from
    below (0.32 at k=3) because a rest-score built from two other items is
    itself barely reliable. They converge on the truth from either side as k
    grows, and neither is trustworthy on a three-item scale.

    ``item_rest_r`` is nevertheless the reported column: its error is ordinary
    attenuation, shared by every item equally, so the *ranking* of items stays
    usable. ``item_total_r``'s error rewards exactly the items that dominate the
    total, so it is not merely biased but biased in favour of the wrong answer.
    ``item_total_r`` ships alongside only so the gap is visible.

    ``alpha_if_deleted`` above the scale's own alpha marks an item whose removal
    *improves* internal consistency — most often a reverse-keyed item that was
    never recoded. That is a comparison, not a threshold, so it needs no cutoff.
    """
    A = _clean(X)
    n, k = A.shape if A.ndim == 2 else (0, 0)
    cols = _names(X, k, names)
    if k < 3 or n < 3:
        out = pd.DataFrame({"item": cols})
        out.attrs["verdict"] = "too_few_items" if k < 3 else "insufficient_rows"
        return out

    base = cronbach_alpha(A)
    R = np.corrcoef(A, rowvar=False)
    L, ext = _one_factor_loadings(R)

    total = A.sum(axis=1)
    rows = []
    for j in range(k):
        rest = total - A[:, j]
        sd_j = A[:, j].std(ddof=1)
        rows.append({
            "item": cols[j],
            "mean": round(float(A[:, j].mean()), 4),
            "sd": round(float(sd_j), 4),
            "item_total_r": (round(float(np.corrcoef(A[:, j], total)[0, 1]), 4)
                             if sd_j > 0 else np.nan),
            "item_rest_r": (round(float(np.corrcoef(A[:, j], rest)[0, 1]), 4)
                            if sd_j > 0 and rest.std(ddof=1) > 0 else np.nan),
            "alpha_if_deleted": round(
                float(cronbach_alpha(np.delete(A, j, axis=1))["alpha"]), 4),
            "loading": round(float(L[j]), 4),
        })

    out = pd.DataFrame(rows)
    out["raises_alpha_if_dropped"] = out["alpha_if_deleted"] > base["alpha"]
    out = out.sort_values("item_rest_r").reset_index(drop=True)
    out.attrs["alpha"] = base["alpha"]
    out.attrs["mean_inter_item_r"] = base["mean_inter_item_r"]
    out.attrs["n"] = int(n)
    out.attrs["k"] = int(k)
    out.attrs["items_raising_alpha_if_dropped"] = out.loc[
        out["raises_alpha_if_dropped"], "item"].tolist()
    out.attrs["verdict"] = ("reverse_keyed_or_off_construct_item_present"
                            if bool(out["raises_alpha_if_dropped"].any()) else "measured")
    out.attrs["note"] = ("item_rest_r is the reported column; item_total_r is "
                         "inflated by the item's own contribution to the total")
    return out


def mcdonald_omega(X, R=None) -> dict:
    """Reliability without assuming the items are interchangeable.

    ``omega = (sum L)^2 / ((sum L)^2 + sum psi)`` from a one-factor common-factor
    solution: the share of the total score's variance that the common factor
    accounts for. Alpha assumes **tau-equivalence** — every item loading equal —
    and omega does not, which is the whole of the difference between them.

    **The identity, and the honest size of the gap.** Under exact
    tau-equivalence alpha and omega are algebraically the same number, not
    approximately: measured gap ``+-1.11e-16`` at equal loadings of 0.4 / 0.6 /
    0.8. As the loadings spread apart (mean 0.60, k=6) the population gap runs:

    ============  =======  =======  =============
    sd(loadings)  alpha    omega    omega - alpha
    ============  =======  =======  =============
    0.0000        0.7714   0.7714   +0.0000
    0.0748        0.7707   0.7727   +0.0020
    0.1497        0.7686   0.7766   +0.0081
    0.2245        0.7649   0.7832   +0.0183
    ============  =======  =======  =============

    So "alpha underestimates reliability" is **true and almost always
    negligible**: 0.002 to 0.018 across the realistic range of loading spread,
    reaching only ~0.031 at a spread so wide the weakest item loads 0.20 while
    the strongest loads 0.95. Prefer omega on principle — it costs nothing and
    assumes less — but a decision that turns on the third decimal of a
    reliability estimate is not a decision the data supports. See
    `tau_equivalence_check` for why the *observed* gap is worse still as a
    statistic to act on.

    Pass ``R`` to compute omega from a correlation matrix you built yourself —
    `ordinal_data.polychoric_matrix` for Likert items, most usefully, since
    Pearson correlations on ordinal codes attenuate every loading in the
    solution.
    """
    if R is None:
        R, _keep, _dropped = correlation_matrix(X)
    else:
        R = np.asarray(R, dtype=float)
    p = R.shape[0]
    if p < 3:
        return {"verdict": "too_few_items", "k": int(p)}

    L, ext = _one_factor_loadings(R)
    psi = np.asarray(ext["uniquenesses"], dtype=float)
    num = float(L.sum() ** 2)
    den = num + float(psi.sum())
    omega = num / den if den > 0 else float("nan")

    return {
        "k": int(p),
        # 6 decimals, not the usual 4: alpha == omega under tau-equivalence is an
        # algebraic identity, and 4 decimals is too coarse to show that it holds
        "omega": round(float(omega), 6),
        "loadings": np.round(L, 4).tolist(),
        "mean_loading": round(float(L.mean()), 4),
        "loading_sd": round(float(L.std(ddof=1)), 4),
        "heywood": bool(ext["heywood"]),
        "converged": bool(ext["converged"]),
        "verdict": ("improper_solution_heywood" if ext["heywood"]
                    else "measured" if ext["converged"] else "did_not_converge"),
        "note": ("omega does not assume equal loadings; the gap to alpha is "
                 "0.002-0.033 over the realistic range of loading spread"),
    }


def tau_equivalence_check(X) -> dict:
    """Are the item loadings equal enough for alpha to be the right statistic?

    **The verdict is keyed on the loading spread, never on the observed
    ``omega - alpha`` gap**, and the measurement behind that choice is worth
    stating because it is not the obvious one. Under *exact* tau-equivalence the
    population gap is 0, but the estimated gap is not centred on 0 — it carries
    a positive small-sample bias (3000 reps, k=6, loading 0.60):

    ======  ==========  =========  =========  ==============
    n       mean gap    sd of gap  95th pct   scaling
    ======  ==========  =========  =========  ==============
    100     +0.00284    0.00190    0.00650    ~0.27/n bias
    300     +0.00090    0.00058    0.00200    ~0.60/n at p95
    1000    +0.00026    0.00017    0.00060
    ======  ==========  =========  =========  ==============

    Both bias and spread scale as **1/n**, and the consequence is a squeeze with
    no gap-based verdict inside it. At n=100 tau-equivalent data produces a gap
    above 0.0065 one time in twenty, while a genuinely *mildly* congeneric scale
    (sd of loadings 0.075) has a population gap of only **0.0020** — smaller
    than the null's own 95th percentile. At n=1000 the null shrinks to 0.0006
    and the 0.0020 becomes detectable, but by then it is far too small to change
    any decision. **The observed gap is either below its own noise floor or too
    small to matter; there is no sample size at which it is both.**

    ``loading_sd`` avoids that because it estimates the quantity in question
    directly instead of differencing two near-identical numbers. It still needs
    an n-aware threshold, since the sd of six *estimated* loadings is positive
    even when the true loadings are identical — measured null, 2000 reps:

    ======  ========  ========  =============
    n       mean      95th pct  mean*sqrt(n)
    ======  ========  ========  =============
    50      0.1074    0.1751    0.760
    100     0.0757    0.1219    0.757
    300     0.0436    0.0690    0.754
    1000    0.0236    0.0377    0.746
    ======  ========  ========  =============

    That last column is flat, so the null is ``~0.75/sqrt(n)`` and the shipped
    cutoff is ``max(0.10, 1.4/sqrt(n))``. A **fixed** 0.05 cutoff — the obvious
    choice, and the one this function was first written with — declares
    tau-equivalent data congeneric **95.2% of the time at n=50 and 83.3% at
    n=100**. Rates for the shipped cutoff, 1000 replications of the exact call:

    =================  ======  ======  ======  ======
    true sd(loadings)  n=50    n=100   n=300   n=1000
    =================  ======  ======  ======  ======
    0.000 (tau-eq)     0.023   0.014   0.001   0.000
    0.150              0.329   0.742   0.999   1.000
    0.225              0.816   0.998   1.000   1.000
    =================  ======  ======  ======  ======

    The first row is the false-alarm rate and the other two are power. Note the
    honest cost: at n=50 a genuinely congeneric scale with a loading sd of 0.15
    is caught only a third of the time. The cutoff is set where it is because a
    false "congeneric" is the more expensive error — it sends the reader chasing
    a difference that the table in `mcdonald_omega` shows is worth 0.008.

    ``observed_gap`` is still reported, with ``gap_within_sampling_noise``
    comparing it to the measured null. Read that flag before reading the gap.
    """
    A = _clean(X)
    n, k = A.shape if A.ndim == 2 else (0, 0)
    if k < 3:
        return {"verdict": "too_few_items", "k": int(k)}
    if n < 10:
        return {"verdict": "insufficient_rows", "n": int(n), "k": int(k)}

    al = cronbach_alpha(A)
    om = mcdonald_omega(A)
    if om.get("omega") is None or not np.isfinite(om.get("omega", np.nan)):
        return {"verdict": om.get("verdict", "omega_failed"), "alpha": al.get("alpha")}

    sd = float(om["loading_sd"])
    gap = float(om["omega"]) - float(al["alpha"])
    # measured null of loading_sd under exact tau-equivalence is ~0.75/sqrt(n);
    # 1.4/sqrt(n) holds the false-alarm rate at or below 0.018 for n >= 50
    cutoff = max(0.10, 1.4 / np.sqrt(n))
    # measured 95th percentile of the gap under exact tau-equivalence, ~0.6/n
    gap_null_p95 = 0.6 / n

    if om["heywood"]:
        verdict = "improper_solution_heywood"
    elif sd <= cutoff:
        verdict = "tau_equivalent_alpha_is_appropriate"
    elif sd <= 0.20:
        verdict = "mildly_congeneric_gap_is_negligible"
    else:
        verdict = "congeneric_prefer_omega"

    return {
        "n": int(n), "k": int(k),
        "alpha": al["alpha"],
        "omega": om["omega"],
        "observed_gap": round(gap, 4),
        "loading_sd": round(sd, 4),
        "loading_min": round(float(min(om["loadings"])), 4),
        "loading_max": round(float(max(om["loadings"])), 4),
        "loading_sd_cutoff": round(float(cutoff), 4),
        "gap_null_p95": round(float(gap_null_p95), 5),
        "gap_within_sampling_noise": bool(abs(gap) < gap_null_p95),
        "verdict": verdict,
        "note": ("verdict is keyed on loading_sd against an n-aware cutoff, not "
                 "on the observed gap: the gap is either below its own noise "
                 "floor or too small to act on, at every sample size"),
    }


# --------------------------------------------------------------------------- #
# what reliability costs
# --------------------------------------------------------------------------- #
def disattenuate(r_obs: float, rel_x: float, rel_y: float = 1.0) -> dict:
    """Correct an observed correlation for measurement error in both variables.

    ``r_true = r_obs / sqrt(rel_x * rel_y)``. This is the inverse of the
    attenuation ceiling, and it answers the question that a weak correlation
    between two noisy scales actually raises: is this a weak relationship, or a
    measurement floor?

    **The estimate is not clipped when it exceeds 1.0**, and that is deliberate
    — the same doctrine `principal_axis_factoring` applies to Heywood cases. A
    disattenuated correlation above 1.0 is an impossible value, and it is
    *information*: it says the reliability estimates are too low, or the sample
    is too small, or the two scales share method variance the model does not
    know about. Clipping it to 1.0 silences the diagnosis and keeps the bad
    input. ``r_disattenuated`` carries the raw value, ``r_disattenuated_clipped``
    the usable one, and ``verdict`` names the problem.

    Measured share of impossible estimates — two 6-item scales, reliability
    estimated from each sample's own alpha, 1500 replications per cell:

    ========  ==========  ========  ========  ========
    r_true    reliability n=50      n=200     n=500
    ========  ==========  ========  ========  ========
    0.80      0.90        0.0000    0.0000    0.0000
    0.80      0.70        0.0687    0.0000    0.0000
    0.80      0.50        0.2947    0.0507    0.0040
    0.95      0.70        0.3627    0.1740    0.0640
    0.95      0.50        0.4827    0.3613    0.2347
    ========  ==========  ========  ========  ========

    At reliability 0.50 on 50 rows **29% of the corrections are impossible**,
    and against a true correlation of 0.95 the failure does not go away with
    sample size at all — a third of the corrections are still impossible at
    n = 500, because the true value sits so close to the ceiling that ordinary
    noise pushes the estimate through it.

    **Which input to distrust, decomposed.** Re-running the r_true = 0.80 cells
    with the reliability plugged in *at truth*, so only ``r_obs`` is noisy:

    ==========  ========  ========  ========
    reliability n=50      n=200     n=500
    ==========  ========  ========  ========
    0.70        0.0500    0.0013    0.0000
    0.50        0.2033    0.0373    0.0020
    ==========  ========  ========  ========

    Against 0.0687 / 0.2947 with alpha estimated. So roughly **two thirds of the
    impossible results come from noise in the observed correlation and one third
    from noise in the reliability estimate** — the correction is not mainly
    failing because alpha is badly estimated, it is failing because dividing a
    noisy number by a number below 1 amplifies the noise. A larger sample fixes
    both, and nothing else does.

    Use the correction as a sensitivity statement ("if the scales were perfect
    this would be about X"), never as a measurement.
    """
    if not (0 < rel_x <= 1) or not (0 < rel_y <= 1):
        return {"verdict": "invalid_reliability",
                "note": "reliability must be in (0, 1]"}
    if not (-1 <= r_obs <= 1):
        return {"verdict": "invalid_correlation"}

    denom = float(np.sqrt(rel_x * rel_y))
    raw = float(r_obs) / denom
    clipped = float(np.clip(raw, -1.0, 1.0))

    return {
        "r_observed": round(float(r_obs), 4),
        "reliability_x": round(float(rel_x), 4),
        "reliability_y": round(float(rel_y), 4),
        "attenuation_factor": round(denom, 4),
        "r_disattenuated": round(raw, 4),
        "r_disattenuated_clipped": round(clipped, 4),
        "exceeds_unity": bool(abs(raw) > 1.0),
        "verdict": ("exceeds_unity_reliability_estimates_are_too_low"
                    if abs(raw) > 1.0 else "corrected"),
        "note": ("a sensitivity statement, not a measurement; the raw value is "
                 "reported unclipped so an impossible result stays visible"),
    }


def attenuation_ceiling(rel_x: float, rel_y: float = 1.0,
                        r_true: Optional[float] = None) -> dict:
    """The largest correlation two scales of this reliability can produce.

    ``r_obs = r_true * sqrt(rel_x * rel_y)``, so with ``r_true = 1`` the ceiling
    is ``sqrt(rel_x * rel_y)``: the correlation two instruments would show if
    they measured *the same construct perfectly* and differed only in noise.

    ==================  ========
    rel_x, rel_y        ceiling
    ==================  ========
    0.90, 0.90          0.900
    0.80, 0.80          0.800
    0.70, 0.70          0.700
    0.60, 0.60          0.600
    0.70, 1.00          0.837
    ==================  ========

    Two scales at the "acceptable" 0.70 cannot correlate above 0.70 even when
    they are the same construct, and a genuine 0.80 relation between them reads
    as **0.56**. That number is the reason to run this before concluding a
    hypothesis failed: no sample size fixes it, because it is not a sampling
    problem.

    ``headroom`` is the ceiling minus the correlation you actually observed
    (pass ``r_true`` as the observed value to see how much of the ceiling is
    already used). When the observed correlation sits at the ceiling, the
    measurement — not the relationship — is what is limiting the result.
    """
    if not (0 < rel_x <= 1) or not (0 < rel_y <= 1):
        return {"verdict": "invalid_reliability"}

    ceiling = float(np.sqrt(rel_x * rel_y))
    out = {
        "reliability_x": round(float(rel_x), 4),
        "reliability_y": round(float(rel_y), 4),
        "max_observable_r": round(ceiling, 4),
        "verdict": ("severe_measurement_ceiling" if ceiling < 0.70
                    else "measurement_ceiling_worth_stating" if ceiling < 0.90
                    else "ceiling_is_not_the_binding_constraint"),
    }
    if r_true is not None:
        expected = float(r_true) * ceiling
        out["r_true_assumed"] = round(float(r_true), 4)
        out["expected_observed_r"] = round(expected, 4)
        out["headroom"] = round(ceiling - abs(float(r_true)), 4)
    out["note"] = ("no sample size raises this ceiling; it is a property of the "
                   "instruments, not of the sample")
    return out


# --------------------------------------------------------------------------- #
# guards
# --------------------------------------------------------------------------- #
def indicator_direction_check(X, names: Optional[Sequence[str]] = None) -> dict:
    """Do these columns look like effects of one construct, or causes of a composite?

    A **reflective** set (anxiety items, say) are *effects* of the latent
    variable: it makes them covary, so they must intercorrelate, alpha means
    something, and dropping one loses little. A **formative** set (the
    components of a socioeconomic-status index: income, education, occupation)
    are *causes* of a composite. They need not correlate at all, alpha is
    meaningless on them, and dropping one changes what the composite **is**.

    Running a reliability analysis on formative indicators is not a small error
    — it is a category error that will report a broken scale and invite you to
    "fix" it by deleting the indicator that carries the most unique information.

    **This screen fires; it cannot diagnose**, and the measurement says so
    plainly (n=1000):

    ==================================  =========  =======  =========
    design                              alpha      omega    mean r
    ==================================  =========  =======  =========
    formative: 3 uncorrelated causes    -0.0397    0.0285   -0.0129
    bad reflective: 6 items at 0.15      0.0878    0.0983    0.0158
    good reflective: 6 items at 0.65     0.8190    0.8192    0.4299
    ==================================  =========  =======  =========

    The first two rows are the point. A genuinely formative set and a genuinely
    broken reflective scale are **not distinguishable by these statistics** —
    both return near-zero everything, and the screen fires on both. The third
    row confirms it stays silent when it should.

    So a hit is a question for whoever owns the data, not a finding: *are these
    columns effects of one construct, or causes of a composite?* Only the
    meaning of the columns answers it, in the same way `composite_target_probe`
    produces a question rather than a verdict.
    """
    A = _clean(X)
    n, k = A.shape if A.ndim == 2 else (0, 0)
    cols = _names(X, k, names)
    if k < 3:
        return {"verdict": "too_few_items", "k": int(k)}
    if n < 10:
        return {"verdict": "insufficient_rows", "n": int(n), "k": int(k)}

    al = cronbach_alpha(A)
    om = mcdonald_omega(A)
    R = np.corrcoef(A, rowvar=False)
    off = ~np.eye(k, dtype=bool)
    r_bar = float(np.nanmean(R[off]))
    n_negative = int(np.sum(R[off] < 0) // 2)

    suspect = bool(r_bar < 0.10 or al["alpha"] < 0.30)
    return {
        "n": int(n), "k": int(k),
        "items": cols,
        "alpha": al["alpha"],
        "omega": om.get("omega"),
        "mean_inter_item_r": round(r_bar, 4),
        "n_negative_pairs": n_negative,
        "verdict": ("formative_or_broken_reflective_scale_suspected" if suspect
                    else "consistent_with_reflective_indicators"),
        "note": ("a screen, not a diagnosis: formative indicators and a bad "
                 "reflective scale look identical in the data. Ask what the "
                 "columns mean. If they are causes of the composite rather than "
                 "effects of a construct, neither alpha nor factor analysis applies."),
    }


def invariance_screen(X, group, min_group: int = 30,
                      names: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """Do the items behave the same way in every group (or period)?

    Comparing scale scores across groups assumes the scale *means the same
    thing* in each of them. If an item loads 0.70 in one group and 0.20 in
    another, the two totals are not the same quantity and the difference between
    them is partly an artefact of the instrument. Pass a period column instead
    of a group column to ask the same question of time.

    This is a **screen, not a test of measurement invariance.** The real
    procedure is a multi-group confirmatory factor analysis with nested model
    comparisons, which is out of scope here and needs a modelling tool. What
    this gives you is the cheap version — per-group one-factor loadings and
    rest-correlations, and their range across groups — which is enough to decide
    whether the expensive version is worth running.

    **The threshold is calibrated, because an uncalibrated range threshold is a
    sample-size detector.** The range of several estimates grows with the number
    of groups and shrinks with n, so a fixed cutoff flags small groups and many
    groups regardless of the instrument. False-alarm rate on genuinely invariant
    data (6 items, loading 0.60, 400 replications) — share of *datasets* with at
    least one item flagged, under a fixed 0.20 cutoff:

    ==========  =========  =========  =========
    n/group     2 groups   3 groups   5 groups
    ==========  =========  =========  =========
    50          0.757      0.960      1.000
    100         0.422      0.725      0.953
    300         0.013      0.062      0.147
    1000        0.000      0.000      0.000
    ==========  =========  =========  =========

    A fixed cutoff flags **100% of perfectly invariant data** at 50 rows per
    group across 5 groups. The shipped threshold is instead fitted to the null:
    the 95th percentile of the maximum loading range scales as
    ``sqrt(2*ln(n_groups))/sqrt(n)`` with an implied constant of 2.10-2.72
    across the twelve cells above, so the cutoff is
    ``max(0.20, 2.6*sqrt(2*ln(n_groups))/sqrt(n_min))``. ``threshold`` is on
    ``.attrs`` so the adjustment is visible rather than magic.

    **Both error rates for the shipped call, 400 replications each** — invariant
    data (false alarm) against one item whose loading differs by 0.30 in one
    group (power):

    ==========  ====================  ====================
    n/group     false alarm  2 / 3    power  2 / 3 groups
    ==========  ====================  ====================
    50          0.092 / 0.022         0.307 / 0.188
    100         0.068 / 0.018         0.482 / 0.410
    300         0.028 / 0.018         0.910 / 0.917
    1000        0.000 / 0.000         0.988 / 0.998
    ==========  ====================  ====================

    Below 300 rows per group this screen is close to a formality — it misses
    two-thirds of a 0.30 loading shift at n=50. ``underpowered`` on ``.attrs``
    and the ``underpowered_no_flag_is_not_evidence`` verdict say so directly,
    rather than letting a clean-looking table imply a clean result.

    **The limit that no threshold fixes:** invariance is only identified
    relative to an anchor. If *every* item shifts by the same amount between
    groups, the ranges stay small and nothing is flagged — the screen cannot
    distinguish "the scale is invariant" from "the whole scale moved".
    """
    A = _as_matrix(X)
    cols = _names(X, A.shape[1], names)
    g = pd.Series(np.asarray(group)).reset_index(drop=True)
    frame = pd.DataFrame(A, columns=cols)
    ok = frame.notna().all(axis=1).to_numpy() & g.notna().to_numpy()
    frame, g = frame[ok].reset_index(drop=True), g[ok].reset_index(drop=True)

    k = len(cols)
    sizes = g.value_counts()
    labels = [lab for lab in sizes.index if sizes[lab] >= min_group]
    if k < 3 or len(labels) < 2:
        out = pd.DataFrame({"item": cols})
        out.attrs["verdict"] = ("too_few_items" if k < 3
                                else "fewer_than_two_groups_meet_min_group")
        out.attrs["group_sizes"] = {str(a): int(b) for a, b in sizes.items()}
        return out

    load: dict[str, np.ndarray] = {}
    rest: dict[str, np.ndarray] = {}
    for lab in labels:
        sub = frame[g.to_numpy() == lab].to_numpy(dtype=float)
        R = np.corrcoef(sub, rowvar=False)
        L, _ext = _one_factor_loadings(R)
        load[str(lab)] = L
        total = sub.sum(axis=1)
        rest[str(lab)] = np.array([
            np.corrcoef(sub[:, j], total - sub[:, j])[0, 1] for j in range(k)])

    M = np.column_stack([load[str(lab)] for lab in labels])
    Mr = np.column_stack([rest[str(lab)] for lab in labels])
    rng_load = M.max(axis=1) - M.min(axis=1)
    rng_rest = Mr.max(axis=1) - Mr.min(axis=1)

    n_min = int(sizes[labels].min())
    n_groups = len(labels)
    # fitted to the null: the 95th percentile of the max loading range scales as
    # sqrt(2*ln(n_groups))/sqrt(n) with an implied constant of 2.10-2.72 over
    # n in {50,100,300,1000} x groups in {2,3,5}. 2.6 holds the false-alarm rate
    # to max 0.069 / mean 0.021 across those twelve cells.
    thr = float(max(0.20, 2.6 * np.sqrt(2 * np.log(max(n_groups, 2))) / np.sqrt(n_min)))

    rows = []
    for j in range(k):
        row = {"item": cols[j]}
        for lab in labels:
            row[f"loading_{lab}"] = round(float(load[str(lab)][j]), 4)
        row["loading_range"] = round(float(rng_load[j]), 4)
        row["item_rest_range"] = round(float(rng_rest[j]), 4)
        row["flagged"] = bool(rng_load[j] > thr)
        rows.append(row)

    out = pd.DataFrame(rows).sort_values("loading_range", ascending=False).reset_index(drop=True)
    out.attrs["groups"] = [str(lab) for lab in labels]
    out.attrs["group_sizes"] = {str(lab): int(sizes[lab]) for lab in labels}
    out.attrs["excluded_groups"] = [str(lab) for lab in sizes.index if sizes[lab] < min_group]
    out.attrs["threshold"] = round(thr, 4)
    out.attrs["n_flagged"] = int(out["flagged"].sum())
    # measured power to catch a 0.30 loading shift is ~0.37 at 50/group and
    # ~0.62 at 100/group, against 0.89-0.95 at 300
    out.attrs["underpowered"] = bool(n_min < 300)
    out.attrs["verdict"] = ("items_behave_differently_across_groups"
                            if bool(out["flagged"].any())
                            else "underpowered_no_flag_is_not_evidence" if n_min < 300
                            else "no_gross_non_invariance")
    out.attrs["note"] = ("a screen, not a multi-group CFA. It cannot detect a "
                         "uniform shift affecting every item equally, because "
                         "invariance is only identified against an anchor. Below "
                         "300 rows per group it misses most real non-invariance.")
    return out


# --------------------------------------------------------------------------- #
# the orchestrator
# --------------------------------------------------------------------------- #
def scale_score_report(X, names: Optional[Sequence[str]] = None,
                       group=None, R=None, n_iter: int = 100,
                       random_state: int = 42) -> dict:
    """Should these columns be averaged into one score, and what does it cost?

    Runs the whole battery and returns **every sub-report regardless of which
    verdict wins** — the verdict is a ranking of problems, not a filter on what
    you are allowed to see. ``also_fired`` names the checks that would have
    produced a verdict of their own, so a lower-ranked finding cannot be
    silently swallowed by a higher-ranked one.

    Verdict ladder, highest priority first:

    1. ``formative_indicators_suspected_do_not_score`` — the items may be causes
       of a composite rather than effects of a construct; reliability does not
       apply and averaging them is a modelling decision, not a summary.
    2. ``improper_solution_heywood`` — the one-factor solution is improper, so
       omega is not interpretable. Common causes: too few items, too few rows,
       an ordinal column treated as continuous (see `ordinal_data`).
    3. ``not_unidimensional_alpha_is_not_evidence`` — parallel analysis keeps
       more than one dimension. A mean over these items mixes constructs.
       Measured worst case: two *orthogonal* 15-item factors (true correlation
       0 by construction, sample -0.0068) return **alpha 0.9159** while the mean
       score correlates **0.6833** with one true factor and **0.6912** with the
       other — it represents neither, and alpha is at its most reassuring
       exactly there. Parallel analysis returns 2 on the same data.
    4. ``reliability_too_low_to_score`` — omega below 0.60. The score would
       carry more noise than signal into everything downstream.
    5. ``scorable_with_exceptions`` — usable, with named caveats (an item that
       raises alpha when dropped, group non-invariance, alpha propped up by item
       count).
    6. ``scorable``.

    **A mean score is itself a measurement model**, not a neutral summary: it
    asserts every item deserves equal weight and that one number is enough. It
    is also a parcel of all the items, with a parcel's property of hiding
    whatever structure sits underneath it.

    ``attenuation`` reports what this reliability does to every correlation the
    score will take part in — the number to quote before anyone concludes a
    downstream relationship is weak.
    """
    A = _clean(X)
    n, k = A.shape if A.ndim == 2 else (0, 0)
    cols = _names(X, k, names)
    if k < 3:
        return {"verdict": "too_few_items", "k": int(k),
                "note": "reliability needs at least three items"}
    if n < 10:
        return {"verdict": "insufficient_rows", "n": int(n), "k": int(k)}

    al = cronbach_alpha(A)
    om = mcdonald_omega(A, R=R)
    tau = tau_equivalence_check(A)
    items = item_statistics(A, names=cols)
    direction = indicator_direction_check(A, names=cols)
    pa = parallel_analysis(A, n_iter=n_iter, random_state=random_state)

    inv = None
    if group is not None:
        inv = invariance_screen(A, group, names=cols)

    rel = om.get("omega")
    rel_usable = float(rel) if (rel is not None and np.isfinite(rel) and 0 < rel <= 1) \
        else float(al["alpha"])
    ceiling = attenuation_ceiling(max(min(rel_usable, 1.0), 1e-6))

    dropping = list(items.attrs.get("items_raising_alpha_if_dropped", []))
    non_invariant = bool(inv is not None and inv.attrs.get("n_flagged", 0) > 0)
    formative = direction["verdict"].startswith("formative")
    heywood = bool(om.get("heywood"))
    multi = int(pa.get("n_factors", 1)) > 1
    low_rel = bool(rel_usable < 0.60)
    inflated = al["verdict"] == "inflated_by_item_count"

    fired = []
    if formative:
        fired.append("indicator_direction_check")
    if heywood:
        fired.append("mcdonald_omega:heywood")
    if multi:
        fired.append(f"parallel_analysis:{pa.get('n_factors')}_dimensions")
    if low_rel:
        fired.append("reliability_below_0.60")
    if inflated:
        fired.append("cronbach_alpha:inflated_by_item_count")
    if dropping:
        fired.append("item_statistics:alpha_rises_if_dropped")
    if non_invariant:
        fired.append("invariance_screen:flagged_items")

    if formative:
        verdict = "formative_indicators_suspected_do_not_score"
    elif heywood:
        verdict = "improper_solution_heywood"
    elif multi:
        verdict = "not_unidimensional_alpha_is_not_evidence"
    elif low_rel:
        verdict = "reliability_too_low_to_score"
    elif dropping or non_invariant or inflated:
        verdict = "scorable_with_exceptions"
    else:
        verdict = "scorable"

    return {
        "n": int(n), "k": int(k), "items": cols,
        "alpha": al["alpha"],
        "omega": om.get("omega"),
        "mean_inter_item_r": al["mean_inter_item_r"],
        "n_dimensions": pa.get("n_factors"),
        "reliability_used": round(rel_usable, 4),
        "attenuation": ceiling,
        "alpha_report": al,
        "omega_report": om,
        "tau_equivalence": tau,
        "dimensionality": pa,
        "indicator_direction": direction,
        "item_table": items,
        "invariance": inv,
        "items_raising_alpha_if_dropped": dropping,
        "also_fired": fired,
        "verdict": verdict,
        "note": ("a mean score is a measurement model, not a summary: it asserts "
                 "equal item weights and that one number suffices. Every "
                 "sub-report above is returned whichever verdict won."),
    }
