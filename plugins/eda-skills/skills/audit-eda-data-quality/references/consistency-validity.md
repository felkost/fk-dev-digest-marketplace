# Consistency, validity, and defect origin

Defect classes where every individual value is well-formed and only the
relationship between values, or the process that produced them, is wrong.
Tooling: `scripts/consistency.py`, plus `profile_schema.py` for the value-level
flags.

## Where the defect came from decides how to fix it

Sort every finding by origin before choosing a remedy — the same wrong value
gets a different treatment depending on which of these produced it:

| Origin | Example | Remedy |
|---|---|---|
| Source/collection | broken sensor, manual entry typo | correct, flag, or exclude rows; add validation at intake |
| **Our own transformation** | `finish_hour - start_hour` = −22 across midnight | **fix the function**; repairing rows hides a bug that regenerates |
| Pipeline structure | duplicate insert on retry, encoding mismatch on import | fix the ETL step; cleaning is re-done and re-lost every load |
| Real but unusual | a genuine 12-hour session | keep; adjust the model or the constraint |

The middle two matter most because both **regenerate**. A cleaned dataset whose
pipeline still writes the defect is clean exactly once, and the next import
silently reintroduces it — often after the model is in production. Record for
each finding whether the fix belongs in this dataset or upstream, and treat
"upstream" findings as pipeline tickets, not notebook cells.

This applies to `mixed_python_types`, `encoding_artifacts`, duplicate inserts,
and every derived-column violation: they are symptoms of a producer, and the
audit's job is to name the producer.

## The rows that are missing entirely

`missingness.py` audits missing **cells**. A separate and less visible defect is
missing **rows**: the sampling frame silently excludes part of the population the
model will actually meet. No column is wrong, no constraint is violated, and no
amount of profiling the table will reveal it — the evidence is outside the file.

The canonical case is **survivorship**. A table of "our customers", assembled
today from the current customer database, contains only those who did not leave;
the churners it should teach the model about were deleted from the frame by the
very process that produced it. Volume does not help: five years and five
petabytes of transaction history is five years of survivors. Big data cures
variance, never selection bias — a larger biased sample just estimates the wrong
number more precisely.

Three checks that surface it, none of which are statistics on the table itself:

- **Reconstruct the frame at the decision time**, not at export time. For churn,
  maintenance, or default modelling, the row must be a *point-in-time snapshot*
  of an entity that still existed then, with the outcome attached afterwards.
  Rebuilding history from a current-state table is what deletes the negatives.
  This is the same point-in-time discipline the temporal-leakage rules impose on
  features, applied one level up — to which rows exist at all.
- **Ask what had to happen for a row to be here.** An entity must have survived
  to be exported, a session must have completed to be logged, a form must have
  been submitted to be stored, an item must have been *shown* to be clicked.
  Each of those is a filter, and each one is a candidate confound with the
  target.
- **Compare the frame against an external count** where one exists (registry
  totals, upstream event counts, billing records). A frame that is 40% of the
  population it claims to describe is a finding to report, with the missing 60%
  characterised as far as possible.

**Logged behavioural data is the sharpest version of this**, because the
exclusion is caused by a previous model. A recommender's training log records
only what that recommender chose to show — impressions are Missing Not At
Random, with the *model* as the missingness mechanism. Reading such a log as if
it described user preference confuses "users did not like this" with "users were
never offered this", and a model retrained on it inherits and hardens the prior
model's blind spots. Where this matters, record the exposure/propensity
alongside the outcome so the analysis can weight by it, and note that some
deliberate exploration must exist in the log or the counterfactual is not
identifiable at all. Flag it in the audit; correcting it is a modelling decision
outside this project's scope.

Record the frame's construction rule in the dataset contract next to the unit of
observation. "Who is *not* in this table, and why" belongs in the dataset card.
Source of the framing: *Top 25 ML System Design Interview Questions* (Hao Hoang,
2025) §2.5 "The Silent Graveyard Effect" and §6.1 "The CTR Feedback Loop Trap".

## Invalid data we produced ourselves

Invalid data is illogical rather than merely extreme: −2 hours in an app, age
170, a delivery before its order. Unlike outliers, there is no distributional
question — the value is impossible by definition.

Encode the definitions as executable rules (`logical_constraints`) and run them
**after every derived-feature step**, not just on raw input:

```python
logical_constraints(df, {
    "duration_non_negative": "time_in_app >= 0",
    "age_plausible":         "age >= 0 & age <= 120",
    "order_before_delivery": lambda d: d.ordered_at <= d.delivered_at,
})
```

The canonical trap: `time_in_app = finish_hour - start_hour` gives −22 for a
23:00→01:00 session. Dropping the negative rows biases the dataset toward
sessions that do not cross midnight — a selection effect introduced by the
"cleaning". Subtract timestamps, not hour-of-day integers.

Keep the rule set as a regression check in the pipeline; a constraint that fires
only during EDA is a constraint that will be violated again.

## Inconsistent representations

`Apples` / `apples` / `APPLES` / `appels` are one product to a human and four
categories to a model — inflating cardinality, splitting counts, and creating
rare levels that look like signal.

- Normalisation (case, whitespace) is deterministic and safe:
  `near_duplicate_categories` reports it as `reason="normalized"`.
- Typo detection is a **review queue, never an auto-merge**. Measured similarity
  ratios: `apples`/`appels` = 0.833 (typo) versus `xl`/`xxl` = 0.800 and
  `a100`/`a101` = 0.750 (legitimately distinct). Similarity alone cannot
  separate them; length can, which is why fuzzy comparison is restricted to
  labels of at least `min_length` characters. Screen short codes against a
  reference list instead.
- `difflib` scores transpositions poorly (`kyiv`/`kiev` = 0.750), so
  transliteration variants need a phonetic or transliteration map.
- The most frequent spelling is the default canonical form, but frequency is not
  correctness — a systematic upstream typo can outnumber the correct value.
- Fit the normalisation map on **train** and apply it to validation/test like
  any other learned transformation; a map built from all splits leaks the test
  vocabulary. Unseen variants at inference must have a defined fallback.

Visualise before deciding: a bar chart of category counts makes variant pairs
obvious, and `categorical_summary` gives cardinality plus rare-level counts.

## Conflicting attributes under one key

Same `product_id`, two products; same `customer_id`, two birth dates
(`key_attribute_conflicts`). The key is intact and every value is valid — only
the join reveals the defect. Distinguish three causes before repairing:

- **Data-entry error** — correct or exclude.
- **Slowly changing dimension** — price legitimately changed over time. The data
  is right and the schema is wrong: the true key is `(id, valid_from)`. Collapsing
  it to one row per id destroys history and, if the surviving row is the current
  value, injects future information into past rows (temporal leakage).
- **Recycled identifier** — the id was reassigned to a new entity. Treating it as
  one entity merges two, and a group-aware split will then leak across them.

## Duplicates: detection is easy, resolution is not

Duplicates inflate counts, shift means toward repeated values, and break
correlation and class-balance estimates (cross-check
`balancing.class_duplicate_report`). Common producers: multi-source merges,
double form submissions, retried inserts, many-to-many joins.

`duplicate_report` returns which columns actually disagree within each group,
because that determines the admissible strategy:

1. **Keep one** — only when no column conflicts. Safe to automate.
2. **Keep the most relevant** (usually most recent) — needs an ordering column;
   inspect `keep_index` before applying. Note this discards the other rows'
   fields even when they are populated and the winner's are not.
3. **Merge into an entity** (record linkage) — when rows are complementary
   rather than redundant. Needs domain rules.

Two cautions:

- **Duplicates are not automatically defects.** Repeated measurements of one
  entity may be legitimate; the correct response is a **group-aware split**, not
  deletion, which would destroy real replication.
- **Deduplicate before splitting.** Duplicates spanning train and test are
  entity leakage — the model is scored on rows it memorised
  (`leakage_checks.py`).

## Data-type traps

**Strings.** Standardise case and whitespace, strip embedded newlines/tabs
(`embedded_newlines_or_tabs` — they break CSV round-trips and token counts), and
fix encoding at the point of reading. Mojibake (`cafÃ©`, `�`) means the bytes
were decoded with the wrong codec; `encoding_artifacts` flags it. Re-decode from
the source with the correct codec rather than substituting characters — the
information is still recoverable at that stage, and lost after. Standardise on
UTF-8 for storage. Stop-word removal and one-hot encoding are modelling choices,
not cleaning, and belong downstream with a train-only fit.

**Dates and times** (`datetime_consistency`). `"24 Oct 2019"` is a string that
sorts alphabetically and compares wrong; coerce types explicitly. Watch for:

- **Ambiguous day/month** — when every parsed day is ≤ 12, `03/04` is undecidable
  from the data. The source format must be supplied, not guessed; `dayfirst`
  silently reorders otherwise.
- **Epoch integers** — a plain `int64` column in the Unix-time band is a
  timestamp that no datetime check will otherwise inspect.
- **Timezones** — mixing tz-aware and tz-naive values raises on comparison, and a
  naive column is unambiguous only when one timezone is documented. For
  cross-region data normalise to UTC **and keep the local offset as a separate
  feature**: local hour-of-day is behaviourally different from UTC hour-of-day,
  so collapsing to UTC destroys the daily-rhythm signal.
- **Point-in-time correctness** — a timestamp converted after the fact can move a
  row across the split boundary. Re-run `leakage_checks.py` after any timezone
  normalisation.

## Non-finite and placeholder values

- **`inf` is not missing.** `pd.isna` does not count it, so it passes every
  missing-rate report as "0% missing" and then turns mean, std, and quantiles
  into `NaN`. `profile_schema` reports `n_inf` separately from `n_missing`.
  Usual producer: a division by zero in a ratio feature — again, fix the
  transformation.
- **Placeholder defaults.** An upstream system writing `email@company.com`,
  `1900-01-01`, or `0` instead of a missing marker produces a valid-looking value
  with no missingness signal. `dominant_value_share` and `constant_value` flag
  the concentration; provenance decides whether it is a default or a real mode.
  A sentinel date inside the plausible range will never trip a range check —
  concentration is the only signal.
- **Sentinel strings** beyond pandas' defaults (`#N/A`, `<NA>`, `(null)`,
  `undefined`) survive when data arrives from Excel, JSON, or a database driver
  rather than `read_csv`.

## Proxy columns: measurement quality is a data-quality defect

A column can pass every check in this file — no missingness, no sentinels, a
plausible range, consistent types — and still be an error-laden stand-in for
the thing it is named after (`self_reported_income`, a survey scale, a sensor
reading, a geocoded centroid). Nothing in the profile reveals it, so it has to
be recorded from provenance, not inferred.

It matters because the consequence is **bias, not merely lost precision**, and
it is asymmetric between the two sides of an analysis:

- Noise in a **predictor** shrinks its estimated slope by roughly its
  reliability — a true slope of 1.0 was measured as 0.8999 / 0.6999 / 0.4998 at
  reliability 0.90 / 0.70 / 0.50.
- Noise in the **target** leaves the slope unbiased but inflates its standard
  error (slope 1.0005 → 1.0020 while the SE grew 0.0112 → 0.0274).
- Any observable correlation is capped at `r_true·√(rel_x·rel_y)`: against a
  true 0.60, reliabilities 1.0 / 0.8 / 0.6 / 0.4 produced 0.6003 / 0.4801 /
  0.3598 / 0.2394. **A weak correlation may be a measurement ceiling rather
  than a weak relationship** — do not retire a hypothesis on it without asking
  how well both sides were measured.
- A **control variable** measured with error only partly removes what it was
  added to remove. Conditioning on a proxy of a confounder, with a true direct
  effect of exactly 0.0, still left +0.1498 at reliability 0.90 and +0.5541 at
  0.30.

Practical step: keep a `measured_or_proxy` note per column in the data
dictionary, flag proxies in the audit manifest, and prefer the directly
measured column when both exist.

**When several columns measure the same construct, reliability stops being a
domain question and becomes computable.** A multi-item scale *is* the repeated
measurement this problem asks for — the items are the parallel instruments — so
`discover-eda-structure/scripts/reliability.py` estimates `rel` from the items
themselves (`scale_score_report`, `mcdonald_omega`) and turns it into the
ceiling every downstream correlation is capped by. Two scales at reliability
0.70 cannot correlate above 0.70 even when they measure the same thing, and a
true 0.80 between them reads as 0.56 — which is worth knowing before a
hypothesis is declared dead. It remains a domain question only for a **single**
column with no parallel measurement. See
`discover-eda-structure/references/measurement-reliability.md` for the estimator
and its limits, and `.../associations.md` for how the attenuation propagates
into association estimates.

### The target is a proxy too, and it is the expensive one

The same defect in the label column is worse, because every metric, every
feature ranking, and every business claim is defined relative to it. `is_fraud`
usually means *detected and confirmed* fraud; `churn` means someone's 90-day
rule; `is_qualified` means a past recruiter's judgement; `arrest` is not
`crime`. The model will faithfully learn the operational definition it was
given, including the parts nobody intended.

Two failure modes, and they need different fixes:

- **Under-coverage** — the label captures only part of the construct. A
  "customer satisfaction" flag built solely from complaint tickets misses every
  silently unhappy customer. Symptom: the label's own base rate disagrees with
  an independent measurement of the same thing.
- **Contamination** — the label mixes in something else. A "high-value
  customer" flag that folds in tenure now measures value *and* tenure
  inseparably; any feature correlated with tenure will look predictive of
  value. Symptom: the label's drivers split along a dimension the name never
  promised.

Checks that are available in the data rather than only from provenance:

1. **Ask how the label was produced**, mechanically — which query, which team,
   which threshold, applied when. A label defined by a rule means the model is
   being asked to relearn that rule, and any feature used in the rule is
   leakage (`splits-leakage.md`).
2. **Look for a second, independently produced measurement** of the same
   construct and check that they agree where both exist. Disagreement is the
   finding; perfect agreement suggests one was derived from the other.
3. **Check that the label means the same thing across time, site, and
   annotator.** A definition change is indistinguishable from a real shift in
   `distribution_shift` output, which is why instrumentation is its first
   alternative hypothesis (`time-series.md`). Label drift also breaks the
   split: rows before and after a definition change are not the same task.
4. **State the population the label can speak for.** A label observed only for
   rows that passed some earlier filter (approved applicants, shown items,
   surviving accounts) describes that filtered world only — the missing-rows
   problem above, in label form.

### The arithmetic, when the label came from a detector

If the label is the output of a detector, rule, or review step whose
sensitivity and specificity you can estimate, `consistency.proxy_label_diagnostics`
turns that into what the column actually contains. Every figure below was
verified against simulation at N = 300 000.

| sens | spec | true prevalence | PPV | apparent positive rate | inflation |
|---|---|---|---|---|---|
| 0.90 | 0.90 | 0.20 | 0.692 | 0.260 | 1.3× |
| 0.90 | 0.90 | 0.05 | **0.321** | 0.140 | 2.8× |
| 0.90 | 0.90 | 0.02 | **0.155** | 0.116 | **5.8×** |
| 0.93 | 0.98 | 0.05 | 0.710 | 0.066 | 1.3× |
| 0.80 | 0.999 | 0.01 | 0.890 | 0.009 | 0.9× |

Three consequences that routinely go unnoticed:

- **Precision collapses at low prevalence even for a "90% accurate" detector.**
  At a 2% base rate, ~85% of the positive labels are wrong while the detector
  is still 90% sensitive and 90% specific. Training on that column teaches a
  model to reproduce mostly false positives.
- **A noisy label inflates the apparent base rate.** The flagged rate is
  `sens·prev + (1−spec)·(1−prev)`, which at prevalence 0.02 reads 0.116 — a
  5.8× overstatement. Any class-imbalance decision taken from the label's own
  frequency inherits this, so "our defect rate is 12%" may be a true 2%.
- **Specificity, not sensitivity, is the lever when positives are rare.** The
  last row has *lower* sensitivity than the first three and by far the best
  precision. Chasing recall is the wrong instinct for a rare class.

Where to spend effort: propagating a 95% CI on a sensitivity of 0.93 estimated
from n = 172 (CI 0.885–0.961) moves PPV only from 0.318 to 0.336, whereas
moving prevalence from 0.20 to 0.02 moves it from 0.692 to 0.155. **Prevalence
uncertainty dominates the quoted-accuracy uncertainty by an order of
magnitude** — and prevalence is also the number nobody measured, because it
requires knowing the truth on unflagged rows. Ask which population the
prevalence refers to before accepting any of it (see also the reference-population
caveat on lift in `discover-eda-structure/references/associations.md`).

Report it as a first-class audit finding with the same fields as any other
defect. A named construct, an operational definition, and the gap between them
belongs in the dataset manifest; downstream stages must not silently treat the
column name as the construct.
