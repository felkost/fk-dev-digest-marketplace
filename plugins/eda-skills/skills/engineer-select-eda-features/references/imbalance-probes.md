# Imbalance handling and diagnostic probes

## Diagnose first

- **Is the imbalance real?** Check per-class duplicate rates (`class_duplicate_report`) before anything else: duplicated majority rows exaggerate imbalance, duplicated minority rows both hide it and shrink the effective number of independent positives. Recompute the class ratio after deduplication — it may change the decision.
- Count classes and effective independent examples by entity, time, source, subgroup, and split.
- Review label definition, delayed/censored outcomes, conflicts, and likely noise.
- Establish whether rare prevalence is the deployment reality or a sampling artifact. Rare-event prevalence in the low percents or below (fraud, screening, defects, ad conversion) is a property of the domain, not a data error to "fix".
- **Know the precision ceiling the base rate imposes before promising one.** Precision is `sens·prev / (sens·prev + (1−spec)·(1−prev))`, so it falls with prevalence no matter how good the detector is. A model at sensitivity 0.90 and specificity 0.90 reaches precision 0.692 at a 20% base rate, **0.321** at 5% and **0.155** at 2% (all verified by simulation; see `audit-eda-data-quality/references/consistency-validity.md`). A stakeholder asking for "90% accuracy and few false alarms" on a 2% class is asking for a specificity they have not stated — and **specificity, not sensitivity, is the lever**: 0.80/0.999 gives precision 0.890 at a 1% base rate, far better than 0.90/0.90 anywhere near it. Resampling does not change this arithmetic; it only changes the prevalence the model is trained at, which is why validation/test must stay at deployment prevalence.
- **ROC-AUC is not "wrong for imbalanced data" — it answers a different question, and so does PR-AUC.** ROC-AUC is the probability that a random positive outranks a random negative. That is a well-defined property of the *ranking*, valid at any prevalence; the error is reading it as a statement about the alert queue. TPR and FPR are each normalised inside their own class, so thinning the negatives leaves AUC unchanged — measured 0.873 / 0.874 / 0.866 / 0.871 / 0.868 for one fixed scorer at prevalence 0.500 / 0.200 / 0.050 / 0.010 / 0.002, while average precision on the *same scores* fell 0.869 → 0.679 → 0.371 → 0.147 → **0.041**. Average precision has a baseline equal to the prevalence, so read it as a lift against that baseline (the lift *rises* as the class thins — 1.7 → 20.6 — which is real and still compatible with an unusable queue). Translate to the operational number with `prevalence_metric_report`: at a fixed **AUC ≈ 0.95**, precision at recall 0.8 was 0.919 / 0.546 / 0.111 / 0.012 at prevalence 0.5 / 0.1 / 0.01 / 0.001, i.e. **1.1 → 89 alerts per true positive**. Same "model quality" by AUC; a review capacity decision that used AUC would be wrong by two orders of magnitude. This is the ranking-side counterpart of the base-rate arithmetic in `audit-eda-data-quality/references/consistency-validity.md`.
- **The mirror-image trap: PR-AUC is not comparable across populations.** The advice "use PR-AUC for imbalanced data" is right about the operating point and wrong about comparison. The same measurement above makes the point: **one fixed scorer**, identical ranking quality throughout, yet AP reads 0.869 / 0.679 / 0.371 / 0.147 / 0.041 purely because prevalence changed. So a model evaluated on a 5% population will look far "better" than the same model on a 0.5% population. Prevalence-invariance is exactly what makes ROC-AUC the right tool for comparing models across datasets, periods, or segments with different base rates — and exactly what disqualifies it from sizing a review queue. Report both, and say which population each number refers to.
- Define the cost/capacity trade-off before choosing metrics or resampling.
- Imbalance is a classification concept; in regression, rare extreme targets are heavy-tail/anomaly territory — handle via distribution analysis, transforms, or asymmetric/quantile losses, not class resampling.
- Imbalance is not sparsity: a sparse label matrix (user-item) can still have near-equal class proportions among observed entries.

Weak Pearson correlation with target is not a reason to smooth or discard features; it misses nonlinear, categorical, and interaction effects.

## Strategy order

- Baseline with no resampling ("do nothing"): a stratified natural distribution with the right metrics often just works, especially for strong learners.
- Acquiring more real minority data (buying, collecting, relabeling) beats synthesizing it whenever the domain allows — evaluate this before any synthetic option.
- Reframing as anomaly detection (one-class/IsolationForest-style) when positives are a handful, heterogeneous, or evolving — then the task is no longer balanced classification at all.
- Class/sample weighting or cost-sensitive learning (`class_weight` in most sklearn classifiers).
- Random oversampling for a transparent baseline. Caveat: replicating rows makes feature variance look **lower** than it is and multiplies every minority error by the replication factor.
- Random undersampling when the majority is redundant and enough information remains. Caveat: it makes feature variance look **higher** and discards data; aggressive distance-based variants (NearMiss) can collapse performance badly.
- SMOTE/Borderline-SMOTE/KMeans-SMOTE for suitable continuous geometry.
- SMOTENC for mixed numeric/categorical data; never treat arbitrary category codes as Euclidean continuous values.
- ADASYN when harder minority neighborhoods deserve more synthesis, with extra noise sensitivity checks.
- Tomek links/ENN or combined methods for overlap cleaning, auditing removed minority points.
- Balanced ensembles when ensemble cost is acceptable: bootstrap the data, downsample each bootstrap to balance, train a learner per sample, vote (Wallace et al., "Class Imbalance, Redux", ICDM 2011) — implemented as `BalancedBaggingClassifier`/`BalancedRandomForestClassifier` in imbalanced-learn. Undersampling inside an ensemble averages away the single-sample information loss.
- AE/VAE/GAN/diffusion generation only as an experiment with strict utility/privacy/fidelity gates.

Do not force 50/50 balance by default. Compare several moderate ratios and weights. Preserve original row IDs and synthetic provenance.

### What works in practice

Benchmarks across learners consistently show: the stronger the model and the cleaner the data, the less sampling helps — a well-tuned boosted-tree model on a clear task often does best with **no resampling** plus threshold/weight adjustment, while resampling mainly pays off for weaker/linear models and noisy overlapping classes. So match the effort to the probe evidence: if the no-resampling baseline with proper metrics is already strong, record that and stop; escalate to synthesis only when weights and thresholds demonstrably fall short.

### Worked rule of thumb

For a 5% positive rate at 150k rows (~7,500 positives), do not force parity. There are enough positives to learn from, and hard rebalancing usually inflates false positives. Start with `class_weight='balanced'` (or a cost-sensitive loss) plus decision-threshold tuning on validation; if resampling still helps, prefer a moderate target (raise minority share toward ~0.1–0.2), not 50/50. Reserve heavier synthesis for genuinely scarce-positive regimes, and always compare against the no-resampling baseline. Threshold tuning is model decision policy — fitted on validation/out-of-fold, never on test — and is not dataset balancing.

## Evaluation

- Keep validation/test at the intended deployment prevalence.
- Use PR-AUC/average precision, class-specific precision/recall, F-beta tied to costs, confusion counts, calibration/Brier/log loss, and operating points.
- Plain accuracy is misleading (a majority-vote dummy already scores the prevalence), but the usual replacements are not interchangeable — see the next two bullets before picking one.
- **Balanced accuracy is prevalence-invariant; Cohen's kappa and MCC are not.** These three get grouped as "robust single-number summaries under imbalance", and they do not behave alike. Balanced accuracy averages TPR and TNR, each normalised inside its own class, so it inherits ROC-AUC's invariance — measured 0.781 / 0.781 / 0.781 / 0.781 / **0.782** for one fixed scorer at prevalence 0.500 / 0.200 / 0.050 / 0.010 / 0.002 — and inherits ROC-AUC's blind spot with it: it says nothing about the alert queue. Kappa and MCC mix the marginals back in and therefore track the base rate the way average precision does: on the **same scores at the same cutoff**, kappa fell **0.562 → 0.451 → 0.196 → 0.048 → 0.010** and MCC 0.562 → 0.477 → 0.284 → 0.134 → 0.061 across that ladder, while ranking quality never moved (AUC 0.863–0.864 throughout). Retuning the threshold to a matched recall of 0.80 in every population does not rescue them (kappa 0.561 → 0.010), so this is prevalence, not threshold drift. Never compare kappa or MCC across populations with different base rates, and never read a low kappa on a rare class as a verdict on the model.
- **Read kappa against its own ceiling, not against 1.** The attainable maximum given the observed marginals is `κ_max = (p_max − p_e) / (1 − p_e)`, with `p_max = min(p_target=1, p_pred=1) + min(p_target=0, p_pred=0)`. It collapses with prevalence faster than kappa does, so the ratio moves the *opposite* way to the raw number: measured κ/κ_max **0.563 → 0.672 → 0.710 → 0.717 → 0.722** over the same ladder on which raw kappa fell 56-fold. At 0.2% prevalence the scorer is capturing a *larger* share of what the marginals permit than it did at 50% — the raw number alone reverses that reading. Report the pair, or report balanced accuracy instead.
- Report the **lift over prevalence** next to any headline number: `precision/prevalence − 1` (the Quetelet coefficient of the confusion table) is the relative gain over predicting at the base rate. Accuracy 98.5% at prevalence 98.5% is zero lift; the same accuracy at 1.5% prevalence with high recall is enormous. This one number exposes "high accuracy by imbalance" instantly.
- ROC-AUC stays useful for ranking and for comparing across populations; it does not "look optimistic under imbalance" — it is invariant to the base rate (measured above), which is a different and more dangerous property. The failure mode is reading an unchanged AUC as an unchanged operating point. Never use it alone: pair it with the operational number from `prevalence_metric_report`.
- Threshold selection belongs to validation/OOF model policy, not data balancing.

## Diagnostic probes

- Use the same folds and fixed preprocessing for all variants.
- Compare raw, weighted, resampled, and cleaned variants with uncertainty across folds.
- Inspect nearest neighbors of synthetic samples and distance to validation/test records.
- Review disagreement and high-loss rows as label-quality candidates; never auto-relabel solely from model predictions.
- For generative data, evaluate marginal/joint fidelity, rare-mode coverage, duplicates/memorization, privacy attacks appropriate to the context, subgroup fairness, and train-on-synthetic/test-on-real utility.
