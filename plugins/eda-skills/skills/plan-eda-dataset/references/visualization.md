# Visualizing EDA stages and results

Visualization is part of the evidence chain, not decoration: every important
claim in the audit/discover/engineer reports should be checkable from a plot,
and every plot should say what may and may not be concluded from it. Helpers
live in `scripts/eda_plots.py` (matplotlib-only, figures returned + optionally
saved as artifacts next to the manifests).

## Ground rules

- Plot the **train partition** (or out-of-fold results). Looking at test plots
  to make decisions is leakage through the analyst.
- Save figures as files with the stage artifacts; a plot that exists only in a
  vanished notebook session is not evidence.
- Heavy-tailed variables get **log scales** (`log_x`/`log_y`), not silently
  trimmed outliers. State transformations on the axis label.
- A beautiful 2D projection is a **hypothesis**, not proof of clusters; a
  heatmap shows association, not causality; an importance bar is one model's
  opinion. Captions must carry these caveats.
- Sample large datasets before pairplots/scatter matrices; annotate the sample
  size on the figure.

## Reading errors that change the conclusion

The rules above keep a plot *honest*. These keep it *readable* — which matters
because a figure nobody can decode gets replaced by whatever the reader
already believed. Unlike the rest of this project, these are **craft
conventions from the visualization literature, not measured claims**; they are
included because plots are how audit findings actually travel, and they are
labelled so nobody mistakes them for verified results.

- **Unlabelled quantities.** Units, and above all *what a percentage is taken
  of*. "91%" is unreadable without knowing whether it is growth versus a base
  year or a share of it. This is the same reference-population problem the
  Quetelet lift carries in `discover-eda-structure/references/associations.md`
  — a percentage without its denominator is not a number yet.
- **Everything at once.** Ten ideas on one chart means none is read. Decide the
  single claim the figure is making; move the rest to an appendix table or a
  second figure. Level of detail is a function of the audience, not of how much
  you computed.
- **No sorting.** Alphabetical or table order hides the ranking that the chart
  exists to show. Sort categorical bars by value unless the category has its
  own natural order (time, ordinal grade, severity). With two periods, pick the
  one that carries the argument and sort by it.
- **The wrong mark.** A line asserts that consecutive points are connected —
  legitimate for time, wrong for unordered categories (no institution "follows"
  another). Pie charts read part-of-whole and fail at comparison or trend; a
  slide with several pies is nearly always a bar chart. Line-plus-bar combos
  inherit the same defect.
- **Violating proximity.** Things you want compared belong next to each other
  and on a shared scale; things that cannot share a scale (different units)
  should not be forced into one panel — use small multiples. Labelling series
  directly usually removes the need for a legend, which is itself a proximity
  fix.

For this project's own figures the frequent offenders are the unlabelled
percentage (a rate plotted without its denominator or reference population)
and unsorted importance/category bars — `importance_plot` and `rate_funnel`
outputs should be value-sorted before they enter a report.

## Library choice

- **matplotlib** (required): every helper works with it alone; reproducible
  static artifacts for reports.
- **seaborn** (optional): nicer statistical defaults for the same plots —
  `pairplot(..., hue=target)`, `histplot(..., kde=True)`, stacked `displot`,
  split `violinplot`, annotated `heatmap`. Use when exploring interactively.
- **plotly** (optional): interactivity — hover values, zooming, series
  toggling (`px.histogram(..., marginal="box")`, `px.imshow(corr)`,
  treemaps for hierarchies). Good for exploration and stakeholder demos; keep
  a static export for the record.
- **ydata-profiling** (optional): an auto-generated first-pass overview report.
  It is a *starting checklist*, not an audit — it knows nothing about the unit
  of observation, split design, availability times, or leakage.

## Stage playbook

### Audit (`$audit-eda-data-quality`)

| Question | Plot |
|---|---|
| What does each variable look like? | `hist_by_group` (no group), ECDF, Q-Q for near-normal claims; log-x for heavy tails |
| Do distributions differ by target/source/time? | `hist_by_group(col, group=target)`, `box_by_group` (violin in seaborn for shape) |
| Where are the missing values, and do they co-occur? | `missingness_matrix` + missingness co-occurrence numbers |
| Are flagged outliers errors or a regime? | `box_by_group` per segment, scatter of the two most-involved variables |
| How imbalanced is the target, where? | bar of class counts per source/time/subgroup |
| Is a subgroup's extreme rate real or just small n? | `rate_funnel` over the `group_rate_funnel` table — only groups outside the binomial funnel deserve a ranking claim |

### Discover (`$discover-eda-structure`)

| Question | Plot |
|---|---|
| Which features are redundant? | `corr_heatmap` with the clustered order from `redundancy_blocks` |
| Is a pairwise link real and what shape? | scatter/conditional plot behind every headline correlation/MI number |
| Which cells drive a categorical association? | heatmap of the `quetelet_table` contribution matrix (highlighted cells = pattern carriers); box plot next to a `tabular_regression` table for nominal→numeric |
| How many clusters, if any? | `k_scan_plot` (elbow + silhouette) corroborated by `silhouette_knives` and stability |
| What are the clusters? | per-cluster profiles on original variables; centroids/medoids rendered in the native modality (e.g. images) for human inspection |
| Does the embedding suggest structure/confounds? | `embedding_scatter` colored by label, then by source/batch — a batch-colored pattern is a confound warning |
| Time series behavior? | series plots per entity sample, ACF/PACF stem plots, seasonal decomposition panels |

### Engineer (`$engineer-select-eda-features`)

| Question | Plot |
|---|---|
| Did the transform do what was intended? | before/after `hist_by_group` of the transformed feature |
| Which features carry signal? | `importance_plot` with error bars and the noise-probe baseline (`probe_p95`) |
| Does a feature set actually help? | `probe_comparison` across raw/cleaned/engineered/selected/balanced variants, same folds, error bars |
| What does the probe get wrong? | confusion matrix at a stated threshold, PR curve, calibration curve — on OOF/validation only |
| Is the diagnostic tree interpretable? | `sklearn.tree.plot_tree` of a shallow (depth ≤ 4) probe tree — as a readable rule sketch, not a final model |
| Did balancing distort the space? | `embedding_scatter` of train before/after resampling, synthetic points marked |

### Readiness gate (`plan-eda-dataset`)

The final report bundles the saved figures as the visual appendix: dataset
contract summary, split diagram (class rates per split), the audit's key
distribution/missingness plots, discover's structure evidence, engineer's
importance + probe comparison, each with its caption and decision reference.
