# Feature engineering and extraction

## Numerical features

- Use ratios only with a meaningful denominator and explicit zero handling.
- Use differences, rates, log returns, and normalized measures when domain semantics support comparability.
- Add log/power/rank transforms to address geometry, not merely to make a histogram look normal.
- Preserve original values until ablation shows a transformed-only representation is preferable.
- Fit clipping, bins, quantiles, and transform parameters on train/folds.

### Distributional and cumulative features

- Percentile-rank / empirical-CDF features map a value to its position in the training distribution (`P(X ≤ x)`); fit the ECDF — and any normal-CDF parameters `(μ, σ)` — on train only, then interpolate for validation/test and out-of-range values. These give a bounded, monotone, outlier-robust view that helps distance- and gradient-based models.
- Cumulative sums, running counts, and running event rates capture trajectory but need stable denominators, confidence bands, and drift-aware interpretation. For temporal data compute them strictly from prior rows (see time features) so they remain point-in-time.

## Categorical features

- One-hot low/moderate-cardinality nominal values.
- Encode ordinal categories with documented order.
- Multi-hot unordered multi-label sets; do not collapse to the first or globally frequent category without a domain rule.
- Consolidate rare levels into an explicit `Other` bucket with a train-fitted frequency threshold; unseen levels at inference also route to `Other` (or to the target-encoding global mean). Record the threshold and the affected levels.
- Use hashing/frequency encoding or learned embeddings for high cardinality.
- Use target/mean encoding out-of-fold with smoothing and train-fitted handling of unseen levels.

### Structured-string parsing

Semi-structured identifiers often hide several real features — parse, don't drop or one-hot the raw string:

- split positional codes into components (`Cabin "C85"` → deck `C` + room `85` via `str.slice`/`str.extract`), keeping an explicit `Unknown` level for missing;
- map free-text markers to a small domain vocabulary (name titles → `Mr/Ms/officer/royalty/kid`), with the mapping recorded in the feature contract;
- shared-key group size via `groupby(key)[key].transform("count")` (co-travelers on one ticket, orders per address) — check it is not a near-duplicate of an existing feature before keeping both;
- prefix/suffix flags (alphanumeric ticket prefix vs digits-only) as cheap binary features.

Parsing rules are transformations: fit any thresholds/vocabularies on train, version them, and apply identically at inference.

## Time and group features

- Create lags, rolling/expanding/EWM statistics, calendar/cyclical features, recency, frequency, and time-since-event only from prior information.
- Point-in-time group aggregates must exclude future rows and, where target-like, the current row.
- Record maximum lookback and minimum history requirements.
- Cumulative features can reveal trajectories but need stable denominators, confidence bands, and drift-aware interpretation.

## Basis expansions (splines)

For a nonlinear numeric→target shape that a *linear* probe or additive model must capture, natural cubic splines / `sklearn.preprocessing.SplineTransformer` beat high-degree polynomials: polynomials oscillate at the boundaries, splines stay stable there (ISLP ch. 7). Knots from train quantiles, fitted in the pipeline (train/fold only); treat the spline columns of one variable as a **feature family** in selection (keep/drop together). Trees and NNs learn nonlinearity themselves — basis expansions are for linear/GAM-style consumers and interpretability.

## High-dimensional modalities

- Text: length/quality/language metadata (chars, tokens, OOV share, all-OOV flag — with inference-time availability), sparse TF-IDF/SVD, or pooled embeddings via `PooledTextEmbedding` — mean pooling as baseline, tf-idf-weighted pooling as the cheap upgrade (idf fitted on train only); OOV policy explicit (zero vector + flag, never a silent constant). See audit `references/text-nlp.md` for the vocabulary/casing audit that must precede this.
- Images: resolution/channel/quality metadata, duplicate hashes, frozen self-supervised embeddings, or task-relevant handcrafted descriptors. With a pretrained encoder, use the *encoder's* normalization/size transforms, not train-fitted stats (audit `references/computer-vision.md`).
- Signals/audio: time/frequency statistics, spectral features, wavelets, or validated learned embeddings.
- Latent encoders: compare PCA/SVD with AE/VAE; fit only on train/folds and record encoder/preprocessing versions.

## Practicalities

- Downcast numeric dtypes (int64→int8/16/32, float64→float32) to cut memory on large frames — after value ranges are audited, and never to float16 for money/aggregation columns where precision loss is real. Record dtype changes in the transformation manifest.
- Persist every fitted statistic the pipeline needs at inference (imputation medians, bin edges, encoders, scalers) as versioned artifacts; recomputing them on new data is leakage and skew.

## Scaling

- Standard/robust scaling for distance-, gradient-, regularization-, and PCA-based components.
- Min-max when bounded input is operationally needed; future values may exceed the training range.
- MaxAbs for sparse values when centering would destroy sparsity.
- Tree-only pipelines usually do not need scaling, but hybrid pipelines might.
- Use a column-aware pipeline so binary/one-hot features are not transformed accidentally.

