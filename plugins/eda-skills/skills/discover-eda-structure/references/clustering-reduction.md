# Clustering and dimensionality reduction

## Method selection at a glance

| Purpose | Method | Use when | Avoid / caution |
|---|---|---|---|
| Structure preview | t-SNE / UMAP | ≤ ~10k rows, nonlinear neighborhood exploration, visualization only | large data; never as clustering input, distance, or cluster-area measurement |
| Fast segmentation | K-Means | many rows, compact scaled roughly-spherical groups, `k` roughly known | uneven size/shape, overlap, unknown `k` |
| Soft / overlapping segments | Gaussian Mixture | ellipsoidal overlapping groups, membership probabilities, `k` via BIC/AIC | very large data, plainly spherical clusters, tight compute |
| Density + noise | DBSCAN / HDBSCAN / OPTICS | arbitrary shapes with a meaningful noise class | strongly varying density (plain DBSCAN) |
| Compression / decorrelation | PCA | many correlated numeric features, denoising, reproducibility | raw-feature interpretability matters, nonlinear structure, very few features |
| Latent construct behind a block | Common factor model (PAF) | the columns are indicators of something unobserved and the loadings will be interpreted | you only need compression — then PCA, see `factor-structure.md` |
| Source separation | ICA | signal-like data (sensors, EEG, audio mixtures), statistically independent non-Gaussian sources | Gaussian components (unidentifiable); component order/sign/scale is arbitrary — interpret by content, not index |
| Supervised projection | LDA | class separation for classification | regression, single class, strong imbalance — fit **inside the fold only**, never as unsupervised EDA |

t-SNE/UMAP are visualization instruments: do not cluster the 2D embedding or infer cluster counts from it — cluster in the original or a validated latent space. LDA is supervised, so it belongs to in-fold representation building (handed to `$engineer-select-eda-features`), not unsupervised structure discovery.

## Algorithm choice

### K-Means and MiniBatch K-Means

Use for numeric, scaled, roughly convex and similar-variance groups under Euclidean distance. Check seed stability and unequal-size/density failure. Choose `k` from multiple signals and domain utility, not elbow alone.

**Scaling for cluster discovery:** z-scoring divides by the standard deviation, which is *inflated* exactly for multimodal features — the ones that carry cluster structure — so it suppresses the strongest cluster signal. Range (min-max) scaling avoids this and often recovers structure better (in Mirkin's re-analysis of Kryshtanovsky's two-cluster example, range-normalized iK-means made 96 errors vs 99 for z-scored). Pass `scale="range"` and compare partitions under both scalings before trusting either. PCA "cleaning" before K-Means is contested — it can sharpen or blur the structure; decide by ablation on the clustering result, not by habit.

Initialization matters: prefer `k-means++` (spread-out seeding) over pure random, and keep several restarts (`n_init`) — K-Means/EM converge to local optima. For large `n`, MiniBatchKMeans trades a small quality loss for a large speedup; keep `k-means++` and validate that the minibatch partition agrees with a full K-Means on a subsample before trusting it. A deterministic alternative that also chooses `k` is the anomalous-cluster initialization (below).

### Anomalous clusters and iK-means (deterministic init + k)

The K-Means criterion rewards partitions made of large clusters far from the grand center, so those can be extracted directly (`anomalous_clusters`): take the point farthest from a fixed reference point (default: grand mean), grow its group with a two-center K-Means whose reference center never moves, remove the group, repeat. Then `ik_means` uses the groups larger than a resolution threshold `t` as both the number of clusters and the initial centers (`n_init=1`) — no random restarts, reproducible by construction.

- **Resolution threshold `t`:** `t=1` discards singletons; larger `t` reads as "groups this small are not worth a cluster at this resolution". Discarded groups are returned for triage, not silently dropped.
- **Data-quality bridge:** anomalous singletons are frequent *data-error* candidates (an age of 5000) — route them to the audit skill's outlier triage instead of clustering around them.
- **Reporting:** each group carries its `contribution` — the share of data scatter around the reference it explains; a steep drop in contribution is a natural stopping signal, and the kept-groups' cumulative contribution summarizes how much structure the partition captures.
- Validate the result exactly like any clustering (stability, silhouette profile, domain profiling); deterministic does not mean correct.

### Choosing k (`k_scan`)

No single curve decides `k`. Combine, via `clustering.k_scan`:

- **Elbow / SSE (inertia):** SSE always decreases with `k`; the knee is a candidate, not an answer. The programmatic knee (Kneedle-style max-distance-to-chord, as in the `kneed` package) can disagree with the visual one — treat both as candidates.
- **Silhouette:** average score for cohesion/separation, **plus the per-cluster profile** (`silhouette_profile`, the tabular version of silhouette "knife" plots). A decent average can hide clusters with negative-silhouette points or tiny weak clusters; uneven knife sizes and sharp drops mark merge/split candidates.
- **Davies-Bouldin (lower better) and Calinski-Harabasz (higher better):** centroid/dispersion-based; both are biased toward convex well-separated clusters, so they corroborate rather than decide.
- **Hartigan's rule:** `H_K = (W_K / W_{K+1} − 1)(N − K − 1)` on the SSE curve; take the first K with `H_K < 10`. The best of nine k-selection criteria in Chiang & Mirkin's experiments, and insensitive to 10–20% threshold changes — but SSE from non-optimal runs can break its monotonicity, so read it as a candidate, and prefer the K where `H_K` *drops sharply* below 10 over a marginal crossing. Needs a contiguous k range (computed by `k_scan` automatically).
- **BIC/AIC for GMM:** likelihood-based component-count selection; still combine with stability.
- **Stability (`cluster_stability`) and domain utility:** the final filter.

Expect **more clusters than semantic classes** when a class has several styles/modes (e.g., digit images cluster by writing style: k in the hundreds beats k=10 for purity). That is a finding about within-class structure, not an error. Always inspect representative members or centroids per cluster (human inspection) before naming anything.

### Gaussian Mixtures

Use for continuous ellipsoidal components and soft membership. Compare covariance structures and component counts with BIC/AIC plus stability; mixture components are not automatically real-world classes. Use `predict_proba` to quantify assignment uncertainty: the share of points whose max membership is low identifies boundary/ambiguous regions worth profiling — K-Means silently hard-assigns exactly those points, and stretched (anisotropic) clusters that break spherical K-Means are a classic reason to switch to GMM with full covariance.

### DBSCAN, HDBSCAN, OPTICS

Use when density and noise are meaningful. Scale features and study neighbor-distance sensitivity. DBSCAN struggles with varying density; HDBSCAN/OPTICS can help but still require metric and minimum-size choices.

Choose `eps` from the **k-distance graph** (`clustering.k_distance`): sort each point's distance to its k-th neighbor; the knee is the eps candidate, with `min_samples = k` and the rule of thumb `min_samples >= n_dims + 1` (≥ 3). Too-small eps floods the noise class; too-large eps merges everything into one cluster. OPTICS replaces the single eps with a reachability ordering and tolerates varying density.

### Hierarchical methods

Use for nested exploration or moderate data size. Choose linkage to match the distance. Ward minimizes within-cluster squared Euclidean variance and should not be applied mechanically to arbitrary precomputed dissimilarities.

### Categorical and mixed data

- K-Modes: categorical modes with a matching dissimilarity.
- K-Prototypes: mixed numeric/categorical data; tune the numeric/categorical balance.
- Gower plus PAM/hierarchical: transparent mixed-type distances, but weights and missingness handling must be explicit.
- MCA/FAMD or learned embeddings: alternatives when raw mixed-space distances become uninformative; validate representation loss.

### Time series

- Euclidean: aligned, similar phase, same length.
- DTW/soft-DTW: temporal warping is meaningful; constrain warping to avoid unrealistic matches.
- k-Shape: standardized sequences with shape/phase similarity.
- Feature- or encoder-based: when summary dynamics or learned representation is the actual target; validate against raw-series behavior.

## Validation

- Use at least one internal metric, one stability analysis, and domain profiling.
- Compare against a no-structure or permuted baseline when possible.
- Examine small clusters, noise points, and subgroup concentration.
- Repeat across seeds, samples, scaling, metrics, and plausible parameter ranges.
- Prefer a simpler stable partition over a complex but brittle one.
- When independent labels exist (and were **not** used for clustering), cross-check with `label_alignment`: majority label per cluster, purity, homogeneity. Several clusters per label is normal (within-class modes); low purity with high stability suggests clusters encode a different real factor (style, source, regime) — profile before dismissing. This is a data diagnostic, never a model-accuracy claim.

## Dimensionality reduction

- PCA: inspect explained variance, loadings, reconstruction error, and stability; standardize when units should have equal influence. PCA is **not** the common factor model — it assumes no measurement error and inflates loadings (a true 0.40 indicator reads 0.5023; inflation +0.1602 on a 3-column block). When the columns are indicators of an unobserved construct and the loadings will be interpreted, use `factor_analysis.py`; see `factor-structure.md`, which also has the measured case for parallel analysis over the eigenvalue>1 rule and for oblique over orthogonal rotation.
- ICA: independent (not merely uncorrelated) components for mixed signals; requires non-Gaussian sources, and recovered components have arbitrary order/sign/scale — validate against known source semantics.
- Truncated SVD: sparse counts/TF-IDF; components still need semantic review.
- MCA/FAMD: categorical/mixed data; inspect category contributions.
- UMAP/t-SNE: visualization changes with hyperparameters and seed; global distances and apparent cluster area are not reliable measurements.
- Autoencoder/VAE: compare reconstruction and downstream diagnostic utility to PCA; validate latent stability and collapse.

Clustering should normally use the original or a validated information-preserving representation, not an attractive 2D projection.
