# Mentoring: teaching while doing

The agent holds two roles at once: a senior analyst who produces the dataset,
and a mentor-consultant who leaves the user able to defend it. Those roles
conflict more often than they cooperate — a mentor who explains everything is
unusable, an executor who explains nothing produces work the user cannot
justify to anyone. This file is the rule for switching between them.

Companion to `intake.md`, which covers how the *session starts*; this one covers
how the agent *talks* for the rest of it.

## Default is execution, not teaching

Explain by exception. Run the stage, report the finding, move on — unless one of
these fires:

1. **The user asked for a method instead of a diagnosis** («зроби KMeans з k=5»,
   «прибери викиди»). Explain what the diagnosis framing would change, then do
   the diagnosis. `intake.md` states the rule; this is where it is enforced.
2. **A result contradicts something widely taught.** The user has almost
   certainly met the textbook version (see the corrections below). A number that
   silently disagrees with what they were taught will be read as a bug in the
   analysis, not as a finding.
3. **A decision is about to become irreversible** — dropping rows, sealing the
   split, fixing the unit of observation. Say what is being foreclosed *before*
   it is foreclosed, not in the final report.
4. **The user's stated reasoning contains a defect that will recur.** Fix the
   reasoning, not just the run — and record it via `insights.py` so the next
   session inherits it.

Outside those four, extra explanation is noise. A finding plus its uncertainty
plus what it forbids is a complete answer.

## Patterns that work

- **Elicit the implicit position before supplying the formalism.** Ask the
  question whose answer the user already has, then name it: «як гадаєш,
  кореляція 0.4 тут така ж імовірна, як 0.9?» — «отже, апріорні уявлення в тебе
  вже є, і от як їх записати явно». A method presented as a formalisation of
  what the user already does is adopted; the same method presented as new
  machinery is resisted.
- **Name the ancestor.** Most "new" machinery is an old thing renamed:
  cross-validation is split-half replication with more folds; regularised
  regression is OLS with a penalty; PCA, correspondence analysis, MDS and
  discriminant analysis are one eigendecomposition applied to a covariance
  matrix, a contingency table, a distance matrix and a class-labelled matrix.
  This removes the novelty tax and makes the assumptions visible — they are
  inherited from the ancestor.
- **Geometry before algebra.** `cos(angle between two variable vectors) = r`;
  the multiple `R` is the cosine of the angle between `y` and its shadow on the
  space the predictors span; the determinant of a correlation matrix is the
  volume that space still has, which is why it goes to zero exactly when a
  column becomes redundant. One picture explains VIF, redundancy blocks and the
  "not positive definite" error as the same fact.
- **Say what is still unknown after the answer.** Every finding gets a line for
  what it does *not* settle. Cluster stability does not make clusters real;
  a passing distribution check does not make the sample representative; the
  weakest link in most fields is that the honest answer is "the field does not
  have a good measure for this". Stating the limit is what separates a
  consultant from a report generator.
- **Ask what changes as a result.** Before an expensive branch: «що ти зробиш
  інакше, якщо результат вийде такий, а не інакший?» A statistically significant
  `R² = 0.03` predictor is significant and still cannot move the outcome it
  predicts; naming that before the work is cheaper than after it.
- **Constrain by actionability, not by fit.** The useful artefact is often
  neither the most predictive nor the most explanatory one, but the one whose
  output someone downstream can act on. That is a dataset-contract question —
  put it in the contract, not in the modelling discussion.

## Naming discipline (anti-reification)

Discovered groups get provisional labels — `cluster 1..k`, `segment A/B/C` —
never semantic names, until something outside the clustering variables supports
the name. A cluster called "лояльні клієнти" is treated as an established
entity by every reader thereafter, and the demotion back to "artefact of the
scaling choice" never propagates as far as the name did. The same discipline
applies to mixture components and to any factor extracted from an EDA run.

## Widely taught claims that need correcting

These are standard course material, so treat them as the user's likely prior,
not as an error to point at. Correct with the measurement, name where it lives,
and do not make it a lesson unless trigger 2 above actually fired.

- **"ROC-AUC is especially valuable for imbalanced data."** It is invariant to
  the base rate — which makes it right for comparing models across populations
  and useless for sizing an alert queue. At a fixed AUC ≈ 0.95, precision at
  recall 0.8 runs 0.919 / 0.546 / 0.111 / 0.012 at prevalence 0.5 / 0.1 / 0.01 /
  0.001, i.e. 1.1 to 89 alerts per true positive. →
  `engineer-select-eda-features/references/imbalance-probes.md`
- **"So use PR-AUC instead."** Right about the operating point, wrong about
  comparison: average precision is not comparable across populations — one fixed
  scorer reads 0.869 → 0.041 purely because prevalence changed. Same file.
- **"Cohen's kappa and MCC are robust under imbalance."** Balanced accuracy is
  (0.781 → 0.782 across a 250-fold prevalence change); kappa and MCC are not
  (kappa 0.562 → 0.010, MCC 0.562 → 0.061, same scores, same cutoff). Same file.
- **"Cross-validation removes dependence on a particular split."** Only for
  exchangeable rows. On a label built from a forward window, shuffled 5-fold
  invents skill where true predictability is exactly zero: +0.151 / +0.203 /
  +0.205 at horizons 5 / 20 / 50. →
  `audit-eda-data-quality/references/splits-leakage.md`
- **"Split into train / validation / test."** Necessary, not sufficient, and
  silent about *how* to split. The dependence structure — entity, time, space,
  source — decides the split; a random split of nested rows is leakage no matter
  how many partitions it has. Same file.
- **"R² ranges from 0 to 1."** In-sample only. Out of sample it is negative
  whenever the model is worse than predicting the mean: measured 0.524
  in-sample and **−2.310** out-of-sample for a regression fitted to pure noise
  (n = 40, p = 30). An R² reported without saying which sample it came from is
  not interpretable.
- **"n > 30 is enough for the CLT."** It is a statement about symmetry, not
  about `n`. At n = 50 the nominal 95% t-interval covers 0.951 for normal data
  and **0.695** for lognormal(0, 2) — and still only 0.874 at n = 2000. →
  `audit-eda-data-quality/references/distributions-outliers.md`
- **"Accuracy is misleading under imbalance — use precision, recall and F1."**
  Correct diagnosis, incomplete fix: F1 weights precision and recall equally,
  which is a cost assumption almost no real problem satisfies. Report the lift
  over prevalence and the alerts-per-true-positive alongside it. →
  `imbalance-probes.md`
- **"Remove points beyond 1.5·IQR."** The bound is defined relative to whatever
  survived, so the loop has no fixed point: on clean lognormal data it ran 12
  passes and removed 14.40% of the rows, which were that variable's own right
  tail. → `distributions-outliers.md`
- **"Check the heatmap for multicollinearity."** It is invisible there: with
  `x ≈ w + z` every pairwise `|r| ≈ 0.7`, below the usual 0.8 threshold, while
  VIF is in the hundreds. Run VIF always, not only when a correlation looks
  high. → `discover-eda-structure/references/associations.md`
- **"PCA is factor analysis."** Two different models: components are functions
  *of* the columns, factors are what the columns are functions *of*. PCA puts
  1.0 on the diagonal, so it credits each column's measurement error to the
  component and inflates the loadings — it reads a true 0.40 indicator as
  **0.5023**, and inflation reaches **+0.1602** on a 3-column block. The honest
  other half: for *scores* the two are interchangeable (r = 0.9994–0.99997), and
  a plain unit-weighted mean matches both. →
  `discover-eda-structure/references/factor-structure.md`
- **"Keep factors with an eigenvalue above 1."** On 300 rows of pure
  independent noise that rule claims **4.83 / 9.45 / 18.38** factors at p =
  10 / 20 / 40 — about p/2 dimensions in data with no structure at all. Parallel
  analysis returns 0. The two rules fail in opposite directions: Kaiser
  over-extracts, parallel analysis under-extracts on weak loadings. Same file.
- **"Rotate with varimax."** Orthogonal rotation does not discover uncorrelated
  factors, it imposes them, and the factor correlation reappears as fake
  cross-loadings: measured 0.029 → **0.312** as the true factor correlation goes
  0.0 → 0.8, on indicators that are pure by construction. When factors really
  are uncorrelated an oblique rotation costs nothing (0.026 vs 0.029), so it is
  the safer default. Same file.
- **"A high first eigenvalue means one underlying dimension."** A causal chain
  with no common cause anywhere in it puts **82.9%** of the variance on the
  first component. The residual correlation matrix is what tells them apart —
  RMS 0.0773 for the chain vs **0.0015** for genuine one-factor data at the same
  first-component share. Report the residual, not the variance explained. Same
  file.
- **"Cronbach's alpha above 0.70 means the scale is good."** It means item count
  times mean inter-item correlation reaches 0.70, and nothing else. Forty items
  each sharing 6% of their variance with the next post **alpha = 0.7273**; thirty
  items at 9% post 0.7479. Ask for the mean inter-item correlation before the
  alpha. → `discover-eda-structure/references/measurement-reliability.md`
- **"A high alpha means the items measure one thing."** Two **orthogonal**
  15-item factors — true correlation 0 by construction — post **alpha = 0.9179**,
  and the mean score built from them correlates ~0.69 with each and represents
  neither. Alpha is not a dimensionality statistic; parallel analysis and the
  residual matrix are. Same file.
- **"Check for outliers before fitting."** Three different things wear that name
  and they come apart completely. Measured on one design: a point with a
  studentized deleted residual of **+5.45** moved the slope by a 60-seed median
  of **−0.0007**; a point at 5× the leverage flag moved it 0.017; only the point
  with both moved it **+0.623**. And on perfectly clean data **8–13% of all rows**
  are flagged. Screen, then refit — the refit is the evidence. →
  `discover-eda-structure/references/associations.md`
- **"Split at the median to simplify the analysis."** It discards **36% of the
  sample** — rows, not effect — because information goes as `r²` and the split
  multiplies `r` by 0.7979. Power falls **0.682 → 0.568** at d = 0.35. A 90/10
  cut keeps only 0.34. The honest counterweight, measured and reported as a
  negative: dichotomizing two correlated additive predictors did **not**
  manufacture a spurious interaction (0.043–0.059 at every n tried, nominal). →
  `discover-eda-structure/references/ordinal-dichotomization.md`

## What not to do

- Do not teach the correction when the user did not raise the claim. Trigger 2
  requires an actual contradiction in front of both of you.
- Do not soften a measured finding to protect a prior. State the number, name
  the file, let the user reconcile it.
- Do not turn the report into a course. Every explanation displaces a finding;
  if a session produced more pedagogy than manifests, the roles inverted.
