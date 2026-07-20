# Association methods

## Selection guide

- **Numeric–numeric, linear:** Pearson with scatter/residual checks and robust sensitivity.
- **Numeric–numeric, monotonic:** Spearman; use Kendall when pairwise rank concordance or small samples matter.
- **Numeric–numeric, nonlinear/nonmonotonic:** mutual information or distance correlation plus plots and estimator sensitivity.
- **Binary–numeric:** point-biserial for a linear mean-shift interpretation; rank tests/effect sizes or MI for broader shapes.
- **Categorical–categorical:** contingency table, chi-square when expected counts suffice, and Cramer's V for strength; read the *structure* with the Quetelet decomposition (below); merge/regularize rare levels only with justification.
- **Categorical–numeric:** group distributions, robust effect sizes, ANOVA/eta-squared only when assumptions fit; otherwise rank-based comparisons, correlation ratio, or MI. Report the tabular regression (below) as the standard artifact.
- **Ordinal:** rank-aware measures; do not silently treat arbitrary codes as interval values.
- **Multivariate:** partial correlation/conditional MI only with an explicit conditioning set and adequate data.

## Contingency structure: Quetelet decomposition

A scalar chi-square / Cramer's V says *whether* two categorical features are related; the Quetelet decomposition (`quetelet_table`) says *which cells* drive it and in which direction:

- **Quetelet index** `q(l/k) = P(l|k)/P(l) − 1` — the relative change of category *l*'s probability once *k* is known (symmetric: `q(l/k) = q(k/l)`). "+400%" reads as "the rate is 5× the base rate" — far more informative than the conditional probability alone when base rates are small.
- **Chi-square is the average Quetelet lift:** `chi2/N = Σ p_kl·q(l/k)` (Pearson's φ²), i.e. the mean relative gain in predicting one feature from the other. This is what justifies using chi-square as an association measure — not only as an independence test.
- **Per-cell contributions** `p_kl·q(l/k)` sum to φ² and can be negative; flag cells with |contribution| above twice the mean as the pattern carriers. Signed **Pearson residuals** `r(k,l) = (p_kl − p_k·p_l)/√(p_k·p_l)` give the same pattern with `Σr² = φ²`.
- **2×2 tables:** `q(Yes/Yes) = (ad − bc)/((a+c)(a+b))`, and the φ coefficient equals the Pearson correlation of the two 0/1-coded features.
- **Reference-population caveat:** the lift is relative to the whole-table base rate. Choosing a different comparison population (convicted vs general population in the stop-and-search controversy) can flip the conclusion — state the reference population explicitly before reporting any lift, and never present a lift as evidence of a causal mechanism.
- For a directional question ("how much does knowing X improve predicting Y", not vice versa), use an asymmetric index (Goodman–Kruskal tau) instead of symmetric chi-square-family measures.

## Tabular regression (categorical → numeric)

The standard artifact for a nominal→numeric pair (`tabular_regression`): one row per category with n, within-category mean (the least-squares piecewise-constant prediction) and within-category std (its error), plus an `(all)` marginal row showing prediction quality *without* the category. The **correlation ratio η²** is its determination coefficient — the share of variance explained by the category (ANOVA decomposition). Notes:

- η² is **asymmetric** (η²(y|x) ≠ η²(x|y)) and is driven purely by within-group variance reduction — group means' locations do not enter it.
- Pair the table with a per-category box plot; small-n categories get wide uncertainty, so read the group sizes before comparing means (see the small-group funnel caution in the audit skill).

### A group-adjusted effect assumes parallel slopes

When a numeric covariate sits alongside the categorical grouping (ANCOVA-style: "the group difference, adjusted for Z"), the adjustment is only a single honest number if the Z↔outcome slope is the same in every group — the "parallelism"/homogeneity-of-regression assumption. A violated assumption is not automatically a defect to fix; it can be the finding (Rogosa's reframe): test the group×Z interaction before reporting one adjusted difference.

Simulated 40 000 rows, two groups with a genuine crossover — group A's outcome rises gently with Z (true slope 0.3), group B's rises steeply (true slope 1.0), crossing at Z≈2.86:

| quantity | value |
|---|---|
| true (B−A) difference at Z=1 | **−1.30** |
| true (B−A) difference at Z=9 | **+4.30** |
| common-slope "adjusted" group effect (one number, ignores interaction) | **+1.51** |
| recovered slopes with the interaction term | 0.299 (A), 1.002 (B) — both match truth |
| F-stat for the group×Z interaction | 41 007 (unmistakably real) |

The single adjusted-mean model reports +1.51 everywhere — a number that matches the truth at *no* value of Z and hides a sign flip (B is worse at high Z, better at low Z). Fit the interaction first (`tabular_regression` per Z-bucket, or an explicit group×Z term); only collapse to a single adjusted difference once the interaction is checked and small. Source: Quantitude S2E14 "Control Variable Issues" (Curran & Hancock, citing Rogosa 1980 on ANCOVA's homogeneity-of-slopes assumption); the measurements above are ours.

## A correlation near zero is a question, not an answer

"These two are uncorrelated, so they are unrelated" is the single most common misreading of a correlation matrix, and it is wrong often enough to deserve a checklist. Each row below is a **distinct** mechanism producing `r ≈ 0` (or worse) over a real, strong relation — measured on 20 000 rows each, with the diagnostic that separates it:

| mechanism | measured | diagnostic |
|---|---|---|
| **Symmetric nonlinearity** (inverted U) | Pearson **+0.002**, Spearman −0.009, but `corr(\|x\|, y) = −0.907` | a rank measure also reads ~0 — only a scatter, MI, or a folded transform shows it |
| **Effect reverses across a subgroup** | pooled **−0.012**, `z=1` **+0.765**, `z=0` **−0.766** | condition on the candidate moderator; both halves are large and opposite |
| **Simpson reversal** | pooled **+0.669**, every subgroup **≈ −0.62** | worse than zero — the pooled *sign is wrong*; compare within-group to pooled |
| **Coarse categorization of the outcome** | continuous **+0.597** → median split **+0.481** → 97th-pct split **+0.238** | attenuation, rarely to exactly zero; keep the continuous form |
| **Range restriction** | full sample **+0.500** → top 5% of `x` only **+0.211** | compare the subgroup's sd on `x` against an external reference (below) |
| **Suppression** | `corr(s, y) = −0.007` while its joint coefficient is large | multivariate screen — see `selection-importance.md` |

Two consequences for EDA practice. First, a near-zero cell is a **prompt to plot the pair**, not a licence to drop a feature — this is the same rule as the suppression finding in the feature-selection reference, arrived at from a different direction. Second, the mechanisms are not exotic; mixed subgroups and pre-filtered samples are the normal condition of observational data.

### Range restriction (`range_restriction`)

Selecting on a variable shrinks its variance, and the correlation shrinks with it **without any change in the underlying relation**. Thorndike Case II, with `u = sd_selected / sd_reference`:

```
r_unrestricted = (r/u) / sqrt(1 + r²/u² - r²)
```

Measured against a known truth of 0.50 on 200 000 rows, keeping only the top quantile of `x`: observed `r` fell to 0.330 / 0.280 / 0.247 / **0.225** at the top 50% / 25% / 10% / 5%; inverting the formula recovered **0.501 / 0.510 / 0.526 / 0.528**. The correction works, but it is a **sensitivity statement, not a measurement**: it assumes selection was on `x` alone, linearity, and homoscedasticity, and `sd_reference` must come from *outside* the filtered data (a published norm, a pre-filter extract, an earlier dump). Without a credible reference the honest output is "this `r` is a lower bound".

This is why "SAT does not predict college GPA" measured on admitted students, or "tenure does not predict performance" measured on people who were not fired, are usually arithmetic rather than findings. Whenever a dataset arrives already filtered — approved loans, surviving customers, completed sessions — every correlation in it is attenuated by construction, and the filter belongs in the dataset card (see the missing-rows section in `audit-eda-data-quality/references/consistency-validity.md`).

## Mutual information

- MI detects dependence but has no sign and is estimator-dependent.
- Continuous MI requires bandwidth or neighbor choices; discretization can create or hide signal.
- Compare against permutation/null MI and assess stability across folds/seeds.
- Use normalized variants only when their definition and comparison purpose are explicit.
- A high MI with target can be leakage, proxy leakage, ID memorization, or genuine signal; audit availability time.

## Correlation blocks

- Cluster a correlation matrix to reveal redundancy blocks, then inspect original pair plots and conditional relationships.
- `abs(r)` discards direction; retain signed summaries for interpretation.
- Correlation among features does not imply one should always be removed. Regularized or tree models can behave differently, and features may differ in cost, missingness, robustness, or availability.

### Clustered correlation matrix

Reorder the matrix by hierarchical clustering of a feature-distance so redundant features form contiguous blocks. Choose distance and linkage deliberately:

- `1 - r` groups features that move in the **same direction**; `1 - |r|` groups **strongly related** features regardless of sign.
- Feed a precomputed dissimilarity to average or complete linkage. Ward assumes Euclidean feature vectors and squared-error minimization, so do **not** apply it mechanically to a `1 - |r|` correlation distance — use average/complete linkage on the correlation distance, or run Ward on standardized feature vectors instead.
- Read blocks as redundancy candidates, not delete lists: from each block keep 1–2 features chosen by target relevance, stability, cost, missingness, and inference-time availability; keep isolated features (light off-diagonal) as unique information.

## What least squares actually assumes

Worth knowing before treating any linear probe's coefficients or intervals as evidence. Gauss–Markov makes OLS the **B**est **L**inear **U**nbiased **E**stimator — best meaning smallest sum of squared residuals *within the class of linear unbiased estimators*, which is a conditional claim, not a general one.

**It does require:** linearity **in the parameters**; homoscedasticity (constant error variance across the fitted surface); independent, identically distributed errors; more rows than parameters (so `X'X` inverts); variability in every predictor; no *perfect* collinearity; no correlation between residual and predictor; and a correctly specified model.

**It does not require — three myths worth retiring:**

- **Normality of the residuals.** Gauss–Markov never invokes it. Least-squares point estimates are unbiased and BLUE whatever the error distribution. Normality enters only when a *sampling distribution* is needed — an interval or a p-value — and even there the CLT usually covers for it.
- **Linearity between X and y.** "Linear" refers to the parameters. `β₀ + β₁x + β₂x²` is a linear model; `β₀ + β₁e^(β₂x)` is not. "Everything I study is nonlinear, so I cannot use regression" is a misreading — see the splines note in the feature-engineering reference.
- **Error-free predictors.** What the theorem states is that the predictor distributions are fixed and known; freedom from measurement error is a consequence of that framing, not a separate stated assumption.

### Check leverage, not residual normality

Measured 95% CI coverage over 6000 replicates, true slope 2.0:

| design / errors | n=10 | n=30 | n=200 |
|---|---|---|---|
| balanced x, normal | 0.953 | 0.952 | 0.951 |
| balanced x, lognormal | 0.947 | 0.947 | 0.954 |
| leveraged x, normal | 0.950 | 0.950 | 0.950 |
| **leveraged x, lognormal** | **0.925** | **0.940** | 0.959 |

The coefficient was unbiased in every cell. Coverage degraded in exactly one: small `n` **and** a heavy-tailed `x` design **and** non-normal errors together. The mechanism is that a few high-leverage rows let individual errors dominate the estimator, so nothing is being averaged and the CLT never engages. With a balanced design, lognormal errors at n=10 still gave nominal coverage.

So the diagnostic that earns its place is `leverage_diagnostics` — hat values, their concentration, and a `clt_safe` flag — not a normality test on residuals. Mean leverage is always `p/n`; flag rows above `2p/n`, and when the design is concentrated, get intervals from a bootstrap instead of assuming them.

### Outlier, leverage and influence are three different things

`leverage_diagnostics` depends on **X only** — no outcome is involved — which is precisely why it says who *could* move the estimate and never who *does*. `influence_diagnostics` supplies the half that needs `y`, and the first thing it shows is that one word is being used for three unrelated properties:

| | what it means | statistic |
|---|---|---|
| **outlier** | far from the fitted surface | studentized deleted residual |
| **leverage** | far out in `X`, with room to pull | hat value `h` |
| **influence** | removing it actually changes the estimate | Cook's D, DFFITS, DFBETAS |

Measured on one clean base (n=60, `x ~ U(0,3)`, `y = 2 + 1·x + N(0,1)`, clean slope 1.0979) with **exactly one planted point per dataset** — flags at `2p/n` = 0.0656, `4/n` = 0.0656, `2√(p/n)` = 0.3621, `|r_del| > 3`:

| planted point | h | stud. deleted | Cook's D | DFFITS | slope shift | flags |
|---|---|---|---|---|---|---|
| **A** x at the mean, y off +6 | 0.0166 | **+5.449** | 0.1685 | +0.708 | +0.013 | outlier+influence |
| **B** x=6, on the true line | **0.3081** | −0.183 | 0.0076 | −0.122 | +0.017 | leverage |
| **C** x=6, y off −9 | 0.3081 | −6.826 | **5.8510** | **−4.554** | **+0.623** | all three |

Only C matters, and only C carries all three flags. Over 60 seeds the separation is total: A's leverage stays in [0.0164, 0.0193] — always *below* the flag; B's studentized deleted residual stays in [−1.16, +1.54], never near 3; C's Cook's D never falls below 3.76.

**The thresholds are scale-free and do not know what is material.** A is flagged `influence` in 60 seeds out of 60 — Cook's D 0.126–0.265 and DFFITS 0.58–1.06, both clearing their conventional flags every time — while the slope it actually moves has a 60-seed **median of −0.0007** against a coefficient of 1.10. It is a real outlier that changes nothing, because a point at the centre of `x` moves the intercept and not the slope. That is why `slope_shift_if_top_dropped` carries the actual refit: it is the only number here denominated in the units of the answer.

**B is not reliably "clean" either**, and the honest version says so: with its outcome on the *true* line but not the *fitted* one, 5× leverage amplifies a small residual enough to trip Cook's D in **27 of 60 seeds**. What holds in every seed is the pair of facts the trichotomy is about — B is a leverage point, and B is not an outlier.

**Three planted points in one dataset contaminate each other.** With B and C sharing an x-position, B's Cook's D rises from a 60-seed median of 0.057 to **0.455**, exceeding the flag in 60 of 60 seeds purely because C is nearby. The trichotomy has to be measured one planted point per dataset, and the smoke test asserts the interference case explicitly so a refactor cannot silently reintroduce it.

**These are screening rules, not tests.** On perfectly clean normal data with no influential structure whatsoever (p ∈ {2,4,8}, 2000 reps):

| n | share of **rows** flagged | share of **datasets** with ≥1 flag |
|---|---|---|
| 30 | 0.122–0.131 | 0.9985 |
| 50 | 0.096–0.124 | **1.0000** |
| 100 | 0.083–0.120 | **1.0000** |
| 300 | 0.077–0.117 | **1.0000** |
| 1000 | 0.075–0.117 | **1.0000** |

"My data has influential points" is the normal condition, not a finding. Roughly a tenth of all rows are flagged on data built to contain nothing. The flags start the investigation; the refit ends it.

**A briefed expectation died here.** Heavy-tailed errors were supposed to raise the flag rate, and they do not: lognormal errors give 0.1190 of rows flagged at n=100/p=2 against 0.1203 for normal errors — indistinguishable, and the same at every cell tried. The rules are studentized, so inflating the error spread inflates the estimated scale with it and the rate self-normalises.

**Masking, measured rather than assumed.** Duplicating point C (two copies, x-separation 0 to 2) drops the largest single-deletion Cook's D from 5.8510 to 1.76–2.23 — a real 3× dilution, since deleting either copy leaves the other holding the fit. But 1.76 is still **27× the flag**, so the points are not hidden; only the magnitude is. Meanwhile the damage doubles: the slope falls to 0.146 with two copies against 0.475 with one, from a clean 1.0979. Masking here costs accuracy in the *diagnostic*, not the detection — the opposite of the usual warning, and what this design actually produced.

**Never delete a flagged row because it is flagged.** A is a real observation. So is B. Deleting either buys nothing and costs a data point; deleting C changes the answer by 60%, which is a reason to *understand* C, not to remove it.

### "Fit a line through the scatter" has three different answers

OLS minimises residuals **vertically**, not perpendicularly — because the goal is predicting `y`, not describing the cloud. The eye does the opposite, gravitating to the perpendicular fit, which is PC1. Slopes measured on the same data:

| corr(x,y) | y on x | 1 / (x on y) | PC1 |
|---|---|---|---|
| 0.30 | 0.298 | 3.246 | 0.946 |
| 0.60 | 0.599 | 1.647 | 0.990 |
| 0.90 | 0.902 | 1.110 | 1.001 |
| 0.99 | 0.990 | 1.009 | 1.000 |

The two regression lines bracket PC1 and all three converge only as `|r| → 1`. Consequences: the regression slope is always shallower than the visual fit (this *is* regression to the mean); "the line" is undefined until you name the outcome; and a PCA component is not a regression line, so do not read one as the other when both appear in the same plot.

### `√R²` is not the correlation coefficient

A recurring line in introductory material is that the correlation coefficient "is simply the square root of the coefficient of determination and ranges from −1 to 1". The two halves of that sentence contradict each other: a square root is non-negative, so it cannot range from −1 to 1. Measured on 500 rows:

| true relation | r | R² | `√R²` |
|---|---|---|---|
| positive slope | **+0.884364** | 0.782100 | +0.884364 |
| negative slope | **−0.904853** | 0.818758 | **+0.904853** |

`√R² = |r|`, and the sign — the part a reader actually acts on — is unrecoverable from `R²`. It has to come from the slope or from `r` itself.

The second half of the error is worse in practice: `R²` is only a squared *pairwise* correlation in **simple** regression. With more than one predictor, `√R²` is the multiple correlation between `y` and the fitted values, and it corresponds to no pair in the data. Measured on three predictors, `R² = 0.7014`, `√R² = 0.8375`, while the pairwise correlations with `y` were `+0.5919`, `−0.5084`, `+0.2539` — the reported "correlation" matches none of them and exceeds all of them. Report `r` for a pair and `R²` for a model, and never convert one into the other.

## Multicollinearity (VIF)

Pairwise correlation and VIF answer **different** questions. `VIF_j = 1 / (1 - R²_j)`, where `R²_j` comes from an auxiliary regression of feature *j* on **all other features** — so VIF detects a feature that is a linear combination of *several* others, which no pairwise heatmap can show.

This is not a corner case. With `w`, `z` independent and `x ≈ w + z`, every pairwise `|r|` sits near 0.7 — under the usual 0.8 "suspicious" threshold — while VIFs run into the hundreds. **Therefore do not gate VIF on a high pairwise correlation**: the dependence VIF exists to catch is exactly the one that is invisible pairwise. Use the heatmap to *understand* structure and VIF to *test* for redundancy; run both.

Conventions (not tests): VIF > 5 strong, VIF > 10 very strong, `inf` = exact linear dependence (duplicated column, a total that equals the sum of its parts, all levels of a one-hot group). The "<2 fine / 2–5 modest / 5–10 moderate" ladder has no distributional justification; it is a convention the field invented and then began to cite.

**Only `inf` is a categorical event.** Perfect collinearity is the one condition the Gauss–Markov assumptions actually exclude, because `X'X` is then singular and no OLS estimate exists at all. Everything short of it is a matter of degree — if the model fitted, you do not "have multicollinearity" in the strict sense, you have overlap that may be inflating standard errors. The term has drifted from "the estimator does not exist" to "some correlations look high", and the two deserve different responses.

- **Prune iteratively** (`vif_prune`), never in one pass: VIF is a joint property, so removing a single feature usually drops the rest below threshold. In the `x ≈ w + z` case, three features exceed VIF 300 but dropping only `x` returns all of them to ~1 — a one-pass "drop everything above 10" would have destroyed the block.
- **Prune only what reaches a focal predictor** (`vif_prune(..., focal=[...])`). Collinearity confined to control variables does not inflate a focal predictor's standard error. Measured over 400 resamples with a focal pair at r=0.5 plus four controls: the focal coefficient's sampling sd was 0.0595 with independent controls and 0.0586 with controls correlated at r=0.99 among themselves. Global pruning would delete those controls for nothing — verified on a synthetic set where it drops two harmless controls while the focal VIFs were already 1.07.
- **One-hot groups** have infinite VIF by construction (levels sum to 1, which the intercept spans). Drop a reference level or judge the group jointly; do not delete arbitrary levels to "fix" the number.
- **Polynomial/interaction terms** are structurally collinear with their parents. Centering makes their VIF readable but changes nothing substantive: on `y ~ x + x²` with `x` centred at 20, VIF falls from **86.7 to 1.002** while R², every fitted value, the `x²` coefficient *and its standard error* are bit-identical — only the lower-order coefficient moves, because it now means the slope at the mean instead of at zero. Centering removes an artefact of measuring overlap around zero. A VIF that "improved" after centering was never reporting a real problem, so do not report the improvement as a fix.
- VIF is scale-invariant (standardizing changes nothing) but the **non-centred variant is location-sensitive**: it reports VIF ≈ 660,000 for three *independent* features that merely sit at mean 1000 with sd 1. The implementation here uses the centred definition (auxiliary regression with an intercept, mean-centred total sum of squares). A VIF quoted by an unfamiliar tool is uninterpretable until you know which definition it used.
- VIF says nothing about the target: `y` appears nowhere in `X'X`, so collinearity is a property of the design matrix alone. It is not a relevance score.
- Needs `n > p` and complete rows; on wide data the auxiliary regressions saturate and VIF is meaningless.

### Collinearity is not a defect to be engineered away

- **Instability is not bias.** Overlap makes a slope estimate unstable, not wrong. The estimator stays unbiased and the standard error reports the instability honestly. A wide interval under heavy overlap is the *correct* answer: if two predictors carry nearly the same information, their unique contributions genuinely are hard to separate, and the model saying so is a result, not a failure.
- **Prediction is largely unaffected.** Measured over 400 resamples: raising `corr(x1,x2)` from 0.0 to 0.999 inflated the coefficient's sampling sd 23-fold (0.050 → 1.138) while held-out RMSE stayed flat (1.003 → 1.002). Geometrically the data lies along a narrow ridge — the fitted plane pivots wildly on it, but any point on that ridge still predicts `y` well. This holds for **linear** models, not only for trees.
- **You often create it yourself**, legitimately: `x` with `x²`, `x1` with `x1·x2`, a time-2 measure controlled for time-1. That overlap is the question you asked, not a flaw. Expect the time-2 unique effect to be small.
- **Diagnostic signature:** a large joint R² with no individually significant predictor is the classic pattern. Read it as "the right variables are on the table and they share their information", not as a failed model.
- **Triage the cause before the symptom.** Three common ones: (a) *measurement* — several indicators of one construct that were never conceptually distinct, in which case the answer is a scale or a factor, not a horse race between them; (b) *sampling* — a subgroup structure that ties predictors together; (c) *the world* — depression, anxiety and withdrawal really do co-occur. Only (a) has a data-side fix.
- Remedies people reach for reflexively — collapse to one score, PCA, drop a variable, ridge/lasso — each trade interpretability or introduce their own assumptions. Justify the choice against the actual goal (a coefficient you must interpret vs a prediction you must ship) rather than applying one because VIF crossed 10.

Source for the framing above: Quantitude S5E02, "Multicollinearity: The Usual Suspect" (Curran & Hancock, 2023); the measurements are ours.

### What multicollinearity actually breaks

It corrupts **coefficient interpretation and stability**, not necessarily prediction:

- Linear models: coefficients become unstable and their signs/magnitudes untrustworthy — the fit is shared arbitrarily among collinear features. Ridge/Elastic Net stabilize this; L1 arbitrarily picks one of a collinear set.
- Tree ensembles: learning is essentially unharmed — a split picks whichever feature looks marginally better — so **for accuracy, collinear features can usually stay**. But importance is *split* between the twins, so neither looks important though jointly they are decisive, and which one wins varies across seeds/samples (a reproducibility cost).
- Decide by purpose: **accuracy → keeping is acceptable**; **interpretation/stability → reduce the block** (keep one, or replace the block with a PCA component/domain composite), and record the decision.

## Unique vs shared association (`semipartial_correlations`)

Once predictors overlap, a coefficient table reports one effect on four scales — raw `b`, standardized `b*`, squared semipartial `sr²`, squared partial `pr²`. They are rescalings, so they never disagree about significance: on a two-predictor design the t from `b`, the t from `b*` and `√F` from `sr²` were all **30.420713**. Two anchors worth keeping: with a single predictor `b*` *is* Pearson r in either direction (0.550031 for x→y, y→x and r alike, while the raw slopes differ, 0.672714 vs 0.449721); with exactly uncorrelated predictors the multiple-regression slopes equal the simple ones, so the joint fit adds nothing.

- **`sr²` = the increment in R²** when the feature enters last — its unique share of the *total* variance of the target. Verified two ways: increment 0.096826 vs `corr(y, e_xj)²` 0.096826.
- **`pr²` = that same increment divided by `1 − R²_without`** — a share of what the other predictors left unexplained. Verified 0.129630 both ways.
- Therefore **`pr² ≥ sr²` always**. Over 100 random designs the ratio ran 1.0000 to 1.6262, hitting exactly 1 when the other predictors explain nothing. Report `sr²`: "this column uniquely accounts for 6% of the variance in y" refers to the outcome the reader cares about, while `pr²` is a share of a residual that shifts whenever the predictor set changes.
- **Residualize the predictor, not the outcome.** Purging the other predictors out of `y` and correlating with raw `x_j` is a *third* quantity. All three share a covariance (0.251731 on one design) and differ only in denominator — `sd(y)·sd(e_xj)`, `sd(x_j)·sd(e_y)`, `sd(e_y)·sd(e_xj)` giving 0.286242, 0.237252, 0.335046. Only the first squares to the R² increment.
- `shared_r2` (= `R²` − Σ`sr²`) is the part no column owns. When it dominates, the honest statement is "these features jointly carry the signal", not a ranking.
- **Reporting convention** (Quantitude S3E09 "Semi-Partially"): raw `b` + its SE + p-value, then `b*` and `sr²` in parentheses — one line covers scale, significance, and the unique-variance share a reader actually wants. `pr²` earns no place in that line (see above); if a paper's table already has a `pr²` column, read `sr²` off it via `pr² · (1 − R²_without)`, don't quote `pr²` as if it were the unique share of total variance.

## Conditioning on a column changes the question

Adding a column to a model is not a neutral act of "cleaning". Three designs that look similar in the data demand different handling, and **no statistic distinguishes them from correlations alone** — measured on 40 000 rows each:

| design | corr(Z,X) | corr(Z,Y) | b_x alone | b_x with Z | wanted |
|---|---|---|---|---|---|
| Z → X, Z → Y (confounder) | +0.573 | +0.575 | +0.3256 | −0.0028 | 0.00 — **condition** |
| X → Z → Y (mediator) | +0.572 | +0.655 | +0.4988 | +0.0011 | 0.49 — **do not** |
| X → Z ← Y (collider) | +0.579 | +0.580 | +0.0064 | −0.4926 | 0.00 — **do not** |

Conditioning drove the confounder and mediator estimates to ~0. In the first that is the right answer; in the second it deleted the entire real effect, which travels *through* Z. The observable correlations are near-identical, so the decision comes from a stated model of what influences what, never from the correlation matrix. This is the association-side instance of the pattern→mechanism rule in `plan-eda-dataset`. Practical EDA consequence: when a stakeholder asks to "control for" a column, ask whether they believe it causes the predictor or is caused by it before adding it.

**The collider row is the sharpest trap of the three, because it manufactures an effect out of nothing.** X and Y are independent by construction (marginal `corr(X,Y) = 0.0064`, indistinguishable from zero) — but both cause Z. Conditioning on Z (a partial correlation, or simply adding Z as a control) induces `corr(X,Y | Z) = −0.4955`, a strong association where the true one is exactly zero. Mechanically: once Z's value is fixed, a high X value forces a compensating low Y (or vice versa) to keep Z where it is — the "explaining-away" pattern (Berkson's paradox). This is the case Sewell Wright's path-tracing rules forbid tracing through: a variable that is a common *effect* of X and Y, not a common cause or a link in the causal chain. It is also why "control for everything you have" is not a safe default — a downstream common effect sitting in a "kitchen sink" covariate list can create a spurious signal at least as easily as an omitted confounder can hide a real one. Source: Quantitude S2E14 "Control Variable Issues" (Curran & Hancock); the measurements above are ours.

## Clustered rows inflate associations, and a heat map cannot see it

If rows are nested in something (users, devices, schools, sessions), two columns that both vary at the cluster level will correlate even when they are causally unrelated — the shared cluster membership is a confounder that no column in the matrix represents. Measured with x and y generated **independently**, sharing only the cluster structure (40 clusters × 25 rows):

| ICC of both columns | false-positive rate at p<0.05 | max &#124;r&#124; seen |
|---|---|---|
| 0.00 | 0.053 | 0.114 |
| 0.15 | 0.117 | 0.132 |
| 0.30 | **0.259** | 0.185 |
| 0.60 | **0.537** | 0.354 |

At ICC 0.60 more than half of all independent pairs read as significant. Every downstream artefact built on that matrix — the redundancy prune, the clustered-correlation dendrogram, a univariate screen — inherits it.

The correction is **not** the design effect for a mean. Use `1 + (m0−1)·ICC_x·ICC_y` (`audit-eda-data-quality/scripts/sampling_design.py::effective_n_for_association`): the product of the two ICCs, verified to restore 0.045–0.052 across eight configurations, whereas substituting the mean's design effect over-corrected to 0.002 and would silently delete real features. A useful corollary: if only one of the two columns is clustered, the product is ≈0 and **no correction is needed** — measured 0.047 uncorrected with ICC_x=0.60, ICC_y=0.00.

Note this is a distinct problem from the group-aware split, which is a leakage control and leaves the inference untouched. See `audit-eda-data-quality/references/sampling-design.md`.

## Measurement quality caps what any association can show

A weak correlation is not always a weak relationship — it can be a measurement ceiling. With reliability `rel` on both sides the observable correlation is `r_true·√(rel_x·rel_y)`; measured against `r_true = 0.60`, reliabilities 1.0/0.8/0.6/0.4 gave observed **0.6003 / 0.4801 / 0.3598 / 0.2394**, matching prediction to three decimals. The two sides are not symmetric:

- **Noise in a predictor attenuates its slope**, by exactly its reliability — true slope 1.0 read as 0.8999 / 0.6999 / 0.4998 at reliability 0.90 / 0.70 / 0.50.
- **Noise in the target leaves the slope unbiased and inflates its standard error** — the slope stayed 1.0005 / 1.0012 / 1.0020 while the SE grew 0.0112 → 0.0274.

So a noisy feature biases the estimate while a noisy target only costs precision. The corollary for control variables is sharper: a covariate measured with error only *partially* removes the confounding it was added for. With a true direct effect of exactly 0.0, conditioning on a proxy of the confounder left a spurious **+0.1498 at reliability 0.90**, rising to +0.3470 at 0.70 and +0.5541 at 0.30. "We adjusted for it" is only as strong as the column's measurement quality — record which columns are proxies (see `audit-eda-data-quality/references/consistency-validity.md`).

## Statistical discipline

- Report effect size and uncertainty, not only significance.
- Correct exploratory families of tests with FDR where inferential claims are made.
- Use bootstrap confidence intervals when analytic assumptions are doubtful.
- Distinguish association from causation and prediction from intervention.

### How fast multiplicity actually bites

`P(at least one false positive) = 1 − (1 − α)^k` for `k` independent tests at level `α`. Simulated against the formula (4000 replicates per cell, all nulls true):

| k tests | 1 | 2 | 5 | 10 | 20 | 50 |
|---|---|---|---|---|---|---|
| formula | 0.050 | 0.098 | 0.226 | **0.401** | 0.642 | 0.923 |
| simulated | 0.049 | 0.099 | 0.233 | **0.406** | 0.646 | 0.924 |

Ten tests is a 40% chance of at least one false positive — and a correlation matrix over 10 features already contains 45 pairs. This is why the FDR line above is not a formality: an exploratory scan **is** a large family, and the "significant" cells in a big heatmap should be read as candidates, not findings.

Two clarifications worth keeping straight, because they are commonly confused:

- **This is about distinct tests, not repeated runs.** Re-running the same model on the same data returns the same p-value every time; nothing inflates. (Re-running with a different *seed*, *split*, or *specification* and keeping the best one is a different sin — that is the garden of forking paths, and no correction formula covers it.)
- **Every estimated parameter is a test.** People who carefully correct a post-hoc comparison in an ANOVA will read a 40-parameter model's coefficient table, or a screen of hundreds of candidate features, without adjusting anything. Structurally these are the same family.

### Post-hoc pairwise comparisons: the standard recipe is protection that evaporates

"Does the target differ across the levels of this feature, and between which levels" is the most routine categorical question in EDA, and it is a family of `g(g−1)/2` tests. The textbook recipe — run a one-way ANOVA, and *if it is significant* run uncorrected pairwise t-tests (Fisher's LSD) — is still recommended by introductory guides. Measured under a **complete** null (all groups identical, n=30 each, 20 000 replicates, α=0.05, Welch throughout):

| groups | pairs | uncorrected | LSD | Holm | Bonferroni | BH |
|---|---|---|---|---|---|---|
| 3 | 3 | 0.1197 | 0.0481 | 0.0411 | 0.0411 | 0.0439 |
| 4 | 6 | 0.2039 | 0.0507 | 0.0418 | 0.0418 | 0.0449 |
| 5 | 10 | 0.2887 | 0.0489 | 0.0388 | 0.0388 | 0.0418 |
| 6 | 15 | 0.3623 | 0.0500 | 0.0379 | 0.0379 | 0.0425 |
| 8 | 28 | **0.5068** | 0.0478 | 0.0390 | 0.0390 | 0.0428 |

On that table LSD looks perfectly safe. **That is the trap, and a simulation that stops here will certify it.** Under the complete null the omnibus itself only fires 5% of the time, so the gate is doing all the work and the pairwise step is never reached. Re-measured under a **partial** null — one group genuinely shifted by 3 sd, the rest identical, counting a false positive only among the pairs that are truly equal:

| groups | uncorrected | LSD | Holm | Bonferroni | BH | omnibus fires |
|---|---|---|---|---|---|---|
| 3 | 0.0488 | 0.0488 | 0.0488 | 0.0149 | 0.0488 | 1.0000 |
| 4 | 0.1224 | **0.1224** | 0.0444 | 0.0235 | 0.0863 | 1.0000 |
| 5 | 0.2036 | **0.2036** | 0.0401 | 0.0246 | 0.1150 | 1.0000 |
| 6 | 0.2843 | **0.2843** | 0.0406 | 0.0278 | 0.1363 | 1.0000 |
| 8 | 0.4374 | **0.4374** | 0.0381 | 0.0295 | 0.1752 | 1.0000 |

The omnibus is now significant in **100%** of replicates — correctly, one group really is different — so the gate stops gating and LSD sits exactly on the uncorrected rate. The partial null is the realistic EDA case: you rarely screen a feature where *nothing* differs. LSD's protection holds only at `g=3` (0.0488, the classical result) and is gone from `g=4` on.

Three consequences, all in `pairwise_group_differences`:

- **Do not gate pairwise tests on the omnibus.** It is the same error as the preliminary-variance-test below: a data-dependent decision about which test to run. Use a procedure that controls the rate on its own.
- **BH is not a substitute for Holm here** — measured 0.0863 → 0.1752 as `g` grows. It controls the false *discovery* rate, which is a different guarantee. BH when the deliverable is a shortlist to follow up; Holm when the claim is "*this particular* pair differs".
- **Holm dominates Bonferroni**: same guarantee, uniformly more power (g=4, n=30, detecting the truly-different pair: 0.2377 vs 0.2210 at d=0.5, 0.6701 vs 0.6388 at 0.8, 0.8866 vs 0.8637 at 1.0). There is no reason to reach for plain Bonferroni.

One calibration note against the section above: introductory sources state the three-group case as "≈15% error rate", which is `1−(1−α)³ = 0.1426`, the *independent*-test formula. Measured, three pairwise comparisons among three groups give **0.1197** — the pairs share groups, so they are correlated. Directionally right, quantitatively the upper bound again, exactly as in the forking-paths table.

### The garden of forking paths, priced

The formula above needs `k` *pre-specified* tests. EDA does not work that way: it makes a chain of individually defensible choices — which outlier rule, which transform, which subgroup, which imputation — and each combination is a different analysis. Measured on data where **x and y are independent by construction**, with a deliberately modest multiverse of 18 paths (3 outlier rules × 3 transforms × 2 subgroup definitions):

| n | one fixed path | best of 18 paths |
|---|---|---|
| 100 | 0.052 | **0.292** |
| 500 | 0.058 | **0.300** |
| 2000 | 0.048 | **0.296** |

Two things to take from this. First, a modest, entirely honest set of analytic choices turns a 5% error rate into ~30%. Second — and this is the part that surprises people — **more data does not help at all**: the rate is flat from n=100 to n=2000, because the multiverse is a selection problem, not a variance problem. It is the same lesson as survivorship in `consistency-validity.md`: large samples cure variance, never selection.

How fast it grows, measured against the independence formula:

| paths | 1 | 2 | 4 | 8 | 16 | 32 |
|---|---|---|---|---|---|---|
| measured | 0.051 | 0.082 | 0.128 | 0.176 | 0.239 | 0.308 |
| `1−(1−α)^k` | 0.050 | 0.098 | 0.185 | 0.337 | 0.560 | 0.806 |

The formula is an **upper bound**, not an estimate: paths that analyse the same rows are correlated, so the real inflation is milder than independence implies. Do not quote `1−(1−α)^k` as "the" error rate of an exploratory session; quote it as the worst case.

The remedy is not to stop exploring — that is the point of this project, see `plan-eda-dataset/references/workflow.md`. It is to record which path was taken and to treat the result as a hypothesis until it survives data that did not shape it. The cost of pre-committing to one path is modest: on a real effect (r=0.15, n=400) the single pre-specified path still had power 0.865.

### Do not choose a test by first testing its assumption

A "preliminary test" — run Levene, then pick pooled or Welch — is itself a data-dependent choice, so the second test's p-value is conditional on the first. Measured under a true null across six designs, the two-stage procedure ran 0.045–0.067 against a nominal 0.05: mildly inflated, not catastrophic. The decisive finding is elsewhere:

| n₁ | n₂ | sd₁ | sd₂ | always pooled | always Welch | two-stage |
|---|---|---|---|---|---|---|
| 30 | 30 | 1 | 1 | 0.045 | 0.045 | 0.045 |
| 50 | 10 | 1 | 3 | **0.289** | 0.060 | 0.067 |
| 10 | 50 | 1 | 3 | **0.001** | 0.053 | 0.052 |
| 100 | 20 | 1 | 4 | **0.325** | 0.054 | 0.054 |

The pooled test is not merely imperfect under unequal variance with unequal group sizes — it is wrong in **both directions** depending on which group is larger: 0.325 when the bigger group has the smaller variance, 0.001 (i.e. no power) when it has the larger. Welch is nominal everywhere, including when variances are equal. So the preliminary test buys nothing: use the robust procedure unconditionally rather than earning the right to a fragile one. The same reasoning applies to "test for normality, then choose" — prefer the method that is valid either way, and spend the diagnostic on leverage instead (see above).

### "Significant" and "large" are different claims, and neither is "important"

Statistical significance answers "could this be noise at this `n`" (see the sample-size caveat in `audit-eda-data-quality/references/distributions-outliers.md`). An effect size answers "how big". Neither answers "does it matter", and the conventional labels attached to standardized effect sizes — 0.2 small, 0.5 medium, 0.8 large — are **benchmarks one author proposed in the 1960s from his own field's experience**, not properties of the number. They assume perfect measurement and carry no context.

A `d` of 0.1 is "small" by that table and can be decisive for a cheap intervention at population scale or a mortality outcome; a `d` of 0.8 can be worthless if the measure is unreliable or the deployment cost exceeds the benefit. Translate the effect into the units the decision is made in — rows affected, currency, events prevented, rank change — and report the standardized value as a secondary aid. When a subgroup or feature is described as having a "small effect", check whether that word came from a measurement or from the 1960s table.
