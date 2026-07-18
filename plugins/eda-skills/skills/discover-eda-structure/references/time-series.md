# Time-series EDA and lag features

## Establish time semantics

- Define entity, event time, ingestion time, timezone, frequency, horizon, and prediction cutoff.
- Detect duplicate timestamps, gaps, irregular sampling, daylight-saving changes, censoring, and late-arriving data.
- Separate one global series from panel/multiple-entity series.

## Resampling and alignment

- Put each entity on a regular time grid so a lag of `k` equals `k` real periods; `to_regular_grid` reindexes per entity and fills only from the past.
- **Downsample** (finer → coarser) by aggregating within each period (sum/mean/last) — this uses only within-period data.
- **Upsample** (coarser → finer) then fill with **past-only** methods (`ffill`, forward time interpolation); never fill a gap with future values, especially across a validation boundary.
- Record the chosen frequency, timezone handling, and how gaps and duplicate timestamps were resolved.

## Explore

- Plot raw and aggregated series at relevant scales.
- Decompose trend/seasonality with `seasonal_decompose` (additive vs multiplicative), STL, or MSTL for multiple/complex seasonal patterns; choose additive when the seasonal amplitude is roughly constant and multiplicative (or log-transform first) when it grows with the level. Inspect the residual for leftover structure and anomalies.
- Inspect ACF/PACF with uncertainty and after appropriate detrending/differencing.
- Check autocorrelation of missingness and observation frequency.
- Compare distributions and target rates across rolling periods to identify drift or structural breaks.
- Track cumulative counts and the running event/positive rate over time to reveal regime shifts and emerging anomalies; treat a rising cumulative rate as a hypothesis to investigate, not an automatic detector — its thresholds and baselines still need statistical justification.

## A change over time is not automatically a change in the world

Before interpreting a trend, break, or drift signal as something the population did, rule out the ways the *measurement* could have moved instead. These are the classical internal-validity threats (Shadish, Cook & Campbell), and they are the alternative hypotheses for almost every temporal finding an EDA produces. The rule they share: **a threat is not a reason to distrust the data, it is a competing explanation that has to be named and, where possible, checked.**

- **Instrumentation — the measure changed, not the thing.** A new form, recalibrated sensor, changed question wording, a vendor swap, a new app version, a schema migration, a relabelled category. This cuts both ways: it can *manufacture* a jump (a published developmental study showed "bursts" in cognitive development that lined up exactly with the dates the achievement test was swapped) and it can *mask* real change (holding one instrument fixed while its relevance shifts across the range). **This is the first alternative hypothesis for anything `distribution_shift` flags** — a large PSI at a known release date is a schema change until proven otherwise. Keep an instrument/version/source column and always cross the shift against it.
- **History — something else happened at that moment.** A policy change, an outage, a competitor launch, a holiday, a pandemic. Any series spanning a real-world event has this as a live alternative to whatever intervention is being credited.
- **Maturation — the units changed on their own.** Entities age, users learn the interface, machines wear, cohorts progress. A useful consequence: an intervention that *slows a rising trend* is effective even though the level still rises, and a flat line can be an achievement rather than a failure. Comparing a treated group to its own past instead of to an untreated trajectory silently assumes maturation is zero.
- **Testing — measuring changes the measured.** Repeatedly surveying the same people sensitises them; repeatedly scoring the same entity changes behaviour when the score is visible (and reactivity is severe once the metric is a target). Panel data has this everywhere the same respondent is re-asked.
- **Attrition — who remains is not who started.** Non-random dropout reshapes the sample between waves. If the worst-off leave, later averages rise with no one improving; this is survivorship applied wave-by-wave (see the missing-rows section in `audit-eda-data-quality/references/consistency-validity.md`). Always report per-wave `n` and compare leavers against stayers on baseline variables — a difference there is the finding.
- **Selection × time interactions.** Groups that differ at baseline can also *mature* differently or experience *different* instrument changes, which is the hardest case because no single check isolates it.

Two further temporal cautions:

- **Temporal precedence is necessary, not sufficient.** "X at t1 predicts Y at t2, so X causes Y" ignores that Y at t1 is usually correlated with both. Where the reverse process is plausible, a lagged regression that omits the baseline outcome will absorb the reverse path — control the prior level of the outcome, or model both directions, before calling a lagged coefficient an effect. The confounder/mediator/collider table in `associations.md` applies unchanged once time is in the picture.
- **The lag length is a substantive claim.** Choosing t+1 month over t+1 day is a hypothesis about how fast the mechanism acts, and the wrong lag hides a real effect as effectively as its absence. Scan a range of lags, report the profile rather than the single best one, and say which lag the domain implies — a null at one arbitrary horizon is not evidence of no relation.

## Stationarity and transforms

A stationary series has a roughly constant mean, variance, and autocovariance over time; trend or seasonality make it non-stationary. Stationarity matters because it separates trend/drift from noise, guides differencing features, and tells you whether a downstream method's assumptions hold — tree/NN feature models do not strictly require it, but differenced/detrended features and drift-awareness often help.

- Assess with a **plot + rolling mean/variance first**, then complementary unit-root tests rather than a single p-value: **ADF** (null = unit root, so a small p implies stationary) and **KPSS** (null = stationary, so a small p implies non-stationary). They have opposite nulls, so read both — agreement is informative; ADF-stationary but KPSS-non-stationary suggests trend-stationarity (detrend), the reverse suggests difference-stationarity (difference). `stationarity_report` runs both plus rolling diagnostics.
- Achieve stationarity where a feature or method needs it: regular and **seasonal differencing**, detrending, and **variance-stabilizing transforms** (log, Box-Cox) when amplitude grows with the level. Fit any transform parameter (e.g., a Box-Cox lambda) on **train only**.

### Fractional differencing: stationarity without erasing the level

Integer differencing is not free — it buys stationarity by discarding the level
information a model needs. Measured on a random walk (n=5000), correlation
between the transformed series and the original level:

| d | ADF p | corr with original level |
|---|---|---|
| 0.00 | 0.483 | 1.000 |
| 0.20 | 0.149 | 0.953 |
| **0.30** | **0.017** | **0.888** |
| 0.50 | 0.000 | 0.676 |
| 1.00 | 0.000 | **0.013** |

`d = 1` threw away essentially all the memory (0.013) to buy a stationarity
that `d = 0.30` already delivered while retaining 0.888 of it. `frac_diff`
applies the binomial weights of `(1 − L)^d` over a fixed-width backward window;
`min_frac_diff_order` scans `d` and reports the whole tradeoff curve.

Properties that matter here, all verified:

- **Identities hold**: `d=0` reproduces the input exactly, `d=1` reproduces
  `np.diff` to 0.00e+00, `d=2` gives `[1, −2, 1]`.
- **Causal, so it is split-safe.** Perturbing `x[500]` changed outputs from
  index 500 onward and never any earlier output. The weights depend on `d`
  alone, so the transform fits nothing. The leakage-relevant step is
  **choosing** `d` — do that on train only and apply the chosen value
  unchanged, exactly like a Box-Cox lambda.
- **`threshold` sets the window width and can eat the series**: widths of
  11 / 55 / 282 / 1458 / 7550 terms at 1e-2 / 1e-3 / 1e-4 / 1e-5 / 1e-6 for
  d=0.4, and at 1e-6 a 2000-point series came back entirely `NaN`.
- **Gaps are fatal and quiet.** Each output needs a complete window, so one
  missing value blanks the next `width` outputs; a series with a gap every 10
  rows and width 11 produced *zero* finite outputs. Put the series on a regular
  grid with past-only filling first. `min_frac_diff_order` reports
  `gaps_block_positive_d` because `d=0` needs a window of 1 and would otherwise
  mask the problem behind an `already_stationary` verdict.

**Do not read the chosen `d` as the series' memory parameter.** The scan finds
the least differencing that stops ADF rejecting — an operational choice about a
feature, not an estimate of the integration order. On ARFIMA(0,d₀,0) series with
a *known* d₀ the recovered minimum d was 0.00 for true d₀ of 0.50, 0.60 and
0.70, and only 0.05–0.40 at d₀ = 1.00. The cause is measurable: **ADF has very
little power against fractional alternatives** — on the raw series it returned
p = 0.0000 even at d₀ = 0.70, hesitating only at d₀ = 0.90 (p = 0.0855). Where
the process really is I(1), ADF works and the scan correctly returns d = 0.30.
If long memory itself is the question, estimate it with a method built for it
(log-periodogram, R/S), not with this scan.
- Treat these tests as diagnostics, not gates — combine with ACF/PACF, the decomposition residual, and domain knowledge.

## Candidate features

- Direct lags: `x[t-k]` for domain, seasonal, and diagnostic candidates.
- Differences and percentage/log changes with zero and sign handling.
- Rolling min/max/mean/median/std/quantiles/counts computed strictly from prior observations.
- Expanding and exponentially weighted summaries using only past data.
- Seasonal/calendar, cyclical sine/cosine, and Fourier features.
- Recency, frequency, time-since-event, consecutive-event, and window-count features.
- Cross-series lags only when the other series is available before the cutoff.

## Avoid leakage

- Split chronologically before fitting normalization, decomposition, lag selection, or feature selection.
- Shift before rolling when the current observation is unavailable at inference.
- Impute time-series gaps with past-only methods (`ffill`, forward time interpolation); fit any model-based or multivariate imputer on train only, and never interpolate across the prediction cutoff or a validation boundary using future observations.
- Fit seasonal/trend decomposition and any learned representation within training windows.
- Use rolling/expanding validation or backtesting that matches deployment.

## Validate lags

- Compare with seasonal-naive and no-lag baselines.
- Check stability across forecast origins and entities.
- Remove redundant lag grids through grouped selection or regularization, not one correlation threshold alone.
- Record the maximum lookback and its operational data requirement.

