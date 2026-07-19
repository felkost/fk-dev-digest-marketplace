"""End-to-end smoke test for the four EDA skills' scripts.

Exercises the leakage-safe utilities on synthetic data (95/5 imbalance + a small
time series + a mixed-category column) and asserts the key invariants the skills
promise:

  1. train-fitted transformers (EmpiricalCDF) do not refit on new data and use
     the training distribution;
  2. rolling/lag features are shifted (no look-ahead);
  3. balancing changes only the training partition and does not force 50/50;
  4. the Ward-on-correlation-distance guard raises;
  5. a leaky single feature is flagged;
  6. the split is index-disjoint and preserves class rates.

Run:  python tests/smoke_test.py     (exit code 0 = all passed)

Uses the core stack only (numpy/pandas/scipy/scikit-learn); optional-dependency
paths (imbalanced-learn, etc.) are skipped if the package is absent.
"""

from __future__ import annotations

import os
import pathlib
import sys
import traceback

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
for sub in ("audit-eda-data-quality", "discover-eda-structure",
            "engineer-select-eda-features", "plan-eda-dataset"):
    sys.path.insert(0, str(ROOT / "skills" / sub / "scripts"))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def deco(fn):
        try:
            fn()
            RESULTS.append((name, True, ""))
            print(f"PASS  {name}")
        except Exception as e:  # noqa: BLE001
            RESULTS.append((name, False, f"{type(e).__name__}: {e}"))
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
    return deco


# --------------------------------------------------------------------------- #
# Synthetic data
# --------------------------------------------------------------------------- #

def make_data(seed: int = 42):
    from sklearn.datasets import make_classification

    X, y = make_classification(
        n_samples=400, n_features=8, n_informative=4, n_redundant=2,
        weights=[0.95, 0.05], class_sep=1.2, random_state=seed,
    )
    cols = [f"f{i}" for i in range(X.shape[1])]
    df = pd.DataFrame(X, columns=cols)
    df["churn"] = y
    # mixed-category column
    rng = np.random.default_rng(seed)
    choices = ["a", "b", "(a, b)", "(b, c)", "c", "(a, c, d)", "d"]
    df["tags"] = rng.choice(choices, size=len(df))
    # inject missingness
    miss_idx = rng.choice(len(df), size=40, replace=False)
    df.loc[miss_idx, "f0"] = np.nan
    return df, cols


DF, NUMCOLS = make_data()


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #

@check("audit.profile_schema roles + issues")
def _():
    import profile_schema as ps
    schema = ps.profile_schema(DF, target="churn")
    assert "role" in schema.columns and schema.loc["churn", "role"].startswith("target/")
    assert schema.loc["tags", "role"] in ("multi_label_or_list", "nominal")


@check("audit.profile_schema: inf is not missing; placeholders/mojibake/#N-A flagged")
def _():
    import profile_schema as ps
    d = pd.DataFrame({
        "ratio": [1.0, 2.0, np.inf, 4.0, -np.inf] + [float(i) for i in range(11)],
        "email": ["email@company.com"] * 14 + ["a@x.com", "b@x.com"],
        "note": ["ok", "cafÃ©"] + ["ok"] * 14,
        "status": ["#N/A"] + ["ok"] * 15,
        "const": [7] * 16,
    })
    sch = ps.profile_schema(d)
    # inf slips past pd.isna(): missing stays 0 while the value destroys stats
    assert sch.loc["ratio", "n_missing"] == 0 and sch.loc["ratio", "n_inf"] == 2
    assert any(i.startswith("non_finite_values") for i in sch.loc["ratio", "issues"])
    assert any(i.startswith("dominant_value_share") for i in sch.loc["email", "issues"])
    assert "encoding_artifacts" in sch.loc["note", "issues"]
    assert "string_sentinels" in sch.loc["status", "issues"]   # Excel #N/A
    assert "constant_value" in sch.loc["const", "issues"]


@check("audit.consistency: label variants, key conflicts, dup resolution, dates, constraints")
def _():
    import consistency as cons

    # 2.4 -- normalized variants caught; short codes NOT fuzzy-merged
    s = pd.Series(["Apples"] * 10 + ["apples"] * 4 + ["appels"] * 3 + ["XL"] * 5 + ["XXL"] * 4)
    nd = cons.near_duplicate_categories(s)
    assert set(nd.loc[nd.reason == "normalized", "variant"]) == {"apples"}
    assert set(nd.loc[nd.reason == "fuzzy", "variant"]) == {"appels"}
    assert "XXL" not in set(nd["variant"])  # length guard, not the ratio cutoff

    # 2.4 -- one product id, two products
    inv = pd.DataFrame({"pid": [1, 1, 2], "name": ["monitor", "monitor stand", "apple"]})
    assert cons.key_attribute_conflicts(inv, "pid")["n_distinct"].tolist() == [2]

    # 2.6 -- conflicting group needs a rule; identical group does not
    d = pd.DataFrame({"c": [1, 1, 3, 3], "city": ["Kyiv", "Lviv", "Rivne", "Rivne"], "t": [1, 2, 1, 1]})
    rep = cons.duplicate_report(d, subset=["c"], order_by="t")
    g = rep["groups"].set_index(rep["groups"]["key"].astype(str))
    assert g.loc["(1,)", "n_conflicting_cols"] > 0 and g.loc["(3,)", "n_conflicting_cols"] == 0
    assert g.loc["(1,)", "keep_index"] == 1  # most recent wins

    # 2.7.2 -- text dates, epoch ints, tz mixture
    dt = pd.DataFrame({
        "signed": ["24 Oct 2019", "25 Oct 2019"],
        "utc": pd.to_datetime(["2024-01-01", "2024-01-02"]).tz_localize("UTC"),
        "naive": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "epoch": [1700000000, 1700000100],
    })
    iss = cons.datetime_consistency(dt)["issues"]
    assert "datetime_stored_as_text" in iss["signed"]
    assert "tz_aware" in iss["utc"] and "tz_naive" in iss["naive"]  # mixture is visible
    assert "possible_epoch_seconds" in iss["epoch"]

    # 2.5 -- invalid produced by our own transformation (midnight wrap)
    app = pd.DataFrame({"start_hour": [9, 23], "finish_hour": [17, 1], "age": [30, 170]})
    app["time_in_app"] = app.finish_hour - app.start_hour
    lc = cons.logical_constraints(app, {
        "duration_non_negative": "time_in_app >= 0",
        "age_plausible": "age >= 0 & age <= 120",
        "broken_rule": "no_such_column > 0",
    })
    assert lc.loc["duration_non_negative", "n_violations"] == 1
    assert lc.loc["age_plausible", "n_violations"] == 1
    assert lc.loc["broken_rule", "error"]  # reported, does not abort the audit


@check("audit.distribution_report numeric + categorical")
def _():
    import distribution_report as dr
    num = dr.numeric_summary(DF, NUMCOLS)
    assert {"median", "mad", "skew"}.issubset(num.columns) and len(num) == len(NUMCOLS)
    cat = dr.categorical_summary(DF, ["tags"])
    assert cat.loc["tags", "cardinality"] >= 4


@check("audit.bootstrap_ci percentile+pivotal cover the truth; diff-CI separates groups")
def _():
    import distribution_report as dr
    rng = np.random.default_rng(0)
    x = rng.normal(10, 2, size=50)
    for method in ("percentile", "pivotal"):
        ci = dr.bootstrap_ci(x, np.mean, n_boot=400, method=method)
        assert ci["low"] < 10 < ci["high"], f"{method} CI misses the true mean"
        assert ci["low"] < ci["estimate"] < ci["high"]
    a, b = rng.normal(8.77, 3, size=40), rng.normal(4.56, 1, size=40)
    diff = dr.bootstrap_diff_ci(a, b, np.mean, n_boot=400)
    assert diff["excludes_zero"] and diff["low"] > 0  # clearly different groups
    same = dr.bootstrap_diff_ci(a, a, np.mean, n_boot=200)
    assert not same["excludes_zero"]


@check("audit.binwidth_sensitivity separates stable from bin-dependent modality")
def _():
    import distribution_report as dr
    rng = np.random.default_rng(1)
    uni = rng.normal(0, 1, size=800)
    bi = np.concatenate([rng.normal(-4, 0.5, 400), rng.normal(4, 0.5, 400)])
    assert dr.binwidth_sensitivity(uni, bins_list=(5, 10)).attrs["conclusion"] == "unimodal"
    out = dr.binwidth_sensitivity(bi, bins_list=(5, 10, 15, 30))
    assert out.attrs["conclusion"] == "multimodal_stable"
    assert (out["n_modes"] >= 2).all()


@check("audit.gini/decile_ratio/group_rate_funnel")
def _():
    import distribution_report as dr
    cat = dr.categorical_summary(DF, ["tags"])
    assert 0 < cat.loc["tags", "gini"] < 1
    rng = np.random.default_rng(2)
    heavy = np.exp(rng.normal(0, 1.5, size=2000))
    assert dr.decile_ratio(heavy) > dr.decile_ratio(rng.uniform(1, 2, size=2000))
    # a large deviating group must fall outside the funnel; a tiny group with a
    # 100% rate must stay inside it (its band is wide) -- ranking it is the trap
    d = pd.DataFrame({
        "g": ["low"] * 450 + ["high"] * 450 + ["tiny"] * 3,
        "y": [1] * 135 + [0] * 315            # low: 30%
             + [1] * 315 + [0] * 135          # high: 70%
             + [1] * 3,                       # tiny: 100% on n=3, overall ~50%
    })
    fun = dr.group_rate_funnel(d, "y", "g", min_n=30).set_index("g")
    assert bool(fun.loc["low", "outside_funnel"]) and bool(fun.loc["high", "outside_funnel"])
    assert not bool(fun.loc["tiny", "outside_funnel"])  # extreme but tiny -> chance
    assert bool(fun.loc["tiny", "small_group"])


@check("audit.count_dispersion separates Poisson / gamma-Poisson / zero-inflated / bounded")
def _():
    import distribution_report as dr
    rng = np.random.default_rng(7)

    pois = dr.count_dispersion(pd.Series(rng.poisson(4.0, 3000)))
    assert pois["verdict"] == "equidispersed" and abs(pois["vmr"] - 1) < 0.25
    assert not pois["excess_zeros"]

    # a Poisson rate that is itself gamma-distributed IS the negative binomial
    lam = rng.gamma(shape=2.0, scale=2.0, size=3000)
    nb = dr.count_dispersion(pd.Series(rng.poisson(lam)))
    assert nb["verdict"] == "overdispersed" and nb["vmr"] > 2
    assert "negative_binomial" in nb["suggested_family"]

    # structural zeros show up as excess zeros, not just as dispersion
    zi = np.where(rng.random(3000) < 0.30, 0, rng.poisson(4.0, 3000))
    z = dr.count_dispersion(pd.Series(zi))
    assert z["excess_zeros"] and z["zero_rate_observed"] > 3 * z["zero_rate_poisson"]

    # binomial has VMR = 1-p by construction, so it reads as underdispersed
    b = dr.count_dispersion(pd.Series(rng.binomial(10, 0.5, 3000)))
    assert b["verdict"] == "underdispersed" and abs(b["vmr"] - 0.5) < 0.1

    assert dr.count_dispersion(pd.Series([1.5, 2.5] * 20))["verdict"] == "not_count_data"
    assert dr.count_dispersion(pd.Series([1, 2, 3]))["verdict"] == "insufficient_data"


@check("audit.mean_variance_scaling recovers b=0/1/2 (additive / count / multiplicative)")
def _():
    import distribution_report as dr
    rng = np.random.default_rng(11)

    def build(kind, n_groups=25, per=400):
        rows = []
        for g in range(n_groups):
            level = 5 + 4 * g
            if kind == "additive":
                v = rng.normal(level, 3.0, per)
            elif kind == "poisson":
                v = rng.poisson(level, per).astype(float)
            else:
                v = rng.lognormal(np.log(level), 0.4, per)
            rows.append(pd.DataFrame({"v": v, "g": g}))
        return pd.concat(rows, ignore_index=True)

    add = dr.mean_variance_scaling(build("additive"), "v", "g")
    assert abs(add["b"]) < 0.5 and add["suggested_transform"] == "none"

    cnt = dr.mean_variance_scaling(build("poisson"), "v", "g")
    assert abs(cnt["b"] - 1) < 0.3 and cnt["suggested_transform"] == "sqrt"

    mul = dr.mean_variance_scaling(build("multiplicative"), "v", "g")
    assert abs(mul["b"] - 2) < 0.3 and mul["suggested_transform"] == "log"

    tiny = pd.DataFrame({"v": [1.0, 2, 3, 4], "g": [0, 0, 1, 1]})
    assert dr.mean_variance_scaling(tiny, "v", "g")["verdict"] == "insufficient_groups"

    # a clean lognormal must still get the log recommendation
    assert mul["zero_fraction"] == 0.0 and mul["warning"] is None


@check("audit.mean_variance_scaling refuses a bare log on zero-inflated (Tweedie 1<p<2) data")
def _():
    import distribution_report as dr
    rng = np.random.default_rng(5)

    # compound Poisson-gamma: a zero mass plus a continuous positive part, with the
    # event SIZE growing across groups so b lands in the log zone (~2)
    rows = []
    for g in range(25):
        n_ev = rng.poisson(1.2, 500)
        scale = 20.0 * (1 + 0.35 * g)
        y = np.array([rng.gamma(2.0, scale, k).sum() if k else 0.0 for k in n_ev])
        rows.append(pd.DataFrame({"spend": y, "g": g}))
    r = dr.mean_variance_scaling(pd.concat(rows, ignore_index=True), "spend", "g")

    assert 1.5 <= r["b"] <= 2.5, r["b"]          # shape alone says "log"
    assert r["zero_fraction"] > 0.2              # but a third of the rows are zero
    assert "NOT a bare log" in r["suggested_transform"]
    assert "Tweedie" in r["mechanism"] and r["warning"]

    # negatives are a different failure: a log is undefined, not merely lossy
    neg = pd.concat([pd.DataFrame({"v": rng.lognormal(np.log(5 + 4 * g), 0.4, 400) - 3,
                                   "g": g}) for g in range(25)], ignore_index=True)
    rn = dr.mean_variance_scaling(neg, "v", "g")
    assert rn["n_negative"] > 0 and "shift" in rn["suggested_transform"]


@check("audit.rate_homogeneity: constant rate aggregates, drifting rate does not")
def _():
    import distribution_report as dr
    rng = np.random.default_rng(3)

    assert dr.rate_homogeneity(rng.poisson(50, 12))["safe_to_aggregate"]
    assert not dr.rate_homogeneity(rng.poisson(np.linspace(20, 90, 12)))["safe_to_aggregate"]

    # unequal period lengths at one true rate must NOT read as drift
    expo = np.array([1, 1, 2, 2, 3, 3, 1, 1, 2, 2, 3, 3], float)
    fp = sum(not dr.rate_homogeneity(rng.poisson(30 * expo), expo)["safe_to_aggregate"]
             for _ in range(400))
    assert fp / 400 < 0.12, f"exposure weighting miscalibrated: {fp / 400}"

    assert dr.rate_homogeneity([5])["verdict"] == "insufficient_data"
    assert dr.rate_homogeneity([1, 2], [1, 0])["verdict"] == "invalid_exposure"


@check("audit.distribution_shift: magnitude survives growing n where the p-value does not")
def _():
    import distribution_report as dr
    rng = np.random.default_rng(3)

    # a shift of 0.005 sd is nothing, but the KS p-value chases n. Magnitude
    # converges on the truth while the test's verdict flips with sample size.
    prev_psi = None
    for n in (10_000, 200_000):
        r = dr.distribution_shift(rng.normal(0, 1, n), rng.normal(0.005, 1, n))
        assert r["verdict"] == "stable", (n, r["verdict"], r["psi"])
        assert r["wasserstein_scaled"] < 0.05
        if prev_psi is not None:
            assert r["psi"] < prev_psi
        prev_psi = r["psi"]

    # The headline: at n=1e6 a 0.01 sd shift -- still practically nothing -- is
    # significant in 15/15 runs while PSI sits ~1000x below the 0.1 threshold.
    # (0.005 sd is deliberately NOT used here: its systematic D of 0.001995 lands
    # almost exactly on the critical value 0.001923, so rejection is only ~73%
    # reliable -- fine as an illustration, useless as an assertion.)
    big_n = dr.distribution_shift(rng.normal(0, 1, 1_000_000),
                                  rng.normal(0.01, 1, 1_000_000))
    assert big_n["ks_p"] < 0.05                  # the test "detects" it...
    assert big_n["verdict"] == "stable"           # ...the magnitude says otherwise
    assert big_n["psi"] < 0.001

    # a real shift must escalate (measured: escalates in 100/100 runs,
    # min psi_ratio 9.4 at n=1000 and 242.9 at n=20000)
    big = dr.distribution_shift(rng.normal(0, 1, 20_000), rng.normal(0.5, 1, 20_000))
    assert big["verdict"] in ("moderate_shift", "major_shift") and big["psi_ratio"] > 10

    # PSI's null expectation is exactly (B-1)*(1/n_ref + 1/n_cur) -- so at n=100
    # raw PSI averages ~0.19 between a sample and ITSELF, which the naive
    # "> 0.1 = drift" rule would report as drift. The guard must absorb that:
    # measured false-alarm rate 5.0% at n=100, 4.5% at n=200, 0% from n=1000.
    small = dr.distribution_shift(rng.normal(0, 1, 100), rng.normal(0, 1, 100))
    assert abs(small["psi_null_expected"] - 9 * (2 / 100)) < 1e-9
    assert not small["psi_reliable"] and "warning" in small

    psis, alarms = [], 0
    for _ in range(40):
        s = dr.distribution_shift(rng.normal(0, 1, 100), rng.normal(0, 1, 100))
        psis.append(s["psi"])
        alarms += s["verdict"] != "stable"
    assert np.mean(psis) > 0.12, np.mean(psis)   # the naive threshold would fire
    assert alarms <= 8, alarms                   # but the guard rarely does

    # categorical: an unseen level is reported without being allowed to dominate
    ref = pd.Series(["a"] * 500 + ["b"] * 300 + ["c"] * 200)
    cur = pd.Series(["a"] * 480 + ["b"] * 320 + ["c"] * 195 + ["NEW"] * 5)
    cat = dr.distribution_shift(ref, cur)
    assert cat["kind"] == "categorical" and cat["unseen_categories"] == ["NEW"]
    assert cat["verdict"] == "stable" and "warning_unseen" in cat

    # an empty bin must stay finite (the common `log(e/a + eps)` idiom returns inf)
    base = rng.normal(0, 1, 5000)
    trunc = base[base > np.percentile(base, 12)]
    assert np.isfinite(dr.distribution_shift(base, trunc)["psi"])

    assert dr.distribution_shift([], [1, 2, 3])["verdict"] == "insufficient_data"


@check("audit.regression_to_mean: separates pure RTM from a real effect")
def _():
    import distribution_report as dr
    rng = np.random.default_rng(0)

    # nothing happens between the two measurements: any movement is RTM
    n = 40_000
    truth = rng.normal(50, 10.0, n)
    pre = truth + rng.normal(0, 7.0, n)
    post = truth + rng.normal(0, 7.0, n)

    low = dr.regression_to_mean(pre, post, select="low", q=0.10)
    assert low["verdict"] == "explained_by_regression_to_mean", low
    assert low["observed_change"] > 5          # the "worst" group visibly "improves"...
    assert abs(low["excess_change"]) < 0.5     # ...and none of it survives
    assert low["reference_fit"] == "non_selected_rows"

    high = dr.regression_to_mean(pre, post, select="high", q=0.10)
    assert high["observed_change"] < -5 and high["verdict"] == "explained_by_regression_to_mean"

    # a real effect on the selected group must be recovered by `excess_change`.
    # The reference line is fitted on the NON-selected rows precisely because a
    # whole-sample fit absorbs part of it (measured: 1.784 recovered of a true 3.0).
    for effect in (3.0, -2.0):
        m = pre <= np.quantile(pre, 0.10)
        post_t = post.copy()
        post_t[m] += effect
        out = dr.regression_to_mean(pre, post_t, select="low", q=0.10)
        assert out["verdict"] == "effect_survives_rtm"
        assert abs(out["excess_change"] - effect) < 0.3, (effect, out["excess_change"])
        # the raw before/after difference is NOT the effect
        assert abs(out["observed_change"] - effect) > 4

    assert dr.regression_to_mean([1, 2, 3], [1, 2, 3])["verdict"] == "insufficient_data"
    assert dr.regression_to_mean([1, 2, 3], [1, 2])["verdict"] == "length_mismatch"
    assert dr.regression_to_mean([5] * 50, [5] * 50)["verdict"] == "no_variance"


@check("discover.range_restriction recovers a known unrestricted correlation")
def _():
    import associations as A
    rng = np.random.default_rng(1)
    n = 120_000
    r_true = 0.50
    x = rng.normal(0, 1, n)
    y = r_true * x + np.sqrt(1 - r_true ** 2) * rng.normal(0, 1, n)

    for keep in (0.50, 0.75, 0.90):
        m = x >= np.quantile(x, keep)
        r_obs = float(np.corrcoef(x[m], y[m])[0, 1])
        assert r_obs < r_true - 0.15            # restriction really did attenuate it
        out = A.range_restriction(r_obs, x[m].std(), x.std())
        assert out["verdict"] == "restricted" and out["u"] < 1
        assert abs(out["r_unrestricted"] - r_true) < 0.06, (keep, out)

    assert A.range_restriction(0.3, 1.0, 1.0)["verdict"] == "no_restriction"
    assert A.range_restriction(0.3, 0.0, 1.0)["verdict"] == "invalid_sd"
    assert A.range_restriction(1.5, 0.5, 1.0)["verdict"] == "invalid_r"
    assert A.range_restriction(0.0, 0.5, 1.0)["r_unrestricted"] == 0.0


@check("audit.family_router: tail classifier separates lognormal / Pareto / log-Cauchy")
def _():
    import family_router as fr
    rng = np.random.default_rng(0)

    # log of a Pareto is exponential (excess kurtosis exactly 6); log of a
    # lognormal is normal (0); log of a log-Cauchy has no moments at all.
    par = fr.tail_index(rng.pareto(1.5, 8000) + 1)
    assert par["tail_family"] == "pareto_like"
    assert abs(par["alpha"] - 1.5) < 0.25, par["alpha"]      # Hill recovers the truth

    ln = fr.tail_index(rng.lognormal(0, 2, 8000))
    assert ln["tail_family"] == "lognormal_like"
    # lognormal(0,2) yields Hill alpha ~1, which read naively claims an infinite
    # mean for a distribution whose moments all exist -- the guard is the family,
    # not alpha
    assert abs(ln["log_skew"]) < 0.5

    lc = fr.tail_index(np.exp(np.clip(rng.standard_cauchy(8000), -500, 500)))
    assert lc["tail_family"] == "log_heavy" and lc["log_kurtosis"] > 20


@check("audit.family_router routes nine known signatures, and stays silent on clean data")
def _():
    import family_router as fr
    rng = np.random.default_rng(4)

    lam = rng.gamma(2.0, 2.0, 4000)
    n_ev = rng.poisson(1.2, 4000)
    spend = np.array([rng.gamma(2.0, 60.0, k).sum() if k else 0.0 for k in n_ev])
    cases = [
        ("overdispersed counts", pd.Series(rng.poisson(lam)), "negative_binomial"),
        ("zero-inflated", pd.Series(np.where(rng.random(4000) < 0.45, 0, rng.poisson(lam))),
         "zero_inflated_poisson"),
        ("underdispersed", pd.Series(rng.binomial(10, 0.5, 4000)), "conway_maxwell_poisson"),
        ("spend with zero mass", pd.Series(spend), "tweedie"),
        ("Pareto tail", pd.Series(rng.pareto(1.5, 4000) + 1), "stable"),
        ("proportion", pd.Series(rng.beta(2, 5, 4000)), "logit_normal"),
    ]
    for name, s, expected in cases:
        fams = list(fr.route(s)["candidates"]["family"])
        assert expected in fams, f"{name}: expected {expected}, got {fams}"

    # families already ON the chart, and well-behaved data, must produce nothing:
    # a router that always answers is a random family generator
    assert fr.route(pd.Series(rng.lognormal(0, 1, 4000)))["candidates"].empty
    assert fr.route(pd.Series(rng.normal(50, 8, 4000)))["candidates"].empty

    # every routed family must carry a URL to read before it may be adopted
    cand = fr.route(pd.Series(rng.pareto(1.5, 4000) + 1))["candidates"]
    assert cand["url"].str.startswith("http").all() and cand["reason"].str.len().min() > 10
    assert all(f in fr.CATALOGUE for f in cand["family"])


@check("audit.missingness by column + vs target")
def _():
    import missingness as ms
    s = ms.missingness_summary(DF)
    assert s.loc["f0", "missing_rate"] > 0
    vt = ms.missingness_vs_target(DF, "churn")
    assert "gap" in vt.columns


@check("audit.lowrank_impute beats column means on correlated data; probe ranks them")
def _():
    import missingness as ms
    rng = np.random.default_rng(5)
    n = 400
    z = rng.normal(size=n)
    d = pd.DataFrame({"a": z + rng.normal(scale=0.1, size=n),
                      "b": -2 * z + rng.normal(scale=0.1, size=n),
                      "c": z + rng.normal(scale=0.1, size=n)})
    d_miss = d.copy()
    hide = rng.choice(n, size=60, replace=False)
    d_miss.loc[hide, "a"] = np.nan
    res = ms.lowrank_impute(d_miss, n_components=1)
    err_lr = float(np.mean(np.abs(res["imputed"].loc[hide, "a"] - d.loc[hide, "a"])))
    err_mean = float(np.mean(np.abs(d_miss["a"].mean() - d.loc[hide, "a"])))
    assert err_lr < 0.5 * err_mean  # correlation structure exploited
    # the probe (masks KNOWN cells) must agree: lowrank clearly better than median
    pr_med = ms.imputation_quality_probe(d_miss, strategy="median", n_repeats=3)
    pr_lr = ms.imputation_quality_probe(d_miss, strategy="lowrank", n_repeats=3,
                                        n_components=1)
    mae_med = pr_med.set_index("column").loc["a", "mae"]
    mae_lr = pr_lr.set_index("column").loc["a", "mae"]
    assert mae_lr < mae_med
    assert pr_lr.set_index("column").loc["a", "truth_corr"] > 0.9


@check("audit.permutation_test_groups detects a shift, passes a null")
def _():
    import distribution_report as dr
    rng = np.random.default_rng(6)
    a = rng.exponential(1.0, size=60)          # skewed: theoretical t dubious
    b = rng.exponential(1.0, size=60) + 0.8
    res = dr.permutation_test_groups(a, b, n_perm=300)
    assert res["p_value"] < 0.05 and res["statistic"] < 0
    null = dr.permutation_test_groups(a, rng.exponential(1.0, size=60), n_perm=300)
    assert null["p_value"] > 0.05


@check("audit.text_profile summary/OOV/all-OOV/case-mismatch/vocab-overlap")
def _():
    import text_profile as tp
    texts = pd.Series(["What is the step by step guide?",
                       "what is the step by step guide?",   # normalized duplicate
                       "",                                   # empty string
                       None,                                 # NaN — separate defect
                       "Xylophone qwertyzz",                # partially OOV
                       "zzqq zzqq"])                        # all-OOV doc
    s = tp.text_summary(texts)
    assert s["n_nan"] == 1 and s["n_empty_string"] == 1
    assert s["duplicate_rate_normalized"] > 0
    vocab = {"what", "is", "the", "step", "by", "guide", "xylophone"}
    cov = tp.vocabulary_coverage(texts, vocab)
    assert cov["n_all_oov_docs"] >= 2          # NaN doc + zzqq doc
    assert 0 < cov["token_oov_rate"] < 1
    # case mismatch: token 'Step' OOV as-is but in vocab lowercased
    cov2 = tp.vocabulary_coverage(pd.Series(["Step Guide"]), vocab,
                                  tokenizer=lambda t: t.split())
    assert cov2["n_case_mismatch_types"] == 2
    ov = tp.vocab_overlap(["the cat sat"], ["the dog sat"])
    assert 0 < ov["unseen_token_rate"] < 1
    freq = tp.token_frequencies(texts)
    assert list(freq.columns) == ["token", "count", "rank"]


@check("audit.outliers multivariate fit-on-train, score-test")
def _():
    import outliers as ol
    train, test = DF.iloc[:300], DF.iloc[300:]
    rep = ol.multivariate_outliers(train, NUMCOLS, score_df=test)
    assert len(rep) == len(test) and {"is_outlier", "anomaly_score"}.issubset(rep.columns)


@check("audit.split_designer stratified is disjoint + preserves rates")
def _():
    import split_designer as sd
    out = sd.make_split(DF, strategy="stratified_random", target="churn", test_size=0.25)
    tr, te = out["train_idx"], out["test_idx"]
    assert len(set(tr) & set(te)) == 0
    assert out["manifest"]["overlap_checks"]["index_overlap"] == 0
    r_tr = DF.iloc[tr]["churn"].mean()
    r_te = DF.iloc[te]["churn"].mean()
    assert abs(r_tr - r_te) < 0.05  # stratification preserved prevalence


@check("audit.leakage_checks flags a leaky single feature")
def _():
    import leakage_checks as lc
    X = DF[NUMCOLS].copy()
    X["leak"] = DF["churn"].astype(float)  # perfect leak
    res = lc.suspicious_single_features(X, DF["churn"])
    row = res[res["column"] == "leak"].iloc[0]
    assert bool(row["suspicious"]) and row["oof_auc"] > 0.9


@check("audit.image_profile integrity/channel-stats/near-dup (needs Pillow)")
def _():
    try:
        from PIL import Image
    except ImportError:
        print("      (Pillow absent -> image_profile check skipped)")
        return
    import os
    import tempfile
    import image_profile as ip
    with tempfile.TemporaryDirectory() as d:
        solid = np.full((24, 24, 3), 120, np.uint8)
        Image.fromarray(solid).save(os.path.join(d, "a.png"))
        Image.fromarray(solid).save(os.path.join(d, "b.png"))  # duplicate
        chk = (np.indices((24, 24)).sum(0) % 2 * 255).astype(np.uint8)
        Image.fromarray(np.stack([chk] * 3, -1)).save(os.path.join(d, "c.png"))
        paths = [os.path.join(d, f) for f in ("a.png", "b.png", "c.png")]
        prof = ip.profile_images(paths)
        assert len(prof) == 3 and int(prof["corrupt"].sum()) == 0
        cs = ip.channel_stats([solid, solid])  # train-only normalization constants
        assert len(cs["mean"]) == 3
        dups = {(os.path.basename(i), os.path.basename(j))
                for i, j, _ in ip.near_duplicate_pairs(paths, max_distance=5)}
        assert ("a.png", "b.png") in dups  # duplicate caught (would be split leakage)
        assert isinstance(ip.blur_score(paths[0]), float)  # cv2-or-numpy fallback


# --------------------------------------------------------------------------- #
# discover
# --------------------------------------------------------------------------- #

@check("discover.auto_association picks a measure")
def _():
    import associations as asc
    r = asc.auto_association(DF, "f0", "f1")
    assert r["measure"] == "spearman" and -1 <= r["value"] <= 1
    v = asc.distance_correlation(DF["f0"].fillna(0), DF["f1"])
    assert 0 <= v <= 1


@check("discover.quetelet_table decomposition consistent with chi-square")
def _():
    import associations as asc
    from scipy import stats as st
    rng = np.random.default_rng(3)
    x = rng.choice(["a", "b", "c"], size=600)
    y = np.where((x == "a") & (rng.random(600) < 0.6), "yes",
                 rng.choice(["yes", "no"], size=600))
    qt = asc.quetelet_table(x, y)
    chi2_ref = st.chi2_contingency(qt["counts"], correction=False)[0]
    assert abs(qt["chi2"] - chi2_ref) < 0.05                 # sum p*q == chi2/N
    # returned frames are rounded for display -> loose-but-tight tolerances
    assert abs(qt["contribution"].to_numpy().sum() - qt["phi2"]) < 1e-4
    assert abs((qt["pearson_residuals"].to_numpy() ** 2).sum() - qt["phi2"]) < 1e-3
    # 2x2: quetelet(cell 0,0) == (ad - bc) / ((a+c)(a+b)) -- Mirkin's four-fold form
    xs = ["y", "y", "n", "n", "y", "n"]
    ys = ["p", "q", "p", "q", "p", "p"]
    t = pd.crosstab(pd.Series(xs), pd.Series(ys))
    a_, b_, c_, d_ = t.iloc[0, 0], t.iloc[0, 1], t.iloc[1, 0], t.iloc[1, 1]
    q2 = asc.quetelet_table(xs, ys)
    expect = (a_ * d_ - b_ * c_) / ((a_ + c_) * (a_ + b_))
    assert abs(q2["quetelet"].iloc[0, 0] - expect) < 1e-6
    assert q2["highlight"].shape == q2["quetelet"].shape


@check("discover.tabular_regression eta^2 matches correlation_ratio")
def _():
    import associations as asc
    cats = pd.Series(["tcp"] * 64 + ["icmp"] * 10 + ["udp"] * 26)
    rng = np.random.default_rng(4)
    vals = pd.Series(np.concatenate([rng.normal(99, 20, 64),
                                     rng.normal(50, 5, 10),
                                     rng.normal(2, 1, 26)]))
    tab = asc.tabular_regression(cats, vals)
    assert "(all)" in tab.index and tab.loc["(all)", "n"] == 100
    assert abs(tab.attrs["eta"] ** 2 - tab.attrs["eta_squared"]) < 1e-9
    assert abs(tab.attrs["eta"] - asc.correlation_ratio(cats, vals)) < 1e-9
    assert tab.attrs["eta_squared"] > 0.5  # groups clearly differ
    # within-category mean is the least-squares piecewise-constant prediction
    assert abs(tab.loc["udp", "mean"] - vals[cats == "udp"].mean()) < 0.05


@check("discover.clustered_correlation + redundancy blocks; Ward guard raises")
def _():
    import clustered_correlation as cc
    res = cc.clustered_correlation(DF[NUMCOLS], distance="1-abs", linkage_method="average")
    assert list(res["ordered_corr"].columns) == res["order"]
    blocks = cc.redundancy_blocks(DF[NUMCOLS], abs_threshold=0.5)
    assert "blocks" in blocks and "isolated" in blocks
    raised = False
    try:
        cc.clustered_correlation(DF[NUMCOLS], linkage_method="ward")
    except ValueError:
        raised = True
    assert raised, "Ward on correlation distance must raise"


@check("discover.cluster_tendency hopkins in [0,1]")
def _():
    import cluster_tendency as ct
    h = ct.hopkins_statistic(DF[NUMCOLS].fillna(0))
    assert 0.0 <= h <= 1.0


@check("discover.VIF catches collinearity pairwise correlation misses")
def _():
    import clustered_correlation as cc
    rng = np.random.default_rng(0)
    n = 400
    w, z = rng.normal(size=n), rng.normal(size=n)
    d = pd.DataFrame({"w": w, "z": z, "x": w + z + rng.normal(scale=0.05, size=n),
                      "q": rng.normal(size=n)})  # x is a combination of w and z

    # the whole point: no pair looks alarming, yet collinearity is severe
    off_diag = d.corr().abs().to_numpy()[~np.eye(4, dtype=bool)]
    assert off_diag.max() < 0.8, "setup broken: a pairwise correlation is already high"
    vt = cc.variance_inflation_factors(d).set_index("feature")["vif"]
    assert vt["x"] > 50 and vt["w"] > 50 and vt["z"] > 50  # VIF sees it
    assert vt["q"] < 2  # unrelated feature stays clean

    dup = d.assign(x_copy=d["x"])
    assert np.isinf(cc.variance_inflation_factors(dup).set_index("feature").loc["x_copy", "vif"])

    # iterative pruning: dropping ONE feature clears the whole block
    res = cc.vif_prune(d, threshold=10.0)
    assert res["dropped"] == ["x"] and set(res["kept"]) == {"w", "z", "q"}
    assert (res["final_vif"]["vif"] <= 10).all()
    assert "x" in cc.vif_prune(d, threshold=10.0, keep=["x"])["kept"]  # protected

    const = cc.variance_inflation_factors(pd.DataFrame({"a": w, "c": np.ones(n)}))
    assert np.isnan(const.set_index("feature").loc["c", "vif"])  # constant -> NaN, no crash


@check("discover.clustering + internal indices + stability")
def _():
    import clustering as cl
    out = cl.run_clustering(DF[NUMCOLS].fillna(0), algorithm="kmeans", k=3)
    idx = cl.internal_indices(out["X"], out["labels"])
    assert idx["n_clusters"] == 3 and -1 <= idx["silhouette"] <= 1
    stab = cl.cluster_stability(DF[NUMCOLS].fillna(0), algorithm="kmeans", k=3, n_boot=6)
    assert -1 <= stab["mean_ari"] <= 1


@check("discover.clustering k_scan/silhouette_profile/k_distance/label_alignment")
def _():
    import clustering as cl
    from sklearn.datasets import make_blobs
    Xb, yb = make_blobs(n_samples=240, centers=3, cluster_std=0.6, random_state=0)
    scan = cl.k_scan(Xb, k_range=range(2, 7), algorithm="kmeans")
    assert {"k", "inertia", "silhouette", "elbow_candidate"}.issubset(scan.columns)
    assert scan["elbow_candidate"].sum() == 1  # one knee flagged on the SSE curve
    assert scan.loc[scan["silhouette"].idxmax(), "k"] == 3  # true k wins silhouette
    gmm_scan = cl.k_scan(Xb, k_range=range(2, 5), algorithm="gmm")
    assert "bic" in gmm_scan.columns
    out = cl.run_clustering(Xb, algorithm="kmeans", k=3)
    prof = cl.silhouette_profile(out["X"], out["labels"])
    assert len(prof) == 3 and prof["mean_sil"].min() > 0.3  # clean blobs: no weak knives
    kd = cl.k_distance(Xb, k=4)
    assert kd["eps_candidate"] > 0 and np.all(np.diff(kd["sorted_k_distances"]) >= 0)
    align = cl.label_alignment(out["labels"], yb)
    assert align["purity"] > 0.95 and align["homogeneity"] > 0.9  # clusters match labels


@check("discover.k_scan hartigan rule + anomalous_clusters/ik_means on blobs")
def _():
    import clustering as cl
    from sklearn.datasets import make_blobs
    from sklearn.metrics import adjusted_rand_score
    # Hartigan's threshold-10 rule scales with N (a split must beat ~10/(N-K-1)
    # relative SSE gain), so use a small sample where the rule can fire at all
    Xh, _ = make_blobs(n_samples=60, centers=3, cluster_std=0.5, random_state=0)
    scan = cl.k_scan(Xh, k_range=range(2, 8), algorithm="kmeans")
    assert {"hartigan", "hartigan_candidate"}.issubset(scan.columns)
    assert scan["hartigan"].iloc[0] == scan["hartigan"].dropna().max()  # sharp drop after k=2
    assert scan["hartigan_candidate"].sum() == 1
    assert int(scan.loc[scan["hartigan_candidate"], "k"].iloc[0]) == 3  # true k

    Xb, yb = make_blobs(n_samples=300, centers=3, cluster_std=0.5, random_state=2)
    # anomalous-cluster init: deterministic, recovers the 3 blobs
    ac = cl.anomalous_clusters(Xb, t=1, scale="range")
    assert ac["K"] >= 3 and ac["groups"]["size"].sum() == 300
    assert abs(ac["groups"].loc[ac["groups"]["is_kept"], "contribution"].sum()) <= 1.01
    ik = cl.ik_means(Xb, t=20, scale="range")  # resolution: ignore groups <= 20
    assert ik["K"] == 3
    assert adjusted_rand_score(yb, ik["labels"]) > 0.95
    # a far-away singleton is set aside as a data-error candidate, not clustered
    Xout = np.vstack([Xb, [[60.0, 60.0]]])
    ac2 = cl.anomalous_clusters(Xout, t=1, scale=False)
    first = ac2["groups"].iloc[0]
    assert first["size"] == 1 and not first["is_kept"]  # extracted first, flagged
    assert 300 in ac2["discarded_indices"]
    # scale routing accepts the named scalers
    for s in (True, False, "standard", "range", "robust"):
        cl.run_clustering(Xb[:50], algorithm="kmeans", k=2, scale=s)


@check("discover.dim_reduction PCA fit-train transform-test (no refit)")
def _():
    import dim_reduction as dm
    train, test = DF[NUMCOLS].fillna(0).iloc[:300], DF[NUMCOLS].fillna(0).iloc[300:]
    state = dm.fit_reduce(train, method="pca", n_components=3)
    emb_test = dm.apply_reduce(state, test)
    assert emb_test.shape == (len(test), 3)
    assert sum(state["explained_variance"]) <= 1.0 + 1e-9


@check("discover.time_series rolling is shifted (no look-ahead)")
def _():
    import time_series_features as ts
    d = pd.DataFrame({"v": np.arange(1, 11, dtype=float)})  # 1..10
    out = ts.add_rolling(d, "v", windows=[3], funcs=["mean"], shift=1)
    # at row index 4 (value 5), rolling mean of PRIOR 3 rows = mean(2,3,4) = 3.0
    assert abs(out.loc[4, "v_roll3_mean"] - 3.0) < 1e-9
    lagged = ts.add_lags(d, "v", lags=[1])
    assert abs(lagged.loc[5, "v_lag1"] - 5.0) < 1e-9  # value at t-1


@check("discover.time_series stationarity/pacf/regular-grid helpers")
def _():
    import time_series_features as ts
    rng = np.random.default_rng(0)
    x = np.zeros(400)
    for t in range(1, 400):
        x[t] = 0.7 * x[t - 1] + rng.standard_normal()
    p = ts.pacf(x, nlags=4)
    assert abs(p[0] - 1.0) < 1e-9 and p[1] > 0.4 and abs(p[2]) < 0.3  # AR(1) signature
    tt = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 03:00"])
    reg = ts.to_regular_grid(pd.DataFrame({"ts": tt, "v": [10.0, 11.0, 13.0]}), "ts", freq="1h")
    assert reg["v"].tolist() == [10.0, 11.0, 11.0, 13.0]  # 02:00 filled from past, not future
    assert ts.add_difference(pd.DataFrame({"v": [1.0, 3.0, 6.0]}), "v")["v_diff1"].iloc[1] == 2.0
    rep = ts.stationarity_report(x)
    assert "rolling" in rep and "adf" in rep


@check("discover.embedding_eda separability/near-dup/label-noise")
def _():
    import embedding_eda as ee
    rng = np.random.default_rng(1)
    A = rng.normal(0.0, 0.5, size=(60, 16))
    B = rng.normal(4.0, 0.5, size=(60, 16))
    X = np.vstack([A, B])
    y = np.array([0] * 60 + [1] * 60)
    X = np.vstack([X, X[0:1]])           # exact duplicate of point 0
    y = np.append(y, y[0])
    dups = ee.near_duplicate_pairs(X, threshold=0.01)
    assert any(0 in (i, j) for i, j, _ in dups)          # duplicate detected (split leakage)
    assert ee.separability_probe(X, y)["linear_probe_accuracy"] > 0.9  # blobs separable
    yn = y.copy(); yn[0] = 1                              # mislabel a blob-A point
    assert ee.label_noise_candidates(X, yn, k=10)["suspect"].sum() >= 1
    s = ee.summary(X, y)
    assert {"clusterability", "n_near_duplicate_pairs", "separability"} <= set(s)


# --------------------------------------------------------------------------- #
# engineer
# --------------------------------------------------------------------------- #

@check("engineer.EmpiricalCDF fit-train, transform-test, range + out-of-range")
def _():
    import feature_builders as fb
    train = DF[["f1"]].iloc[:300].to_numpy()
    cdf = fb.EmpiricalCDF().fit(train)
    out = cdf.transform(DF[["f1"]].iloc[300:].to_numpy())
    assert out.min() >= 0.0 and out.max() <= 1.0
    # a value above the training max maps to ~1.0 (uses train distribution)
    big = cdf.transform(np.array([[DF["f1"].max() + 100]]))
    assert big[0, 0] == 1.0


@check("engineer.MixedCategoryMultiHot train vocab + unknown handling")
def _():
    import feature_builders as fb
    enc = fb.MixedCategoryMultiHot(name="tags").fit(DF["tags"].iloc[:300])
    out = enc.transform(pd.Series(["(a, b)", "zzz", "c"]))
    assert "tags__count" in out.columns and "tags__unknown" in out.columns
    assert out.loc[1, "tags__unknown"] == 1  # 'zzz' unseen
    assert out.loc[0, "tags__count"] == 2


@check("engineer.oof_target_encode returns oof + mapping")
def _():
    import feature_builders as fb
    from sklearn.model_selection import StratifiedKFold
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    oof, mapping, gm = fb.oof_target_encode(DF["tags"], DF["churn"], cv)
    assert len(oof) == len(DF) and 0 <= gm <= 1 and len(mapping) >= 1


@check("engineer.PooledTextEmbedding mean/tfidf pooling + explicit OOV policy")
def _():
    import feature_builders as fb
    emb = {"cat": np.array([1.0, 0.0]), "dog": np.array([0.0, 1.0]),
           "the": np.array([0.5, 0.5])}
    train = pd.Series(["the cat", "the dog", "cat dog", "the the cat"])
    pool = fb.PooledTextEmbedding(emb, weighting="mean", name="q").fit(train)
    out = pool.transform(pd.Series(["cat dog", "zzz unknown", None]))
    assert list(out.columns) == ["q_emb0", "q_emb1", "q_all_oov"]
    assert np.allclose(out.iloc[0, :2], [0.5, 0.5])          # mean of cat+dog
    assert out.loc[1, "q_all_oov"] == 1 and np.allclose(out.iloc[1, :2], 0)
    assert out.loc[2, "q_all_oov"] == 1                       # NaN -> flagged, not 0.1
    # tf-idf weighting: 'the' is frequent -> low idf -> 'cat' dominates the pool
    poolw = fb.PooledTextEmbedding(emb, weighting="tfidf", name="q").fit(train)
    v = poolw.transform(pd.Series(["the cat"])).iloc[0]
    assert v["q_emb0"] > 0.5  # closer to 'cat' than the unweighted mean
    raised = False
    try:
        fb.PooledTextEmbedding(emb, oov_policy="error").fit(train).transform(["zzz"])
    except ValueError:
        raised = True
    assert raised


@check("engineer.one_se_rule picks the simplest model within one SE")
def _():
    import wrapper_embedded as we
    res = pd.DataFrame({
        "k": [1, 2, 3, 4, 5, 6],
        "mean_score": [0.60, 0.79, 0.80, 0.805, 0.81, 0.808],
        "se": [0.01, 0.012, 0.012, 0.012, 0.012, 0.012],
    })
    out = we.one_se_rule(res)
    assert out["best_size"] == 5
    # threshold = 0.81 - 0.012 = 0.798: k=2 (0.79) misses it, k=3 (0.80) is in
    assert out["chosen_size"] == 3
    low = we.one_se_rule(res.assign(mean_score=lambda d: 1 - d["mean_score"]),
                         higher_is_better=False)
    assert low["chosen_size"] == 3


@check("engineer.label_mapping_consistency catches shifted folder-derived labels")
def _():
    import readiness_check as rc
    train_map = {"pizza": 0, "steak": 1, "sushi": 2}
    ok = rc.label_mapping_consistency(train_map, dict(train_map),
                                      names=["train", "test"])
    assert ok["consistent"]
    # 'steak' folder missing in test -> sushi silently becomes index 1
    test_map = {"pizza": 0, "sushi": 1}
    bad = rc.label_mapping_consistency(train_map, test_map, names=["train", "test"])
    assert not bad["consistent"]
    d = bad["differences"][0]
    assert d["missing_classes"] == ["steak"] and d["index_shifted"] == ["sushi"]


@check("audit.folder_census counts per class per split + missing folders")
def _():
    import tempfile
    import image_profile as ip
    with tempfile.TemporaryDirectory() as root:
        for split, classes in {"train": {"pizza": 3, "steak": 2, "sushi": 1},
                               "test": {"pizza": 1, "sushi": 2}}.items():
            for cls, n in classes.items():
                d = pathlib.Path(root) / split / cls
                d.mkdir(parents=True)
                for i in range(n):
                    (d / f"{i}.jpg").write_bytes(b"x")
        (pathlib.Path(root) / "test" / "steak").mkdir()  # empty class folder
        census = ip.folder_census(root)
        assert census.loc["pizza", "train"] == 3 and census.loc["steak", "test"] == 0
        assert "steak" in census.attrs["missing_class_folders"]["test"]


@check("engineer.filter_select constants/dupes/relevance/prune")
def _():
    import filter_select as fs
    d = DF[NUMCOLS].copy()
    d["const"] = 1.0
    d["dupe_f1"] = d["f1"]
    assert "const" in fs.constant_and_low_variance(d)
    assert "dupe_f1" in fs.duplicate_columns(d)
    rel = fs.relevance_scores(DF[NUMCOLS].fillna(0), DF["churn"])
    assert "mutual_info" in rel.columns and len(rel) == len(NUMCOLS)
    pr = fs.prune_redundant(d, abs_threshold=0.95)
    assert "dupe_f1" in pr["dropped"]


@check("engineer.mrmr select + stability")
def _():
    import mrmr
    sel = mrmr.mrmr_select(DF[NUMCOLS].fillna(0), DF["churn"], k=4)
    assert len(sel["selected"]) == 4
    stab = mrmr.mrmr_stability(DF[NUMCOLS].fillna(0), DF["churn"], k=4, n_folds=3)
    assert "frequency" in stab.columns


@check("engineer.wrapper embedded + permutation-OOF + null + paired A/B")
def _():
    import wrapper_embedded as we
    from sklearn.tree import DecisionTreeClassifier
    X, y = DF[NUMCOLS].fillna(0), DF["churn"]
    light = DecisionTreeClassifier(max_depth=4, random_state=0)
    imp = we.embedded_importance(X, y)
    assert len(imp) == len(NUMCOLS)
    perm = we.permutation_importance_oof(X, y, estimator=light, cv=3)
    assert "perm_importance" in perm.columns
    nul = we.null_target_importance(X, y, n_perm=4)
    assert "above_noise" in nul.columns
    sig = we.paired_feature_significance(
        X, y, features_to_test=["f0", "f1"], estimator=light,
        mode="cv", n_runs=3, cv=3, scoring="f1",
    )
    assert {"mean_gain", "wilcoxon_p"}.issubset(sig)


@check("engineer.noise_probe_importance canaries flag no-signal features")
def _():
    import wrapper_embedded as we
    X, y = DF[NUMCOLS].fillna(0).copy(), DF["churn"]
    rng = np.random.default_rng(7)
    X["pure_noise"] = rng.normal(size=len(X))  # a known no-signal feature
    npi = we.noise_probe_importance(X, y, n_repeats=3, random_state=7)
    assert {"mean_importance", "probe_p95", "above_probes"}.issubset(npi.columns)
    assert not npi.set_index("feature").loc["pure_noise", "above_probes"]
    assert npi["above_probes"].sum() >= 2  # informative features do beat the probes
    assert not npi["feature"].str.startswith("_probe").any()  # probes not returned as features


@check("engineer.balancing weights + moderate resample (train-only)")
def _():
    import balancing as bl
    train = DF.iloc[:300]
    w = bl.compute_class_weights(train["churn"])
    assert set(w) == {0, 1} and w[1] > w[0]  # minority upweighted
    Xr, yr, man = bl.random_resample(train[NUMCOLS], train["churn"], kind="over", target_ratio=0.2)
    minority_ratio = np.mean(yr == 1) / np.mean(yr == 0)
    assert 0.15 < minority_ratio < 0.45  # moved toward ~0.2, NOT 50/50
    assert man["validation_test_prevalence"].startswith("natural")
    assert len(Xr) >= len(train)  # oversampled


@check("engineer.class_duplicate_report detects duplication-inflated imbalance")
def _():
    import balancing as bl
    X = DF[NUMCOLS].fillna(0).copy()
    y = DF["churn"].copy()
    # duplicate a majority row many times -> imbalance looks worse than it is
    maj_idx = y[y == 0].index[0]
    X_dup = pd.concat([X, X.loc[[maj_idx]].iloc[[0] * 60]], ignore_index=True)
    y_dup = pd.concat([y, pd.Series([0] * 60)], ignore_index=True)
    rep = bl.class_duplicate_report(X_dup, y_dup)
    assert rep["classes"][0]["duplicate_rate"] > 0.1
    assert rep["classes"][1]["duplicate_rate"] == 0.0
    assert rep["minority_ratio_dedup"] > rep["minority_ratio_raw"]  # dedup reveals milder imbalance


@check("engineer.readiness structural checks + verdict")
def _():
    import readiness_check as rc
    train, test = DF.iloc[:300].copy(), DF.iloc[300:].copy()
    train["id"] = np.arange(300)
    test["id"] = np.arange(300, len(DF))
    checks = rc.run_structural_checks(train, test, key_cols=["id"])
    good = rc.readiness_gate(checks)
    assert good["verdict"] in ("ready", "ready_with_accepted_limitations")
    # now force a leak: overlapping ids
    test2 = test.copy(); test2["id"] = 0
    bad = rc.readiness_gate(rc.run_structural_checks(train, test2, key_cols=["id"]))
    assert bad["verdict"] == "not_ready"


@check("plan.eda_plots stage visualizations render (Agg)")
def _():
    try:
        import matplotlib
    except ImportError:
        return  # optional dependency absent -- helpers are lazy, skip
    matplotlib.use("Agg")
    import eda_plots as ep
    import clustering as cl
    from sklearn.datasets import make_blobs

    f1 = ep.hist_by_group(DF, "f1", group="churn")
    f2 = ep.box_by_group(DF, "f1", "churn")
    f3 = ep.missingness_matrix(DF)
    f4 = ep.corr_heatmap(DF[NUMCOLS].corr())
    Xb, yb = make_blobs(n_samples=150, centers=3, cluster_std=0.7, random_state=1)
    scan = cl.k_scan(Xb, k_range=range(2, 6))
    f5 = ep.k_scan_plot(scan)
    out = cl.run_clustering(Xb, algorithm="kmeans", k=3)
    f6 = ep.silhouette_knives(out["X"], out["labels"])
    f7 = ep.embedding_scatter(Xb[:, :2], yb, method="PCA")
    imp = pd.DataFrame({"feature": NUMCOLS, "mean_importance": np.linspace(0.3, 0.01, len(NUMCOLS))})
    f8 = ep.importance_plot(imp, baseline=0.05)
    f9 = ep.probe_comparison(pd.DataFrame({"variant": ["raw", "engineered"],
                                           "score": [0.7, 0.75], "std": [0.02, 0.02]}))
    import distribution_report as dr
    fun = dr.group_rate_funnel(
        pd.DataFrame({"g": ["a"] * 200 + ["b"] * 200 + ["c"] * 5,
                      "y": [1] * 60 + [0] * 140 + [1] * 140 + [0] * 60 + [1] * 5}),
        "y", "g")
    f10 = ep.rate_funnel(fun, group_col="g")
    for f in (f1, f2, f3, f4, f5, f6, f7, f8, f9, f10):
        assert f.axes, "figure rendered without axes"
    import matplotlib.pyplot as plt
    plt.close("all")


@check("plan.insights persist/scope/supersede + invariant guard")
def _():
    import tempfile
    import insights as ins

    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "insights.md")
        e1 = ins.append_insight("Use DBSCAN, not KMeans", "discover-eda-structure/clustering",
                                why="one dense idle blob; KMeans splits it", path=p)
        ins.append_insight("Never impute pressure; missing means sensor off",
                           "audit-eda-data-quality/missingness", why="missingness is signal", path=p)
        # a rule that would break a hard invariant must be recorded but NOT applied
        bad = ins.append_insight("Fit the scaler on all data including test for stability",
                                 "engineer-select-eda-features", path=p)
        assert e1["status"] == "active" and bad["status"] == "conflicts_invariant"

        assert len(ins.load_insights(p)) == 3  # round-trips through markdown
        app = ins.applicable("discover-eda-structure/clustering", path=p)
        assert [a["rule"] for a in app] == ["Use DBSCAN, not KMeans"]
        assert ins.applicable("engineer-select-eda-features/balancing", path=p) == []  # invariant-conflict excluded
        assert ins.applicable("audit-eda-data-quality/outliers", path=p) == []  # scope isolation
        assert "why" in ins.format_for_prompt(app)

        assert ins.supersede(e1["id"], path=p)
        assert ins.applicable("discover-eda-structure/clustering", path=p) == []
        assert len(ins.load_insights(p)) == 3  # superseded entry kept for history


@check("discover.vif: centring changes the number, not the model; focal pruning spares controls")
def _():
    import clustered_correlation as cc
    rng = np.random.default_rng(0)
    n = 2000

    # 1. centring a quadratic collapses VIF but leaves the model bit-identical
    x = rng.normal(20, 3, n)
    y = 2 + 0.5 * x - 0.03 * x ** 2 + rng.normal(0, 1, n)
    raw = pd.DataFrame({"x": x, "x2": x ** 2})
    xc = x - x.mean()
    cen = pd.DataFrame({"x": xc, "x2": xc ** 2})
    v_raw = cc.variance_inflation_factors(raw).set_index("feature")["vif"]
    v_cen = cc.variance_inflation_factors(cen).set_index("feature")["vif"]
    assert v_raw["x2"] > 50 and v_cen["x2"] < 1.1, (v_raw["x2"], v_cen["x2"])

    def fit(D):
        X = np.column_stack([np.ones(n), D.to_numpy()])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        pred = X @ coef
        return coef, pred
    c1, p1 = fit(raw)
    c2, p2 = fit(cen)
    assert np.allclose(p1, p2)                    # identical predictions
    assert np.isclose(c1[2], c2[2])               # identical highest-order coefficient
    assert not np.isclose(c1[1], c2[1])           # lower-order term now means something else

    # 2. collinearity confined to controls must not trigger pruning
    z, u = rng.normal(size=n), rng.normal(size=n)
    d = pd.DataFrame({
        "focal_a": z * 0.5 + rng.normal(size=n) * 0.87,
        "focal_b": z * 0.5 + rng.normal(size=n) * 0.87,
        "ctrl_1": u * 0.995 + rng.normal(size=n) * 0.1,
        "ctrl_2": u * 0.995 + rng.normal(size=n) * 0.1,
        "ctrl_3": u * 0.995 + rng.normal(size=n) * 0.1,
    })
    assert cc.vif_prune(d, threshold=10.0)["dropped"], "global prune should fire here"
    focal = ["focal_a", "focal_b"]
    assert cc.vif_prune(d, threshold=10.0, focal=focal)["dropped"] == [], \
        "controls collinear only among themselves cost the focal predictors nothing"

    # 3. but a control that overlaps a focal predictor IS removed
    d2 = d.copy()
    d2["ctrl_bad"] = d2.focal_a * 0.97 + rng.normal(size=n) * 0.24
    out = cc.vif_prune(d2, threshold=10.0, focal=focal)
    assert out["dropped"] == ["ctrl_bad"], out["dropped"]
    assert set(focal).issubset(out["kept"])       # focal features are never dropped


@check("discover.leverage_diagnostics: mean h = p/n, flags concentrated designs")
def _():
    import associations as A
    rng = np.random.default_rng(0)

    # identity that must hold exactly for any design: mean leverage == p/n
    r = A.leverage_diagnostics(pd.DataFrame(rng.normal(size=(500, 4))))
    assert r["p"] == 5 and np.isclose(r["mean_leverage"], r["p"] / r["n"])

    bal = A.leverage_diagnostics(pd.DataFrame(rng.normal(size=(200, 3))))
    assert bal["clt_safe"] and bal["max_leverage"] < 0.2

    # a heavy-tailed design concentrates leverage: this is the case where
    # non-normal errors actually break interval coverage
    lev = A.leverage_diagnostics(pd.DataFrame(rng.pareto(1.2, size=(200, 3)) + 1))
    assert not lev["clt_safe"] and lev["max_leverage"] > 0.5

    # a single extreme row is enough
    X = np.vstack([rng.normal(size=(199, 3)), [[50, 50, 50]]])
    one = A.leverage_diagnostics(pd.DataFrame(X))
    assert not one["clt_safe"] and one["top"][0]["leverage"] > 0.5

    assert A.leverage_diagnostics(pd.DataFrame(rng.normal(size=(3, 5))))["verdict"] == "insufficient_rows"


@check("discover.semipartial_correlations: sr2 is the R2 increment, pr2 >= sr2")
def _():
    import associations as A
    rng = np.random.default_rng(3)
    n = 4000
    x1 = rng.normal(size=n)
    x2 = 0.6 * x1 + np.sqrt(1 - 0.36) * rng.normal(size=n)
    y = 0.5 * x1 + 0.3 * x2 + rng.normal(size=n)
    df = pd.DataFrame({"x1": x1, "x2": x2, "y": y})

    out = A.semipartial_correlations(df, "y")
    row = out.set_index("feature").loc["x1"]

    # sr2 must equal the drop-column increment in R2, by definition
    def r2(cols):
        Xm = np.column_stack([np.ones(n)] + [df[c].to_numpy() for c in cols])
        coef, *_ = np.linalg.lstsq(Xm, y, rcond=None)
        res = y - Xm @ coef
        return 1 - (res @ res) / ((y - y.mean()) ** 2).sum()

    assert np.isclose(row["sr2"], r2(["x1", "x2"]) - r2(["x2"]), atol=1e-6)
    # pr2 uses the smaller denominator, so it can never be below sr2
    assert (out["pr2"] >= out["sr2"] - 1e-12).all()
    # unique parts cannot exceed the joint fit; the remainder is shared
    assert out.attrs["sum_sr2"] <= out.attrs["r2_full"] + 1e-9
    assert np.isclose(out.attrs["shared_r2"],
                      out.attrs["r2_full"] - out.attrs["sum_sr2"], atol=1e-9)

    # single predictor: standardized slope IS the Pearson correlation
    one = A.semipartial_correlations(df[["x1", "y"]], "y")
    assert np.isclose(one["b_star"].iloc[0], np.corrcoef(x1, y)[0, 1], atol=1e-6)

    # equality case: when the other predictor explains nothing, pr2 == sr2
    z = rng.normal(size=n)
    ind = pd.DataFrame({"x1": x1, "z": z, "y": 0.5 * x1 + rng.normal(size=n)})
    eq = A.semipartial_correlations(ind, "y").set_index("feature").loc["x1"]
    assert abs(eq["pr2"] - eq["sr2"]) < 0.01

    assert A.semipartial_correlations(df.head(2), "y").attrs["verdict"] == "insufficient_rows"


@check("leakage_checks.composite_target_probe: target built from its own features")
def _():
    import leakage_checks as LC

    rng = np.random.default_rng(5)
    n, k = 158, 7
    comp = np.abs(rng.normal(1.0, 0.45, (n, k)))
    names = ["economy", "family", "health", "freedom",
             "trust", "generosity", "dystopia"]
    X = pd.DataFrame(comp, columns=names)
    y = pd.Series(comp.sum(1))

    # no single column is remarkable -- that is the whole point of the probe
    assert max(abs(np.corrcoef(X[c], y)[0, 1]) for c in names) < 0.8

    hit = LC.composite_target_probe(X, y)
    assert hit["verdict"] == "exact_identity", hit
    assert hit["relative_residual"] < 1e-10
    assert hit["looks_like_plain_sum"] is True
    assert hit["minimal_subset_size"] == k

    # must stay SILENT on an honest model, even a very good one
    Xh = pd.DataFrame(rng.normal(size=(4000, 5)), columns=list("abcde"))
    sig = Xh.to_numpy() @ np.array([1.0, -0.7, 0.5, 0.3, -0.2])
    yh = pd.Series(sig + rng.normal(0, np.sqrt(sig.var() * 0.01 / 0.99), 4000))
    quiet = LC.composite_target_probe(Xh, yh)
    assert quiet["verdict"] == "no_identity", quiet
    assert quiet["r2_full"] > 0.98            # genuinely a strong model
    assert quiet["relative_residual"] > 0.05  # yet nowhere near an identity

    # names the minimal subset when only some columns build the target
    sub = LC.composite_target_probe(Xh, pd.Series(Xh["a"] + Xh["b"]))
    assert sub["verdict"] == "exact_identity"
    assert sorted(sub["minimal_subset"]) == ["a", "b"], sub["minimal_subset"]

    # with n <= p+1 OLS fits ANY target exactly -- the probe must refuse
    assert LC.composite_target_probe(
        X.head(10), y.head(10))["verdict"] == "insufficient_rows"
    noise = pd.DataFrame(rng.normal(size=(6, 5)), columns=list("abcde"))
    assert LC.composite_target_probe(
        noise, pd.Series(rng.normal(size=6)))["verdict"] == "insufficient_rows"
    assert LC.composite_target_probe(
        X, pd.Series([3.0] * n))["verdict"] == "degenerate_target"


@check("discover.pairwise_group_differences: Holm-controlled post-hoc pairs")
def _():
    import associations as A

    # --- holm_bonferroni: mathematical properties, no RNG ---------------- #
    p = np.array([0.001, 0.02, 0.03, 0.5])
    h = A.holm_bonferroni(p)
    assert (h >= p - 1e-12).all()                 # never below the raw p
    assert (h <= np.clip(p * p.size, 0, 1) + 1e-12).all()   # never above Bonferroni
    assert (np.diff(h[np.argsort(p)]) >= -1e-12).all()      # monotone in rank
    assert np.isclose(h[0], 0.004)                # 4 * 0.001, smallest rank
    assert (A.holm_bonferroni([0.4, 0.4, 0.4]) <= 1.0).all()

    # --- one group genuinely shifted, three identical -------------------- #
    rng = np.random.default_rng(11)
    levels = np.repeat(list("ABCD"), 40)
    vals = rng.standard_normal(160)
    vals[:40] += 3.0                              # only A differs
    out = A.pairwise_group_differences(levels, vals)

    assert out.attrs["n_pairs"] == 6
    assert len(out) == 6
    # the Welch interval must bracket the point difference it was built around
    assert ((out["ci_low"] <= out["diff"]) & (out["diff"] <= out["ci_high"])).all()
    # adjustment can only make a p larger
    assert (out["p_adj"] >= out["p_raw"] - 1e-9).all()
    # delta = 3 sd at n = 40 is essentially power 1: all three A-pairs survive
    a_pairs = out[(out["group_a"] == "A") | (out["group_b"] == "A")]
    assert len(a_pairs) == 3 and a_pairs["significant"].all(), a_pairs
    assert out.attrs["verdict"] == "candidates"
    # the uncorrected upper bound is the independence formula, not the truth
    assert np.isclose(out.attrs["fwer_uncorrected_upper_bound"],
                      1 - 0.95 ** 6, atol=1e-4)

    # BH is never more conservative than Holm -- that is why it is not a
    # substitute when the claim is about one specific pair
    bh = A.pairwise_group_differences(levels, vals, correction="fdr_bh")
    key = ["group_a", "group_b"]
    merged = out.merge(bh, on=key, suffixes=("_holm", "_bh"))
    assert (merged["p_adj_bh"] <= merged["p_adj_holm"] + 1e-9).all()

    # degenerate inputs degrade, they do not raise
    assert A.pairwise_group_differences(
        ["A"] * 10, list(range(10))).attrs["verdict"] == "too_few_usable_groups"
    try:
        A.pairwise_group_differences(levels, vals, correction="lsd")
        raise AssertionError("unknown correction accepted")
    except ValueError:
        pass


@check("sampling_design: ICC, design effect, effective n")
def _():
    import sampling_design as SD

    rng = np.random.default_rng(4242)
    k, m, true_icc = 80, 20, 0.30
    ce = rng.normal(0, np.sqrt(true_icc), k)
    y = np.repeat(ce, m) + rng.normal(0, np.sqrt(1 - true_icc), k * m)
    df = pd.DataFrame({"y": y, "g": np.repeat(np.arange(k), m)})
    row = SD.intraclass_correlation(df, "g", ["y"]).iloc[0]

    # recovers the injected ICC (estimator is consistent; loose band for one draw)
    assert 0.20 < row["icc"] < 0.40, row["icc"]
    # deff is exactly Kish's identity on the reported numbers
    assert np.isclose(row["deff_mean"],
                      1 + (row["mean_cluster_size"] - 1) * row["icc"], atol=1e-9)
    assert np.isclose(row["n_eff_mean"], row["n_rows"] / row["deff_mean"], atol=1e-6)
    # real clustering at ICC 0.30 is detected 100% of the time (measured)
    assert row["verdict"] == "substantial"

    # truly independent rows must NOT be called clustered: the F gate is the
    # whole point -- without it the point estimate alone fires in 10-22% of
    # samples. Measured non-negligible rate with the gate: ~5% (nominal).
    flagged = 0
    for s in range(20):
        r2 = np.random.default_rng(1000 + s)
        iid = pd.DataFrame({"y": r2.normal(size=k * m),
                            "g": np.repeat(np.arange(k), m)})
        if SD.intraclass_correlation(iid, "g", ["y"]).iloc[0]["verdict"] != "negligible":
            flagged += 1
    assert flagged <= 4, f"false-alarm rate too high: {flagged}/20"

    # one row per cluster carries no clustering: deff is exactly 1, not NaN
    singles = pd.DataFrame({"y": rng.normal(size=50), "g": np.arange(50)})
    srow = SD.intraclass_correlation(singles, "g", ["y"]).iloc[0]
    assert srow["deff_mean"] == 1.0 and srow["verdict"] == "negligible"

    # Kish weight deff: algebraic identity, and equal weights cost nothing
    assert np.isclose(SD.weight_design_effect(np.ones(100))["deff_weights"], 1.0)
    w = np.concatenate([np.ones(500), np.full(500, 10.0)])
    d = SD.weight_design_effect(w)
    assert np.isclose(d["deff_weights"], w.size * np.sum(w ** 2) / np.sum(w) ** 2)
    # scale invariance
    assert np.isclose(d["deff_weights"], SD.weight_design_effect(w * 7.3)["deff_weights"])
    assert d["n_dropped"] == 0
    assert SD.weight_design_effect([1.0, -2.0, np.nan, 3.0])["n_dropped"] == 2

    # association deff uses the PRODUCT of ICCs, never the mean's deff
    pair = SD.effective_n_for_association(0.30, 0.30, 25, 1000)
    assert np.isclose(pair["deff_pair"], 1 + 24 * 0.09)
    # clustering in only ONE column needs no correction at all
    one_sided = SD.effective_n_for_association(0.60, 0.0, 25, 1000)
    assert one_sided["deff_pair"] == 1.0 and one_sided["n_eff_pair"] == 1000
    # and it must be far smaller than the mean's deff for the same data
    assert pair["deff_pair"] < 1 + 24 * 0.30

    rep = SD.design_effect_report(df, group="g", columns=["y"])
    assert "deff_total" in rep.columns and rep.attrs["notes"]


@check("filter_select: winner's curse probes")
def _():
    import filter_select as FS

    # the noise floor must rise with the number of candidates screened
    d10 = FS.expected_max_noise_correlation(200, 10, n_sim=60, random_state=0)
    d500 = FS.expected_max_noise_correlation(200, 500, n_sim=60, random_state=0)
    assert d500["mean_max_abs_r"] > d10["mean_max_abs_r"] > 0
    # the winner's naive p-value tracks the alpha-inflation identity
    assert 0.3 < d500["naive_p_value_of_winner"] / d500["alpha_inflation_reference"] < 3.0

    rng = np.random.default_rng(77)
    n, p = 400, 60

    # pure noise: an honest re-estimate must collapse well below the selected score
    X = pd.DataFrame(rng.normal(size=(n, p)), columns=[f"f{i}" for i in range(p)])
    noise = FS.selection_inflation_probe(X, pd.Series(rng.normal(size=n)),
                                         top_k=5, n_repeats=15, random_state=1)
    assert len(noise) > 0
    # bounds calibrated over 60 seeds, not chosen by eye: the honest/selected
    # ratio ran 0.291-0.516 and the median inflation 1.97-5.43, so `ratio < 0.5`
    # (the obvious bound) would have been flaky at 96.7%. Both below are 100%.
    assert noise["honest_abs_r"].mean() < 0.6 * noise["selection_abs_r"].mean()
    assert noise["inflation"].median() > 1.5
    assert noise.attrs["n_features_screened"] == p

    # real signal: the planted feature is found and does NOT shrink on re-estimation
    sig = rng.normal(size=n)
    y = 0.45 * X["f0"] + np.sqrt(1 - 0.45 ** 2) * sig
    real = FS.selection_inflation_probe(X, pd.Series(y), top_k=5,
                                        n_repeats=15, random_state=2)
    f0 = real[real["feature"] == "f0"]
    assert len(f0) == 1, "planted feature was not selected"
    assert f0["honest_abs_r"].iloc[0] > 0.3
    assert 0.7 < f0["inflation"].iloc[0] < 1.4, f0["inflation"].iloc[0]

    # too few rows returns an empty frame rather than raising
    assert FS.selection_inflation_probe(X.head(5), pd.Series(rng.normal(size=5))).empty


@check("sampling_design: overlapping-label design effect")
def _():
    import sampling_design as SD

    # h=1 is NOT overlap: deff must be exactly 1, not the 2h/3 limit's 0.67
    one = SD.overlapping_label_deff(1, 500)
    assert one["deff_overlap"] == 1.0 and one["uniqueness"] == 1.0
    assert one["n_eff"] == 500.0 and one["verdict"] == "negligible"

    # uniqueness is 1/h exactly; deff is the Bartlett sum, NOT h and NOT 1/h
    for h in (5, 20, 50):
        d = SD.overlapping_label_deff(h, 1000)
        assert np.isclose(d["uniqueness"], 1.0 / h)
        assert np.isclose(d["deff_overlap"], 1 + (h - 1) * (2 * h - 1) / (3 * h))
        assert np.isclose(d["n_eff"], 1000 / d["deff_overlap"])
        # must sit far below h -- using h over-corrects alpha to ~0.011 (measured)
        assert d["deff_overlap"] < h
        # and approach 2h/3 from above
        assert d["deff_overlap"] >= 2 * h / 3

    # verified against simulation: measured deff 3.34 / 13.43 / 33.28
    assert abs(SD.overlapping_label_deff(5, 1000)["deff_overlap"] - 3.40) < 0.05
    assert abs(SD.overlapping_label_deff(20, 1000)["deff_overlap"] - 13.35) < 0.05

    # explicit spans reproduce the analytic rectangular case
    n, h = 400, 5
    s = np.arange(n) + 1.0
    lc = SD.label_concurrency(s, s + h - 1)
    assert abs(lc["uniqueness_mean"] - 1.0 / h) < 0.01, lc["uniqueness_mean"]
    assert abs(lc["mean_span"] - h) < 1e-9
    assert abs(lc["max_concurrency"] - h) < 1e-9
    assert SD.label_concurrency([], [])["verdict"] == "undetermined"
    # ragged spans must not raise
    assert SD.label_concurrency([0, 5, 10], [3, 30, 12])["n"] == 3


@check("split_designer.purge_and_embargo drops exactly the leaking rows")
def _():
    import split_designer as SPD

    tr, te, h = np.arange(0, 700), np.arange(700, 900), 20
    res = SPD.purge_and_embargo(tr, te, horizon=h)
    # ground truth: row i leaks iff its label span [i+1, i+h] reaches the test block
    truth = [i for i in tr if i + h >= 700]
    assert res["n_purged"] == len(truth) == 20, (res["n_purged"], len(truth))
    assert not any(i + h >= 700 for i in res["train_idx"]), "a leaking row survived"
    assert res["manifest"]["n_train_after"] == 680

    # embargo removes rows just AFTER the test block
    tr2 = np.concatenate([np.arange(0, 700), np.arange(900, 1000)])
    r2 = SPD.purge_and_embargo(tr2, te, horizon=h, embargo=15)
    assert r2["n_embargoed"] == 15, r2["n_embargoed"]
    assert 0.0 < r2["manifest"]["fraction_dropped"] < 1.0

    # degenerate inputs return cleanly rather than raising
    assert SPD.purge_and_embargo(tr, [], 10)["n_purged"] == 0
    assert SPD.purge_and_embargo(tr, te, 0)["n_purged"] == 0
    assert SPD.purge_and_embargo([], te, 10)["n_purged"] == 0


def _er_edges(n: int, p: float, seed: int = 7):
    rng = np.random.default_rng(seed)
    iu = np.triu_indices(n, k=1)
    keep = rng.random(iu[0].size) < p
    return iu[0][keep], iu[1][keep]


@check("graph_profile: mirrored storage, loops, duplicates, isolates-are-invisible")
def _():
    import graph_profile as GP

    # an UNDIRECTED graph stored as both (a,b) and (b,a): the classic silent defect
    i, j = _er_edges(300, 0.02)
    mirrored = pd.DataFrame({"src": np.concatenate([i, j]), "dst": np.concatenate([j, i])})
    pr = GP.profile_graph(mirrored)
    assert pr["n_edges_raw"] == 2 * pr["n_edges_simple"], "mirror not collapsed"
    assert pr["directedness"]["perfectly_mirrored"] and pr["directedness"]["reciprocity"] > 0.999
    assert any("UNDIRECTED" in f for f in pr["findings"])
    # the mirror must NOT also be reported as duplicate edges -- one fact, one finding
    assert not any("duplicate edges" in f for f in pr["findings"])

    # a genuinely dirty list: self-loop, a real duplicate, a disconnected pair
    dirty = pd.DataFrame({"src": [0, 1, 2, 2, 5], "dst": [1, 2, 0, 0, 5]})
    pd_ = GP.profile_graph(dirty, directed=False)
    assert pd_["self_loops"] == 1 and pd_["duplicate_edges"]["undirected_key"] == 1
    assert pd_["components"]["count"] == 2
    assert any("duplicate edges" in f for f in pd_["findings"])
    # isolates cannot appear in an edge list -> the caveat must always be raised
    assert any("isolates are invisible" in f for f in pd_["findings"])


@check("split_designer.graph_split: node-disjoint arithmetic, and no node crosses the split")
def _():
    import split_designer as SPD

    i, j = _er_edges(1200, 0.01)
    e = pd.DataFrame({"src": i, "dst": j})
    for q in (0.1, 0.2, 0.447):
        r = SPD.graph_split(e, mode="inductive", test_size=q, seed=1)
        mf = r["manifest"]
        # edges divide as (1-q)^2 / q^2 / 2q(1-q); measured 0.040 test + 0.318 dropped at q=0.2
        assert abs(mf["edge_test_share"] - q ** 2) < 0.012, (q, mf["edge_test_share"])
        assert abs(mf["cross_edge_share"] - 2 * q * (1 - q)) < 0.012, (q, mf["cross_edge_share"])
        # the guarantee that makes it inductive at all
        assert mf["overlap_checks"]["node_overlap"] == 0, "a node appears on both sides"
        assert mf["endpoints_seen_in_train"] == 0.0
        assert r["train_idx"].size + r["test_idx"].size + r["dropped_idx"].size == len(e)

    with_bad_mode = dict(edges=e, mode="nope")
    try:
        SPD.graph_split(**with_bad_mode)
        raise AssertionError("unknown mode must raise")
    except ValueError:
        pass


@check("split_designer.graph_split: transductive test edges are not new (measured ~1.000)")
def _():
    import split_designer as SPD

    # floors are the measured worst case over 20 random graphs, not one lucky draw:
    # mean 0.9818 / 0.9999 / 1.0000, min 0.9664 / 0.9986 / 1.0000
    for p, floor in ((0.005, 0.95), (0.01, 0.995), (0.05, 0.9999)):
        i, j = _er_edges(1200, p)
        r = SPD.graph_split(pd.DataFrame({"src": i, "dst": j}),
                            mode="transductive", test_size=0.2, seed=1)
        seen = r["manifest"]["endpoints_seen_in_train"]
        assert seen >= floor, (p, seen)
        assert r["dropped_idx"].size == 0, "transductive drops nothing"
        assert abs(r["manifest"]["edge_test_share"] - 0.2) < 0.01


@check("sampling_design.dyadic_design_effect: n_eff scales with nodes, not edges")
def _():
    import sampling_design as SD

    rng = np.random.default_rng(11)
    n = 200
    i, j = _er_edges(n, 0.10, seed=11)
    z = rng.normal(size=n)
    y = z[i] + z[j] + rng.normal(size=i.size)      # dependence is node-level by construction
    res = SD.dyadic_design_effect(pd.DataFrame({"src": i, "dst": j, "y": y}), value="y")
    # measured: true deff 14.80, jackknife 14.93, n_eff/nodes ~0.66 at this design
    assert res["deff"] > 5.0, res["deff"]
    assert res["n_eff"] < 0.25 * res["n_edges"], (res["n_eff"], res["n_edges"])
    assert 0.2 < res["n_eff"] / n < 1.5, res["n_eff"] / n
    assert res["verdict"] == "substantial"

    # independent dyad values carry no node-level dependence -> deff near 1
    y0 = rng.normal(size=i.size)
    flat = SD.dyadic_design_effect(pd.DataFrame({"src": i, "dst": j, "y": y0}), value="y")
    assert flat["deff"] < 3.0, flat["deff"]

    tiny = SD.dyadic_design_effect(pd.DataFrame({"src": [0], "dst": [1], "y": [1.0]}), value="y")
    assert tiny["verdict"] == "undetermined"


@check("consistency.proxy_label_diagnostics: base-rate arithmetic")
def _():
    import consistency as C

    # verified against simulation at N=300k: PPV 0.692 / 0.321 / 0.155
    for sens, spec, prev, ppv, infl in [(0.9, 0.9, 0.20, 0.692, 1.30),
                                        (0.9, 0.9, 0.05, 0.321, 2.80),
                                        (0.9, 0.9, 0.02, 0.155, 5.80)]:
        d = C.proxy_label_diagnostics(sens, spec, prev)
        assert abs(d["ppv"] - ppv) < 0.005, (prev, d["ppv"])
        assert abs(d["base_rate_inflation"] - infl) < 0.02
        assert np.isclose(d["false_positive_share_of_labels"], 1 - d["ppv"])

    # at a 2% base rate a "90% accurate" detector yields mostly false positives
    assert C.proxy_label_diagnostics(0.9, 0.9, 0.02)["verdict"] == "label_mostly_false_positives"

    # specificity, not sensitivity, is the lever when positives are rare
    hi_spec = C.proxy_label_diagnostics(0.80, 0.999, 0.01)["ppv"]
    hi_sens = C.proxy_label_diagnostics(0.99, 0.900, 0.01)["ppv"]
    assert hi_spec > 0.85 and hi_sens < 0.15, (hi_spec, hi_sens)

    # a perfect detector must be an identity
    p = C.proxy_label_diagnostics(1.0, 1.0, 0.1)
    assert p["ppv"] == 1.0 and p["base_rate_inflation"] == 1.0

    for bad in [(1.5, 0.9, 0.1), (0.9, -0.1, 0.1), (0.9, 0.9, 2.0)]:
        try:
            C.proxy_label_diagnostics(*bad)
            raise AssertionError(f"accepted out-of-range {bad}")
        except ValueError:
            pass


@check("distribution_report.quantile_convention_report separates value from convention")
def _():
    import distribution_report as DR

    rng = np.random.default_rng(0)

    # small sample: the convention itself moves the number materially
    small = DR.quantile_convention_report(rng.normal(size=8))
    assert small["verdict"] == "convention_matters"
    assert small["max_spread_share_of_sd"] > 0.05

    # large sample: the VALUE converges, so the verdict must not cry wolf even
    # when one borderline row still changes side (this was a real defect --
    # gating on the binary flip alone reported convention_matters at n=20000
    # with a spread of 0.0004 sd)
    big = DR.quantile_convention_report(rng.normal(size=20000))
    assert big["max_spread_share_of_sd"] < 0.01
    assert big["verdict"] in ("convention_irrelevant", "borderline_points_only")
    assert big["verdict"] != "convention_matters"

    # numpy's default IS the stdlib's "inclusive"; the stdlib's own default is not
    r = DR.quantile_convention_report(rng.normal(size=40))
    q = r["quantiles"]
    assert "stdlib_exclusive" in q and "stdlib_inclusive" in q and "linear" in q
    assert abs(q["linear"][0.25] - q["stdlib_inclusive"][0.25]) < 1e-9
    assert abs(q["linear"][0.25] - q["stdlib_exclusive"][0.25]) > 1e-6

    assert DR.quantile_convention_report([1.0, 2.0, 3.0])["verdict"] == "insufficient_rows"
    assert DR.quantile_convention_report([5.0] * 50)["verdict"] == "convention_irrelevant"
    assert DR.quantile_convention_report([1.0, np.nan, 3.0, 4.0, 9.0])["n"] == 4


@check("balancing.prevalence_metric_report: AUC is blind to the base rate")
def _():
    import balancing as B

    rng = np.random.default_rng(3)
    n_pos = 1500
    aucs, aps, precs = [], [], []
    for prev in (0.5, 0.01):
        n_neg = int(n_pos * (1 - prev) / prev)
        y = np.r_[np.ones(n_pos), np.zeros(n_neg)]
        s = np.r_[rng.normal(2.33, 1, n_pos), rng.normal(0, 1, n_neg)]
        r = B.prevalence_metric_report(y, s)
        if r["verdict"] == "sklearn_unavailable":
            return
        aucs.append(r["roc_auc"])
        aps.append(r["average_precision"])
        precs.append(r["precision_at_recall"][0.8])
        assert np.isclose(r["ap_baseline"], r["prevalence"])
        assert np.isclose(r["alerts_per_true_positive"][0.8],
                          1 / r["precision_at_recall"][0.8], rtol=1e-6)

    # Bounds calibrated over 30 seeds rather than guessed: across prevalence
    # 0.5 vs 0.01 the AP ratio ran 2.16-2.49, the precision@0.8 ratio 7.73-9.67,
    # and |dAUC| 0.000-0.013. (A first attempt asserted AP ratio > 5, which was
    # read off the 0.5-vs-0.001 comparison and failed every seed.)
    assert abs(aucs[0] - aucs[1]) < 0.05, aucs          # ROC-AUC is invariant
    assert aps[0] > 1.8 * aps[1], aps                    # AP is not
    assert precs[0] > 5 * precs[1], precs                # nor is usable precision

    # and the verdict names that specific failure mode
    n_neg = int(n_pos * 0.999 / 0.001)
    y = np.r_[np.ones(n_pos), np.zeros(n_neg)]
    s = np.r_[rng.normal(2.33, 1, n_pos), rng.normal(0, 1, n_neg)]
    assert B.prevalence_metric_report(y, s)["verdict"] == "good_ranking_unusable_operating_point"

    assert B.prevalence_metric_report([1, 1, 1], [1, 2, 3])["verdict"] == "single_class_or_empty"
    assert B.prevalence_metric_report([], [])["verdict"] == "single_class_or_empty"


@check("time_series_features: fractional differencing keeps memory, stays causal")
def _():
    import time_series_features as TS

    # exact identities: d=0 is the input, d=1 IS the first difference
    assert list(TS.frac_diff_weights(0.0)) == [1.0]
    assert np.allclose(TS.frac_diff_weights(1.0), [1.0, -1.0])
    assert np.allclose(TS.frac_diff_weights(2.0), [1.0, -2.0, 1.0])

    rng = np.random.default_rng(0)
    x = rng.normal(size=400).cumsum()
    fd1 = TS.frac_diff(x, 1.0)
    ref = np.r_[np.nan, np.diff(x)]
    both = np.isfinite(fd1) & np.isfinite(ref)
    assert np.max(np.abs(fd1[both] - ref[both])) < 1e-12
    fd0 = TS.frac_diff(x, 0.0)
    ok = np.isfinite(fd0)
    assert np.max(np.abs(fd0[ok] - x[ok])) < 1e-12

    # CAUSAL: perturbing x[t] must never change an output before t.
    # This is what makes the transform safe to compute before splitting.
    x = rng.normal(size=800).cumsum()
    a = TS.frac_diff(x, 0.4)
    x2 = x.copy()
    x2[400] += 100.0
    b = TS.frac_diff(x2, 0.4)
    moved = np.flatnonzero(np.abs(np.nan_to_num(a) - np.nan_to_num(b)) > 1e-9)
    assert moved.size > 0 and moved.min() == 400, moved[:5]
    assert not (moved < 400).any(), "fractional differencing looked into the future"

    # the tradeoff itself: a fractional order beats d=1 on retained memory
    walk = rng.normal(size=3000).cumsum()
    res = TS.min_frac_diff_order(walk)
    if res["verdict"] == "statsmodels_unavailable":
        return
    assert res["verdict"] == "fractional_beats_integer", res["verdict"]
    assert 0.0 < res["d"] < 1.0, res["d"]
    assert res["corr_at_d"] > 0.6, res["corr_at_d"]
    tbl = res["table"].set_index("d")
    assert abs(tbl.loc[1.0, "corr_with_original"]) < 0.2   # d=1 erases the level
    assert tbl.loc[res["d"], "corr_with_original"] > abs(tbl.loc[1.0, "corr_with_original"])

    # an already-stationary series must not be over-differenced
    assert TS.min_frac_diff_order(rng.normal(size=1500))["verdict"] == "already_stationary"

    # gaps blank whole windows; d=0 needs width 1 and would hide that, so the
    # flag must fire even when the verdict reads "already_stationary"
    gappy = pd.Series([1.0, 2, np.nan, 4, 5, 6, 7, 8, 9, 10] * 8)
    g = TS.min_frac_diff_order(gappy, threshold=1e-2)
    assert g["n_missing_input"] == 8
    assert g["gaps_block_positive_d"] is True
    assert len(g["d_blocked_by_gaps"]) > 0

    # guards
    assert np.all(np.isnan(TS.frac_diff([1.0, 2.0, 3.0], 0.4, 1e-5)))  # window > series
    for bad in ((-0.5,), ):
        try:
            TS.frac_diff_weights(*bad)
            raise AssertionError("negative d accepted")
        except ValueError:
            pass
    try:
        TS.frac_diff_weights(0.4, threshold=2.0)
        raise AssertionError("out-of-range threshold accepted")
    except ValueError:
        pass


def _factor_data(loadings, phi, n, seed):
    """Rows from a common-factor model with known loadings and factor correlations."""
    rng = np.random.default_rng(seed)
    L = np.asarray(loadings, dtype=float)
    F = rng.multivariate_normal(np.zeros(L.shape[1]), np.asarray(phi, dtype=float), size=n)
    uniq = np.clip(1.0 - np.sum((L @ phi) * L, axis=1), 1e-6, None)
    return F @ L.T + rng.standard_normal((n, L.shape[0])) * np.sqrt(uniq)


@check("factor_analysis: rotation preserves fit; oblique recovers what orthogonal hides")
def _():
    import factor_analysis as FA

    L = np.zeros((10, 2)); L[:5, 0] = 0.7; L[5:, 1] = 0.7
    phi = np.array([[1.0, 0.6], [0.6, 1.0]])
    X = _factor_data(L, phi, 800, seed=3)
    R, _, _ = FA.correlation_matrix(X)
    ext = FA.principal_axis_factoring(R, 2)
    assert not ext["heywood"], ext["heywood_columns"]

    # rotation is a change of basis: communalities and the reproduced correlation
    # matrix are untouched (measured 6.7e-16 / 7.8e-16), only the loadings move
    obl = FA.rotate_loadings(ext["loadings"], "promax")
    ort = FA.rotate_loadings(ext["loadings"], "varimax")
    assert obl["verdict"] == "fit_preserved" and ort["verdict"] == "fit_preserved"
    assert obl["fit_preserved_max_diff"] < 1e-8, obl["fit_preserved_max_diff"]
    assert max(abs(a - b) for a, b in
               zip(obl["communalities"], ort["communalities"])) < 1e-8

    # measured: promax |r| ~0.585 against a true 0.6; varimax reports 0 by construction
    assert abs(obl["factor_correlations"][0]) > 0.35, obl["factor_correlations"]
    assert ort["factor_correlations"] == [0.0], ort["factor_correlations"]

    # the price of the right angle is fake cross-loadings (measured 0.221 vs 0.037).
    # Factor order/sign are arbitrary after rotation, so score order-free: on a pure
    # design the smaller |loading| of each row IS the cross-loading.
    cross_o = float(np.mean(np.min(np.abs(np.asarray(ort["pattern"])), axis=1)))
    cross_p = float(np.mean(np.min(np.abs(np.asarray(obl["pattern"])), axis=1)))
    assert cross_o > 2 * cross_p, (cross_o, cross_p)


@check("factor_analysis: parallel analysis refuses noise where the eigenvalue>1 rule invents factors")
def _():
    import factor_analysis as FA

    rng = np.random.default_rng(5)
    Xn = rng.standard_normal((300, 20))
    pa = FA.parallel_analysis(Xn, n_iter=60, random_state=5)
    # measured: Kaiser claims ~10 factors here, parallel analysis 0
    assert pa["n_factors"] == 0, pa["n_factors"]
    assert pa["kaiser_count"] >= 6, pa["kaiser_count"]
    rep = FA.factor_structure_report(Xn, n_iter=60, random_state=5)
    assert rep["verdict"] == "no_common_factor_supported", rep["verdict"]

    # the two identities on a correlation matrix: eigenvalues sum to p, and their
    # product is the determinant (which is why a redundant column zeroes both)
    er = FA.eigenvalue_report(Xn)
    assert abs(er["sum_eigenvalues"] - 20.0) < 1e-6, er["sum_eigenvalues"]
    prod = float(np.prod(np.asarray(er["eigenvalues"], dtype=float)))
    assert abs(prod - er["determinant"]) < 1e-6 * max(1.0, abs(er["determinant"]))

    dup = np.column_stack([Xn, Xn[:, 0]])
    er2 = FA.eigenvalue_report(dup)
    assert er2["verdict"] == "singular_or_near_singular", er2["verdict"]
    assert abs(er2["determinant"]) < 1e-10, er2["determinant"]


@check("factor_analysis: Heywood cases are reported, never clipped")
def _():
    import factor_analysis as FA

    L = np.array([[.75, 0.], [.75, 0.], [0., .75], [0., .75]])
    phi = np.array([[1.0, .25], [.25, 1.0]])
    hits = 0
    for s in range(40):                      # 2 indicators/factor, n=45: measured ~0.30
        X = _factor_data(L, phi, 45, seed=100 + s)
        R, _, _ = FA.correlation_matrix(X)
        res = FA.principal_axis_factoring(R, 2)
        if res["heywood"]:
            hits += 1
            assert res["verdict"] == "improper_solution_heywood"
            assert max(res["communalities"]) >= 1.0      # surfaced, not clipped to 1
            assert min(res["uniquenesses"]) <= 0.0       # the negative variance is visible
    assert hits > 0, "no improper solution in a design measured to produce ~25-30%"

    # 6 indicators/factor with enough rows: measured 0.000 over 300 reps
    L6 = np.zeros((12, 2)); L6[:6, 0] = .7; L6[6:, 1] = .7
    X6 = _factor_data(L6, phi, 600, seed=9)
    R6, _, _ = FA.correlation_matrix(X6)
    ok = FA.principal_axis_factoring(R6, 2)
    assert not ok["heywood"] and ok["verdict"] == "proper", ok["verdict"]


@check("factor_analysis: a causal chain is caught by the residual matrix, not by variance explained")
def _():
    import factor_analysis as FA

    def chain(b, n=3000, seed=21):
        rng = np.random.default_rng(seed)
        Z = np.zeros((n, 6)); Z[:, 0] = rng.standard_normal(n)
        for j in range(1, 6):                # no common cause anywhere in this
            Z[:, j] = b * Z[:, j - 1] + np.sqrt(1 - b ** 2) * rng.standard_normal(n)
        return Z

    Z8 = chain(0.8)
    er = FA.eigenvalue_report(Z8)            # measured 0.680 -- reads as unidimensional
    assert er["explained_variance_ratio"][0] > 0.55, er["explained_variance_ratio"][0]
    c8 = FA.factor_structure_report(Z8, n_factors=1, n_iter=60)
    assert c8["verdict"] == "factor_model_does_not_reproduce_correlations", c8["verdict"]
    assert c8["rms_residual_correlation"] > 0.08, c8["rms_residual_correlation"]

    # A tighter chain hides better, and this is the honest limit of the absolute
    # threshold: at path 0.9 the residual is ~0.077, i.e. BELOW the 0.08 convention,
    # so the verdict alone reads "clean". What still separates it from a real
    # one-factor dataset is the comparison -- a 25-50x gap, not a cutoff.
    Z9 = chain(0.9)
    c9 = FA.factor_structure_report(Z9, n_factors=1, n_iter=60)
    assert FA.eigenvalue_report(Z9)["explained_variance_ratio"][0] > 0.75
    assert c9["rms_residual_correlation"] < 0.08, c9["rms_residual_correlation"]

    # genuine one-factor data at a comparable first-component share: measured 0.0015
    Xt = _factor_data(np.full((6, 1), 0.9), np.eye(1), 3000, seed=22)
    true1 = FA.factor_structure_report(Xt, n_factors=1, n_iter=60)
    assert true1["rms_residual_correlation"] < 0.02, true1["rms_residual_correlation"]
    assert true1["rms_residual_correlation"] * 10 < c9["rms_residual_correlation"]


@check("factor_structure_report: orphan columns surface, and PCA inflates the loadings")
def _():
    import factor_analysis as FA

    L = np.zeros((12, 2)); L[:6, 0] = .65; L[6:, 1] = .65
    phi = np.array([[1.0, .35], [.35, 1.0]])
    X = _factor_data(L, phi, 700, seed=13)
    rng = np.random.default_rng(13)
    df = pd.DataFrame(np.column_stack([X, rng.standard_normal(700), np.ones(700)]),
                      columns=[f"item{i}" for i in range(12)] + ["junk", "const"])

    rep = FA.factor_structure_report(df, n_iter=60)
    assert rep["dropped_constant_columns"] == ["const"], rep["dropped_constant_columns"]
    # measured: an injected noise column lands at communality 0.0129 vs a 0.4772 median
    assert rep["orphan_columns"] == ["junk"], rep["orphan_columns"]
    assert rep["communalities"]["junk"] < 0.05, rep["communalities"]["junk"]
    assert sum(len(v) for v in rep["assignment"].values()) == 12
    assert rep["fit_preserved_max_diff"] < 1e-8

    # PCA credits each column's measurement error to the component: +0.0567 at a 0.60 loading
    cmp = FA.pca_vs_fa(X, 2)
    assert cmp["loading_inflation"] > 0.01, cmp["loading_inflation"]
    assert cmp["mean_communality_pca"] > cmp["mean_communality_fa"]


@check("contracts manifests serialize")
def _():
    import contracts as ct
    fm = ct.FeatureManifest(features=[ct.FeatureSpec(name="f0_cdf", kind="engineering")])
    js = ct.to_json(fm)
    assert "f0_cdf" in js


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print("\n" + "=" * 60)
    print(f"{len(RESULTS) - n_fail}/{len(RESULTS)} checks passed")
    if n_fail:
        print("FAILURES:")
        for name, ok, msg in RESULTS:
            if not ok:
                print(f"  - {name}: {msg}")
    sys.exit(1 if n_fail else 0)
