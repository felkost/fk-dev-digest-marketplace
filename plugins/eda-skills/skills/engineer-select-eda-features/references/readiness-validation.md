# Final dataset validation

## Structural checks

- Schema, types, ordering, units, allowed ranges, uniqueness, and referential integrity.
- Expected row/feature counts and documented exclusions.
- Missing/unseen-category behavior on every split.
- Exact and near-duplicate checks across evaluation boundaries.
- **Label-mapping consistency** (`label_mapping_consistency`): one persisted class→index mapping in the dataset card, verified against every split and artifact. Folder-derived mappings rebuilt per split shift indices silently when a class folder is missing.
- **Input contract for non-tabular data:** dtype, value range, channel order/layout, size + interpolation (images); tokenizer + casing + vocabulary version (text). A mismatch raises no error — it just degrades predictions silently.

## Pipeline checks

- Every learned operation is fit only on train/folds.
- Pipeline order is explicit and reproducible.
- Feature names, lineage, seeds, software/model versions, and parameters are saved. For GPU pipelines that includes device seeds (e.g. `torch.cuda.manual_seed_all`) and determinism flags.
- **Round-trip check:** persist the pipeline/artifacts, reload in a fresh state, and reproduce a reference batch of outputs within tolerance — the cheapest proof that what is saved is what was validated.
- Inverse mapping or original values are retained where auditability requires it.

## Statistical checks

- Distribution and missingness summaries by split, time, source, target, and relevant subgroup.
- Drift baseline and alert thresholds are documented, not inferred from one test alone.
- Selected features and representations are stable across folds/seeds/time.
- Cluster-derived features pass stability and domain-coherence checks.

## Diagnostic checks

- Dummy and simple baselines exist.
- Raw versus cleaned/engineered/selected/balanced ablations use the same protocol.
- Out-of-fold predictions support error and label review without touching test.
- Report effect size and uncertainty, not only a best score.
- No result from SHAP, importance, clustering, or a generative model is presented as causal evidence.

## Handoff package

- Dataset card.
- Feature and transformation manifests.
- Split and sampling manifests.
- Data-quality and selection reports.
- Diagnostic probe and ablation report.
- Known limitations, forbidden uses, unresolved risks, and accepted exceptions.

Return `ready`, `ready with accepted limitations`, or `not ready`. A high-severity unresolved leakage, label, identity, or split defect forces `not ready`.

