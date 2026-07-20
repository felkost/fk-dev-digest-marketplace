# Scale reliability, and what it caps

`associations.md` states the attenuation ceiling `r_obs = r_true·√(rel_x·rel_y)` in three separate
places and computes `rel` in none of them. `consistency-validity.md` names the dead end outright:
repeated measurements or parallel instruments "are the only in-data evidence of reliability;
otherwise it is a domain question". **A multi-item scale is that repeated measurement** — the items
*are* the parallel instruments — so this file closes the loop: estimate reliability from the items,
then say what it costs every correlation the scale takes part in.

Everything here is `scripts/reliability.py`. Measurements are ours unless stated.

## Alpha is not what it is used for

`alpha = k/(k−1)·(1 − Σvar_i/var_total)`. The standardized form is Spearman-Brown on the mean
inter-item correlation, `k·r̄/(1 + (k−1)·r̄)`, and *that* form is the warning label: **alpha is a
function of two things only — how many items there are, and how much they share on average.**
Neither term knows what the items mean.

**The 0.70 convention is clearable by item count alone.** Population correlation matrices, so these
are exact and contain no sampling at all:

| design | mean inter-item r | alpha | items needed for 0.70 |
|---|---|---|---|
| 6 items, loading 0.70 | 0.4900 | 0.8522 | 3 |
| 15 items, loading 0.40 | 0.1600 | 0.7407 | 13 |
| 30 items, loading 0.30 | 0.0900 | 0.7479 | 24 |
| 40 items, loading 0.25 | 0.0625 | 0.7273 | 35 |

Forty items each sharing 6% of their variance with the next clear "alpha > 0.70". `cronbach_alpha`
reports `k_for_alpha_070` for exactly this reason: it turns a passing grade back into the trade it
was made of.

**A briefed claim died here and is recorded so it is not re-briefed.** "Alpha rises when junk items
are added" is **false**. Appending 0/2/4/6 items at loading 0.10 to six items at loading 0.70 drove
population alpha *down* monotonically — **0.8522 / 0.7681 / 0.7168 / 0.6823**. Junk items lower the
mean inter-item correlation faster than the extra `k` raises alpha. The real trap is *many mediocre*
items, not a few bad ones.

**The headline: alpha is not a dimensionality statistic.** Two **orthogonal** factors — true factor
correlation 0 by construction — at loading 0.75:

| items per factor | total k | mean inter-item r | alpha |
|---|---|---|---|
| 5 | 10 | 0.2500 | 0.7692 |
| 10 | 20 | 0.2664 | 0.8790 |
| 15 | 30 | 0.2716 | **0.9179** |

An alpha of 0.92 on data with two unrelated constructs in it. Worse, the mean score built from those
30 items correlates **0.6833** with one true factor and **0.6912** with the other — it represents
neither, and alpha is at its most reassuring exactly there. Parallel analysis returns 2 on the same
data, which is why `scale_score_report` runs it and ranks
`not_unidimensional_alpha_is_not_evidence` above the reliability verdicts.

## Omega, and the honest size of the difference

`omega = (Σλ)²/((Σλ)² + Σψ)` from a one-factor solution. Alpha assumes **tau-equivalence** — every
loading equal — and omega does not. That is the entire difference between them.

Under exact tau-equivalence they are **algebraically the same number**: measured gap ±1.11e-16 at
equal loadings of 0.4 / 0.6 / 0.8. As the loadings spread (mean 0.60, k=6):

| sd(loadings) | alpha | omega | omega − alpha |
|---|---|---|---|
| 0.0000 | 0.7714 | 0.7714 | +0.0000 |
| 0.0748 | 0.7707 | 0.7727 | +0.0020 |
| 0.1497 | 0.7686 | 0.7766 | +0.0081 |
| 0.2245 | 0.7649 | 0.7832 | +0.0183 |

So "alpha underestimates reliability" is **true and almost always negligible** — 0.002 to 0.018 over
the realistic range, reaching ~0.031 only where the weakest item loads 0.20 while the strongest loads
0.95. Prefer omega on principle; it costs nothing and assumes less. But a decision turning on the
third decimal of a reliability estimate is not a decision the data supports. Same shape as round 28's
"PCA loadings matter, PCA scores do not".

### Why the verdict keys on the loading spread and never on the observed gap

This is the round-21/23 threshold bug in a new costume, and it was caught by measuring rather than
assuming. Under *exact* tau-equivalence the population gap is 0, but the **estimated** gap is not
centred on 0 (3000 reps, k=6, loading 0.60):

| n | mean gap | sd of gap | 95th pct |
|---|---|---|---|
| 100 | +0.00284 | 0.00190 | 0.00650 |
| 300 | +0.00090 | 0.00058 | 0.00200 |
| 1000 | +0.00026 | 0.00017 | 0.00060 |

Both bias and spread scale as **1/n**, and that leaves no sample size where a gap-based verdict
works. At n=100 tau-equivalent data exceeds 0.0065 one time in twenty, while a genuinely *mildly*
congeneric scale (sd of loadings 0.075) has a population gap of only **0.0020** — smaller than the
null's own 95th percentile. At n=1000 the null shrinks to 0.0006 and the 0.0020 becomes detectable,
but by then it is far too small to change any decision. **The observed gap is either below its own
noise floor or too small to act on.**

`loading_sd` estimates the quantity directly instead of differencing two near-identical numbers, but
it still needs an n-aware cutoff, because the sd of six *estimated* loadings is positive even when
the true loadings are identical:

| n | mean null loading_sd | 95th pct | mean·√n |
|---|---|---|---|
| 50 | 0.1074 | 0.1751 | 0.760 |
| 100 | 0.0757 | 0.1219 | 0.757 |
| 300 | 0.0436 | 0.0690 | 0.754 |
| 1000 | 0.0236 | 0.0377 | 0.746 |

The last column is flat, so the null is `~0.75/√n` and the shipped cutoff is `max(0.10, 1.4/√n)`.
**A fixed 0.05 cutoff — which this function shipped with before it was measured — declares
tau-equivalent data congeneric 95.2% of the time at n=50 and 83.3% at n=100.** Rates for the shipped
cutoff, 1000 reps of the exact call:

| true sd(loadings) | n=50 | n=100 | n=300 | n=1000 |
|---|---|---|---|---|
| 0.000 (tau-equivalent) | 0.023 | 0.014 | 0.001 | 0.000 |
| 0.150 | 0.329 | 0.742 | 0.999 | 1.000 |
| 0.225 | 0.816 | 0.998 | 1.000 | 1.000 |

Row one is the false-alarm rate; the others are power. The cost is stated rather than hidden: at
n=50 a genuinely congeneric scale is caught a third of the time. That is the right side to err on,
because the thing being detected is worth 0.008.

## What reliability costs: the ceiling and the correction

`attenuation_ceiling(rel_x, rel_y)` returns `√(rel_x·rel_y)` — the correlation two instruments would
show **if they measured the same construct perfectly** and differed only in noise.

| rel_x, rel_y | ceiling |
|---|---|
| 0.90, 0.90 | 0.900 |
| 0.80, 0.80 | 0.800 |
| 0.70, 0.70 | 0.700 |
| 0.60, 0.60 | 0.600 |
| 0.70, 1.00 | 0.837 |

Two scales at the "acceptable" 0.70 cannot correlate above 0.70 even when they are the same thing,
and a genuine 0.80 relation between them reads as **0.56**. No sample size raises this: it is a
property of the instruments. Run it before concluding a hypothesis failed.

`disattenuate` inverts it, and **does not clip the result when it exceeds 1.0** — the same doctrine
`principal_axis_factoring` applies to Heywood cases. An impossible value is information: the
reliability estimates are too low, or the sample is too small. Measured share of impossible
estimates (two 6-item scales, `rel` from each sample's own alpha, 1500 reps):

| r_true | reliability | n=50 | n=200 | n=500 |
|---|---|---|---|---|
| 0.80 | 0.90 | 0.0000 | 0.0000 | 0.0000 |
| 0.80 | 0.70 | 0.0687 | 0.0000 | 0.0000 |
| 0.80 | 0.50 | 0.2947 | 0.0507 | 0.0040 |
| 0.95 | 0.70 | 0.3627 | 0.1740 | 0.0640 |
| 0.95 | 0.50 | 0.4827 | 0.3613 | 0.2347 |

At reliability 0.50 on 50 rows **29% of corrections are impossible**, and against a true 0.95 the
problem does not go away with sample size at all — a third still fail at n=500, because the truth
sits so close to the ceiling that ordinary noise pushes through it.

**Which input to distrust, decomposed.** Re-running the r_true=0.80 cells with reliability plugged in
*at truth*, so only `r_obs` is noisy: 0.0500 / 0.2033 at n=50 for rel 0.70 / 0.50, against
0.0687 / 0.2947 with alpha estimated. So roughly **two thirds of the failures come from noise in the
observed correlation and one third from noise in the reliability estimate.** The correction is not
mainly failing because alpha is badly estimated — it is failing because dividing a noisy number by a
number below 1 amplifies noise. Treat it as a sensitivity statement, never a measurement.

## item_total_r vs item_rest_r

Both are wrong at small `k`, **in opposite directions** — which is the honest form of this finding
and not the one usually stated. True loading 0.50, n=1000, 500 reps:

| k | item_total_r | item_rest_r | true |
|---|---|---|---|
| 3 | 0.7074 | 0.3171 | 0.50 |
| 5 | 0.6319 | 0.3771 | 0.50 |
| 8 | 0.5854 | 0.4170 | 0.50 |
| 15 | 0.5477 | 0.4537 | 0.50 |
| 30 | 0.5235 | 0.4750 | 0.50 |

`item_total_r` is inflated from above by the item's own share of the total. `item_rest_r` is
attenuated from below because a rest-score built from two other items is barely reliable. They
converge on the truth from either side, and **neither is trustworthy on a three-item scale**.

`item_rest_r` is nevertheless the reported column: its error is ordinary attenuation shared by every
item equally, so the *ranking* stays usable, whereas `item_total_r`'s error rewards exactly the items
that dominate the total. `alpha_if_deleted` above the scale's own alpha marks an item whose removal
*improves* consistency — usually a reverse-keyed item nobody recoded. That is a comparison, not a
threshold, so it needs no cutoff.

## Two guards this file exists to raise

### Formative indicators: a category error, not a bad scale

A **reflective** set (anxiety items) are *effects* of a latent variable, so they must intercorrelate.
A **formative** set (income, education, occupation → socioeconomic status) are *causes* of a
composite. They need not correlate, alpha is meaningless on them, and dropping one changes what the
composite **is**. Running reliability analysis on formative indicators will report a broken scale and
invite you to delete the indicator carrying the most unique information.

`indicator_direction_check` fires, and **cannot diagnose** (n=1000):

| design | alpha | omega | mean r |
|---|---|---|---|
| formative: 3 uncorrelated causes | −0.0397 | 0.0285 | −0.0129 |
| bad reflective: 6 items at 0.15 | 0.0878 | 0.0983 | 0.0158 |
| good reflective: 6 items at 0.65 | 0.8190 | 0.8192 | 0.4299 |

Rows one and two are the point: **a formative set and a broken reflective scale are not
distinguishable by these statistics.** A hit is a question for whoever owns the data — *are these
columns effects of one construct, or causes of a composite?* — exactly as `composite_target_probe`
produces a question rather than a verdict.

### Invariance: a screen, calibrated, with its power stated

Comparing scale scores across groups assumes the scale means the same thing in each. `invariance_screen`
gives the cheap version — per-group one-factor loadings and their range — which is enough to decide
whether a multi-group CFA is worth running. **Multi-group CFA itself is out of scope here.** Pass a
period column instead of a group column to ask the same question of time.

An uncalibrated range threshold is a sample-size detector. False alarms on genuinely invariant data
(6 items, loading 0.60, 400 reps) under a **fixed 0.20 cutoff**, share of datasets with ≥1 flag:

| n/group | 2 groups | 3 groups | 5 groups |
|---|---|---|---|
| 50 | 0.757 | 0.960 | **1.000** |
| 100 | 0.422 | 0.725 | 0.953 |
| 300 | 0.013 | 0.062 | 0.147 |
| 1000 | 0.000 | 0.000 | 0.000 |

The shipped threshold is fitted to the null instead: the 95th percentile of the maximum loading range
scales as `√(2·ln(n_groups))/√n` with an implied constant of 2.10–2.72 across those twelve cells, so
the cutoff is `max(0.20, 2.6·√(2·ln(n_groups))/√n_min)`. Both error rates for the shipped call, 400
reps — invariant data (false alarm) against one item whose loading differs by 0.30 in one group
(power):

| n/group | false alarm 2 / 3 groups | power 2 / 3 groups |
|---|---|---|
| 50 | 0.092 / 0.022 | 0.307 / 0.188 |
| 100 | 0.068 / 0.018 | 0.482 / 0.410 |
| 300 | 0.028 / 0.018 | 0.910 / 0.917 |
| 1000 | 0.000 / 0.000 | 0.988 / 0.998 |

**Below 300 rows per group this screen is close to a formality** — it misses two thirds of a 0.30
loading shift at n=50. The `underpowered` attribute and the
`underpowered_no_flag_is_not_evidence` verdict say so rather than letting a clean table imply a clean
result.

**The limit no threshold fixes:** invariance is identified only against an anchor. If *every* item
shifts by the same amount, the ranges stay small and nothing is flagged — the screen cannot separate
"the scale is invariant" from "the whole scale moved".

## A mean score is a measurement model

Averaging items is not a neutral summary. It asserts that every item deserves equal weight and that
one number suffices, and **a mean score is a parcel of all the items** — with a parcel's property of
hiding whatever structure sits underneath. The two-orthogonal-factor result above is the
demonstration: a 30-item mean that correlates ~0.69 with each of two unrelated constructs.

`scale_score_report` ranks the problems highest-first —
`formative_indicators_suspected_do_not_score` → `improper_solution_heywood` →
`not_unidimensional_alpha_is_not_evidence` → `reliability_too_low_to_score` →
`scorable_with_exceptions` → `scorable` — and **returns every sub-report regardless of which verdict
won**, with `also_fired` naming the checks that would have produced a verdict of their own. The
verdict is a ranking of problems, not a filter on what you may see; round 20's `regression_to_mean`
three-tier bug is the precedent for collapsing tiers rather than hiding them.

## Deliberately out of scope

Recorded so a later round does not re-open them as if they were oversights: multi-group and
longitudinal confirmatory factor analysis (only the screen above is kept), item-parcel allocation
studies (only "a mean score IS a parcel" is kept), item response theory, and structural models fitted
after a measurement model. All are modelling, not EDA.
