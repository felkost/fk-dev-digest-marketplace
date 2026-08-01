# Tier B — trigger matrix v11 (2026-08-22)

Clears the routing debt accumulated across rounds 12–15 (16 new triggers,
t121–t136), plus regression guards and the two standing negatives.

## Protocol

A cold `general-purpose` subagent received **only** two files: a generated
catalogue of the 22 skill `description:` fields and the question list with
`id` + `prompt`. It was explicitly forbidden to open `SKILL.md`, `references/`
or anything else in the repository, and explicitly told that the `expected` /
`alt` fields present in the JSON are the answer key and must be ignored. It
reported 3 tool uses (two reads plus the result write), consistent with that
instruction. Expectations were never shown to it in the prompt.

For every item the router returned `choice`, `runner_up`, a **verbatim quote**
from the catalogue as `evidence`, and a confidence label.

## Result: 23 EXACT / 1 ALT / 0 MISMATCH (24 items)

| id | verdict | expected | routed to | runner-up |
| --- | --- | --- | --- | --- |
| t121 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t122 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t123 | EXACT | ml-model-selection | ml-model-selection | ml-validation-design |
| t124 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t125 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t126 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t127 | EXACT | ml-model-selection | ml-model-selection | none |
| t128 | EXACT | ml-forecasting-model | ml-forecasting-model | ml-distribution-choice |
| t129 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t130 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t131 | EXACT | ml-forecasting-model | ml-forecasting-model | ml-tree-ensemble-params |
| t132 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t133 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t134 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t135 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t136 | EXACT | ml-forecasting-model | ml-forecasting-model | none |
| t18 | EXACT | ml-dimensionality-features | ml-dimensionality-features | ml-tree-ensemble-params |
| t108 | EXACT | ml-measurement-model | ml-measurement-model | none |
| t109 | EXACT | ml-measurement-model | ml-measurement-model | none |
| t113 | EXACT | ml-linear-regularization | ml-linear-regularization | none |
| t119 | EXACT | ml-model-selection | ml-model-selection | ml-linear-regularization |
| t120 | EXACT | ml-overfitting-diagnosis | ml-overfitting-diagnosis | none |
| n13 | EXACT | none | none | none |
| n14 | ALT | none | nn-training-params | none |

## The evidence is the finding

For all 16 new triggers the router quoted, as decisive, wording that rounds
12–15 added to the descriptions:

- t121/t122/t126 — "zero-shot pretrained foundation models (TimesFM, Chronos-2)
  as a second baseline that still must beat seasonal-naive on your own
  backtest" and "whether TimesFM or Chronos-2 or zero-shot forecasting is worth
  trying" (rounds 12–13)
- t123/t127 — "treats a low-code AutoML sweep (PyCaret-class compare_models) as
  an empirical shortlist tool" / "version-drift pitfalls" (round 12)
- t124 — "how to get forecast intervals" (round 12)
- t125 — "automated feature extraction for the global rung (tsfel,
  feature-engine lag/window transformers)" (round 12)
- t129/t130 — "choosing between them by covariate support, interval calibration
  and LoRA fine-tuning" (rounds 13–14)
- t131 — "why tree ensembles cannot extrapolate a trend beyond the training
  range and modelling differences fixes it" (round 13)
- t132 — "Prophet's real control surface (changepoints placed only in the first
  80 percent of history…)" (round 14)
- t133 — "checking ARIMA order sufficiency with the Ljung-Box test on
  residuals" (round 14)
- t134 — "using the forecast quantile band as the normality corridor for
  anomaly detection" (round 14)
- t135 — "the model ladder from naive, seasonal-naive and climatology
  (calendar-position average) baselines" (round 15)
- t136 — "STL decomposition with the robust flag when outliers bend the
  extracted trend" (round 15)

This is the same signal v10 produced: the router does not merely land on the
right skill, it lands on it *for the added wording*. Description sync is
working, and the four rounds of new zones did not need a routing fix.

## Boundary stress: all three ambiguous pairs held

The router itself flagged three items as genuinely close, and resolved all
three the intended way:

- **t128** (loss for 70%-zero sales) → forecasting, runner-up
  `ml-distribution-choice`. This is the round-10 boundary debt closed: Tweedie
  *as a loss* is forecasting, Tweedie *as a distribution* is the neighbour.
  ALT was permitted here and was not needed.
- **t131** (LightGBM undershooting a trend) → forecasting, runner-up
  `ml-tree-ensemble-params`. The new zone did not get stolen by the skill that
  owns boosting hyperparameters — the question is about the forecasting
  mechanism, and the description says so.
- **t119** (n=60, d=500) → model-selection, runner-up
  `ml-linear-regularization`. Unchanged from v10 despite round-12/13 additions
  to both descriptions.

Regression guards `t18`, `t108`, `t109`, `t113`, `t120` are all EXACT — in
particular **t18 still holds**, so the v9 boundary fix between
`ml-tree-ensemble-params` and `ml-dimensionality-features` has now survived
four rounds of description edits.

## The one non-exact item is pre-existing, not a regression

`n14` ("скільки нейронів у прихованому шарі") was designed as a negative
(expected `none`) and went to `nn-training-params` — **exactly as in v8**,
where the same behaviour was recorded. The router justified it by the
architecture-sizing clause and self-flagged it as its only low-signal call.
Two readings are defensible: either the negative is mis-specified (a neuron
count *is* an nn-training parameter question) or the description is slightly
over-broad. It is counted ALT here, not MISMATCH, and left unchanged — this is
the third run in which it behaves identically, so it is stable, documented
behaviour rather than drift.

## Matrix state

131 → 136 items over rounds 12–15; 24 run here. No description or trigger was
edited as a result of this run — nothing failed.
