# Latent factor structure behind a redundancy block

`clustered_correlation.py` finds *that* a set of columns is redundant and VIF says *how much* they
overlap. This file covers the question that comes next: **are these columns several noisy
measurements of one underlying thing, or genuinely distinct information that happens to co-move?**
The first answer means build one scale; the second means keep them apart. `associations.md` already
routes here — its multicollinearity section says the measurement-caused case is answered by "a scale
or a factor, not a race between the columns", and this is how that is done.

Everything here is `scripts/factor_analysis.py`. Measurements are ours unless stated.

## Component model vs common-factor model

They are not the same model, and the difference is not pedantry about vocabulary:

| | PCA (component) | Common factor (PAF/ML) |
|---|---|---|
| Direction | composites are functions **of** the columns | columns are functions **of** the factors |
| Diagonal of `R` | 1.0 — all observed variance is available | communality — the shared part only |
| Measurement error | credited to the component | left in the uniqueness |
| Scores | exact closed-form weighted sum | an estimate |
| Answers | "how do I compress this?" | "is there a construct here?" |

Both are one eigendecomposition of a correlation matrix (same ancestor as MDS, correspondence
analysis and discriminant analysis — `mentoring.md`), which is why they agree whenever communalities
are high and diverge exactly where they are not.

**Measured loading inflation.** One-factor design, 9 indicators, n=500, 60 reps, mean `|loading|`:

| true loading | PCA | PAF | inflation |
|---|---|---|---|
| 0.90 | 0.9118 | 0.9002 | +0.0116 |
| 0.80 | 0.8236 | 0.7989 | +0.0248 |
| 0.70 | 0.7382 | 0.6987 | +0.0395 |
| 0.60 | 0.6555 | 0.5988 | +0.0567 |
| 0.50 | 0.5758 | 0.4984 | +0.0774 |
| 0.40 | 0.5023 | 0.4000 | +0.1022 |

PCA reads a 0.40 indicator as 0.50. It gets worse as the block shrinks: at a fixed true loading of
0.60, inflation ran **+0.1602 / +0.0985 / +0.0562 / +0.0343 / +0.0208** for p = 3 / 5 / 9 / 15 / 25.
Three noisy indicators is where people reach for PCA and is its worst case.

**The scope of that finding is narrower than it looks, and saying so honestly matters more than
winning the argument.** If the deliverable is a *score* rather than an interpretation of loadings,
the two are interchangeable: factor and component scores correlated **0.9994–0.99997** in every
design tested, and tracked the true latent variable equally well (0.9362 vs 0.9365 at loading 0.8
with 4 indicators; 0.6532 vs 0.6588 at loading 0.4). The **unit-weighted mean of the z-scored
columns** matched both (0.9366 / 0.6597) — the machinery bought nothing over an average.

Weighting pays only when indicators are unequal. With loadings 0.8/0.7/0.6/0.5/0.4/0.3 plus two junk
columns at 0.05: **0.8915** (factor score) vs 0.8763 (PCA) vs **0.8124** (plain mean) — ~8 points,
all of it from not letting the junk columns vote.

**Decision rule.** Interpreting loadings or arguing about dimensionality → common factor model.
Compression/decorrelation with no intention of calling a component a construct → PCA. Either way,
compute the plain mean first and check whether the complexity earns its place.

## How many factors

`parallel_analysis` (Horn): simulate datasets of the same n×p shape from independent normals, take
the 95th percentile eigenvalue at each position, keep the leading factors that beat it.

Against Kaiser's eigenvalue>1 rule (3 true factors, factor correlation 0.30, 50 reps/cell):

| design | Kaiser | parallel analysis |
|---|---|---|
| load .65, p=15, n=300 | 3.00, exact 100% | 3.00, exact 100% |
| load .45, p=15, n=300 | 4.18, over-extracts 94% | 3.00, exact 100% |
| load .45, p=12, n=200 | 4.02, over-extracts 86% | 2.58, exact 66% |
| load .35, p=12, n=200 | 4.92, over-extracts 100% | 1.98, exact 18% |
| load .45, p=24, n=300 (k=4) | 7.26, over-extracts 100% | 3.98, exact 98% |
| **pure noise, p=20, n=300** | **10 factors** | **0 factors** |

**The errors point in opposite directions**, which is the whole argument. Kaiser never
under-extracts and is wrong upward everywhere except the strongest design; on 300 rows of pure
independent noise it claims 4.83 / 9.45 / 18.38 factors at p = 10 / 20 / 40 — roughly **p/2
dimensions in data with no structure at all**. Parallel analysis never over-extracts in any cell and
errs downward on weak loadings, where 0.35 loadings on 200 rows genuinely sit near the noise floor —
under-extraction there is the honest answer, not a defect.

Both agree when the structure is strong, i.e. when the choice does not matter. Treat the count as a
**candidate**, confirmed against the residual matrix and against what the columns mean.

## A big first eigenvalue is not evidence of a common cause

The most important negative result here. Factor analysis will show you factors whether or not a
factor mechanism exists. A pure causal chain `x1 → x2 → … → x6`, which has **no common cause
anywhere in it**, produces a dominant first component:

| path coefficient | PC1 share | chain: 1-factor RMS residual | true 1-factor data at same PC1 |
|---|---|---|---|
| 0.6 | 47.3% | 0.1612 | 0.0052 |
| 0.8 | 68.0% | 0.1301 | 0.0030 |
| 0.9 | 82.9% | 0.0773 | 0.0015 |

82.9% of variance on one component is a number any scree plot or variance-explained read would call
unidimensional. **The residual correlation matrix is what separates the two — a 25–50× gap.** So:
report `rms_residual_correlation`, never variance explained, as the check that the model reproduces
the data.

**And note where that check runs out.** The usual ~0.08 convention flags the 0.6 and 0.8 chains but
**not** the 0.9 one, whose residual (0.0773) sits just under it — the `verdict` alone reads
`clean_simple_structure` there. The gap against genuine one-factor data (0.0773 vs 0.0015) is still
enormous, but it is a *comparison*, not a threshold. A tight chain is genuinely hard to distinguish
from a common factor by fit alone, which is the real lesson: the absolute cutoff is a convention,
the ratio is the evidence, and neither is a substitute for knowing whether a common cause is
plausible. Even a small residual only rules out one alternative; it does not establish the
mechanism. A latent variable is a hypothesis about why columns co-move, and the same correlation
matrix is reproducible by a chain, by a common cause, and by a selection artefact.

## Rotation

Rotation is a change of basis, not a change of model. It leaves communalities and the reproduced
correlation matrix **exactly** where they were (measured max abs difference 6.7e-16 and 7.8e-16)
while moving the loadings a great deal (max abs difference 1.03 on the same data). Nothing is gained
or lost in fit — only readability. A rotation therefore cannot be "wrong" the way an estimate can;
it can only be less interpretable, or dishonestly chosen. This is also why trying several rotations
is **not** p-hacking: they are equivalent expressions of one solution, and none of them has a
p-value attached. Rotating until the structure matches a hypothesis and then presenting it as a
discovery is the abuse; the fix is to say which rotation was used and why.

**Default to oblique.** Orthogonal rotation fixes the angle between factors at 90°, whose cosine is
0, so it *imposes* uncorrelated factors instead of finding them — and the relation between the
factors has to go somewhere. It goes into the loadings. Clean 2-factor design, 5 pure indicators
each, loading 0.70, n=500, 60 reps, factor columns aligned to truth before scoring:

| true factor r | varimax salient / cross | promax salient / cross |
|---|---|---|
| 0.0 | 0.701 / 0.029 | 0.701 / 0.026 |
| 0.2 | 0.698 / 0.066 | 0.702 / 0.025 |
| 0.4 | 0.684 / 0.138 | 0.698 / 0.028 |
| 0.6 | 0.666 / 0.221 | 0.696 / 0.037 |
| 0.8 | 0.625 / 0.312 | 0.665 / 0.064 |

Every one of those cross-loadings is **manufactured** — the items are pure by construction. At a
true factor correlation of 0.8, varimax reports items loading 0.31 on a factor they have nothing to
do with, which reads as "these columns are double-barrelled" and is entirely an artefact of the
right angle. Promax keeps them near zero and reports the correlation instead, recovering |r| =
0.035 / 0.194 / 0.379 / 0.585 / 0.748 against a truth of 0.0 / 0.2 / 0.4 / 0.6 / 0.8 (slight
shrinkage, 80 reps).

The first row is the argument: when the factors really are uncorrelated, oblique costs nothing
(0.026 vs 0.029) and reports r = 0.035. **An orthogonal rotation cannot return the oblique answer;
an oblique rotation can return the orthogonal one.**

Pattern coefficients under an oblique rotation are exactly the partial-regression analogue —
a column's relation to a factor *controlling for* the other factors — which is the same distinction
as `sr²` vs a raw correlation in `associations.md`.

## Improper solutions (Heywood cases)

A communality that reaches or exceeds 1.0 implies a **negative uniqueness**: the column would need
more than all of its variance explained. Same family as a correlation above 1 or a non-positive-
definite matrix. It is an improper solution, not a rounding artefact, and it is a statement about
the *model*, not about that one column.

Measured frequency (2 factors, loading 0.70, factor correlation 0.30, 200 reps/cell):

| indicators/factor | n=50 | n=100 | n=300 | n=1000 |
|---|---|---|---|---|
| 2 | 0.240 | 0.170 | 0.035 | 0.000 |
| 3 | 0.085 | 0.005 | 0.000 | 0.000 |
| 4 | 0.005 | 0.000 | 0.000 | 0.000 |
| 6 | 0.000 | 0.000 | 0.000 | 0.000 |

**Three indicators per factor is where the problem mostly stops; two is a design that fails a
quarter of the time on small n** (0.240 at n=50; 26.3% measured at n=60 over 300 reps). Two
indicators per factor is also *empirically* under-identified — the factor correlation is the only
thing holding it together — and improper solutions rose from 0.010 to 0.070 as that correlation fell
from 0.60 to 0.05.

Causes, in the order worth checking: too few indicators; too few rows; too many factors extracted;
an outlier; a column that is ordinal or heavily non-linear being treated as continuous; columns on
wildly different scales.

**Do not repair it by clipping the communality to 1.0 or by deleting the offending column
reflexively.** Clipping silences the warning without changing what caused it and biases the
remaining loadings. The negative variance is a canary, not the gas leak. Add indicators, add rows,
or extract fewer factors — and if none of those is available, report that the block does not support
a factor solution at this sample size, which is a finding.

## Reading the report

`factor_structure_report` returns:

- `rms_residual_correlation` — **the** fit check. Above ~0.08 the solution does not reproduce the
  observed correlations, whatever the variance explained says.
- `orphan_columns` — communality below 0.20; they belong to no extracted factor. An injected
  pure-noise column landed at **0.0129** against a median of **0.4772** for real indicators. An
  orphan is a finding, not a defect: usually either a column measuring something the others do not
  (keep it separate, possibly the seed of a second construct) or one measuring nothing (a data
  quality question). Do not average it into a scale either way.
- `complex_columns` — salient on more than one factor. Check the rotation first: under an orthogonal
  rotation a share of these are manufactured (table above).
- `factor_correlations` — if a pair approaches 1.0, there are fewer factors than extracted; the
  cosine of a vanishing angle is the correlation.
- `heywood` / `heywood_columns` — above.

**Naming discipline applies to factors exactly as to clusters** (`mentoring.md`): `factor_1..k`
until something outside the analysed columns supports a name. A factor called "engagement" is
treated as an established entity by every reader thereafter, and the demotion back to "artefact of
which columns happened to be in the block" never travels as far as the name did.

## Scope limits

- **This is EDA, not psychometrics.** Confirmatory factor analysis — fixing loadings to zero and
  testing the restriction — is modelling, requires an SEM package, and is out of scope. The line
  worth carrying over is that "exploratory" and "confirmatory" are the ends of a continuum and real
  practice sits in the middle: the columns were chosen deliberately, so nothing here was ever purely
  exploratory. Report the structure you started from, what the data changed, and why — and treat the
  result as a hypothesis until it is checked on rows that did not shape it.
- **An established instrument's published structure is a hypothesis about your sample, not a
  fact.** If a scale's scoring manual assumes three subscales, check that the structure holds in this
  population before computing them; a structure that does not replicate makes the resulting scores
  uninterpretable. The opposite error is as bad — re-deriving a bespoke structure for every sample
  means every study uses a different ruler and nothing is comparable. When they conflict, that is a
  finding to report, not a discrepancy to smooth over.
- Fit on train/fold only. The correlation matrix is part of the model.

Sources for the framing: Quantitude S1E22 "Factor Analysis: The Good, The Bad, and The Ugly",
S3E03 "Principal Components Analysis Is Your Pal", S3E15 "Heywood You Help Me With Negative
Residual Variances", S5E06 "Advanced Factor Structures", S6E14 "Factor Rotation, But Is It Art?"
(Curran & Hancock). All measurements above are ours.
