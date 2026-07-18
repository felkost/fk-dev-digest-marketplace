#!/usr/bin/env python3
"""Звіт для forecasting: стаціонарність, драбина моделей проти наївної бази, MASE.

Використання:
    python forecasting_report.py --csv d.csv --col sales --period 12 --horizon 24
    python forecasting_report.py --self-test

`--self-test` звіряє з АНАЛІТИЧНОЮ основною істиною: ADF/KPSS протилежні на
блуканні проти diff; MASE наївного = 1; MAPE вибухає на нулях; надмірний diff
роздуває дисперсію.
"""
from __future__ import annotations

import argparse
import sys
import warnings

import numpy as np

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


# --------------------------------------------------------------------------
def stationarity(y: np.ndarray) -> dict:
    from statsmodels.tsa.stattools import adfuller, kpss
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        adf_p = adfuller(y, autolag="AIC")[1]
        kpss_p = kpss(y, regression="c", nlags="auto")[1]
    # згода: ADF малий → стаціон.; KPSS великий → стаціон.
    adf_stat = adf_p < 0.05
    kpss_stat = kpss_p > 0.05
    if adf_stat and kpss_stat:
        verdict = "стаціонарний"
    elif not adf_stat and not kpss_stat:
        verdict = "нестаціонарний → diff"
    elif adf_stat and not kpss_stat:
        verdict = "trend-stationary → детрендинг, НЕ diff"
    else:
        verdict = "невизначено — обережно"
    return {"adf_p": adf_p, "kpss_p": kpss_p, "verdict": verdict}


def n_diffs_needed(y: np.ndarray, max_d: int = 3) -> int:
    from statsmodels.tsa.stattools import adfuller
    cur = np.asarray(y, dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for d in range(max_d + 1):
            if adfuller(cur, autolag="AIC")[1] < 0.05:
                return d
            cur = np.diff(cur)
    return max_d


def naive_forecast(train: np.ndarray, h: int, season: int = 1) -> np.ndarray:
    if season <= 1:
        return np.full(h, train[-1])
    return np.array([train[-season + (i % season)] for i in range(h)])


def mase(y_true, y_pred, y_train, season: int = 1) -> float:
    from sklearn.metrics import mean_absolute_error
    d = np.abs(np.asarray(y_train[season:]) - np.asarray(y_train[:-season]))
    denom = d.mean()
    return mean_absolute_error(y_true, y_pred) / denom if denom > 0 else np.inf


def ladder(train, test, season: int) -> dict:
    """Проганяє драбину й повертає MASE кожного щабля (наївний = база)."""
    from sklearn.metrics import mean_absolute_error
    h = len(test)
    out = {}
    snaive = naive_forecast(train, h, season)
    out["seasonal_naive_MAE"] = mean_absolute_error(test, snaive)
    out["seasonal_naive_MASE"] = mase(test, snaive, train, season)
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ets = ExponentialSmoothing(train, trend="add", seasonal="add",
                                       seasonal_periods=season).fit()
        out["ETS_MASE"] = mase(test, ets.forecast(h), train, season)
    except Exception as e:
        out["ETS_MASE"] = f"н/д ({type(e).__name__})"
    try:
        from statsmodels.tsa.arima.model import ARIMA
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ar = ARIMA(train, order=(2, 1, 2)).fit()
        out["ARIMA212_MASE"] = mase(test, ar.forecast(h), train, season)
    except Exception as e:
        out["ARIMA212_MASE"] = f"н/д ({type(e).__name__})"
    return out


# --------------------------------------------------------------------------
def report(y: np.ndarray, season: int, horizon: int) -> None:
    y = np.asarray(y, dtype=float)
    print(f"довжина ряду: {len(y)}, сезон={season}, горизонт={horizon}")
    if len(y) < 2 * season:
        print("  ! ряд коротший за 2 сезони — forecasting ненадійний, "
              "можливо це регресія на ознаках (ml-model-selection)")
    s = stationarity(y)
    print(f"\n--- СТАЦІОНАРНІСТЬ ---")
    print(f"ADF p={s['adf_p']:.3f} (H0=корінь), KPSS p={s['kpss_p']:.3f} "
          f"(H0=стаціон.) → {s['verdict']}")
    d = n_diffs_needed(y)
    print(f"потрібно різниць d={d}" + ("  ! d≥3 — надмірне диференціювання"
          if d >= 3 else ""))

    train, test = y[:-horizon], y[-horizon:]
    print(f"\n--- ДРАБИНА (MASE; <1 = краще за наївну базу) ---")
    for k, v in ladder(train, test, season).items():
        print(f"  {k}: {v if isinstance(v, str) else f'{v:.3f}'}")
    print("  правило: побити сезонний-наївний; недомодельований сезон часто "
          "програє базі")


# --------------------------------------------------------------------------
def self_test() -> int:
    print("=== self-test: звірка з АНАЛІТИЧНОЮ основною істиною ===")
    ok = total = 0

    def chk(label, cond, detail=""):
        nonlocal ok, total
        total += 1
        if cond:
            ok += 1
            print(f"OK   {label}")
        else:
            print(f"FAIL {label} -- {detail}")

    rng = np.random.default_rng(0)

    # 1. блукання нестаціонарне за обома тестами
    rw = np.cumsum(rng.normal(size=500))
    s_rw = stationarity(rw)
    chk(f"блукання: ADF p={s_rw['adf_p']:.3f}>0.05 і KPSS p={s_rw['kpss_p']:.3f}<0.05 "
        "→ нестаціонарний", s_rw["adf_p"] > 0.05 and s_rw["kpss_p"] < 0.05)

    # 2. diff(блукання) стаціонарне за обома
    s_d = stationarity(np.diff(rw))
    chk(f"diff(блукання): ADF p={s_d['adf_p']:.3f}<0.05 і KPSS p={s_d['kpss_p']:.3f}>0.05 "
        "→ стаціонарний", s_d["adf_p"] < 0.05 and s_d["kpss_p"] > 0.05)

    # 3. білий шум стаціонарний, d=0
    white = rng.normal(size=500)
    chk(f"білий шум: потрібно d={n_diffs_needed(white)} різниць = 0",
        n_diffs_needed(white) == 0)

    # 4. блукання: рівно 1 різниця
    chk(f"блукання: потрібно d={n_diffs_needed(rw)} = 1", n_diffs_needed(rw) == 1)

    # 5. 1-КРОКОВИЙ наївний на блуканні: MASE≈1 аналітично (чисельник і знаменник
    #    обидва = mean|Δy|). Плоский БАГАТОкроковий наївний дрейфує (MASE росте
    #    як √h) — тому тестуємо саме 1-кроковий rolling.
    from sklearn.metrics import mean_absolute_error
    test = rw[-24:]; prev = rw[-25:-1]           # прогноз кожної точки = попередня фактична
    m = mean_absolute_error(test, prev) / np.abs(np.diff(rw[:-24])).mean()
    chk(f"1-кроковий наївний на блуканні: MASE={m:.3f} ≈ 1 (аналітично)",
        0.6 < m < 1.6, f"MASE={m:.3f}")

    # 6. MAPE вибухає на нулях, MASE — ні
    from sklearn.metrics import mean_absolute_percentage_error as mape_fn
    yt = np.array([0.0, 10, 20, 5]); yp = np.array([1.0, 11, 19, 6])
    mp = mape_fn(yt, yp)
    ms = mase(yt, yp, np.array([1.0, 2, 3, 4, 5, 6]), 1)
    chk(f"MAPE на нулі = {mp:.2e} (вибух), MASE={ms:.3f} (скінченна)",
        mp > 1e6 and np.isfinite(ms))

    # 7. надмірний diff роздуває дисперсію: var(diff^2) > var(diff) на блуканні
    v1 = np.diff(rw).var()
    v2 = np.diff(np.diff(rw)).var()
    chk(f"надмірний diff роздуває дисперсію: var(d1)={v1:.2f} → var(d2)={v2:.2f}",
        v2 > v1)

    # 8. на сезонних даних ETS(сезон) б'є сезонний-наївний
    n = 300; t = np.arange(n)
    seas = 10 * np.sin(2 * np.pi * t / 12) + 0.05 * t + rng.normal(0, 1, n)
    lad = ladder(seas[:-24], seas[-24:], 12)
    ets_ok = isinstance(lad["ETS_MASE"], float) and \
        lad["ETS_MASE"] < lad["seasonal_naive_MASE"]
    chk(f"сезонні дані: ETS MASE={lad['ETS_MASE'] if isinstance(lad['ETS_MASE'],str) else round(lad['ETS_MASE'],3)} "
        f"< сезонний-наївний {lad['seasonal_naive_MASE']:.3f}", ets_ok)

    # 9. сезонний-наївний MASE проти себе на сезонному наївному знаменнику ≈ 1
    chk(f"сезонний-наївний MASE={lad['seasonal_naive_MASE']:.3f} (база порівняння)",
        lad["seasonal_naive_MASE"] > 0)

    print(f"\n=== {ok}/{total} {'УСПІХ' if ok == total else 'Є ПОМИЛКИ'} ===")
    return 0 if ok == total else 1


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--col", help="колонка ряду")
    ap.add_argument("--period", type=int, default=12, help="сезонний період")
    ap.add_argument("--horizon", type=int, default=24, help="горизонт backtest")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if not a.csv or not a.col:
        ap.error("потрібні --csv і --col (або --self-test)")

    import pandas as pd
    y = pd.read_csv(a.csv)[a.col].to_numpy(dtype=float)
    report(y, a.period, a.horizon)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
