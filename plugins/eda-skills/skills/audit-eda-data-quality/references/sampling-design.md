# Sampling design: how many independent rows do you actually have?

Every inferential number this project produces — a confidence interval, a
bootstrap, a PSI reliability guard, a chi-square, a correlation p-value, a
significance-based feature screen — assumes rows are independent draws from the
population you want to talk about. Datasets are rarely collected that way.
Pupils sit inside classes, readings inside sensors, sessions inside users,
claims inside policies, households inside census tracts. Rows may also carry
unequal selection weights because some subgroup was deliberately oversampled.

`scripts/sampling_design.py` quantifies the consequence. This is an audit-stage
question, not a modelling one: the deliverable is *the effective sample size and
which later claims it invalidates*, not a survey-weighted estimator.

## The two questions to ask at intake

1. **What is a row nested in?** (user, device, school, household, session,
   site, day) — this is the cluster.
2. **Was every row equally likely to be sampled?** If not, where are the
   weights and what generated them?

If the answer to (1) is "nothing" and to (2) "yes", the design effect is 1 and
this whole file is a no-op. Say so explicitly in the audit rather than leaving
it unexamined — an unstated assumption is how this defect survives.

## Design effect and effective sample size

`deff` is the factor by which the sampling variance of an estimate is inflated
relative to a simple random sample of the same size. `n_eff = n / deff`.

| quantity | formula | verified |
|---|---|---|
| mean / rate under clustering | `1 + (m0 − 1)·ICC` | predicted 1.95 / 3.85 / 6.70 at ICC 0.05 / 0.15 / 0.30, measured 1.93 / 4.35 / 7.06 |
| unequal weights | `n·Σw² / (Σw)²` (Kish) | predicted 1.11 / 1.67 / 2.78, measured 1.10 / 1.62 / 2.81 |
| **association between two columns** | `1 + (m0 − 1)·ICC_x·ICC_y` | restores nominal α (0.045–0.052) across 8 configurations |

`m0` is Kish's mean cluster size, which equals the plain mean when clusters are
equal-sized. **The three are different numbers and are not interchangeable.**

### What ignoring it costs

60 clusters × 25 rows, nominal 95% CI for the mean:

| ICC | n rows | n_eff | coverage, naive | coverage, cluster-aware |
|---|---|---|---|---|
| 0.00 | 1500 | 1500 | 0.945 | 0.941 |
| 0.05 | 1500 | 682 | **0.817** | 0.947 |
| 0.15 | 1500 | 326 | **0.637** | 0.947 |
| 0.30 | 1500 | 183 | **0.488** | 0.949 |

At ICC 0.30 a "95%" interval is right less than half the time. Note that the
naive interval is not merely *slightly* optimistic — it is reporting a precision
the data never contained.

## Where clustering actually bites — and where it does not

A first run of this analysis found **no** inflation at all in a chi-square test
on clustered rows, which contradicted the expectation. The reason turned out to
be the rule worth remembering:

> Clustering inflates contrasts that vary **between** clusters. It leaves
> contrasts that vary **within** a cluster alone.

Same null test, 50 clusters × 20 rows, no real group effect:

| ICC | group varies WITHIN cluster | group is a CLUSTER-LEVEL property |
|---|---|---|
| 0.00 | 0.039 | 0.038 |
| 0.10 | 0.038 | **0.184** |
| 0.30 | 0.049 | **0.359** |
| 0.50 | 0.043 | **0.483** |

So "the data are clustered, therefore every test is broken" is over-broad. A
comparison of, say, two payment methods that both occur inside every user is
unaffected; a comparison of two *cohorts of users* is badly affected.

The same logic explains the product rule for associations. If only one of the
two columns carries cluster structure, the product `ICC_x·ICC_y ≈ 0` and no
correction is needed — measured false-positive rate 0.047 with ICC_x = 0.60 and
ICC_y = 0.00. When both are clustered, the naive test collapses:

| ICC_x = ICC_y | naive false-positive rate | corrected |
|---|---|---|
| 0.05 | 0.053 | 0.049 |
| 0.15 | 0.110 | 0.047 |
| 0.30 | **0.272** | 0.047 |
| 0.60 | **0.525** | 0.050 |

At ICC 0.60, more than half of all *independent* column pairs look
"significantly correlated". Any correlation heat map, redundancy prune, or
univariate screen run on such data is reading cluster structure as signal.

**Do not substitute the mean's deff here.** Using `1 + (m0−1)·ICC` to correct a
correlation drove the false-positive rate to 0.002 against a nominal 0.05 — a
massive over-correction that would silently delete real features. The corrected
test still detects real effects: at true r = 0.20 it rejected 95.5% of the time,
at r = 0.30, 100%.

## Overlapping labels: the dependence you build yourself

Clustering arrives with the data. This one you create, by defining a label over
a forward span: "return over the next 20 days", "churn within 90 days",
"readmission within 30 days", any rolling sum, max, or count. Row `t` and row
`t+1` then share `h−1` of their `h` ingredients. Nothing in the schema shows
it — the column looks like one number per row.

Two quantities, and conflating them is the trap:

| quantity | value | what it is for |
|---|---|---|
| uniqueness | `1/h` | the correct **sample weight** — how much of a label is its own |
| design effect | `1 + (h−1)(2h−1)/(3h)` → `2h/3` | the correct **variance inflation** for anything estimated on those rows |

Uniqueness verified exactly (measured mean 0.202 / 0.052 / 0.022 against 1/h =
0.200 / 0.050 / 0.020 at h = 5 / 20 / 50). The design effect is the Bartlett
sum of the squared triangular autocorrelation `ρ_k = 1 − k/h` that a
rectangular window induces; measured 3.34 / 13.43 / 33.28 against a predicted
3.40 / 13.35 / 33.34.

**Using `1/h` as the variance inflation over-corrects badly.** False-positive
rates for a correlation between two *independent* forward-window series
(α = 0.05, n = 1000):

| h | naive | corrected by `h` | corrected by the formula |
|---|---|---|---|
| 1 | 0.049 | 0.049 | 0.046 |
| 5 | **0.290** | 0.017 | 0.045 |
| 20 | **0.580** | 0.012 | 0.051 |
| 50 | **0.740** | 0.011 | 0.045 |

Uncorrected, three-quarters of independent pairs read as significant at h = 50.
Corrected by `h`, alpha collapses to 0.011 and real features get deleted. This
is the same shape of error as using the mean's design effect on an association,
above — the right correction for one job is the wrong correction for another.

The exact form matters at small `h`: at h = 2 it gives α = 0.057 where the
`2h/3` limit gives 0.071, and at h = 1 it returns exactly 1.0 where `2h/3`
would claim 0.67 for data that has no overlap at all.

Assumes a rectangular window of constant length. For ragged spans, decayed
weights, or per-row horizons use `label_concurrency` with explicit start/end
bounds, and treat the implied deff as an approximation — prefer a block
bootstrap when the spans are genuinely irregular.

## A group-aware split does not fix inference

The project already recommends group-aware splits for repeated entities. That
is a **leakage** control, and it does not address this problem at all. Measured
on the same clustered null data:

- false-positive rate on a random-row half: 0.164
- false-positive rate on a group(cluster) half: **0.247**

The group split is *worse* here, because concentrating whole clusters in one
partition lowers the number of independent units in it. Both controls are
needed and they are answering different questions: the split protects the
estimate of generalization error, `n_eff` protects every claim made during EDA.

## Weights

Only the *variability* of weights costs precision; the formula is
scale-invariant, so raw weights, normalized weights and inverse selection
probabilities all give the same answer.

Combining the two design effects as `deff_mean × deff_weights` is the standard
working approximation. Measured behaviour, which is the **opposite** of the
natural guess:

- weights that are a **cluster-level** property (one weight per school): the
  product is essentially exact — empirical/predicted 1.05 / 0.99 / 0.99;
- weights varying **within** clusters: the product **overstates** deff —
  empirical/predicted 0.70 / 0.70 / 0.67, conservative by ~1.4×.

Averaging many weights inside a cluster makes cluster totals more nearly equal
than the raw weight spread implies. Treat `deff_total` as accurate for
cluster-level weights and as a safe upper bound otherwise.

## Reading the output honestly

- **Unequal cluster sizes make `deff_mean` a lower bound.** At ICC 0.30 the
  empirical/predicted ratio grew 1.03 → 1.14 → 1.27 → 1.35 as cluster sizes
  spread from 18–22 to 10–30, 2–40, 1–60. With ragged clusters, report the
  number as "at least".
- **The verdict is gated by an F test on purpose.** The ICC point estimate
  alone cries wolf: on genuinely independent rows the estimator returns
  ICC ≈ 0.003, which `(m0−1) = 19` multiplies into `deff > 1.2` in 10–22% of
  samples. With the gate, the non-negligible rate on independent rows is
  5.2 / 3.0 / 0.5 / 4.5% — the nominal 5%. The cost sits at the bottom of the
  range: true ICC of 0.01 / 0.02 is flagged only 30% / 63% of the time, where
  deff is 1.20 / 1.36 and barely consequential. From ICC 0.05 up, detection
  was 100%.
- **One row per cluster means deff = 1 exactly.** Passing an ID column as
  `group` is a common slip; the function answers it cleanly instead of
  returning `NaN`.

## What to do with the number

1. **Report it.** Every CI, bootstrap interval, and p-value produced elsewhere
   in the audit inherits it. A finding stated as "significant" on 1500 rows
   with `n_eff = 183` should say so.
2. **Recheck the guards that are sample-size-based.** The PSI reliability guard
   (≥50 rows per bucket, see `distributions-outliers.md`) counts rows, not
   independent observations; under clustering it is optimistic by `deff`.
3. **Prefer cluster-level aggregates for cluster-level questions.** Collapsing
   to one row per cluster costs no real information for a between-cluster
   contrast and makes the independence assumption true rather than assumed.
4. **Do not "fix" clustering by deleting rows.** Duplicated or repeated
   measurement is information about the process; the defect is in the
   inference, not the data. (Compare the duplicates-as-legitimate-replication
   case in `consistency-validity.md`.)
5. **Carry it into the split decision.** Clustering is simultaneously an
   inference problem (this file) and a leakage problem
   (`splits-leakage.md` → group-aware split). Handle both.

## Non-probability samples

Weights and design effects assume every unit had a known, non-zero selection
probability. Convenience samples, opt-in panels, social-media polls, and
snowball/respondent-driven recruitment do not satisfy this, and **no weighting
scheme recovers what was never sampled**. For those, the honest audit output is
a description of the achieved sample plus an explicit statement of the
population it can and cannot speak for — the same discipline as the
missing-rows / survivorship section in `consistency-validity.md`. Increasing `n`
does not help: large samples cure variance, never selection bias.
