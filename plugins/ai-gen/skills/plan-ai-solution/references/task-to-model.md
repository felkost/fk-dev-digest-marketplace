# Task-to-model-class decision procedure

The goal is a *justified* class choice, not a name-drop. Walk the signals top-down; the first
strong match wins, but always record the strongest losing alternative and why it lost.

## Signals → class

| Task signal | Likely class | Why |
|---|---|---|
| Output is open-ended text/code/image/audio; instructions vary per request | Generative (LLM/VLM/diffusion) | Only class that produces novel structured output on demand |
| Input includes images/video AND the answer needs language reasoning about them | VLM (vision-language) | Joint embedding + generation; classical CV can't answer "why" |
| Fixed label set over images (defect/no-defect, object present) with training data | Computer vision (CNN/ViT classifier or detector) | Cheaper, faster, deterministic, measurable with standard metrics |
| Tabular rows with engineered features, target column exists | Gradient-boosted trees first | Consistently strong on tabular data; interpretable via importances; trains in minutes |
| Continuous target, few features, need coefficients/inference | Regression (linear/GLM) | Interpretability and statistical inference are the point |
| Explicit time index, forecast horizon, seasonality/trend | Time-series methods (statistical or NN: ARIMA-class, Prophet-class, N-BEATS/TFT-class) | Temporal structure must be modeled, not shuffled away |
| Perception task with huge labeled data and no pretrained fit | Task-specific deep net (CNN/RNN/Transformer trained/fine-tuned) | When transfer from a foundation model underperforms or is disallowed |
| Task is retrieval/matching/similarity, not generation | Encoder (embedding model) + vector search | Generation is unnecessary; embeddings are cheaper and controllable |

## The generative-first trap (and the reverse trap)

- **Trap 1 — LLM for everything.** An LLM classifying tabular churn rows underperforms boosted
  trees, costs orders of magnitude more per row, and is harder to validate. If the task reduces to
  a fixed-schema prediction with training data, classical ML wins by default.
- **Trap 2 — dismissing generative where it belongs.** Extraction from messy documents,
  normalization of free text, few-shot classification with *no* training data, tool-using
  workflows — generative models are the practical choice precisely because labeled data or fixed
  schemas are missing.
- **Hybrid is often the answer**: encoder for retrieval + LLM for synthesis (RAG); LLM to extract
  structure from text + trees on the extracted features; CV detector + VLM for open-ended
  description. Say explicitly which component carries which responsibility.

## Required justification format

1. Recommended class + 2–4 arguments tied to the task statement (not generic virtues).
2. Strongest losing alternative + the specific reason it lost.
3. Risks of the recommendation and a PoC-scale measurement that would confirm/refute it
   *before* full investment (e.g. "50 labeled rows, compare LLM few-shot vs boosted tree").
4. If generative: single-call vs agentic loop (does the task need tools, multi-step state,
   external actions?), which routes the next step to `design-agent-architecture`.

## Questions worth blocking on

Only these justify a clarifying question before recommending (a wrong guess invalidates the whole
recommendation): what decision the output feeds; whether training/eval data exists at all; hard
privacy/deployment constraints (e.g. "no data leaves the premises" excludes hosted APIs);
latency/cost ceilings that exclude whole classes.
