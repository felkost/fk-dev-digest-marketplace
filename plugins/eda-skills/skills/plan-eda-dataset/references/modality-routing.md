# Modality routing

Stages 1–5 are the same for every dataset. Modality switches on **extra
branches inside a stage** — never a different pipeline, and never a second
dataset prepared per model. Fix the modality in the dataset contract, then open
only the branches below that apply.

> **Maintenance:** this file is the expanded routing table. A condensed twin
> lives in `plan-eda-dataset/SKILL.md` ("Маршрутизація за модальністю та
> цільовою моделлю") for the Claude-side reader, and `chatgpt/gpt_instructions.md`
> carries only the branch index plus a pointer here, because its 8000-byte
> budget cannot hold the table. **Adding a modality means editing this file and
> the SKILL.md section.** `tests/check_docs.py` fails if a
> `references/*.md` modality file exists that this table never routes to.

## Time series / panel

Open `discover-eda-structure/references/time-series.md` + `time_series_features.py`.

- Regular grid first: irregular sampling breaks lags, rolling windows and resampling.
- Stationarity (ADF/KPSS) is a **diagnostic, not a verdict**; whole differencing
  buys stationarity by destroying memory — see `frac_diff` / `min_frac_diff_order`.
- Lags and rolling features via `shift` only; the window must end before the
  prediction moment.
- Chronological split + embargo; when the label spans a forward window, apply
  `split_designer.purge_and_embargo` and read `sampling_design.overlapping_label_deff`.

## Images (classification / detection-segmentation / medical-satellite)

Open `audit-eda-data-quality/references/computer-vision.md` + `image_profile.py`;
embeddings as a probe via `discover-eda-structure/embedding_eda.py`.

- Integrity and property distributions before anything semantic.
- Boxes/masks: coordinate convention, out-of-frame, empty masks.
- Image leakage is near-duplicate + group (patient / scene / video), not row identity.
- Per-channel normalisation constants from **train only** — and for a pretrained
  encoder, from its own pretraining (`weights.transforms()`), not from your train.
- `folder_census` + label-mapping consistency: a missing class folder silently
  shifts every label index.

## Text

Audit the raw text first: `audit-eda-data-quality/references/text-nlp.md` + `text_profile.py`.

- NaN and the empty string are different defects — never convert silently.
- OOV coverage of the pretrained vocabulary, per split and per class.
- All-OOV documents flagged explicitly; mean-pooling them yields NaN, so the
  policy must be stated rather than replaced by a magic constant.
- Then embeddings as a probe (`discover-eda-structure/references/diagnostic-representations.md`)
  and pooled features (`PooledTextEmbedding`) with idf fitted on train.

## Geospatial (points / polygons / raster tiles / trajectories)

Open `audit-eda-data-quality/references/geospatial.md`.

- Declared CRS and axis order; distances and areas only in a projected CRS.
- Geometry validity repaired explicitly and logged, never auto-dropped.
- Coordinate sentinels: Null Island, geocoder centroids repeated thousands of times.
- Spatial autocorrelation (Moran's I, semivariogram) is the leakage mechanism →
  block / buffered spatial split via `split_designer.py`; the measured
  autocorrelation range sets the buffer.
- H3/geohash aggregates are learned statistics — fit on train only.

## Relational / graph (social, user-item, transactions, knowledge graph)

Open `audit-eda-data-quality/references/graph-network.md` + `graph_profile.py`.

- **Name the unit of observation first** — node / dyad / directed edge /
  edge-at-time. The row is not it.
- Direction is a declaration, not a property of the file: a mirrored edge list
  (`(a,b)` and `(b,a)`) doubles every degree and halves density; the signature
  is reciprocity exactly 1.000.
- Isolates cannot appear in an edge list, so node count from edges is a lower bound.
- `sampling_design.dyadic_design_effect` instead of the edge count as `n`: a
  nominal 95% CI on the edge table covered the truth 35–55% of the time.
- `split_designer.graph_split` — a declared choice between `transductive` (a new
  link among known nodes) and `inductive` (a new entity arrives). Holding out 20%
  of nodes yields 4% of edges as test and discards 32%.
- Degree / centrality / embeddings computed on the **training graph only**;
  otherwise a node's degree contains its own test edges.

## Other high-dimensional modalities

Embeddings as a probe: `embedding_eda.py` with
`discover-eda-structure/references/diagnostic-representations.md`. Validate
representation loss before trusting distances.

## Mixed / multimodal

Run several branches at once. Prepare the dataset **once**, not separately per
downstream model. Group keys must hold across modalities: the same patient,
scene or user must land on one side of the split in every branch.

## Target model — the thin final layer only

The dataset stays model-agnostic; encoding for a specific model is a documented
final step, not a pipeline fork.

- **Trees / boosting (XGBoost, LightGBM, CatBoost)** — no scaling, native or
  ordinal category encoding, often no imputation.
- **Neural, including generative** — standardisation/normalisation fitted on
  train, one-hot or embedding for categories, imputation required; distance- and
  PCA-based components need scale.

The normalisation block in `audit-eda-data-quality/references/distributions-outliers.md`
holds the transform choices themselves.
