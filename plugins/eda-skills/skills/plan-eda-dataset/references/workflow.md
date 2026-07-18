# EDA workflow

## 1. Frame

- Define the unit of observation, intended decision, target availability, prediction horizon, and operational constraints.
- Record the raw-data version, sources, collection windows, joins, filters, and known selection mechanisms.
- Define group, entity, time, spatial, and source boundaries before choosing a split.

## 2. Protect evaluation integrity

- Preserve an immutable raw layer.
- Reserve a holdout only when enough data exist and the future evaluation protocol is known.
- Use stratified splits only for IID class-balance preservation; use group-aware splits for repeated entities; use chronological or rolling splits for temporal prediction.
- Fit every learned transformation inside train/folds. This includes imputers, scalers, encoders, feature selectors, samplers, PCA, target encoders, and learned embeddings.

## 3. Audit before repair

- Profile schema, semantics, missingness, duplicates, ranges, distributions, labels, and split contamination.
- Separate observation-level defects from feature-level defects and dataset-level sampling bias.
- Flag suspicious values before deciding to correct, cap, impute, or remove them.

## 4. Discover structure

- Match association measures to variable types and relationship shapes.
- Explore clusterability before choosing a clustering algorithm.
- Use dimensionality reduction for a stated purpose: compression, denoising, visualization, or representation discovery.
- For temporal data, test ordering, frequency, gaps, seasonality, drift, and availability before creating lags.

## 5. Engineer and select

- Generate features from domain hypotheses and observed structure.
- Compare filter, wrapper, embedded, and model-agnostic evidence.
- Assess importance stability across folds, seeds, periods, and relevant subgroups.
- Apply any balancing only inside training data and preserve the natural distribution in validation/test.

## 6. Validate readiness

- Re-run schema and integrity checks on the produced dataset.
- Verify split disjointness and point-in-time correctness.
- Perform ablations against a simple baseline; use model results only as diagnostic evidence.
- Save manifests for features, transformations, splits, exclusions, and unresolved risks.

## Iteration rule

Return to an earlier phase only for a named failure. Do not repeatedly inspect the holdout or redesign features from holdout performance.

## What EDA is allowed to conclude

Exploration and confirmation are different activities with different rules, and most damage in practice comes from reporting the output of the first as if it were the second. Tukey's framing — exploratory and confirmatory analysis are complements, and neither replaces the other — is the operating assumption of this whole project. EDA's job is to **generate well-founded hypotheses and to establish that the data can support the intended claim**; it is not to establish that a relationship is real.

Three consequences that bind every stage:

- **Looking at your data is mandatory, not a violation.** The opposite instinct — that inspecting distributions, outliers, dimensionality or cross-loadings is "p-hacking" and should be avoided — gets the ethics backwards. Shipping a model built on a matrix nobody examined is the actual failure. What is forbidden is *undisclosed* data-dependent choice, not data-dependent choice. Every diagnostic in this project exists because deciding without it is worse.
- **Every data-dependent choice is a fork, and forks are expensive.** A modest multiverse of 18 defensible EDA choices turns a 5% false-positive rate into ~30%, and — measured — **does not shrink as `n` grows** (0.292 / 0.300 / 0.296 at n = 100 / 500 / 2000). See `discover-eda-structure/references/associations.md`. This is the quantitative reason the decision log below is not bureaucracy.
- **A pattern is only a pattern against a null.** "Something looks structured here" needs a reference for what unstructured would have looked like at this `n` and this number of candidates: `filter_select.expected_max_noise_correlation` for a screen, `binwidth_sensitivity` for multimodality, `k_scan` for cluster count, `noise_probe_importance` for importance rankings. Without the reference, human pattern-detection supplies one for free, and it is wrong.

### The record that makes exploration legitimate

The distinction that matters is not *whether* choices were data-driven but whether a reader can reconstruct them. For each non-obvious decision record: what was chosen, what the alternatives were, what evidence drove it, and what would have to be true for it to be wrong. Persist domain rules confirmed by the user via `insights.py`; keep one-off choices in the decision log.

This also fixes the scope of a sensitivity/multiverse check: re-running a finding across plausible alternative paths is informative, but only across paths that were *defensible in the first place*. Averaging over choices you would never have made — keeping points every diagnostic calls corrupt, or a transform the mechanism contradicts — dilutes the answer rather than testing it.

### Confirmation is repetition

The one thing exploration cannot do for itself is confirm. A finding earns confidence by reappearing in data that did not shape it — a held-out partition, a later time window, a different site, an independent cohort — not by surviving a more elaborate analysis of the same rows. Where the project can approximate this cheaply it does: split-based re-estimation (`selection_inflation_probe`), out-of-fold scoring, stability across seeds and folds, `label_alignment` against independent labels. Where it cannot, the honest output is a ranked list of hypotheses with the evidence and the ambiguity attached, handed to whoever collects the next batch.

Report format that follows from this: state findings as facts measured / interpretations / hypotheses / missing information (the audit report already requires this split), and never promote a hypothesis to a fact because it was interesting.
