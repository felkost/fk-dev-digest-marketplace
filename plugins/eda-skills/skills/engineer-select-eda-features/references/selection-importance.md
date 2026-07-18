# Feature selection and importance

## Layered selection

1. **Integrity filters:** IDs/proxies, unavailable features, constants, duplicates, invalid columns, and **dataset-metadata columns** — sampling/survey weights (e.g., census `fnlwgt`), batch/file identifiers, row provenance. These describe how the sample was collected, not the phenomenon; use them for weighting/grouping, never as predictors.
2. **Unsupervised filters:** missingness, variance, redundancy blocks, representation quality.
3. **Supervised filters:** effect size, MI, chi-square/ANOVA/rank scores.
4. **mRMR:** balance relevance and redundancy sequentially.
5. **Embedded:** regularized linear coefficients and tree-based selection.
6. **Wrapper:** SFS/SBS, RFE/RFECV, grouped or heuristic searches.
7. **Model-agnostic validation:** permutation, drop-column, SHAP, null importance, noise probes, ablation.

The order is also a compute strategy (coarse-to-fine): filters are cheap (linear in features) and are the right first screen when features vastly outnumber rows (genomics, medicine); wrappers then refine the surviving shortlist. Exhaustive subset search is combinatorial (2^n) — never the plan.

**Univariate blindness:** filters score each feature in isolation, so any signal that exists only jointly (XOR-like interactions, a ratio of two weak features) is invisible to them — and pairwise mRMR only partially helps. If domain knowledge suggests interactions, test them with embedded/wrapper methods or explicit interaction features before dropping the components.

**Suppression — the same blindness without any interaction.** It is tempting to read the paragraph above as "filters only miss nonlinear structure". They also miss features whose contribution is perfectly linear and additive. A *suppressor* correlates with another predictor but not with the target; including it removes variance from that predictor which is unrelated to the target, sharpening the predictor's own estimate. Measured on `y = x − 0.7·s + ε` with `corr(x, s) = 0.7`: the suppressor's correlation with `y` is **−0.0142** — indistinguishable from zero, so any `|corr(y)|` or univariate-MI screen drops it — yet adding it moves R² from **0.3322 to 0.6707 (+0.3385)**, and its coefficient in the joint fit recovers the true −0.70. The rule that follows is the practical one: **never drop a feature on its bivariate association with the target alone.** Screen on a multivariate criterion (embedded L1, drop-column, or `semipartial_correlations` in discover) before deleting columns, or keep the candidate through to a wrapper stage. Note the asymmetry with redundancy pruning — a feature can be near-useless alone and decisive jointly, so "weak correlation with y" and "safe to drop" are different claims.

**Tune the selector inside CV:** the number of kept features (top-k, threshold, percentile) is a hyperparameter. Put the selector in the pipeline and pick k by cross-validation together with model parameters; a selector fitted on the full data before the split is itself leakage. Selection can also transfer across models (e.g., `SelectFromModel` over a tuned L1-regularized linear model feeding a tree model) — document that the selected set inherits the selecting model's biases.

**One-standard-error rule (`one_se_rule`):** CV score curves over feature-set/model size are flat near the optimum, so the literal argmax moves with the fold split — it is noise, not a decision. Compute the SE of the CV mean per size and take the **smallest** size whose score is within one SE of the best (ISLP §6.1.3). The same Occam logic applies across model families: at statistically indistinguishable CV performance, prefer the simpler method.

**High-dimensional regime (p ≈ n or p > n):** a perfect train fit is guaranteed and meaningless — train R², Cp/AIC/BIC and adjusted R² computed on the training data break down (σ̂² is not estimable), and any claim must come from CV/hold-out only (ISLP §6.4). Multicollinearity becomes extreme (any feature is expressible through others), VIF needs n > p, and the selected subset is one of many equally-plausible subsets — report it as *a* predictive set, never *the* relevant set.

## mRMR

At each step, prefer a candidate with high relevance to `y` and low redundancy with selected features. Relevance/redundancy may use MI or another compatible association measure.

- Fit discretization/MI estimators only within training folds.
- Check estimator sensitivity and sample requirements.
- Group one-hot levels and lag families where individual competition would be misleading.
- Re-run across folds; report selection frequency and rank variability.

## Wrapper controls

- Keep the estimator and metric aligned with the future task, but avoid full tuning during EDA.
- Use nested CV when reporting an unbiased selection-performance estimate.
- Compare to a small/top-k/filter baseline to quantify wrapper value.
- Stop when added complexity is not stable or practically meaningful.

### Paired feature-set significance

To test whether a feature or feature group actually helps, compare two otherwise-identical models — with and without that feature set — over repeated runs (multiple seeds under a fixed hold-out, or across CV folds), and compare the **paired score distributions** with uncertainty, not two single numbers.

- Fit both arms only on training data; score on validation or out-of-fold predictions. Never tune or read this on test.
- Keep split, preprocessing, and folds identical across arms so the only difference is the feature set.
- A hold-out variant answers "how does this look on one fixed new sample"; a CV variant answers "how stable is the effect" — report which and why.
- A non-significant or unstable gain is a reason to drop the feature for parsimony, not to keep resampling until noise looks significant.

## Redundancy vs multicollinearity

`prune_redundant` works **pairwise** and therefore cannot see a feature that is a linear combination of several others (`x ≈ w + z` keeps every pairwise `|r|` around 0.7). Corroborate with VIF (`clustered_correlation.variance_inflation_factors` / `vif_prune` in `$discover-eda-structure`) before concluding a block is clean; prune iteratively, and decide by purpose — collinear features are usually acceptable for tree/boosting accuracy, but they must be reduced when coefficients or importances have to be interpreted.

## Importance controls

- Impurity importance is biased toward features with many split points.
- Permutation importance measures dependence on the fitted model; correlated substitutes can appear unimportant.
- **Collinear twins split their importance.** Two near-duplicate features each take part of the credit, so neither clears a threshold although jointly they are decisive — and which one leads changes across seeds/samples. Before dropping a "weak" feature, check whether it sits in a redundancy/high-VIF block, and test the block by group ablation rather than by individual scores.
- SHAP explains a model under a chosen explainer/background/dependence assumption, not the data-generating causal process.
- Aggregate one-hot/embedding/lag families when the user cares about the original concept.
- Inspect fold/seed/time/subgroup stability and confidence intervals.
- Confirm removal decisions with group ablation or drop-column tests.

### Noise probes (canary features)

Inject synthetic probe features — noise columns from several distributions plus "shadow" probes (permuted copies of real columns, the Boruta idea) — and refit (`noise_probe_importance`). Two readings:

- A real feature whose importance sits **below the probes** has no demonstrated signal at this sample size and model — a drop candidate pending domain review.
- Probes ranking **above real features**, especially with an unchanged-or-improved CV score, expose importance bias or an overfitted protocol. A poorly regularized tree ensemble can rank pure noise above real predictors while its CV score goes *up* — treat a score that improves when noise is added as a protocol red flag, not a gain.

### Red flags from the field

- **Nonsense at the top.** If the most important feature has no plausible mechanism (a sampling weight, a row index, an ID), suspect metadata leakage or impurity bias before inventing an explanation. Cross-check with a differently-biased model — e.g., an L1-regularized linear model after a power transform against a tree ensemble; a feature that only one family ranks high needs investigation, and features whose story survives both are safer.
- **Too good to be true.** A near-perfect single feature usually means the target (or a post-outcome proxy) is still in the matrix — re-run the audit-stage single-feature leakage check rather than celebrating.

## The winner's curse: a selected score is a biased score

Selecting a feature *because* its measured association was large and then
reporting that same association is circular. The estimate is conditioned on
having been extreme, so it is biased upward, and the bias grows with how many
candidates were screened. `filter_select.expected_max_noise_correlation` and
`filter_select.selection_inflation_probe` measure both halves of this.

**What pure noise looks like when you let it compete.** No feature has any
relation to the target; we report the best one anyway:

| n | features screened | mean max &#124;r&#124; | naive p-value of the winner |
|---|---|---|---|
| 200 | 10 | 0.132 | 6.3e-2 |
| 200 | 50 | 0.176 | 1.2e-2 |
| 200 | 200 | 0.209 | 3.0e-3 |
| 200 | 1000 | 0.241 | **6.0e-4** |
| 1000 | 1000 | 0.108 | **6.6e-4** |

The winner's p-value is governed by the *number of candidates*, not by `n` —
compare the last two rows. It is the alpha-inflation identity from
`associations.md` wearing a different hat: `1 − 0.5**(1/p)` predicts the median
winner's p-value closely (6.9e-4 predicted vs 6.0e-4 measured at p=1000).
Screening a thousand columns makes `p < 0.001` the *typical* output of noise.

**How much of the top-k is real.** n=500 with 5 genuinely predictive features:

| features screened | expected #real in top 5 | P(top-1 is pure noise) |
|---|---|---|
| 10 | 4.26 | 0.013 |
| 50 | 3.20 | 0.102 |
| 200 | 2.39 | 0.205 |
| 1000 | 1.50 | 0.427 |
| 5000 | 0.88 | **0.672** |

**The fix, and its limit.** Select on one partition, re-estimate on another.
Measured inflation of the selected features' `|r|` (select-and-report on all
rows vs the same features on fresh rows): 1.78× at p=20/n=200, 2.62× at
p=100/n=200, 3.29× at p=500/n=200, falling to 1.85× at p=500/n=1000 — the bias
grows with the number of candidates and shrinks with sample size.

`inflation` is a **discriminator**, not merely a correction. Verified against
designs with known real features: genuinely predictive columns returned
inflation 0.94 / 1.05 / 1.08 — an honest re-estimate simply reproduces them —
while columns that reached the top by luck went 0.183 → 0.042, a 3.8× median
inflation. So:

- inflation ≈ 1 → the feature is real and the number was already honest;
- inflation ≫ 1 with `honest_abs_r` still respectable → real feature, overstated
  magnitude; report the honest one;
- `honest_abs_r` collapses to ≈ 0 → **the selection found noise**. The split
  fixed the reporting bias but did not rescue the selection. Measured: at p=200,
  n=300 the honest re-estimate returned 0.072 against a true 0.112 — correct
  for the junk set that was actually picked. More rows is what fixes this (at
  n=3000: 0.100 vs 0.112), not a better estimator.

This is the same mechanism that makes a replication powered from an original
study's published effect size systematically underpowered: the published number
was selected for being large.

**Consequence for the selection record:** state how many candidates were
screened. A feature that survived a screen of 12 columns and one that won a
screen of 5000 carry very different evidence, and the score alone does not
distinguish them.

## Selection record

For every kept/dropped feature record method evidence, stability, redundancy group, cost, availability, leakage risk, subgroup impact, final decision, and reversibility.
