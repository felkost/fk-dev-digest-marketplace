# Ordinal codes and deliberate coarsening

`associations.md` opens by warning not to "silently treat arbitrary codes as interval values" and
then offers no way to detect or repair it. This file is the repair, and it covers one axis with two
ends: **ordinal data you were given** (a 5-point Likert item) and **coarsening you chose** (a median
split). Both push a continuous latent variable through thresholds; the difference is only whether it
was your decision.

Everything here is `scripts/ordinal_data.py`. Measurements are ours unless stated.

## The engine

`_bvn_cdf` evaluates the standard bivariate normal CDF via Drezner's identity —
`Phi2(h,k;rho) = Phi(h)·Phi(k) + ∫₀^rho phi2(h,k;r) dr` — with 48-node Gauss-Legendre quadrature.
**Verified against `scipy.stats.multivariate_normal.cdf` to 2.220e-16** over 200 random `(h,k,rho)`
triples, and it vectorises over whole threshold grids where scipy's is scalar in practice. The
polychoric likelihood needs one evaluation per cell per iteration, so that matters.

Two implementation notes worth keeping:

- **`±inf` thresholds return `nan`** through the integrand. Cumulative shares are floored at `0.5/n`
  and thresholds clipped to ±8 — `Phi(8) = 1 − 6e-16`, exact at float precision. Same continuity
  correction round 19 adopted for PSI, for the same reason.
- **The quadrature nodes are cached.** `leggauss(48)` eigendecomposes a 48×48 companion matrix at
  **1.77 ms** a call; a polychoric fit evaluates the integrand ~14 times. Computing them per call
  added ~25 ms to a 13 ms fit and made a 12-column matrix take 2.5 s instead of 0.69 s.

## What Pearson costs on ordinal codes

Latent bivariate normal, true `r = 0.60`, n = 200 000 — population values, not sampling noise:

| k | Pearson, symmetric cuts | Pearson, skewed cuts | retention (symmetric) |
|---|---|---|---|
| 2 | 0.4121 | 0.3849 | 0.687 |
| 3 | 0.4981 | 0.4754 | 0.830 |
| 5 | 0.5489 | 0.5317 | 0.915 |
| 7 | 0.5659 | 0.5329 | 0.943 |
| 10 | 0.5742 | 0.5308 | 0.957 |

A binary split loses **31%** of the true correlation, and **asymmetric thresholds are worse at every
k**. The practical break is k ≈ 5–7 — where a Likert item usually sits — so the error is real but
rarely catastrophic on a 7-point scale, and severe on a dichotomy. `ordinality_report` reports
`expected_pearson_retention` from this table so "this column is ordinal" becomes "this costs about
9%", which is a form a decision can be made on.

## Polychoric wins on RMSE everywhere, including where it was expected to lose

The briefed expectation was that polychoric buys back bias but pays in variance, so at k=2 with small
n Pearson would win on RMSE. **It does not, in any cell tested** (true r = 0.60, 100–200 reps):

| k | n | Pearson mean | poly mean | poly sd | Pearson RMSE | poly RMSE |
|---|---|---|---|---|---|---|
| 2 | 200 | 0.4104 | 0.5980 | 0.0788 | 0.1997 | **0.0787** |
| 2 | 500 | 0.4080 | 0.5965 | 0.0539 | 0.1967 | **0.0539** |
| 2 | 2000 | 0.4096 | 0.5996 | 0.0256 | 0.1915 | **0.0255** |
| 3 | 200 | 0.4990 | 0.6007 | 0.0644 | 0.1172 | **0.0642** |
| 5 | 200 | 0.5440 | 0.5958 | 0.0526 | 0.0761 | **0.0526** |
| 5 | 2000 | 0.5466 | 0.5983 | 0.0162 | 0.0557 | **0.0162** |
| 7 | 2000 | 0.5650 | 0.6015 | 0.0185 | 0.0396 | **0.0185** |

Polychoric won in **all twelve cells**. Pearson's bias is simply too large for its low variance to
rescue: at k=2 it is wrong by 0.19 every single time, while polychoric is unbiased with an sd of
0.079. The variance is still real and should be reported — at k=2, n=200 a 2-sd interval spans about
±0.16 — but that is honest width around the right value rather than precision around the wrong one.

**Where polychoric genuinely is worse is a sparse table.** `polychoric_correlation` returns
`sparse_table_unstable` when any expected cell falls below 5. On a sparse table the estimator has
little to fit and is *less* trustworthy than Pearson — the same lesson round 26 recorded for
`n ≤ p+1`.

## The round-28 guard: Pearson on ordinal items invents a difficulty factor

`factor-structure.md` lists "a column that is ordinal being treated as continuous" as a Heywood cause
without saying what to do about it. This is what to do about it — and the measurement narrowed the
claim considerably.

One-factor latent (loading 0.70, p=12, n=500), ordinalized with threshold groups that **differ across
items** (6 easy, 6 hard). **Ground truth is 1 factor.** 25 reps per cell; share extracting ≥2 factors
by parallel analysis:

| k | spread | Pearson ≥2 | polychoric ≥2 |
|---|---|---|---|
| 2 | none | 0.00 | 0.00 |
| 2 | moderate | **0.52** | 0.00 |
| 2 | extreme | **1.00** | **0.96** ⚠ |
| 3 | moderate | 0.00 | 0.00 |
| 3 | extreme | **1.00** | 0.36 |
| 5 | extreme | **1.00** | 0.00 |
| 7 | extreme | **1.00** | 0.00 |

Read carefully, because three separate things are true:

1. **The guard is real.** At extreme threshold spread, Pearson manufactures a second factor **100% of
   the time at every k from 2 to 7**, splitting exactly along the easy/hard grouping. It is a
   difficulty artefact wearing the costume of a substantive dimension. Polychoric returns the correct
   single factor at k=5 and k=7.
2. **It matters much less than briefed at moderate spread.** With a moderate threshold difference,
   Pearson only over-extracts at k=2 (0.52); at k ≥ 3 it returns the right answer. Typical Likert
   data with mild difficulty variation is not in danger.
3. **⚠ Polychoric does not rescue binary items.** At k=2 with extreme spread it extracts 2.76 factors
   on average and over-extracts in **96%** of reps — *worse than Pearson*. Extreme thresholds on
   binary items make every two-way table sparse, which is precisely the condition
   `sparse_table_unstable` exists to flag. **On binary items with very different base rates, neither
   correlation is trustworthy; that is a data-collection finding, not an estimator choice.**

**A briefed hypothesis did not survive: the Pearson path does not raise the Heywood rate.** Zero
improper solutions in either path across all twelve cells. The artefact shows up as an extra factor,
not as a boundary estimate.

`polychoric_matrix` feeds `factor_analysis.principal_axis_factoring` and `reliability.mcdonald_omega`
directly — both accept an explicit `R` — so the ordinal path costs nothing structurally.

**Pairwise matrices are not guaranteed positive definite**, because each cell is fitted from its own
two-way table with nothing constraining them jointly. `polychoric_matrix` returns `R` and
`R_smoothed` **separately** and says which is which rather than silently smoothing — the same
doctrine `principal_axis_factoring` applies to Heywood cases. Smoothing changes the data to fit the
method, so it should be a decision. The flag fires on `min_eigenvalue < -1e-8`, not `< 0`: a pairwise
matrix routinely lands at -1e-16 through nothing but floating point, and a flag that fires there is a
rounding-error detector.

## Dichotomization: what a median split actually costs

Splitting a continuous variable to "simplify the analysis" is the most common deliberate act of
measurement destruction in applied work, usually defended as costing "a bit of power".

**The arithmetic.** Dichotomizing one variable of a bivariate normal at the median multiplies the
correlation by `phi(0)/sqrt(0.25) = 0.7979`. Information in a correlation goes as its square, so the
surviving share is `0.7979² = 2/pi = 0.6366`. **A median split throws away 36% of the sample** — not
36% of the effect, 36% of the rows, and without telling you which ones. That is what
`effective_n_equivalent` reports. Measured against the theory on 5000 rows (`r = 0.4983`):

| split | r dichotomized | retained (measured) | retained (theory) | effective n |
|---|---|---|---|---|
| median | 0.3858 | 0.5996 | 0.6366 | 2998 of 5000 |
| top 25% | 0.3677 | 0.5446 | 0.5386 | 2723 |
| top 10% | 0.2907 | 0.3403 | 0.3422 | 1701 |

Away from the median it is far worse, because the split is also unbalanced: a 90/10 cut retains about
a third of what the median cut does.

**Power cost** (two groups of 100, 2000 reps, alpha = 0.05): at `d = 0.35` power falls
**0.682 → 0.568**; at `d = 0.50`, **0.936 → 0.827**.

### A claim that died on contact with data

The briefed expectation was that dichotomizing two *correlated* predictors of a strictly additive
outcome manufactures a spurious interaction, at a rate **rising** with n. Measured on
`y = 0.4·x1 + 0.4·x2 + eps` with both predictors median-split, testing `d1:d2` at alpha = 0.05, 1000
reps per cell:

| corr(x1,x2) | n=200 | n=500 | n=2000 | continuous control (n=2000) |
|---|---|---|---|---|
| 0.0 | 0.0560 | 0.0460 | 0.0500 | 0.0480 |
| 0.3 | 0.0560 | 0.0490 | 0.0590 | 0.0600 |
| 0.5 | 0.0530 | 0.0530 | 0.0480 | 0.0500 |
| 0.7 | 0.0430 | 0.0420 | 0.0460 | 0.0530 |

**Nominal everywhere, flat in n, and indistinguishable from the continuous control.** With linear
effects and normal predictors there is no spurious interaction to find. Recorded as a negative result
rather than softened — the same treatment round 28 gave the dropped factor-score-indeterminacy claim
and this round gave "alpha rises when junk items are added". The cost of a median split in this
design is the power and the effective sample size, and stating a second cost that is not there would
weaken the first one, which is large and real.

## Detecting the problem

Nothing in a column's dtype distinguishes "7 = strongly agree" from "7 kilograms". What the data
shows is a fingerprint: few distinct values, all integers, consecutive, starting at 0 or 1.
`ordinality_report` reports it as a **screen, not a determination** — a genuine count variable with a
small range looks identical, and only the column's meaning settles it. Same posture as
`indicator_direction_check` in `measurement-reliability.md`: the output is a question for whoever
owns the data.
