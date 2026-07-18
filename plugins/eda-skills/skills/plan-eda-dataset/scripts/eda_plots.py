"""Stage visualizations for the EDA workflow (all four skills).

Chart helpers for documenting each EDA stage: distributions and missingness
(audit), correlation structure / cluster diagnostics / embeddings (discover),
importance and probe comparisons (engineer). Every function returns a
matplotlib ``Figure`` and optionally saves it, so plots become reproducible
artifacts next to the manifests rather than one-off notebook output.

Rules the helpers follow (and you should too):
  * plots describe the TRAIN partition (or OOF results) -- never tune anything
    by looking at test;
  * a pretty 2D embedding is not proof of clusters, and a heatmap is not
    causality; captions should state what the viewer may and may not conclude;
  * heavy-tailed axes get log scales instead of silently clipped outliers.

Only matplotlib is required (lazy import). seaborn (nicer statistical defaults)
and plotly (interactive exploration) are optional upgrades -- see
references/visualization.md.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd


def _plt():
    import matplotlib
    import matplotlib.pyplot as plt
    return plt


def _finish(fig, save_path: Optional[str]):
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def hist_by_group(df: pd.DataFrame, col: str, group: Optional[str] = None,
                  bins: int = 30, log_x: bool = False, save_path: Optional[str] = None):
    """Histogram of ``col``, optionally overlaid per ``group`` level (e.g. target).

    Overlaid semi-transparent histograms show where class distributions
    separate or overlap. Use ``log_x`` for heavy-tailed variables (price,
    duration) instead of dropping large values.
    """
    plt = _plt()
    fig, ax = plt.subplots(figsize=(8, 4))
    s = df[col].dropna()
    data = np.log10(s[s > 0]) if log_x else s
    if group is None:
        ax.hist(data, bins=bins, alpha=0.85)
    else:
        for lvl, grp in df.dropna(subset=[col]).groupby(group, observed=True):
            v = grp[col]
            v = np.log10(v[v > 0]) if log_x else v
            ax.hist(v, bins=bins, alpha=0.55, label=f"{group}={lvl}")
        ax.legend()
    ax.set_xlabel(f"log10({col})" if log_x else col)
    ax.set_ylabel("count")
    ax.set_title(f"Distribution of {col}" + (f" by {group}" if group else ""))
    return _finish(fig, save_path)


def box_by_group(df: pd.DataFrame, col: str, group: str, log_y: bool = False,
                 save_path: Optional[str] = None):
    """Box plots of ``col`` per ``group`` level: medians, IQR, whisker outliers.

    Points beyond the whiskers are IQR-flagged candidates, not confirmed
    errors -- route them to the outlier triage, do not delete from the plot.
    """
    plt = _plt()
    d = df.dropna(subset=[col, group])
    levels = sorted(d[group].dropna().unique(), key=str)
    data = [d.loc[d[group] == lvl, col] for lvl in levels]
    fig, ax = plt.subplots(figsize=(max(6, 1.2 * len(levels)), 4))
    ax.boxplot(data, tick_labels=[str(x) for x in levels])
    if log_y:
        ax.set_yscale("log")
    ax.set_xlabel(group)
    ax.set_ylabel(col)
    ax.set_title(f"{col} by {group}")
    return _finish(fig, save_path)


def missingness_matrix(df: pd.DataFrame, max_cols: int = 40,
                       save_path: Optional[str] = None):
    """Binary missingness image (rows x columns) plus per-column missing rate.

    Vertical bands = column-level missingness; horizontal bands = broken
    records/batches; co-occurring bands support a shared-mechanism hypothesis
    (check missingness.cooccurrence for the numbers).
    """
    plt = _plt()
    cols = df.columns[:max_cols]
    M = df[cols].isna().to_numpy()
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(max(6, 0.3 * len(cols)), 6),
        gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    ax1.imshow(M, aspect="auto", interpolation="nearest", cmap="Greys")
    ax1.set_ylabel("row")
    ax1.set_title("Missingness matrix (dark = missing)")
    rates = df[cols].isna().mean().to_numpy()
    ax2.bar(np.arange(len(cols)), rates)
    ax2.set_ylabel("missing rate")
    ax2.set_xticks(np.arange(len(cols)))
    ax2.set_xticklabels(cols, rotation=90, fontsize=7)
    return _finish(fig, save_path)


def corr_heatmap(corr: pd.DataFrame, order: Optional[Sequence[str]] = None,
                 annot_threshold: int = 20, save_path: Optional[str] = None):
    """Correlation/association heatmap; pass a clustered ``order`` (e.g. from
    clustered_correlation.redundancy_blocks) to make redundancy blocks visible.

    Annotates cells only for small matrices. Correlation is association within
    this sample -- not causality, and not proof a feature is (un)informative.
    """
    plt = _plt()
    C = corr.loc[order, order] if order is not None else corr
    n = C.shape[0]
    fig, ax = plt.subplots(figsize=(max(6, 0.35 * n), max(5, 0.35 * n)))
    im = ax.imshow(C.to_numpy(), vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(n)); ax.set_xticklabels(C.columns, rotation=90, fontsize=7)
    ax.set_yticks(range(n)); ax.set_yticklabels(C.index, fontsize=7)
    if n <= annot_threshold:
        for i in range(n):
            for j in range(n):
                ax.text(j, i, f"{C.iat[i, j]:.2f}", ha="center", va="center", fontsize=6)
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title("Association heatmap" + (" (clustered order)" if order is not None else ""))
    return _finish(fig, save_path)


def k_scan_plot(scan: pd.DataFrame, save_path: Optional[str] = None):
    """Elbow + silhouette view of a ``clustering.k_scan`` result table.

    Left axis: SSE/inertia (or BIC) with the flagged knee; right axis: mean
    silhouette. Read both together with stability -- neither curve alone
    chooses k, and more clusters than semantic classes is a valid answer.
    """
    plt = _plt()
    curve = "inertia" if "inertia" in scan.columns else ("bic" if "bic" in scan.columns else None)
    fig, ax1 = plt.subplots(figsize=(8, 4))
    if curve:
        ax1.plot(scan["k"], scan[curve], "o-", label=curve)
        if "elbow_candidate" in scan.columns and scan["elbow_candidate"].any():
            kb = scan.loc[scan["elbow_candidate"], "k"]
            ax1.axvline(float(kb.iloc[0]), ls="--", alpha=0.6, label=f"knee k={int(kb.iloc[0])}")
        ax1.set_ylabel(curve)
    ax1.set_xlabel("k")
    if "silhouette" in scan.columns:
        ax2 = ax1.twinx()
        ax2.plot(scan["k"], scan["silhouette"], "s--", color="tab:green", label="silhouette")
        ax2.set_ylabel("mean silhouette")
    fig.legend(loc="upper right", bbox_to_anchor=(0.98, 0.95), fontsize=8)
    ax1.set_title("k-scan: elbow and silhouette (corroborate with stability)")
    return _finish(fig, save_path)


def silhouette_knives(X, labels, save_path: Optional[str] = None):
    """Classic per-cluster silhouette 'knife' plot.

    Even knives above the dashed mean line = coherent clusters; short or
    negative-tailed knives are merge/split/noise candidates (see
    clustering.silhouette_profile for the table form).
    """
    from sklearn.metrics import silhouette_samples

    plt = _plt()
    X = np.asarray(X, dtype=float)
    labels = np.asarray(labels)
    mask = labels != -1
    sil = silhouette_samples(X[mask], labels[mask])
    lab = labels[mask]
    fig, ax = plt.subplots(figsize=(7, 5))
    y0 = 10
    for lvl in np.unique(lab):
        vals = np.sort(sil[lab == lvl])
        ax.fill_betweenx(np.arange(y0, y0 + vals.size), 0, vals, alpha=0.7)
        ax.text(-0.05, y0 + 0.5 * vals.size, str(lvl))
        y0 += vals.size + 10
    ax.axvline(float(sil.mean()), ls="--", color="red", label=f"mean={sil.mean():.2f}")
    ax.set_xlabel("silhouette value")
    ax.set_yticks([])
    ax.set_title("Silhouette knives per cluster")
    ax.legend()
    return _finish(fig, save_path)


def embedding_scatter(emb, labels=None, method: str = "embedding",
                      save_path: Optional[str] = None):
    """2D scatter of a PCA/UMAP/t-SNE embedding, optionally colored by labels.

    Fit the projection on train only. Visual grouping here is a hypothesis to
    verify in the original/validated space -- never cluster the 2D projection
    or measure cluster sizes/distances from it.
    """
    plt = _plt()
    E = np.asarray(emb, dtype=float)
    fig, ax = plt.subplots(figsize=(6, 5))
    if labels is None:
        ax.scatter(E[:, 0], E[:, 1], s=12, alpha=0.7)
    else:
        labels = np.asarray(labels)
        for lvl in pd.unique(labels):
            m = labels == lvl
            ax.scatter(E[m, 0], E[m, 1], s=12, alpha=0.7, label=str(lvl))
        ax.legend(fontsize=8, markerscale=1.5)
    ax.set_xlabel(f"{method} 1"); ax.set_ylabel(f"{method} 2")
    ax.set_title(f"{method} projection (visual hypothesis, not proof of clusters)")
    return _finish(fig, save_path)


def importance_plot(imp: pd.DataFrame, feature_col: str = "feature",
                    value_col: str = "mean_importance", err_col: Optional[str] = None,
                    baseline: Optional[float] = None, top: int = 25,
                    save_path: Optional[str] = None):
    """Horizontal-bar importance/score plot with optional error bars and a
    noise baseline (e.g. ``probe_p95`` from noise_probe_importance).

    Bars below the baseline line have no demonstrated signal. One ranking from
    one model is evidence, not a verdict -- see selection-importance.md.
    """
    plt = _plt()
    d = imp.nlargest(top, value_col).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, max(3, 0.3 * len(d))))
    err = d[err_col] if err_col and err_col in d.columns else None
    ax.barh(d[feature_col], d[value_col], xerr=err, alpha=0.85)
    if baseline is not None:
        ax.axvline(baseline, ls="--", color="red", label=f"noise baseline={baseline:.4f}")
        ax.legend(fontsize=8)
    ax.set_xlabel(value_col)
    ax.set_title(f"Top-{len(d)} by {value_col} (one method = one piece of evidence)")
    return _finish(fig, save_path)


def probe_comparison(results: pd.DataFrame, variant_col: str = "variant",
                     score_col: str = "score", err_col: Optional[str] = "std",
                     save_path: Optional[str] = None):
    """Bar chart comparing dataset variants (raw/cleaned/engineered/selected/
    balanced) under the SAME probe and split protocol, with fold dispersion.

    Overlapping error bars mean the difference is not established -- use
    paired_feature_significance before claiming a gain.
    """
    plt = _plt()
    fig, ax = plt.subplots(figsize=(max(6, 1.1 * len(results)), 4))
    err = results[err_col] if err_col and err_col in results.columns else None
    ax.bar(results[variant_col].astype(str), results[score_col], yerr=err,
           alpha=0.85, capsize=4)
    ax.set_ylabel(score_col)
    ax.set_title("Probe scores by dataset variant (same folds, OOF/validation)")
    ax.tick_params(axis="x", rotation=20)
    return _finish(fig, save_path)


def rate_funnel(funnel: pd.DataFrame, group_col: Optional[str] = None,
                n_col: str = "n", rate_col: str = "rate",
                save_path: Optional[str] = None):
    """Funnel plot of subgroup rate vs subgroup size (log x).

    Small groups land at both extremes of a rate ranking by chance alone
    (the kidney-cancer-county / small-school effect), so never rank subgroups
    by raw rate. Takes the table from ``distribution_report.group_rate_funnel``
    (or any frame with n / rate / overall_rate / funnel bounds): points inside
    the binomial funnel are statistically indistinguishable from the overall
    rate; only points outside it deserve a ranking claim, and those are
    annotated.
    """
    plt = _plt()
    d = funnel.sort_values(n_col)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if {"funnel_low", "funnel_high"}.issubset(d.columns):
        ax.fill_between(d[n_col], d["funnel_low"], d["funnel_high"],
                        alpha=0.15, color="tab:blue", label="binomial funnel")
    if "overall_rate" in d.columns:
        ax.axhline(float(d["overall_rate"].iloc[0]), ls="--", color="tab:blue",
                   alpha=0.7, label="overall rate")
    out_mask = d["outside_funnel"] if "outside_funnel" in d.columns \
        else pd.Series(False, index=d.index)
    ax.scatter(d.loc[~out_mask, n_col], d.loc[~out_mask, rate_col],
               s=25, alpha=0.7, color="grey", label="inside funnel")
    ax.scatter(d.loc[out_mask, n_col], d.loc[out_mask, rate_col],
               s=35, alpha=0.9, color="tab:red", label="outside funnel")
    if group_col and group_col in d.columns:
        for _, row in d.loc[out_mask].iterrows():
            ax.annotate(str(row[group_col]), (row[n_col], row[rate_col]),
                        fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.set_xscale("log")
    ax.set_xlabel("group size (log)")
    ax.set_ylabel(rate_col)
    ax.set_title("Rate vs group size (extremes in small groups are expected)")
    ax.legend(fontsize=8)
    return _finish(fig, save_path)


__all__ = [
    "hist_by_group", "box_by_group", "missingness_matrix", "corr_heatmap",
    "k_scan_plot", "silhouette_knives", "embedding_scatter", "importance_plot",
    "probe_comparison", "rate_funnel",
]
