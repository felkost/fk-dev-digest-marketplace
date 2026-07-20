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

## Producing the labels this file demands

The table above asks for "labeled question→passage pairs" and the section above tells you to
build 30–200 examples with expected outcomes. Neither says where labels come from, and for a
private corpus nobody has any. That gap is where most eval sets die, so this section is about
manufacturing labels at a scale a person cannot reach by hand.

The useful framing comes from a systematic review of agent-based annotation (Karim, Khan, Van,
Liu, Wang & Qu, "Transforming Data Annotation with AI Agents", *Future Internet* 2025, 17(8),
353, <https://doi.org/10.3390/fi17080353>, §7), which sorts these systems into a ladder. Climb it
only as far as the quality bar forces you to — each rung multiplies cost.

| Rung | What it is | What it buys | What it costs / how it fails |
|---|---|---|---|
| **1. Single agent** | One model generates labels from the data | Cheapest; adequate for a first eval set | The review notes single-agent setups operate without external feedback — nothing catches a systematic error, so it propagates through the whole set |
| **2. Dual agent** | A generator–reviewer pair: one labels, one critiques, iterating | A second opinion, and a natural place for a rubric | **Confirmation bias when both agents share similar training data**, plus the extra compute (§7.2) |
| **3. Multi-agent, role-based** | Specialized roles coordinating, hierarchically or by negotiation (§7.3) | Coverage of aspects one labeller misses | Coordination overhead and many more calls; worth it only when labels genuinely need different expertise |
| **4. HITL as agent** | Humans as components of the architecture, not a review queue bolted on (§7.4) | The quality ceiling | Human throughput. The review describes CoAnnotating's framing as *dynamic work allocation* between humans and agents — route by uncertainty rather than sending everything to a person |

### Generating retrieval labels specifically

For RAG the cheap trick is that generation runs backwards: sample a chunk, prompt a model to
write a question that chunk answers, and you have a (question, gold passage) pair **for free**,
because you know which chunk produced it.

It has one failure mode that will flatter you badly: a question written from a chunk tends to
reuse the chunk's vocabulary, so lexical overlap alone retrieves it and recall@k looks
excellent. Counter it by instructing the generator to paraphrase away from the source wording,
rejecting questions that quote the chunk, and spot-checking that a BM25-only baseline does *not*
ace your set. Also mark known-equivalent passages: if three chunks answer the question, scoring
against a single gold passage under-reports recall and you will "fix" a retriever that was right.

### The quality-assurance loop

The review's Figure 4 gives a topology worth copying, mostly because it names the step naive
pipelines skip: dataset → **orchestrator** → annotator agent → quality-checker agent → decision
point → *unacceptable labels feed back to the orchestrator for re-annotation, with human
intervention available* → acceptable labels consolidated by an aggregator. The re-annotation
path is the point. A pipeline that only flags bad labels produces a report; one that routes them
back produces a dataset.

### The rule that keeps this honest

**This one is engineering discipline, not a finding from the review, and it is not optional: a
machine-labelled eval set measures the labeller until a human-verified subsample bounds it.**

- Draw a random subsample — 20–30 items is enough to see a problem — and label it by hand,
  blind to the machine's labels.
- Report agreement between your labels and the machine's *alongside* every metric computed on
  the set. Not once at the start: whenever the labelling model or prompt changes.
- If agreement is poor, the eval number describes your annotator, not your system, and every
  decision made from it is unsupported.
- Keep the human-verified subsample as a permanent fixture of the set, versioned with it.

The same separation rule as everywhere else applies to the labeller: if the model producing
labels is the model under test, the eval set is graded homework. Use a different family, and
where that is impossible, say so next to the number.

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
