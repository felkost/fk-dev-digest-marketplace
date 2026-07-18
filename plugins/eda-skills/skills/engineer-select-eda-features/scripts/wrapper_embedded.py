"""Wrapper, embedded, and model-agnostic evidence (engineer steps 4-5).

RFE/SFS, L1/tree importance, out-of-fold permutation importance, a null-target
baseline, an optional SHAP hook, and a paired feature-set significance test.
All evaluation is on validation / out-of-fold predictions -- never tune or read
these on the final test set. No score here is causal evidence.

Core is scikit-learn; SHAP is optional (lazy).
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd


def _default_estimator(task: str, random_state: int):
    if task == "classification":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(n_estimators=200, random_state=random_state, n_jobs=-1)
    from sklearn.ensemble import RandomForestRegressor
    return RandomForestRegressor(n_estimators=200, random_state=random_state, n_jobs=-1)


def rfe_select(X, y, n_features: int = 10, estimator=None, task: str = "classification",
               random_state: int = 42) -> dict:
    from sklearn.feature_selection import RFE

    est = estimator or _default_estimator(task, random_state)
    sel = RFE(est, n_features_to_select=n_features).fit(X.fillna(X.median()), y)
    kept = list(X.columns[sel.support_])
    return {"selected": kept, "ranking": dict(zip(X.columns, sel.ranking_.tolist()))}


def embedded_importance(X, y, task: str = "classification", random_state: int = 42) -> pd.DataFrame:
    """Tree-based importance. Impurity importance is biased toward high-cardinality
    / continuous features -- corroborate with permutation or drop-column."""
    est = _default_estimator(task, random_state).fit(X.fillna(X.median()), y)
    imp = getattr(est, "feature_importances_", None)
    return (
        pd.DataFrame({"feature": X.columns, "importance": np.round(imp, 5)})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


def permutation_importance_oof(X, y, estimator=None, task: str = "classification",
                               cv: int = 5, scoring: Optional[str] = None,
                               random_state: int = 42) -> pd.DataFrame:
    """Permutation importance evaluated out-of-fold (not on training rows)."""
    from sklearn.inspection import permutation_importance
    from sklearn.model_selection import StratifiedKFold, KFold

    est = estimator or _default_estimator(task, random_state)
    Xf = X.fillna(X.median())
    splitter = (StratifiedKFold(cv, shuffle=True, random_state=random_state)
                if task == "classification" else KFold(cv, shuffle=True, random_state=random_state))
    importances = np.zeros((cv, X.shape[1]))
    for i, (tr, va) in enumerate(splitter.split(Xf, y)):
        est.fit(Xf.iloc[tr], y.iloc[tr])
        r = permutation_importance(est, Xf.iloc[va], y.iloc[va], n_repeats=5,
                                   random_state=random_state, scoring=scoring)
        importances[i] = r.importances_mean
    return (
        pd.DataFrame({"feature": X.columns,
                      "perm_importance": importances.mean(0).round(5),
                      "std": importances.std(0).round(5)})
        .sort_values("perm_importance", ascending=False)
        .reset_index(drop=True)
    )


def null_target_importance(X, y, task: str = "classification", n_perm: int = 20,
                           random_state: int = 42) -> pd.DataFrame:
    """Importance under permuted targets -- a noise floor to filter rankings."""
    rng = np.random.default_rng(random_state)
    real = embedded_importance(X, y, task, random_state).set_index("feature")["importance"]
    null = np.zeros((n_perm, X.shape[1]))
    Xf = X.fillna(X.median())
    for i in range(n_perm):
        yp = pd.Series(rng.permutation(y.to_numpy()), index=y.index)
        null[i] = embedded_importance(Xf, yp, task, random_state).set_index("feature").loc[X.columns, "importance"].to_numpy()
    null_df = pd.DataFrame(null, columns=X.columns)
    return pd.DataFrame({
        "feature": X.columns,
        "real": real.loc[X.columns].to_numpy().round(5),
        "null_p95": np.percentile(null_df, 95, axis=0).round(5),
        "above_noise": real.loc[X.columns].to_numpy() > np.percentile(null_df, 95, axis=0),
    }).sort_values("real", ascending=False).reset_index(drop=True)


def noise_probe_importance(X, y, task: str = "classification", n_probes_per_kind: int = 3,
                           n_shadow: int = 3, n_repeats: int = 5,
                           random_state: int = 42) -> pd.DataFrame:
    """Importance vs injected noise probes (canary features).

    Appends synthetic probes -- normal/uniform/laplace noise columns plus
    'shadow' probes (permuted copies of real columns, Boruta-style, which keep
    marginal distributions but break the target link) -- refits an embedded
    model ``n_repeats`` times, and flags real features whose mean importance
    exceeds the 95th percentile of all probe importances.

    Read it two ways: (1) a real feature below the probes has no evidence of
    signal at this sample size/model; (2) probes ranking high -- especially if
    CV score *improved* after adding them -- expose importance bias or an
    overfitted protocol, not real signal.
    """
    rng = np.random.default_rng(random_state)
    Xf = X.fillna(X.median(numeric_only=True))
    real_cols = list(Xf.columns)
    num_cols = list(Xf.select_dtypes(include=[np.number]).columns)
    n = len(Xf)

    real_imp = np.zeros((n_repeats, len(real_cols)))
    probe_imp_all = []
    for r in range(n_repeats):
        Xa = Xf.copy()
        probes = []
        for i in range(n_probes_per_kind):
            Xa[f"_probe_norm_{i}"] = rng.normal(rng.integers(0, 10), rng.integers(1, 10), n)
            Xa[f"_probe_unif_{i}"] = rng.uniform(rng.integers(1, 4), rng.integers(5, 10), n)
            Xa[f"_probe_lapl_{i}"] = rng.laplace(rng.integers(0, 10), rng.integers(1, 10), n)
            probes += [f"_probe_norm_{i}", f"_probe_unif_{i}", f"_probe_lapl_{i}"]
        for i, c in enumerate(rng.choice(num_cols, min(n_shadow, len(num_cols)), replace=False)):
            Xa[f"_shadow_{c}"] = rng.permutation(Xf[c].to_numpy())
            probes.append(f"_shadow_{c}")
        imp = embedded_importance(Xa, y, task, random_state + r).set_index("feature")["importance"]
        real_imp[r] = imp.loc[real_cols].to_numpy()
        probe_imp_all.append(imp.loc[probes].to_numpy())

    probe_p95 = float(np.percentile(np.concatenate(probe_imp_all), 95))
    mean_imp = real_imp.mean(axis=0)
    return pd.DataFrame({
        "feature": real_cols,
        "mean_importance": np.round(mean_imp, 5),
        "std_importance": np.round(real_imp.std(axis=0), 5),
        "probe_p95": round(probe_p95, 5),
        "above_probes": mean_imp > probe_p95,
    }).sort_values("mean_importance", ascending=False).reset_index(drop=True)


def shap_summary(estimator, X_background, X_explain):
    """Optional SHAP values (lazy). Explains a model under a chosen background,
    not the data-generating cause."""
    try:
        import shap
    except ImportError as e:  # pragma: no cover
        raise ImportError("shap is optional; `pip install shap`") from e
    explainer = shap.Explainer(estimator, X_background)
    return explainer(X_explain)


def paired_feature_significance(X, y, features_to_test: Sequence[str], estimator=None,
                                task: str = "classification", mode: str = "cv",
                                n_runs: int = 10, cv: int = 5, scoring: str = "f1",
                                X_val=None, y_val=None, random_state: int = 42) -> dict:
    """Test whether ``features_to_test`` help, comparing model-with vs model-without
    over repeated runs. Returns paired score distributions and a Wilcoxon p-value.

    mode='cv' (preferred): repeated cross-validation on training data.
    mode='holdout': fit on X (train), score on a provided validation set
    ``X_val``/``y_val``. Never pass the final test set here.
    """
    from scipy.stats import wilcoxon
    from sklearn.base import clone
    from sklearn.metrics import get_scorer
    from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold

    est = estimator or _default_estimator(task, random_state)
    Xf = X.fillna(X.median())
    reduced = [c for c in Xf.columns if c not in set(features_to_test)]
    scores_a, scores_b = [], []

    if mode == "cv":
        for r in range(n_runs):
            splitter = (StratifiedKFold(cv, shuffle=True, random_state=random_state + r)
                        if task == "classification"
                        else KFold(cv, shuffle=True, random_state=random_state + r))
            scores_a.append(cross_val_score(clone(est), Xf, y, cv=splitter, scoring=scoring).mean())
            scores_b.append(cross_val_score(clone(est), Xf[reduced], y, cv=splitter, scoring=scoring).mean())
    elif mode == "holdout":
        if X_val is None or y_val is None:
            raise ValueError("mode='holdout' needs a validation set (X_val, y_val), not test")
        scorer = get_scorer(scoring)
        Xv = X_val.fillna(X.median())
        for r in range(n_runs):
            ea, eb = clone(est), clone(est)
            for e in (ea, eb):
                if hasattr(e, "random_state"):
                    e.set_params(random_state=random_state + r)
            ea.fit(Xf, y); eb.fit(Xf[reduced], y)
            scores_a.append(scorer(ea, Xv, y_val))
            scores_b.append(scorer(eb, Xv[reduced], y_val))
    else:
        raise ValueError("mode must be 'cv' or 'holdout'")

    a, b = np.array(scores_a), np.array(scores_b)
    diff = a - b
    try:
        p = float(wilcoxon(a, b).pvalue) if np.any(diff != 0) else 1.0
    except ValueError:
        p = 1.0
    return {
        "scoring": scoring, "mode": mode, "n_runs": n_runs,
        "mean_with": round(float(a.mean()), 5), "mean_without": round(float(b.mean()), 5),
        "mean_gain": round(float(diff.mean()), 5), "std_gain": round(float(diff.std()), 5),
        "wilcoxon_p": round(p, 4),
        "note": "Diagnostic on validation/OOF only; the final test set stays untouched.",
    }


def one_se_rule(results, size_col: str = "k", score_col: str = "mean_score",
                se_col: str = "se", higher_is_better: bool = True) -> dict:
    """Pick the smallest model/feature-set size within one standard error of
    the best CV score (ISLP par. 6.1.3).

    CV score curves are flat near the optimum, so the literal argmax is fold
    noise: rerunning with different folds moves it. When several sizes are
    statistically indistinguishable, take the simplest. ``results`` needs one
    row per candidate size with the CV mean and its standard error
    (``std / sqrt(n_folds)``).
    """
    d = pd.DataFrame(results).dropna(subset=[score_col, se_col]).sort_values(size_col)
    if d.empty:
        raise ValueError("no rows with score and se")
    if higher_is_better:
        best = d.loc[d[score_col].idxmax()]
        threshold = float(best[score_col] - best[se_col])
        ok = d[d[score_col] >= threshold]
    else:
        best = d.loc[d[score_col].idxmin()]
        threshold = float(best[score_col] + best[se_col])
        ok = d[d[score_col] <= threshold]
    chosen = ok.loc[ok[size_col].idxmin()]
    return {"chosen_size": chosen[size_col].item() if hasattr(chosen[size_col], "item") else chosen[size_col],
            "chosen_score": round(float(chosen[score_col]), 5),
            "best_size": best[size_col].item() if hasattr(best[size_col], "item") else best[size_col],
            "best_score": round(float(best[score_col]), 5),
            "threshold": round(threshold, 5)}


__all__ = [
    "rfe_select", "embedded_importance", "permutation_importance_oof",
    "null_target_importance", "noise_probe_importance", "shap_summary",
    "paired_feature_significance", "one_se_rule",
]
