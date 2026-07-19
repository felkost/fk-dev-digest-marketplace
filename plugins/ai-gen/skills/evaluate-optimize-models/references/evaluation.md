# Evaluation by task class

Pick the metric the task actually needs; then build the smallest eval set that can detect the
regressions you care about.

## Metric by class

| Task class | Primary metrics | Notes |
|---|---|---|
| Structured extraction / classification via LLM | Exact/field-level accuracy, precision/recall per class | Deterministic checks — no judge needed; report per-field, not just overall |
| Open-ended generation (answers, summaries) | Rubric-scored LLM-as-judge + spot human agreement | Reference-based n-gram metrics (BLEU/ROUGE) correlate poorly with quality here; use rubrics |
| Code generation | Test pass rate (execute!), lint/type checks | Executable checks beat any judge |
| RAG | Retrieval: recall@k, MRR on labeled question→passage pairs. Generation: groundedness (claims supported by retrieved text), citation correctness | Evaluate the two stages separately or you can't localize failures |
| Agents (tool use, multi-step) | Task success rate end-to-end, steps-to-success, tool-error rate, cost per solved task | Define "success" operationally per scenario; log full trajectories |
| Classical ML (trees/regression/TS) | Standard ML metrics (AUC/F1/MAE/MAPE...) on a leakage-safe split | Out of this skill's depth — see the eda-skills plugin for dataset/split rigor |

## Building the eval set

- 30–200 examples with expected outcomes; sample from *real* inputs where possible, and
  deliberately include hard/edge/adversarial cases (they detect regressions first).
- Split dev (for prompt iteration) from test (touched rarely) — prompt tuning overfits an eval
  set exactly like hyperparameters overfit validation data.
- Version the set; every quality claim cites the set version and date.
- Refresh with production failures: every triaged incident becomes an eval case.

## LLM-as-judge: use with eyes open

Known biases to design around: **self-preference** (judges favor outputs of the same model
family — prefer a different family, or better: pairwise judging with randomized order),
**position bias** (first/last answer favored — randomize order, judge pairs both ways),
**verbosity bias** (longer answers score higher — cap length or instruct explicitly),
**sycophancy toward confident tone**. Always calibrate: score 20–30 items by hand, check
agreement with the judge before trusting it at scale; re-check after changing the judge model
or rubric. Rubrics with concrete anchors ("5 = every claim supported by a citation") beat
"rate quality 1–10".

## Statistical hygiene

Small eval sets have wide error bars: a 2-point gain on 50 examples is noise until repeated
(bootstrap a CI over examples; for generation, also over sampling runs at the same prompt).
Report the operating point (temperature, model ID, prompt version) with every number — an eval
number without its configuration is unreproducible.
