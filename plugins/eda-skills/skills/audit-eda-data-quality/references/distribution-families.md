# Distribution families: mechanism, not shape

Choosing a family by eyeballing a histogram fits the symptom. The relationships
between families encode *how the data was generated*, and the generating
mechanism is what decides the transform, the aggregation rule, and whether a
"long tail" is a defect or the point.

Reference for the relationships: Leemis & McQueston (2008), *Univariate
Distribution Relationships*, The American Statistician 62(1), and the
interactive chart at `www.math.wm.edu/~leemis/chart/UDR/UDR.html` (76
distributions, 357 linked PDFs).

**Getting a proof.** The chart's URL scheme is
`.../UDR/PDFs/<Name>.pdf` for a distribution, `<Name><Letter>.pdf` for a
property proof, and `<From><To>.pdf` for an arrow. One collision to know:
`ExponentialF.pdf` is the *arrow to the F distribution*, not the forgetfulness
property — that one is `ExponentialForgetfulness.pdf`. The same applies to
`ChisquareF`, `TF`, `NoncentralfF`.

Every claim in this file below is quoted from those proofs.

Tooling: `distribution_report.count_dispersion`, `mean_variance_scaling`,
`rate_homogeneity`.

## The four kinds of relationship

The chart distinguishes them by line style, and they answer different questions:

| Kind | Meaning | EDA use |
|---|---|---|
| **Special case** | fix a parameter (`Binomial n=1` → `Bernoulli`) | is the simpler model enough? |
| **Transformation** | a function of the variable (`Normal → Lognormal` via `e^X`) | which scale is the natural one |
| **Limiting** | a parameter goes to a boundary (`Binomial → Poisson`) | when an approximation is admissible |
| **Bayesian** | a parameter is itself random (`Poisson` with `μ ~ gamma` → gamma-Poisson) | **where overdispersion comes from** |

Simplified versions of this chart circulating online usually drop the Bayesian
class entirely. That is the one that explains real count data, so it is the one
worth knowing.

## Mean-variance scaling picks the transform

Group the variable by a real grouping (segment, period, site) and regress
`log(variance)` on `log(mean)` across groups (`mean_variance_scaling`). The
exponent `b` in `Var ≈ mean^b` names the mechanism, and the
variance-stabilising transform is `x^(1 − b/2)`, with `log` as the limiting case
at `b = 2`:

`b` is the **Tweedie power parameter**, and the family it names is the mechanism:

| b | mechanism | family | transform |
|---|---|---|---|
| ~0 | additive noise, constant spread | Normal | none |
| ~1 | counts | Poisson | sqrt |
| 1–2 | zero mass + continuous positive part | **compound Poisson-gamma** | see below |
| ~2 | constant CV, multiplicative | lognormal / gamma | **log** |
| ~3 | — | inverse Gaussian | 1/sqrt |

Measured on simulated data with known truth: additive → `b = 0.01`, Poisson →
`b = 1.03`, lognormal → `b = 2.07`.

**The zero trap — verified, and it bit this very function.** Strictly between 1
and 2 the Tweedie family is the compound Poisson-gamma: a point mass at zero plus
a continuous positive part. This is the shape of spend per customer, insurance
claims, and revenue per user. Simulated such data with the event *size* growing
across groups: `b = 2.02` with **30.4% zeros** — the exponent alone says "log",
and a bare log then produces `-inf` in 3804 of 12500 rows. Worse, `pd.isna()`
does not count `-inf` as missing, so the damage passes the missingness report
silently (this is exactly what `profile_schema.count_non_finite` exists to
catch). `mean_variance_scaling` therefore reports `zero_fraction` and refuses to
recommend a bare log when non-positive values are present, pointing instead at
`log1p`, a two-part/hurdle model, or a Tweedie GLM. Negative values are a
separate case: a log is undefined, and an arbitrary shift changes the estimated
`b` itself.

The zeros are usually the interesting half of the data — "did the customer
transact at all" and "how much given that they did" are two different questions,
which is what a hurdle model makes explicit.

**Why `b ≈ 2` justifies a log.** On the chart the lognormal carries property
**P** (product), and its proof is the argument itself:

> *The product of n mutually independent lognormal random variables is
> lognormal. Proof (an elegant proof that uses the **L property of the normal
> distribution**)…* — `LognormalP.pdf`

The lognormal is closed under products *because* the normal is closed under
sums, with `log`/`exp` as the bridge. A multiplicative process — growth rates,
compounding, a product of several factors — therefore lands on the lognormal,
and taking logs is not cosmetic rescaling but a move back onto the additive
scale where mean and standard deviation mean something. Log because the
mechanism is multiplicative, not because the histogram leans right.

Do **not** bin the variable by its own value to get the groups: that
manufactures a mean-variance relationship out of nothing.

## Count data: dispersion before family

Poisson forces `variance = mean`. Measure the index of dispersion
`VMR = s²/x̄` (`count_dispersion`) and read the **VMR, not the p-value** — on
large n the dispersion test flags departures far too small to matter, the same
trap as a normality p-value.

- `VMR ≈ 1` — Poisson is a viable mechanism.
- `VMR > 1` (**overdispersion**, the common case) — usually **unmodelled
  heterogeneity**, not a wrong family. This is exactly the chart's Bayesian
  arrow, and both halves are proved on the site:

  > *If `X ~ Poisson(µ)` and `µ ~ gamma(α, β)` then the pmf of `X` is
  > `Γ(x+β)αˣ / [Γ(β)(1+α)^(β+x) x!]`, known as the gamma–Poisson distribution.*
  > — `PoissonGammapoisson.pdf`
  >
  > *The Pascal distribution is a special case of the gamma–Poisson distribution
  > when `α = (1−p)/p` and `β = n`.* — `GammapoissonPascal.pdf`

  A Poisson rate that itself varies across units *is* the gamma-Poisson mixture,
  and its marginal *is* the negative binomial (Pascal). So overdispersion is
  evidence that units differ — look for the variable that explains the variation
  (segment, device, hour) before switching family: the covariate is information,
  the family switch only absorbs it. Also check duplicates first — duplicated
  rows inflate VMR (`balancing.class_duplicate_report`).
- `VMR < 1` (**underdispersion**) — a constrained process, not Poisson at all.
  A binomial has `VMR = 1 − p` by construction (verified: `Binomial(10, 0.5)`
  gives `VMR = 0.51`), so bounded counts out of a fixed number of trials look
  underdispersed whenever they are compared against Poisson.

**Excess zeros are a separate question.** Compare the observed zero rate against
the Poisson expectation `exp(−mean)`. A large gap means **structural zeros** —
units that could not have produced an event at all (a closed store, a disabled
sensor, a customer without the feature) — mixed with sampling zeros. That is a
data-definition question before it is a modelling one: if the structural group
is identifiable, it usually should not be in the same table.

## Aggregation is only safe when the parameter is stable

Summing is always arithmetically valid. Staying **in the same family** is not.
The chart marks the convolution property conditionally, and the proofs show
exactly which parameter has to be shared:

> *If `Xᵢ ~ binomial(nᵢ, p)` … then `Σ Xᵢ ~ binomial(Σ nᵢ, p)`* — one **`p` for
> every term**; only the trial counts add. (`BinomialC.pdf`)
>
> *If `Xᵢ ~ gamma(α, βᵢ)` … then `Σ Xᵢ ~ gamma(α, Σ βᵢ)`* — one **shared scale
> `α`**; the shapes add. (`GammaC.pdf`)
>
> *If `Xᵢ ~ Poisson(µᵢ)` … then `Σ Xᵢ ~ Poisson(Σ µᵢ)`* — the means may differ.
> (`PoissonC.pdf`)

Poisson is the permissive one: its convolution needs nothing shared, which is
why aggregating counts feels safe. Binomial and gamma are not. The minimum
property carries the same kind of condition — *if `Xᵢ ~ Weibull(αᵢ, β)` then
`min{Xᵢ} ~ Weibull([Σ 1/αᵢ]⁻¹, β)`* (`WeibullM.pdf`): scales may differ, the
**shape `β` must be shared**.

So rolling sums, weekly totals, and per-user aggregates inherit the family only
if the underlying rate held constant across the parts. When it drifts, the total
still looks perfectly reasonable while every confidence interval, control limit,
and test that assumes that family is silently wrong.

`rate_homogeneity` tests this (chi-square against the pooled rate, with an
`exposure` weight for unequal periods). Two cautions, both measured:

- It is calibrated at the nominal level (false-positive rate 0.046–0.051 over
  4000 replicates), which means **~1 in 20 homogeneous series gets flagged**.
- Read `rate_min`/`rate_max` beside the p-value: a 2% spread and a 5-fold spread
  can produce the same p-value at different numbers of parts.

If the rate drifts, aggregate at a level where it is stable, or add the variable
that drives the drift — do not simply widen the window.

## Properties worth checking before modelling

Each box on the chart carries letters for the properties the family satisfies.
The ones that change EDA decisions:

- **F (memoryless)** — held by exactly two distributions, geometric and
  exponential: *`P(X > s+t | X > t) = P(X > s)`* (`ExponentialForgetfulness.pdf`).
  If the process has memory (wear, burn-in, user fatigue, learning), an
  exponential waiting-time model is wrong by construction, no test needed.
- **R (residual)** — the conditional distribution after left-truncation stays in
  the family (and `F ⇒ R`): *the `U(a,b)` distribution left-truncated at `c`,
  `a < c < b`, is also uniform* (`UniformR.pdf`). This is the criterion for
  **truncation bias**: when data is observed only above a threshold (customers
  who survived 30 days, transactions over $10), families without R change shape,
  and statistics fitted on them are biased for the untruncated population.
- **M / X (minimum / maximum)** — features like "time to first event" or "peak
  over the period" keep the family for exponential and Weibull, and do not for
  most others.
- **C (convolution)** — see the aggregation section above.
- **L (linear combination)** — `L ⇒ C` and `L ⇒ S`.

## What the chart leaves out, and why that matters here

The chart's own FAQ lists ~140 further univariate distributions that did not fit.
The selection criterion is **provable connectivity and a planar layout**, not
empirical frequency — so the families you meet most often in messy operational
data are disproportionately the omitted ones. The ones that change an EDA
decision:

| Off-chart family | The EDA question it answers |
|---|---|
| **Tweedie** | the power-variance family itself; the `b` above *is* its parameter |
| **Zero-inflated (ZIP/ZINB)** | structural zeros mixed with sampling zeros |
| **Conway-Maxwell-Poisson** | under- **and** overdispersion in one family |
| **Poisson-binomial** | what a binomial sum becomes when `p` drifts |
| **Stable** | why some heavy-tailed sums never become normal |
| **Mixture** | the general mechanism behind multimodality |
| **Categorical** | the everyday distribution of a nominal column |
| **Zipf–Mandelbrot** | real token-frequency tails (plain Zipf fits the head only) |
| **Skellam** | differences of counts (day-over-day deltas, count A/B tests) |
| **Truncated / folded / half-normal** | observation windows and `|x|` transforms |
| **Generalized Pareto (Pickands), GEV** | threshold exceedances and block maxima |

`family_router.py` turns this into a measured routing step: `route(series, by=…)`
returns the signature it measured plus ranked candidates, each with the trigger
that raised it and a URL. It stays **silent** on well-behaved data and on
families already covered by the chart — a router that always answers is a random
family generator.

### Following a link: the discipline

Reading the source is part of the method, not an optional extra. The rules:

1. **Only follow a link a measurement raised.** Never pick a family because it
   appears in a list or sounds apt. The trigger goes in the report next to the
   name.
2. **Fetch, then map the parameterization before touching a parameter.** Sources
   disagree on scale vs rate and on argument order; `scipy.stats` takes `scale`,
   most textbooks give a rate. Quote the source's density and match it to the
   library's signature explicitly.
3. **Verify on held-out data.** Fit on train/fold only, compare against the
   simpler baseline family with a Q-Q or PP plot and a proper scoring rule. More
   parameters always fit better in-sample; that is not evidence.
4. **Require a mechanism.** A family that fits but describes a process nobody in
   the domain believes in is a curve, not an explanation. Ask what generates it.
5. **Record the rejected alternatives**, not just the winner.
6. A candidate that survives none of the above is reported as *considered and
   dropped*, which is a finding too.

Access note: Wikipedia and most journal hosts fetch normally. `math.wm.edu`
serves an incomplete certificate chain, so a standard fetch fails to verify it;
`curl --ssl-no-revoke` works and still validates the chain (Windows cannot reach
the revocation server — that is the actual failure). The chart's own PDFs are
enumerable from the page's `href="PDFs/…"` links.

Three of these close gaps left open elsewhere in this file:

- **Poisson-binomial** is the missing half of the aggregation rule. `BinomialC`
  requires one shared `p`; when the rate drifts, the sum of independent Bernoulli
  trials with differing `p` is Poisson-binomial — a real distribution, just not a
  binomial. So "the total is not binomial" is not hand-waving, and the fix is to
  model the drift rather than to widen the window.
- **Stable distributions** are the family closed under convolution up to location
  and scale; the normal is the only member with finite variance, and the Cauchy
  is the index-1 member. The generalized CLT sends sums of heavy-tailed variables
  to a stable law, not to a normal. The chart shows the normal and the Cauchy but
  not the family that explains why they behave alike under addition.
- **Conway-Maxwell-Poisson** is the honest answer for underdispersed counts,
  where `count_dispersion` otherwise only reports that Poisson is not the
  mechanism.

**A name collision to check.** The chart carries a node called
`Generalized Pareto(δ, κ, γ)` from the survival/hazard literature, while the
extreme-value `Generalized Pareto` (Pickands, shape `ξ` and scale `σ`) is on the
*omitted* list. Same name, different distribution — confirm which one a library
or paper means before matching parameters.

## Where the chart stops

It encodes closure properties, not moment existence, and that gap matters. The
Cauchy carries **C**: sums of independent Cauchy variables are Cauchy. The
normal carries **L** (*`Σ aᵢXᵢ ~ N(Σ aᵢµᵢ, Σ aᵢ²σᵢ²)` for nonzero real
constants*, `NormalL.pdf`). Both are closed under addition, but only the normal
is the central-limit limit — the difference is finite variance, which the chart
does not show. Measured: the standard deviation of the sample mean of Cauchy
draws does not shrink at all between `n = 10` and `n = 100 000`, while for the
normal it falls exactly as `1/√n`.

Worth knowing about the source: `CauchyC.pdf` is headed **"[UNDER
CONSTRUCTION!]"** and its symbolic check reports "fail to confirm the result for
`n = 2`". The result is classically true (the Cauchy is a stable law with index
1), but the site does not currently prove it — the 2012 paper openly invites the
community to finish such proofs. `BinomialC.pdf` likewise notes its computer
algebra step "fail[s] to provide the appropriate moment generating function"
while the analytic MGF proof above it is complete. Treat an unfinished proof page
as a prompt to check a textbook, not as a refutation.

Consequence for EDA: on heavy-tailed features, CLT-based confidence intervals
fail silently. Use bootstrap (`bootstrap_ci`) or a permutation test
(`permutation_test_groups`), and read the tail behaviour before trusting any
`mean ± z·se`.
