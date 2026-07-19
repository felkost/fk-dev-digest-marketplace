# Python visualization for AI work

Charts in this plugin's scope serve three jobs: eval results, cost/latency profiles, and
embedding-space diagnostics. Pick the library by job, not habit.

## Library choice

| Job | Default | Why |
|---|---|---|
| Static eval/report figures (PNG/SVG into a README or paper) | matplotlib | Universal, scriptable, no runtime dependency in the artifact |
| Statistical views (distributions by group, heatmaps) | seaborn (on matplotlib) | Better defaults for exactly these plot families |
| Interactive exploration (hover = example text, zoom) | plotly | Hovering an embedding point to read its text is the feature |
| Dashboards/demo UI in Python | plotly + Streamlit/Gradio | Fast to ship; not a substitute for the React frontend in production examples |

## The recurring plots

- **Eval comparison**: grouped bars or dot-plots of metric-per-model/prompt-version with
  bootstrap CIs over eval examples — a bar chart without error bars on a 50-example eval
  invites overreading noise. Annotate each figure with eval-set version and model IDs.
- **Quality vs cost frontier**: scatter of eval score (y) vs measured cost per request (x) per
  candidate model; the Pareto edge is the decision, everything below it is dominated.
- **Latency**: histogram or ECDF of total latency with p50/p95 markers; TTFT and total as two
  distributions, not one blended number.
- **Token budgets**: stacked bars input/output tokens per pipeline stage — makes the "where do
  tokens go" conversation concrete.
- **Embedding projections** (UMAP/t-SNE/PCA to 2D): color by label/source/cluster; treat as a
  *hypothesis generator*, not evidence — 2D neighborhoods distort high-dimensional structure,
  so caption what may and may not be concluded. (Deeper structure-discovery rigor lives in the
  eda-skills plugin.)
- **Agent traces**: Gantt-style timeline of tool calls per run (plotly) — the fastest way to
  see serial chains that should be parallel.

## Hygiene

Label axes with units (ms, $, tokens) · log-scale for costs/latencies with heavy tails ·
save figures as files next to the eval manifests they illustrate · one figure = one claim,
stated in the title.
