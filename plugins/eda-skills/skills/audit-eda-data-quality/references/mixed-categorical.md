# Mixed and categorical values

## Diagnose before encoding

- Determine whether a cell contains one category, an ordered list, an unordered set, a hierarchy, or malformed text.
- Normalize Unicode, whitespace, case, separators, aliases, and explicit unknown/not-applicable states.
- Preserve the original value and record parsing failures.
- Fit category vocabularies only on training data; map unseen values explicitly.

## Strategy selection

- **One nominal label:** one-hot, ordinal encoding only when order is real, or model-native categorical handling.
- **Unordered multi-label set:** multi-hot encoding; optionally add count and domain-valid interaction features.
- **Ordered list:** preserve order only if collection semantics support it; first-item reduction otherwise loses information.
- **Hierarchy:** encode levels separately or use a hierarchy-aware representation.
- **Combination as a real entity:** use a normalized combination category only when the combination itself has stable meaning and adequate support.
- **High cardinality:** hashing, frequency/count encoding, learned embeddings, or out-of-fold target encoding with regularization.

Do not choose the most frequent label from a multi-label value merely to preserve global frequency. It discards row-level information and can amplify majority categories. Priority reduction requires explicit domain rules.

## Parsing multi-value cells

Cells like `a`, `(a, b)`, `(a, c, d)` mix single and multi-category values in one column. Parse each cell to a list of categories (strip brackets/whitespace, split on the separator, drop empties, normalize aliases and case), keep the raw string, and flag parse failures. Then encode the lists with a multi-hot binarizer whose vocabulary is fitted on **training rows only**; map unseen categories to an explicit `unknown` indicator rather than silently dropping them. Optionally add a set-size count feature.

### Reductions to avoid by default

Each of these collapses a multi-value cell to a single label and destroys row-level information. Use only under an explicit domain rule, never as a convenience default:

- **First-category:** keeps only the first parsed item — item order is usually a data-entry artifact, not signal.
- **Most-frequent / dominant:** replaces the set with its globally most common member — amplifies majority categories and leaks global frequency into every row.
- **Priority:** picks by a fixed priority list — acceptable only when that priority is a real, recorded domain rule.

Prefer multi-hot encoding; reduce to a single normalized combination category only when the combination is a stable real entity with adequate support.

## Leakage controls

- Compute frequency and target encodings within train/folds.
- Use out-of-fold target encoding for training rows and train-fitted mappings for validation/test.
- Treat rare-category grouping thresholds as learned parameters fitted on train.
- Audit category distribution and unseen rates by split and time.
