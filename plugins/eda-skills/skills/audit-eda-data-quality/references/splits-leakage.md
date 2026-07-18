# Split and leakage audit

## Choose the split by the deployment unit

- New independent rows: random or stratified split may be appropriate.
- New records from known entities: decide whether within-entity forecasting is intended; otherwise group split.
- New entities/sites/devices: group or source holdout.
- Future observations: chronological, expanding-window, rolling-window, and when required a gap/embargo.
- Spatial generalization: block or region holdout.

## Cross-validation vs hold-out

Both estimate generalization; choose by data size and stability need, not by reputation.

- **Hold-out (single train/test, or train/val/test):** one draw, cheap, and natural when a temporal or deployment boundary is already fixed. Its estimate carries single-split variance and can be optimistic or pessimistic depending on the draw.
- **Cross-validation (k-fold, stratified, group, or rolling/expanding):** reuses data for both roles, giving a lower-variance, more stable estimate; preferred for small/medium data and for stabilizing feature selection and importance. Cost: more compute, and every learned step must be refit inside each fold.

Hold-out is **not** automatically more realistic than CV. Realism comes from matching the split mechanism to deployment (group / chronological / spatial), which either protocol can respect or violate. During EDA prefer repeated or nested CV for selection and importance stability, and keep one untouched hold-out/test for the single final estimate.

## Labels defined over a forward window

If the target spans time — return over the next 20 days, churn within 90 days,
readmission within 30 days, any rolling aggregate — then a training row at `t`
carries information about `t+1 … t+h`. When that span reaches into the test
period, the *training label itself* contains the test outcome. No feature-side
check can see this, because the offending column is the target.

Measured on a design where the true skill is **exactly zero by construction**
(label = sum of the next `h` innovations; features built from past innovations
only, so they share no ingredient), the apparent out-of-sample correlation was:

| h | shuffled 5-fold | contiguous 5-fold | purged + embargoed |
|---|---|---|---|
| 5 | **+0.151** | −0.026 | −0.027 |
| 20 | **+0.203** | −0.048 | −0.047 |
| 50 | **+0.205** | −0.116 | −0.127 |

Three readings, and the second is not what the technique's reputation implies:

1. **Shuffling is the catastrophic error.** A shuffled k-fold invents 0.15–0.21
   of correlation out of data with no signal whatsoever. This is the single
   most common way a time-spanning label produces a model that backtests well
   and dies in production.
2. **Contiguity does nearly all the repair; explicit purging added nothing
   measurable here.** Shuffling's damage comes from interleaving training rows
   *among* the test rows, not from the fold boundary, so once folds are
   contiguous there is little left for purging to remove. Purging remains the
   correct guard — it costs a handful of rows, and it is the only thing that
   removes the boundary leak when folds are many and small — but do not expect
   it to rescue a shuffled split, and do not treat "we purged" as a substitute
   for contiguity.
3. **Contiguous k-fold carries a negative bias at large h** (−0.116 at h = 50):
   with a persistent label, each held-out block sits systematically opposite
   the training mean. So on overlapping labels a single CV number is unreliable
   in *both* directions, and its spread across repetitions is large. Report the
   spread, and see the effective-sample-size correction in `sampling-design.md`
   (`overlapping_label_deff`) before calling any of it significant.

`split_designer.purge_and_embargo` implements the purge (drop training rows
whose label span reaches the test block) plus an embargo after the block.

## Leakage classes

- **Target leakage:** direct label, post-outcome fields, target-derived aggregates, target encoding fitted globally, and — see below — a target that is *itself computed from* the feature columns.
- **Temporal leakage:** future measurements, centered windows, backfilled values, aggregates crossing the prediction timestamp.
- **Entity leakage:** the same entity or near-duplicate content appears across splits.
- **Preprocessing leakage:** imputer, scaler, encoder, PCA, selector, sampler, or feature generator fitted before splitting.
- **Synthetic leakage:** augmented siblings or generated rows derived from validation/test cross split boundaries.
- **Evaluation leakage:** repeated decisions based on holdout/test performance. A common tutorial-borne variant: tuning a **decision/similarity threshold on the pooled full dataset** (no split at all) — the threshold is a learned parameter and belongs on validation/OOF like any other.

### The target is computed from the features (`composite_target_probe`)

Index-style and score-style targets are frequently *defined* as a function of columns shipped in the same table: the World Happiness Report's Happiness Score is exactly `Economy + Family + Health + Freedom + Trust + Generosity + Dystopia Residual`; a "risk score" is a weighted sum of the bureau fields beside it; a `total` column is the sum of its parts. Correlating such a target with its own components and reporting the result is circular — it recovers the definition, not a relationship in the world.

**No single-feature screen can see this.** `suspicious_single_features` takes one column at a time and requires a binary target, so it is structurally blind here. Measured on the Happiness structure (n=158, 7 components), the individual correlations with the target ran +0.36 to +0.45; the published heat map for the real dataset reports 0.72–0.78. Either way, nothing crosses a leakage threshold — the identity only exists jointly:

| fit | R² | relative residual |
|---|---|---|
| all 7 components | 1.000000000000 | **1.07e-15** |
| one component missing | 0.866 – 0.893 | 0.326 – 0.367 |
| an honest model at a true R² of 0.99 | 0.990 | **0.0992** |

An identity and a genuinely excellent model are fifteen orders of magnitude apart on the residual, so this is not threshold tuning.

**The guard is the hard part.** With `n ≤ p+1`, least squares reproduces *any* target exactly, so an unguarded probe reports "identity" on pure noise. Minimum relative residual over 400 pure-noise draws, by `n/(p+1)`: 0.0000 at 1.0, 0.0008–0.0720 at 1.2–1.3, 0.066–0.210 at 1.5, 0.246–0.428 at 2.0. The probe therefore refuses below `n ≥ 2(p+1)`, leaving five orders of margin against a 1e-6 tolerance.

What to do with a hit: it is a **question for whoever produced the column** ("how was this computed?"), not a licence to auto-drop features. Sometimes the components are the real predictors and the target must be replaced with something measured independently; sometimes the composite is legitimately what you must predict for future rows, and then the components are simply unavailable at prediction time and belong in `availability_audit`.

## Verification

- Assert disjoint primary keys and group keys where required.
- Check whether the target is reconstructable from the features taken together (`composite_target_probe`), not only one at a time.
- Search exact and near-duplicates across splits.
- Audit feature availability timestamps against prediction timestamps.
- Compare suspiciously predictive single features with domain semantics and acquisition time.
- Verify all fitted pipeline steps expose only training indices.
- Keep validation for decisions and test/holdout for the final untouched estimate.
