# Diagnostic representations and current probes

Use representation models as optional instruments, not default requirements.

## Tabular data

- Start with PCA/FAMD and simple tree/linear probes.
- Use an autoencoder or VAE when nonlinear compression, denoising, missingness-aware reconstruction, or anomaly ranking is a concrete hypothesis and data volume supports it.
- A current tabular foundation model can be a no/low-tuning predictive probe. As of July 2026, TabPFN-3 is a current example, but its performance must not replace split integrity, simple baselines, calibration checks, or dataset-specific validation: https://arxiv.org/abs/2605.13986

## Images

- Use frozen self-supervised embeddings for duplicate search, outlier review, cluster exploration, and label-noise triage.
- DINOv3 is a current 2025 self-supervised vision representation example with dense features: https://arxiv.org/abs/2508.10104
- Check domain shift, image preprocessing, resolution, licensing/model-card constraints, and nearest-neighbor failure cases.

## Text

- Precede any embedding use with the raw-text and vocabulary audit (`$audit-eda-data-quality` `references/text-nlp.md` + `text_profile.py`): OOV rate per split/class, all-OOV documents, tokenizer/vocabulary case parity.
- **Neighbor smell test:** nearest neighbors of a handful of domain words/phrases must make sense; garbage neighbors mean corpus/domain mismatch, and no downstream metric fixes that. Analogy arithmetic is a demo, not a quality gate.
- **Social-bias probe:** pretrained word/sentence embeddings encode gender/ethnicity/age associations from their training corpora. When embedding features feed decisions about people, probe bias directions relevant to the domain (e.g. profession↔gender similarity gaps) and record findings in the dataset card's fairness section — a biased representation is a dataset property, not a modeling detail.
- Pooled document vectors (mean / tf-idf-weighted via `PooledTextEmbedding` in `$engineer-select-eda-features`) are legitimate cheap representations; idf is train-fitted, OOV policy explicit.

## Time series

- Compare learned embeddings or a time-series foundation model with statistical features and naive baselines.
- Current model names change rapidly; verify the official paper/model card at execution time. Test zero-shot contamination risk, horizon/frequency compatibility, and panel leakage.

## Generative probes

- AE/VAE, GAN, or diffusion models may support reconstruction analysis, imputation experiments, anomaly review, and synthetic-data hypotheses.
- Do not add generated records by default. Evaluate marginal and joint fidelity, rare modes, privacy/memorization, subgroup fairness, duplicate proximity, and train-on-synthetic/test-on-real utility.
- Keep all fitting and generation inside train/folds. Never synthesize validation/test or allow siblings across splits.
- Diffusion-based tabular generation remains an active area rather than a universal best practice: https://arxiv.org/abs/2502.17119

## Acceptance

Accept a representation only when it improves a stated diagnostic or feature objective, remains stable across seeds/splits, and passes leakage, privacy, cost, and interpretability checks. Preserve the raw features and document the encoder version and preprocessing.

