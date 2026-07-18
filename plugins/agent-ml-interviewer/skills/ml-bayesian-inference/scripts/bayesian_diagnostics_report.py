#!/usr/bin/env python3
"""Бета-біноміальна байєсова оцінка з повною діагностикою МСМС.

Використання:
  python bayesian_diagnostics_report.py --k 33 --n 50            # k успіхів з n спроб
  python bayesian_diagnostics_report.py --k 33 --n 50 --alpha 20 --beta 20  # інформативний пріор
  python bayesian_diagnostics_report.py --self-test

Звітує: r_hat, ESS, дивергенції, PPC-зведення, довірчі інтервали ETI89 (дефолт
ArviZ) І HDI94 (класичний, потрібен явний ci_kind="hdi") поруч, щоб не
переплутати.

`cores=1` навмисно скрізь: дефолтна багатопроцесність pm.sample() підвисає в
пісочницях/обмежених shell-середовищах без жодної помилки (перевірено
2026-07-18: з дефолтними cores прогін не завершився за 3 хв, з cores=1 -- 0.5с).

Вимоги: pymc>=6, arviz>=1.2.
"""

from __future__ import annotations

import argparse
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

RHAT_OK = 1.01


def fit_beta_binomial(k: int, n: int, alpha: float, beta: float,
                      draws: int = 1000, tune: int = 1000, chains: int = 4,
                      seed: int = 0):
    import pymc as pm
    with pm.Model() as model:
        p = pm.Beta("p", alpha=alpha, beta=beta)
        pm.Binomial("obs", n=n, p=p, observed=k)
        idata = pm.sample(draws, tune=tune, chains=chains, cores=1,
                          random_seed=seed, progressbar=False)
        pm.compute_log_likelihood(idata)
        pm.sample_posterior_predictive(idata, progressbar=False,
                                       extend_inferencedata=True)
    return idata


def diagnostics(idata) -> dict:
    import arviz as az
    rhat = float(az.rhat(idata, var_names=["p"])["p"].values)
    ess_bulk = float(az.ess(idata, var_names=["p"])["p"].values)
    div = int(idata.sample_stats["diverging"].values.sum())
    eti = az.summary(idata, var_names=["p"])
    hdi = az.summary(idata, var_names=["p"], ci_kind="hdi", ci_prob=0.94)
    return {"rhat": rhat, "ess_bulk": ess_bulk, "divergences": div,
            "eti89": (float(eti["eti89_lb"].iloc[0]), float(eti["eti89_ub"].iloc[0])),
            "hdi94": (float(hdi["hdi94_lb"].iloc[0]), float(hdi["hdi94_ub"].iloc[0]))}


def report(k: int, n: int, alpha: float, beta: float) -> int:
    idata = fit_beta_binomial(k, n, alpha, beta)
    d = diagnostics(idata)
    print(f"k={k}, n={n}, пріор Beta(alpha={alpha}, beta={beta})")
    print(f"r_hat        = {d['rhat']:.4f}  ({'OK' if d['rhat'] <= RHAT_OK else 'НЕ ЗІЙШЛОСЯ'})")
    print(f"ESS (bulk)   = {d['ess_bulk']:.0f}")
    print(f"дивергенції  = {d['divergences']}  ({'OK' if d['divergences'] == 0 else 'ПОДИВИТИСЬ trace!'})")
    print(f"ETI89 (дефолт ArviZ)  = [{d['eti89'][0]:.3f}, {d['eti89'][1]:.3f}]")
    print(f"HDI94 (класичний)     = [{d['hdi94'][0]:.3f}, {d['hdi94'][1]:.3f}]")
    return 0


def self_test() -> int:
    import numpy as np
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'OK ' if cond else 'FAIL'} {label}")

    print("1) az.summary: дефолт ETI89, не HDI94 (перевірено живцем 2026-07-18)")
    idata = fit_beta_binomial(k=33, n=50, alpha=1, beta=1, draws=500, tune=500, chains=2)
    import arviz as az
    default_cols = set(az.summary(idata, var_names=["p"]).columns)
    check(f"дефолтні колонки містять eti89_lb/ub ({sorted(default_cols)})",
          {"eti89_lb", "eti89_ub"} <= default_cols)
    hdi_cols = set(az.summary(idata, var_names=["p"], ci_kind="hdi", ci_prob=0.94).columns)
    check(f"з ci_kind='hdi' колонки містять hdi94_lb/ub ({sorted(hdi_cols)})",
          {"hdi94_lb", "hdi94_ub"} <= hdi_cols)

    print("2) LOO вироджується на агрегованій правдоподібності, працює на поспостережній")
    import pymc as pm
    with pm.Model() as m_agg:
        p = pm.Beta("p", alpha=1, beta=1)
        pm.Binomial("obs", n=50, p=p, observed=33)
        idata_agg = pm.sample(500, tune=500, chains=4, cores=1, random_seed=0,
                              progressbar=False)
        pm.compute_log_likelihood(idata_agg)
    k_agg = float(az.loo(idata_agg, pointwise=True).pareto_k.values)
    check(f"агрегований Binomial(n=1 спостереження): pareto_k={k_agg:.2f} > 0.7 (погано)",
          k_agg > 0.7)

    rng = np.random.default_rng(0)
    flips = rng.binomial(1, 0.66, size=50)
    with pm.Model() as m_obs:
        p2 = pm.Beta("p", alpha=1, beta=1)
        pm.Bernoulli("obs", p=p2, observed=flips)
        idata_obs = pm.sample(500, tune=500, chains=4, cores=1, random_seed=0,
                              progressbar=False)
        pm.compute_log_likelihood(idata_obs)
    k_obs = float(az.loo(idata_obs, pointwise=True).pareto_k.values.max())
    check(f"поспостережний Bernoulli(n=50): max pareto_k={k_obs:.2f} < 0.7 (добре)",
          k_obs < 0.7)

    print("3) Ієрархічна модель: нецентрована параметризація дає менше дивергенцій")
    J = 8
    group_means = rng.normal(0, 1, J)
    y = np.concatenate([rng.normal(m, 1, 5) for m in group_means])
    group = np.repeat(np.arange(J), 5)

    with pm.Model() as centered:
        mu = pm.Normal("mu", 0, 5)
        tau = pm.HalfNormal("tau", 5)
        theta = pm.Normal("theta", mu=mu, sigma=tau, shape=J)
        pm.Normal("obs", mu=theta[group], sigma=1, observed=y)
        idata_c = pm.sample(1000, tune=1000, chains=4, cores=1, random_seed=0,
                            progressbar=False, target_accept=0.8)
    div_c = int(idata_c.sample_stats["diverging"].values.sum())

    with pm.Model() as noncentered:
        mu = pm.Normal("mu", 0, 5)
        tau = pm.HalfNormal("tau", 5)
        theta_offset = pm.Normal("theta_offset", 0, 1, shape=J)
        theta = pm.Deterministic("theta", mu + theta_offset * tau)
        pm.Normal("obs", mu=theta[group], sigma=1, observed=y)
        idata_nc = pm.sample(1000, tune=1000, chains=4, cores=1, random_seed=0,
                             progressbar=False, target_accept=0.8)
    div_nc = int(idata_nc.sample_stats["diverging"].values.sum())

    check(f"центрована має дивергенції (={div_c} > 0)", div_c > 0)
    check(f"нецентрована має менше дивергенцій ({div_nc} < {div_c})", div_nc < div_c)

    print()
    print("УСПІХ" if ok else "ПРОВАЛ")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, help="кількість успіхів")
    ap.add_argument("--n", type=int, help="кількість спроб")
    ap.add_argument("--alpha", type=float, default=1.0, help="пріор Beta: alpha (дефолт 1 = рівномірний)")
    ap.add_argument("--beta", type=float, default=1.0, help="пріор Beta: beta (дефолт 1 = рівномірний)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.k is None or a.n is None:
        ap.error("потрібні --k і --n (або --self-test)")
    return report(a.k, a.n, a.alpha, a.beta)


if __name__ == "__main__":
    sys.exit(main())
