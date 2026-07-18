# Distribution and outlier checks

## Numerical distributions

- Report center and spread with both classical and robust statistics.
- Report center and spread as a **matched pair** — each center minimizes its own error criterion and pairs with the spread built on the same criterion: mean ↔ standard deviation (L2), median ↔ MAD (L1), midrange ↔ half-range (L∞; maximally outlier-sensitive). `median ± std` mixes criteria and misleads. The family generalizes to Minkowski-p centers; the practical takeaway is the pairing rule, not the exotic centers.

  The pairing is not a convention — it falls out of the fact that **the criterion defines both at once**. Ask "where should I stand so the typical deviation is smallest?" and the answer simultaneously fixes a center *and* the measure of spread around it. Laplace considered several such criteria (minimise the largest residual, the sum of signed residuals, the mean absolute residual) before least squares won, largely because squares are analytically tractable where absolute values are not, and because squared deviations connect to variance, the moments, and the χ²/F distributions. The **sample mean is exactly the least-squares estimator** of a single set of scores. So "which center?" is a choice of loss, and it should follow the decision the number will feed, not habit.

  The direct cost of choosing L2: squaring gives distant points disproportionate say, so least-squares summaries are **highly sensitive to outliers** by construction. That is the reason to pair a robust criterion alongside, not an accident to be patched afterwards.
- Use quantiles and ECDF for heavy tails; use log axes only when values and semantics permit. For inequality-type questions on positive heavy-tailed features, the decile ratio (`decile_ratio`: mean of top 10% over mean of bottom 10%) is an interpretable one-number descriptor.
- Check zero inflation, censoring, truncation, rounding/heaping, multimodality, unit mixtures, and detection limits. For the *mechanism* behind these — which family the generating process implies, why a log is justified, when counts are overdispersed, and whether aggregation preserves the family — see [distribution-families.md](distribution-families.md).
- Compare distributions across target, source, subgroup, time, and proposed split with effect sizes and uncertainty.

### Kurtosis is a tail measure, not "peakedness"

`numeric_summary` reports kurtosis, and the near-universal gloss — "distributions with higher peaks have positive kurtosis" — will send an agent looking in the wrong place. Excess kurtosis is the standardized fourth moment, and `z⁴` is arithmetically dominated by whatever is far from the center. Measured on a standard normal, decomposing `E[z⁴] = 2.9914`:

| region | share of the statistic | share of the rows |
|---|---|---|
| \|z\| < 0.5 | 0.15% | 38.29% |
| \|z\| < 1.0 | 3.75% | 68.26% |
| \|z\| < 1.5 | 18.68% | 86.63% |
| \|z\| < 2.0 | 45.23% | 95.46% |

Two thirds of the rows — the entire peak region — contribute under 4% of the number. The peak is essentially invisible to it.

**Why the misconception survives, and where it breaks.** Across common distributions peak height and kurtosis do move together (Spearman +0.94 over exact values for uniform/normal/Laplace/t(5)/t(8)/t(20)), which is why the rule of thumb usually looks right. It inverts on constructible pairs. Standardized to variance 1, using exact analytic values, not simulation:

| distribution | density at the mode | excess kurtosis |
|---|---|---|
| uniform | 0.2887 | −1.200 |
| normal | 0.3989 | 0.000 |
| **Laplace** | **0.7071** | **+3.000** |
| **t(5)** | **0.4901** | **+6.000** |

The Laplace peak is 44% higher than t(5)'s while its excess kurtosis is half — read as "peakedness", the ranking is backwards. Practical readings: high kurtosis means **rare extreme values relative to a normal**, which is a statement about outlier risk, interval validity and the estimability of the mean (see the CLT subsection above); it says nothing about whether the middle is sharp or flat, and a bimodal or flat-topped variable can carry high kurtosis purely from its tails.

One further caution measured in passing: **sample kurtosis is a poor estimator exactly where it matters**. A t(5) sample of 400 000 draws returned 5.337 against a true 6.000, because the fourth moment of a t(5) barely exists. Treat a large sample kurtosis as a flag to plot the tail (`tail_index`, `family_router`), not as a quantity to compare across columns.

### Histogram bin sensitivity

Histogram shape is a function of the bin count, and no reliable theoretical rule chooses it. On small samples many bins fabricate gaps (a 45-row sample already looks "gappy" at 10 bins); on large samples few bins hide real modes. Before claiming multimodality, rerun the histogram across several bin counts (`binwidth_sensitivity`, e.g. 5/10/15/30) and claim it only when the mode count is stable — or confirm with a KDE/dip test. Small n → few bins.

### "The 25th percentile" is not one number

There are nine documented interpolation methods for a sample quantile, and
tools disagree **by default**:

- `numpy.percentile` / `pandas.quantile` default to linear interpolation
  (R type 7). This is exactly the Python stdlib's `statistics.quantiles(...,
  method="inclusive")` — verified to full floating-point equality at
  n = 9, 11, 25, 101.
- `statistics.quantiles` itself defaults to **`"exclusive"`** (`i/(m+1)`),
  which is a different number.

Measured gap between those two defaults, as a share of the sample sd: **21.3%
at n=8, 31.1% at n=12, 14.1% at n=20**, then 1.0% at n=50, 0.2% at n=100,
0.01% at n=10 000. Across all nine numpy methods the q25 spread was 23.4% of an
sd at n=10 and 0.5% at n=200. On a small sample the convention can outweigh the
signal.

**The value converges; the decision it drives does not.** For IQR fences the
two conventions disagreed on at least one flagged point in:

| n | normal | lognormal |
|---|---|---|
| 10 | 0.215 | 0.288 |
| 50 | 0.154 | 0.258 |
| 200 | 0.131 | 0.235 |
| 1000 | 0.124 | 0.253 |
| 5000 | 0.128 | 0.250 |

(3000 reps per cell, ±0.007.) It plateaus near **12%** for normal data and
**25%** for heavy-tailed data instead of vanishing: the fence gap shrinks with
`n`, but proportionally more points sit inside that shrinking gap. Heavy tails
sit higher because more mass lands near the upper fence.

Both facts hold at once — on a large sample the quantile *value* is
convention-free while the *outlier flag on a borderline row* is not. Practical
consequences:

- `quantile_convention_report` measures this on your data and returns three
  states: `convention_matters` (numbers differ by >5% of an sd),
  `borderline_points_only` (numbers agree, some row still changes side),
  `convention_irrelevant`.
- `borderline_points_only` is not a defect to repair. It is the reason not to
  hang an irreversible action on one borderline row — prefer a review queue.
- State the convention next to any published quantile, fence, or decile cut.
  This also applies to PSI reference bins and percentile bootstrap intervals,
  which are quantiles too.
- Reproducibility: a collaborator "getting different outliers" from the same
  data is often this, not a bug.

### Uncertainty of reported statistics

A center/spread/coefficient that grounds a decision needs an uncertainty measure, especially on small samples (`bootstrap_ci`):

- **Percentile (non-pivotal) bootstrap** — CI from the quantiles of the bootstrap distribution; free of a *distributional* assumption, the default. It is **not** free of a sample-size assumption — see the next subsection, where it is measurably *worse* than a t-interval on small samples.
- **Pivotal bootstrap** — `estimate ± z·std(bootstrap)`; assumes the bootstrap distribution is roughly Gaussian — inspect its histogram before using it for skewed statistics.
- **Comparing two groups:** build the CI of the *difference* (`bootstrap_diff_ci`), not two separate CIs. Two independent 95% intervals that fail to overlap correspond to ≈90% (0.95²) joint confidence, not 95%; overlap does not prove equality either.

### "n > 30 is enough for the CLT" is a claim about symmetry, not about `n`

Introductory guides put a fixed number on it — 30, or 50 — with no condition attached. The number that actually governs it is the population's **skewness**, because the skewness of the sampling distribution of the mean falls as `skew(x)/√n`. Verified directly on lognormal(0,1) (population skew 6.185): measured skew of the sample mean 1.2551 / 0.6355 / 0.3092 / 0.1663 at n = 25 / 100 / 400 / 1600, against `6.185/√n` = 1.2370 / 0.6185 / 0.3092 / 0.1546.

So a fixed `n` threshold cannot work. Measured 95% t-interval coverage of the **mean** (20 000 replicates per cell, nominal 0.950):

| distribution | pop skew | n=10 | n=30 | n=50 | n=100 | n=250 | n=1000 | n=2000 |
|---|---|---|---|---|---|---|---|---|
| normal(0,1) | 0.00 | 0.948 | 0.952 | 0.947 | 0.950 | 0.949 | 0.950 | 0.948 |
| uniform(0,1) | 0.00 | 0.945 | 0.949 | 0.951 | 0.949 | 0.950 | 0.950 | 0.948 |
| exponential(1) | 2.00 | 0.901 | 0.928 | 0.934 | 0.942 | 0.944 | 0.950 | 0.952 |
| poisson(0.1) | 3.16 | 0.623 | 0.949 | 0.870 | 0.932 | 0.937 | 0.946 | 0.947 |
| lognormal(0,1) | 6.18 | 0.840 | 0.884 | 0.900 | 0.917 | 0.933 | 0.945 | 0.949 |
| pareto(α=3) | 16.0 | 0.822 | 0.865 | 0.882 | 0.906 | 0.925 | 0.939 | 0.946 |
| lognormal(0,2) | 414 | 0.573 | 0.648 | 0.695 | 0.738 | 0.795 | 0.851 | **0.874** |

At the advertised n=50 a symmetric variable is fine at n=10, while lognormal(0,1) reads 0.900 and lognormal(0,2) reads 0.695. The last row still has not arrived at n=2000. Revenue per user, session duration, claim size and time-to-event all live in the bottom half of that table.

**The failure is one-sided, which is the part that matters.** At n=50, counting which side the interval landed on (nominal 0.025 each):

| distribution | interval entirely **below** the truth | entirely above |
|---|---|---|
| normal(0,1) | 0.0257 | 0.0233 |
| exponential(1) | 0.0587 | 0.0099 |
| lognormal(0,1) | **0.0943** | 0.0028 |
| pareto(α=3) | 0.1150 | 0.0023 |
| lognormal(0,2) | **0.3054** | 0.0001 |

A right-skewed sample usually misses the rare large values that carry the mean, so both `x̄` and `s` come in low and the whole interval sits *under* the truth. You do not get a slightly-too-narrow interval; you get a confident understatement, ~34× more often than an overstatement on lognormal(0,1). Any "average revenue per user" quoted from a small sample is biased low by construction.

The `n > 25·skew²` rule of thumb is worth knowing but is not a substitute for measuring: it landed exactly right on exponential (predicted 100, measured 100) and close on lognormal(0,1) (956 vs 750), but was 6× too conservative on pareto(α=3) (6400 vs 1000) and 8× too conservative on poisson(0.1) (250 vs 30). Note also that poisson(0.1)'s coverage is **not monotone in n** (0.623 → 0.949 → 0.870 → 0.932): with a discrete low-rate count the interval's coverage oscillates as the attainable sample means change, so "the n where it first looks fine" is a meaningless summary there. Read the curve, not one cell.

**The bootstrap is not the escape hatch here, and this corrects the bullet above.** Measured on the same populations (3000 replicates, B=2000 resamples), comparing the t-interval against percentile and BCa bootstraps:

| distribution | n | t-interval | percentile | BCa |
|---|---|---|---|---|
| normal(0,1) | 10 | **0.951** | 0.890 | 0.888 |
| normal(0,1) | 30 | 0.953 | 0.940 | 0.939 |
| exponential(1) | 10 | 0.896 | 0.856 | 0.870 |
| exponential(1) | 50 | 0.941 | 0.933 | 0.939 |
| lognormal(0,1) | 30 | 0.883 | 0.876 | 0.893 |
| lognormal(0,1) | 50 | 0.904 | 0.899 | 0.911 |
| pareto(α=3) | 50 | 0.875 | 0.875 | 0.890 |

Two corrections to the common instinct. First, on **small** samples the percentile bootstrap is *worse* than the t-interval, including on a perfectly normal population (0.890 vs 0.951 at n=10) — "assumption-free" is not "accurate". Second, BCa, which exists precisely to correct bias and skew, recovers only about a percentage point on the skewed cases (0.899 → 0.911 at lognormal n=50) and does not reach nominal either. The mechanism is the same one that breaks the t-interval: the bootstrap resamples the rows you *have*, and a small right-skewed sample usually contains none of the large values that carry the mean. **No interval formula can recover mass that was never drawn.**

What to do instead, in order of preference: get more rows; change the estimand to something the sample can actually support (median, trimmed mean, or the geometric mean — all far better behaved here than the arithmetic mean); or model the family and estimate the mean through it (`mean_variance_scaling` identifies the mechanism, see `distribution-families.md`). Reporting an arithmetic mean with a 95% interval on n=50 lognormal data is reporting a number whose stated uncertainty is wrong by a factor of two in one direction only — the honest output is the skewness, the `n`, and the caveat.

## A p-value answers a question about `n` as much as about the data

This is the single most reusable caveat in this module, and it cuts **both** ways. Every test statistic here — dispersion, rate homogeneity, distribution shift, normality — reports significance, and none of them lets significance drive a verdict. The reason is that a p-value mixes effect size with sample size, so the same data can produce either verdict by changing `n` alone.

**Large `n`: everything is significant.** The two-sample KS critical value falls as `1.36·√(2/N)`, so resolution grows without bound. Measured on a shift of 0.005 sd — far too small to move any prediction — the KS p-value runs:

| N | 10² | 10³ | 10⁴ | 10⁵ | 10⁶ |
|---|---|---|---|---|---|
| KS p | 0.70 | 0.65 | 0.39 | 0.19 | **0.0068** |
| PSI | 0.202 | 0.024 | 0.0013 | 0.0003 | 0.00003 |
| Wasserstein / sd | 0.158 | 0.074 | 0.016 | 0.007 | 0.005 |

Nothing about the data changed; only `n` did. At production volumes every column is "significantly" drifted, so a p-value threshold on a monitor is an alarm that never stops ringing — retraining triggered on noise, at real compute cost, with alert fatigue as the second-order damage. Note what the magnitude columns do instead: they *converge on the truth* (0.005) as `n` grows, which is the behaviour you want from a monitor.

The last column is one draw, and 0.005 sd at N=10⁶ happens to sit right on the knife edge — its systematic `D = 0.001995` against a critical value of `0.001923` — so rejection there is only ~73% reliable (measured over 15 runs). Push the shift to 0.01 sd, still far too small to matter, and rejection is **15/15** with mean p ≈ 0.0000 while PSI is 0.000111, three orders of magnitude below the "stable" threshold. The trend is the point, not any single cell.

**The test is not broken, and that matters.** Under a true null the KS rejection rate stayed at ~0.05 for every `n` from 50 to 20 000 — perfectly calibrated. It is answering "is there *any* difference at all", faithfully. That is simply not the question. Ask *how much* difference (`distribution_shift` → PSI, Wasserstein), then calibrate the threshold against something you care about — historical episodes where a known shift cost a known amount of model performance — rather than against 0.05.

**Small `n`: nothing is significant, and "post-hoc power" cannot rescue it.** The mirror-image error is reading a non-significant result as evidence of no effect. The standard reviewer request — "report the observed power for the null finding" — is circular: observed power computed from the *observed* effect size is a deterministic decreasing function of the p-value. Measured over 3000 simulated two-sample studies, Spearman rank correlation between p and observed power was **−1.000000** exactly; observed power at the p=0.05 boundary is ≈0.50, and the maximum observed power among *all* non-significant studies was 0.5027. So "the finding was non-significant" and "observed power was low" are the same sentence twice — the calculation cannot discover anything p did not already say. Power analysis is worth doing **prospectively**, to decide whether a study/probe can detect the effect you care about; computing it after a null result is theatre.

The EDA consequence, since this project runs feature-ablation A/B probes: a non-significant gain from a feature set is *not* evidence the feature is useless. It is evidence that this sample could not resolve it. Report the effect size and its interval (`bootstrap_diff_ci`, `paired_feature_significance`), and treat "no detectable gain at this n" as a statement about the experiment, not about the feature. Compare to the structurally identical trap already documented for outliers: `|z| > 3` cannot fire at all when n ≤ 10, because `max|z| = √(n−1)` — an empty result there means too little data, not no outliers.

Sources: the large-`n` direction from *Top 25 ML System Design Interview Questions* (Hao Hoang, 2025) §2.6 "The P-Value Mirage" — whose arithmetic checks out (`D_crit = 0.001923` vs `D = δ/√(2π) = 0.001995`, so it does reject); the small-`n` direction from Quantitude S1E02 "Statistical Power Struggles" (Curran & Hancock), and the observed-power result is Hoenig & Heisey (2001), *The Abuse of Power*. Measurements above are ours.

### Measuring shift: read PSI against its null floor, not against 0.1

`distribution_shift` reports PSI, Wasserstein (raw and in sd units), and the test p-value as context. Two implementation points worth knowing, both measured:

- **PSI has a sample-size floor that the usual rule of thumb ignores.** "PSI < 0.1 stable, > 0.25 major" is quoted without an `n` condition, but PSI is a J-divergence between two multinomials whose null expectation is `(B−1)·(1/n_ref + 1/n_cur)` — verified within 5% across 14 configurations (varying buckets, sample sizes, unequal `n`, non-normal reference; quantile binning makes it distribution-free). On **identical** distributions with 10 buckets that floor reads PSI **0.64 at n=50** and **0.20 at n=100** — the raw rule of thumb would report "major drift" between a sample and itself. Read `psi_ratio` (PSI over its null expectation) and treat raw PSI against a fixed threshold only when `psi_reliable` is True (≥ ~50 rows per bucket). Fewer buckets lower the floor proportionally.
- **Floor the proportions, not the log ratio.** A widely-copied PSI snippet writes `np.log(expected/actual + 1e-10)`; the epsilon is added to the *ratio*, which does not protect a zero denominator — verified to return `inf` on a current sample that simply never reaches the reference's lowest decile. Floor each proportion at a half-count (`0.5/n`) per side instead, so the floor scales with the sample rather than setting the answer: with a `1e-12` floor, one unseen category at 0.5% frequency contributed 0.111 to PSI single-handedly, enough to flip the verdict; at a half-count floor the same case reads 0.0126 and `stable`, with the real signal surfaced separately as `unseen_categories`.

Bins are taken from the **reference** quantiles only, never pooled, which keeps the statistic train-only fittable and makes it deliberately asymmetric (measured PSI 3.72 vs 1.89 for normal-vs-lognormal in the two directions) — pass the training sample as `reference`.

## Categorical distributions

- Report cardinality, entropy, Gini index (qualitative variance `1 − Σp²` — the error rate of proportional prediction; entropy and Gini nearly coincide at small p), top-level concentration, rare-level counts, and unseen-level rates.
- Examine combinations of rare levels with source/time; apparent rare categories may be parsing errors or source-specific codes.

## Small groups produce extreme rates

When ranking subgroups by a target rate (defect rate by site, conversion by cohort, disease by county), the smallest groups occupy **both** ends of the ranking by pure chance — the variance of a rate scales as 1/n (the kidney-cancer-county / small-school effect). Do not rank by raw rate:

- Build the funnel table (`group_rate_funnel`) / plot (`eda_plots.rate_funnel`): a group deserves a ranking claim only when its rate leaves the binomial band around the overall rate at its own n.
- For downstream use, prefer shrinkage (empirical-Bayes-style pooling toward the overall rate) over raw small-group rates.
- The same trap applies to per-cluster and per-segment profiles: report group sizes next to every rate.

## Selecting on an extreme guarantees movement toward the mean

Any group chosen **because it was extreme on a baseline** — the worst-performing sites, the top-decile churn risks, patients past a clinical cutoff, the schools put on an improvement plan, the features with the highest score in fold 1 — will move toward the average on remeasurement, with no intervention and no real change. This is not a subtle bias; it is the dominant term in most naive before/after comparisons.

Measured on 100 000 rows where **nothing at all happened between the two measurements** (one latent score, independent noise on each occasion, `r(pre,post) = 0.671`):

| selected group | pre | post | change |
|---|---|---|---|
| worst 10% | 28.57 | 35.65 | **+7.08** |
| worst 25% | 34.45 | 39.58 | +5.13 |
| best 10% | 71.40 | 64.49 | **−6.91** |

The size is predictable, not mysterious: `E[post | pre] = μ_post + r·(σ_post/σ_pre)·(pre − μ_pre)`, so the expected change for a group at baseline mean `m` is that value minus `m`. `regression_to_mean` computes it and returns `excess_change` — the part of the observed movement that regression to the mean does *not* explain. Injecting true effects of 0.0 / 3.0 / 6.0 / −2.0 into the selected group, `excess_change` recovered **+0.03 / +3.03 / +6.03 / −1.97** while the raw observed change read +7.11 / +10.11 / +13.11 / +5.11.

**The reference line is fitted on the non-selected rows, and that detail is load-bearing** — it was found by testing, not by design. A real effect on the selected group also shifts the pooled mean, spread and correlation, so a whole-sample fit absorbs part of the effect it is meant to measure: on a true +3.0 it recovered only **+1.784**, losing 40%. Truncating on the baseline does not bias an OLS slope under linearity and homoscedasticity, which is what makes the untreated remainder a valid reference.

Read `excess_change`, not `observed_change`, and read `rtm_share_of_observed` beside it — a real effect can survive while regression to the mean still accounts for most of the raw number (in the +3.0 case, 70%). The function is a **screen, not a substitute for a control group**: it assumes the pre/post relation is linear and that the non-selected rows really are untreated, and a surviving effect is still only an association.

Practical EDA consequences beyond pre/post analysis: a feature selected for its top score in one fold will score lower in the next (this is why selection stability is checked across folds, not asserted from one); a "worst offenders" cohort profiled at time 1 and revisited at time 2 will look improved regardless; and any threshold-triggered action creates a selected group whose later measurements are biased by construction.

## Outlier decision sequence

1. Confirm the value and unit.
2. Check whether the row violates a domain constraint.
3. Check duplicates, source, time, group, and label context.
4. Compare univariate and multivariate signals.
5. Decide: correct, retain, flag, cap/transform, segment, or exclude.
6. Validate the decision with an ablation and document its scope.

Never equate unusual with erroneous. Never remove an entire minority class or rare subgroup because a generic anomaly detector ranks it as unusual.

### "Drop by 1.5·IQR, re-plot, the data is now outlier-free" is a loop with no fixed point

The standard tutorial gesture — apply the 1.5·IQR fence, redraw the box plot, observe there are no dots left, declare the data clean — hides two things. First, the fence is defined **relative to whatever is currently in the sample**, so removing the flagged points moves the quartiles and manufactures a fresh set of flagged points. Second, on a skewed variable the rule flags a large share **by construction**, with nothing wrong in the data at all. Measured on 100 000 clean draws, applying the rule repeatedly until it stops firing:

| distribution | removed per pass | passes | total removed | sd before → after |
|---|---|---|---|---|
| normal(0,1) | 0.73%, 0.04%, 0.00% | 4 | 0.77% | 0.9975 → 0.9663 |
| exponential(1) | 4.69%, 1.77%, 0.71%, 0.29%, … | 12 | 7.70% | 0.9934 → 0.6351 |
| lognormal(0,1) | 7.87%, 3.39%, 1.60%, 0.77%, … | 12 | **14.40%** | 2.1433 → **0.6866** |

On perfectly clean lognormal data the loop deletes one row in seven and removes **68% of the variable's spread**. The "outliers" it kept finding were the distribution's own right tail — which for revenue, duration or claim size is usually the part the decision depends on. Even on a textbook normal the first pass deletes 0.73% of rows that are not errors.

The loop does terminate, but only because it has truncated the distribution into one whose tails fit inside its own fences; "no dots on the box plot" is a statement about the box plot, not about the data. Related and already documented above: percentile trimming labels a fixed share by construction, and `|z| > 3` cannot fire at all for n ≤ 10. Use the sequence above — confirm, check constraints, decide per case — and if a transform is what the shape calls for, transform (see `mean_variance_scaling`) rather than delete.

## Scaling and transformation

- Standard scaling is useful for distance-, gradient-, regularization-, and PCA-based workflows; it does not make data normally distributed.
- Robust scaling reduces the influence of extreme values but does not remove outliers.
- Min-max scaling fixes the training range but future values may fall outside it.
- Power/log/quantile transforms change distribution geometry and interpretability; validate downstream benefit.
- Tree splits usually do not need monotonic scaling, but mixed pipelines or regularized components may.
- L2 normalization acts across a vector/sample or selected axis and is not interchangeable with per-feature scaling.

Fit every transformer on train/folds. Pandas `Series.std()` uses `ddof=1` by default, while scikit-learn `StandardScaler` uses a population-style variance (`ddof=0`), so naive manual checks can differ.

### Normalization decision by model family

Scaling is a modeling-pipeline choice, not a data-quality repair; decide it per downstream consumer and validate the benefit.

- **Needs scaling:** distance/kernel methods (KNN, K-Means, DBSCAN, SVM-RBF), gradient-trained models (neural nets, SGD), regularized linear models (Ridge/Lasso/ElasticNet, penalized logistic), and PCA/other variance-based projections — otherwise large-scale features dominate distances, penalties, or components.
- **Usually no scaling:** axis-aligned tree ensembles (Random Forest, XGBoost, LightGBM, CatBoost, Decision Tree) split on thresholds and are invariant to monotonic per-feature rescaling.
- **Do not re-scale:** already-bounded features (probabilities, percentages, 1–5 ratings, binary/one-hot) unless a specific method requires it.
- **Method by data shape:** StandardScaler as default; RobustScaler under heavy outliers; PowerTransformer/quantile transform under strong skew; MinMax/MaxAbs when a bounded or sparsity-preserving range is operationally needed (future values may exceed the training range).
- **Interpretation caveat:** scaling obscures original units; keep raw values when coefficient or threshold interpretability matters.

This is a starting heuristic, not a rule. Fit the chosen transformer on train/folds only (wrap it in a `Pipeline` so cross-validation refits per fold), persist it for inference, and confirm the downstream benefit rather than scaling by reflex.
