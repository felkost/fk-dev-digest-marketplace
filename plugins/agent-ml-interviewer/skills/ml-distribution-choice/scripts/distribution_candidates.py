#!/usr/bin/env python3
"""Підпис даних -> кандидатні розподіли -> AIC-ранжування -> чесний GoF.

Використання:
  python distribution_candidates.py --csv data.csv --col amount
  python distribution_candidates.py --self-test

Що робить:
  1. Підпис: support, цілочисельність, нулі, VMR, skew, ексцес, skew(log), хвіст.
  2. Шортліст кандидатів за гілкою (бінарна / лічильна / додатна / вся вісь / [0,1]).
  3. MLE-фіт кандидатів (scipy.stats), ранжування за AIC.
  4. GoF для переможця: KS із ПАРАМЕТРИЧНИМ БУТСТРЕПОМ (рефіт на кожній симуляції).
     Наївний kstest із фітованими параметрами дає завищений p-value (Ліллієфорс) --
     скрипт друкує обидва, щоб різниця була видима.

Вимоги: numpy, pandas (для --csv), scipy.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
from scipy import stats

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# Кандидати за гілками: (ім'я, заморожені kwargs фіту)
POSITIVE = [("lognorm", {"floc": 0}), ("gamma", {"floc": 0}),
            ("weibull_min", {"floc": 0}), ("expon", {"floc": 0}), ("norm", {})]
REALLINE = [("norm", {}), ("laplace", {}), ("t", {}), ("cauchy", {})]

HINTS = {
    "poisson":     "PoissonRegressor / HGBR(loss='poisson'); mean_poisson_deviance; offset=log(exposure)",
    "negbin":      "спершу коваріата, що пояснює варіацію µ; далі statsmodels NegativeBinomial (доказ: PoissonGammapoisson.pdf + GammapoissonPascal.pdf)",
    "bernoulli":   "логістична регресія, log-loss; дисбаланс -> скіл ml-metric-choice",
    "lognorm":     "модель на log(y); метрики на лог-шкалі; зворотне перетворення зі smearing-поправкою",
    "gamma":       "GammaRegressor / HGBR(loss='gamma'); mean_gamma_deviance",
    "weibull_min": "надійність/час до події; за цензурування -- survival (lifelines), C-index",
    "expon":       "перевірте memorylessness (ExponentialForgetfulness.pdf); за цензурування -- survival",
    "norm":        "MSE/RMSE/R² легітимні (MLE ≡ MSE за гаусового шуму)",
    "laplace":     "MAE (медіанна регресія) або Huber",
    "t":           "важкі хвости: Huber/квантильна втрата; CI -- бутстреп",
    "cauchy":      "моментів немає: середнє/MSE безглузді; медіана, квантилі, бутстреп",
    "beta":        "Beta-регресія (statsmodels) або logit-трансформація частки",
}


def signature(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if x.size == 0:
        raise ValueError("колонка порожня після зняття NaN")
    pos = x[x > 0]
    s = {
        "n": int(x.size),
        "min": float(x.min()), "max": float(x.max()),
        "integer": bool(np.all(np.isclose(x, np.round(x))))
                   and float(x.max()) - float(x.min()) > 0,
        "share_zero": float((x == 0).mean()),
        "share_neg": float((x < 0).mean()),
        "mean": float(x.mean()), "var": float(x.var(ddof=1)),
        "skew": float(stats.skew(x)), "ex_kurt": float(stats.kurtosis(x)),
        "log_skew": float(stats.skew(np.log(pos))) if pos.size > 10 else np.nan,
        "tail_q99_q50": float(np.quantile(x, .99) / np.quantile(x, .50))
                        if np.quantile(x, .50) > 0 else np.nan,
    }
    s["vmr"] = s["var"] / s["mean"] if s["mean"] > 0 else np.nan
    return s, x


def branch(sig: dict, x: np.ndarray) -> str:
    vals = np.unique(x)
    if len(vals) == 2 and set(np.round(vals)) <= {0.0, 1.0}:
        return "binary"
    if sig["integer"] and sig["min"] >= 0:
        return "count"
    if sig["min"] > 0 and sig["max"] < 1:
        return "unit"
    if sig["min"] >= 0:
        return "positive"
    return "realline"


def fit_rank(x: np.ndarray, candidates) -> list[dict]:
    rows = []
    for name, kw in candidates:
        dist = getattr(stats, name)
        try:
            params = dist.fit(x, **kw)
            ll = float(dist.logpdf(x, *params).sum())
            if not np.isfinite(ll):
                continue
            k = len(params) - len(kw)          # зафіксовані не рахуємо
            rows.append({"name": name, "params": params,
                         "loglik": ll, "aic": 2 * k - 2 * ll})
        except Exception:
            continue
    return sorted(rows, key=lambda r: r["aic"])


def ks_naive_and_bootstrap(x: np.ndarray, name: str, params, kw,
                           B: int = 200, seed: int = 0) -> dict:
    """Наївний kstest (невалідний за фітованих параметрів) і бутстреп-версія."""
    dist = getattr(stats, name)
    d_obs = stats.kstest(x, name, args=params).statistic
    p_naive = stats.kstest(x, name, args=params).pvalue
    rng = np.random.default_rng(seed)
    n = len(x)
    d_sim = np.empty(B)
    frozen = dist(*params)
    for b in range(B):
        xb = frozen.rvs(size=n, random_state=rng)
        pb = dist.fit(xb, **kw)                 # ключове: РЕФІТ на симуляції
        d_sim[b] = stats.kstest(xb, name, args=pb).statistic
    p_boot = (1 + int((d_sim >= d_obs).sum())) / (B + 1)
    return {"D": float(d_obs), "p_naive": float(p_naive), "p_boot": float(p_boot), "B": B}


def analyse(x: np.ndarray, B: int = 200, seed: int = 0, do_gof: bool = True) -> dict:
    sig, x = signature(x)
    br = branch(sig, x)
    out = {"signature": sig, "branch": br, "ranking": [], "gof": None,
           "verdict": None, "hint": None, "notes": []}

    if br == "binary":
        p = float(x.mean())
        out["verdict"], out["hint"] = "bernoulli", HINTS["bernoulli"]
        out["notes"].append(f"Bernoulli(p={p:.4f})")
        return out

    if br == "count":
        mu, vmr = sig["mean"], sig["vmr"]
        zero_gap = sig["share_zero"] - float(np.exp(-mu))
        out["notes"].append(f"VMR = {vmr:.3f}; надлишок нулів проти Poisson = {zero_gap:+.3f}")
        ll_pois = float(stats.poisson.logpmf(x.astype(int), mu).sum())
        out["ranking"].append({"name": "poisson", "params": (mu,),
                               "loglik": ll_pois, "aic": 2 * 1 - 2 * ll_pois})
        if sig["var"] > mu:                     # NegBin методом моментів
            p_mm = mu / sig["var"]
            n_mm = mu * p_mm / (1 - p_mm)
            ll_nb = float(stats.nbinom.logpmf(x.astype(int), n_mm, p_mm).sum())
            out["ranking"].append({"name": "negbin(MoM)", "params": (n_mm, p_mm),
                                   "loglik": ll_nb, "aic": 2 * 2 - 2 * ll_nb})
        out["ranking"].sort(key=lambda r: r["aic"])
        if vmr > 1.2:
            out["verdict"], out["hint"] = "negbin", HINTS["negbin"]
        elif vmr < 0.8:
            out["verdict"] = "binomial-подібний (underdispersed)"
            out["hint"] = "обмежений процес: біноміальна GLM з відомим n (VMR=1-p конструктивно, BinomialC.pdf)"
        else:
            out["verdict"], out["hint"] = "poisson", HINTS["poisson"]
        if zero_gap > 0.05:
            out["notes"].append("надлишок нулів: розділіть структурні нулі (hurdle/ZIP)")
        return out

    if br == "unit":
        a, b_, loc, sc = stats.beta.fit(x, floc=0, fscale=1)
        ll = float(stats.beta.logpdf(x, a, b_, loc, sc).sum())
        out["ranking"] = [{"name": "beta", "params": (a, b_), "loglik": ll, "aic": 4 - 2 * ll}]
        out["verdict"], out["hint"] = "beta", HINTS["beta"]
        return out

    cands = POSITIVE if br == "positive" else REALLINE
    if br == "positive" and sig["share_zero"] > 0:
        x = x[x > 0]
        out["notes"].append(f"нулі ({sig['share_zero']:.1%}) зняті для фіту: "
                            "точна маса в нулі -> розгляньте Tweedie 1<p<2")
    out["ranking"] = fit_rank(x, cands)
    top = out["ranking"][0]
    out["verdict"] = top["name"]
    out["hint"] = HINTS.get(top["name"], "")
    if top["name"] == "t" and top["params"][0] < 5:
        out["notes"].append(f"t: df={top['params'][0]:.2f} < 5 -- важкі хвости підтверджені")
    if do_gof:
        kw = dict(cands)[top["name"]]
        out["gof"] = ks_naive_and_bootstrap(x, top["name"], top["params"], kw, B=B, seed=seed)
    return out


def report(res: dict) -> str:
    s = res["signature"]
    L = [f"n = {s['n']}   support [{s['min']:.4g}, {s['max']:.4g}]   "
         f"цілі: {'так' if s['integer'] else 'ні'}   нулі: {s['share_zero']:.1%}",
         f"mean = {s['mean']:.4g}   var = {s['var']:.4g}   VMR = {s['vmr']:.3f}   "
         f"skew = {s['skew']:.2f}   ex.kurt = {s['ex_kurt']:.2f}   "
         f"skew(log) = {s['log_skew']:.2f}",
         f"гілка: {res['branch']}", ""]
    if res["ranking"]:
        L.append(f"{'кандидат':<14}{'loglik':>14}{'AIC':>14}")
        for r in res["ranking"]:
            L.append(f"{r['name']:<14}{r['loglik']:>14.1f}{r['aic']:>14.1f}")
        L.append("")
    if res["gof"]:
        g = res["gof"]
        L.append(f"GoF для '{res['verdict']}': KS D = {g['D']:.4f}")
        L.append(f"  p наївний (НЕВАЛІДНИЙ, параметри фітовані) = {g['p_naive']:.3f}")
        L.append(f"  p бутстреп (B={g['B']}, рефіт на кожній симуляції) = {g['p_boot']:.3f}")
        L.append("")
    L.append(f"Вердикт: {res['verdict']}")
    L.append(f"Модель/втрата/метрика: {res['hint']}")
    for n in res["notes"]:
        L.append(f"  · {n}")
    return "\n".join(L)


def self_test() -> int:
    rng = np.random.default_rng(42)
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'OK ' if cond else 'FAIL'} {label}")

    print("1) Poisson(3), n=4000")
    r = analyse(rng.poisson(3.0, 4000).astype(float), do_gof=False)
    check("вердикт poisson", r["verdict"] == "poisson")
    check("VMR у [0.9, 1.1]", 0.9 < r["signature"]["vmr"] < 1.1)

    print("2) NegBin(n=3, p=0.3) -> overdispersed")
    r = analyse(rng.negative_binomial(3, 0.3, 4000).astype(float), do_gof=False)
    check("вердикт negbin", r["verdict"] == "negbin")
    check("negbin(MoM) б'є poisson за AIC",
          r["ranking"][0]["name"].startswith("negbin"))

    print("3) Lognormal(0, 0.8), n=3000")
    x = rng.lognormal(0.0, 0.8, 3000)
    r = analyse(x, B=99, seed=1)
    check("топ-1 lognorm за AIC", r["verdict"] == "lognorm")
    check("|skew(log)| < 0.2", abs(r["signature"]["log_skew"]) < 0.2)
    check("бутстреп-p не відкидає істину (p > 0.01)", r["gof"]["p_boot"] > 0.01)

    print("4) Gamma(shape=2, scale=3), n=3000")
    r = analyse(rng.gamma(2.0, 3.0, 3000), do_gof=False)
    check("істина в топ-2 за AIC",
          "gamma" in [r["ranking"][0]["name"], r["ranking"][1]["name"]])

    print("5) Cauchy, n=2000")
    r = analyse(stats.cauchy.rvs(size=2000, random_state=rng), do_gof=False)
    check("топ-1 cauchy або t із df<2",
          r["verdict"] == "cauchy" or
          (r["verdict"] == "t" and r["ranking"][0]["params"][0] < 2))

    print("6) Хибне сімейство мусить провалити бутстреп-GoF: expon на lognormal-даних")
    params = stats.expon.fit(x, floc=0)
    g = ks_naive_and_bootstrap(x, "expon", params, {"floc": 0}, B=99, seed=2)
    check("бутстреп-p < 0.05", g["p_boot"] < 0.05)

    print()
    print("УСПІХ" if ok else "ПРОВАЛ")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--col")
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-gof", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.csv and a.col):
        ap.error("потрібні --csv і --col (або --self-test)")
    import pandas as pd
    df = pd.read_csv(a.csv)
    if a.col not in df.columns:
        ap.error(f"колонки '{a.col}' немає; наявні: {list(df.columns)}")
    res = analyse(df[a.col].to_numpy(dtype=float), B=a.bootstrap,
                  seed=a.seed, do_gof=not a.no_gof)
    print(report(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
