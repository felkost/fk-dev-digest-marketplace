# Dataset readiness output contract

## Required artifacts

1. **Dataset contract**: unit of observation, target, horizon, keys, time semantics, allowed values, and intended use.
2. **Data-quality report**: issue, evidence, severity, affected scope, proposed action, and status.
3. **Split manifest**: strategy, seed or time boundaries, group constraints, row counts, class rates, and overlap checks.
4. **Feature manifest**: feature name, source, formula, type, availability time, missingness rule, encoding/scaling, and leakage risk.
5. **Transformation manifest**: ordered fit/transform operations and the split on which each operation is fitted.
6. **Selection report**: candidate, evidence from multiple methods, stability, redundancy, cost, decision, and caveat.
7. **Sampling manifest**: original and resampled counts, algorithm, parameters, fold scope, and provenance of synthetic rows.
8. **Diagnostic report**: baseline/probe protocol, out-of-fold results, error slices, ablations, and forbidden causal interpretations.
9. **Dataset card**: provenance, intended use, exclusions, representativeness, privacy/fairness risks, known limitations, and version.

## Readiness gate

Mark the dataset ready only when:

- schema and semantic constraints pass or have documented exceptions;
- labels and row identity are sufficiently trustworthy for the intended use;
- no known duplicate, target, temporal, group, preprocessing, or synthetic-data leakage crosses evaluation boundaries;
- missingness, outliers, imbalance, and subgroup coverage have explicit handling decisions;
- every learned transformation is reproducible and fitted only on allowed data;
- selected features are available at inference time and have stable evidence beyond one split or one importance method;
- cluster or representation-based features are stable enough for their declared use;
- validation/test retain the deployment distribution unless a different target distribution is explicitly justified;
- unresolved high-severity risks are absent, or the user explicitly accepts them.

If a gate fails, return `not ready`, name the blocking evidence, and specify the smallest corrective experiment.

