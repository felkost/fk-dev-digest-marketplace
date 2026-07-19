# Graph / network EDA

Relational data follows the same leakage-safe discipline as the rest of the
skills; what changes is that **the row is not the observation**. The deliverable
is a validated relational dataset + manifests, not a trained link predictor.

Read the data model first — it changes what must be checked:

- **Social / interaction** — actors and ties (advice, friendship, messages).
  Ties may be directed and are usually not reciprocal.
- **Bipartite / user-item** — two node types, edges only across them; degree
  and transitivity mean different things here (transitivity is 0 by
  construction).
- **Transaction / flow** — directed, weighted, timestamped; combine with
  `discover-eda-structure/references/time-series.md`.
- **Knowledge / heterogeneous** — typed nodes and typed edges; every check below
  applies per edge type, not pooled.
- **Derived similarity graph** — edges created by thresholding a distance. This
  is a *modelling decision that manufactured the graph*, not observed data: the
  threshold is a hyperparameter and must be chosen on train only. Every
  structural finding below is conditional on it.

## 1. What is one row? (audit)

- Name the unit explicitly: **node**, **dyad** (unordered pair), **directed
  edge**, or **edge-at-time**. A node table and an edge table answer different
  questions and need different splits.
- An edge list on `n` nodes spans `n(n-1)/2` possible dyads, but the information
  is carried by the `n` nodes. Row count is not sample size here by a wide
  margin — §4 measures the gap.
- Node attributes joined onto an edge table are duplicated across every incident
  edge. Any statistic over that column is a node statistic counted `degree`
  times; weight by `1/degree` or aggregate to the node level first.

## 2. Edge-list integrity (audit) — `graph_profile.profile_graph`

- **Self-loops:** meaningful (a retweet of one's own post) or an artefact of a
  join. Decide explicitly; never drop silently.
- **Duplicate edges:** a multigraph (three payments between the same pair), a
  repeated measurement, or a join that multiplied rows. Not automatically a
  defect — the same distinction as `duplicate_report` in
  `references/consistency-validity.md`.
- **Direction is a declaration, not a property of the file.** An undirected
  graph stored as both `(a,b)` and `(b,a)` is the most common silent defect:
  measured on a mirrored 300-node graph, the profile read **1752 raw edges for
  876 real ones**, i.e. every degree doubled and every density halved. The
  signature is reciprocity `1.000` exactly, which `profile_graph` flags.
- **Isolates are invisible in an edge list.** A node with no edges cannot appear
  in a list of edges, so node count from an edge list is a *lower bound*. This
  is the relational form of "the rows that are missing entirely" in
  `references/consistency-validity.md`: pass `nodes=` from a node table, or say
  in the report that isolates were unobservable.
- **Components:** a graph that is one giant component plus a dust of singletons
  behaves nothing like a connected one, and a split that ignores components can
  place an entire component in test.

## 3. Dependence: how many independent observations? (audit) — critical

`sampling_design.dyadic_design_effect` estimates this with a delete-one-**node**
jackknife (deleting rows would assume the independence that is missing).

Measured on a design with known dependence (dyad value `= z_i + z_j + noise`,
Erdős–Rényi graph, 400 replicates, truth `E[y] = 0`):

| nodes | edges | true deff | jackknife deff | n_eff | n_eff / nodes | coverage of a nominal 95% CI |
|---|---|---|---|---|---|---|
| 100 | 473 | 7.03 | 8.12 | 58 | 0.58 | **0.550** |
| 200 | 1 972 | 14.80 | 14.93 | 132 | 0.66 | **0.372** |
| 400 | 3 976 | 14.46 | 15.16 | 262 | 0.66 | **0.400** |
| 800 | 9 505 | 15.40 | 17.84 | 533 | 0.67 | **0.350** |

Three things to carry out of that table:

- A "95%" interval computed on the edge table covers the truth **35–55%** of the
  time. This is the dyadic sibling of the clustered-rows result in
  `references/sampling-design.md` (48.8% at ICC 0.30), and it propagates to
  every bootstrap, p-value, χ² and PSI reliability guard downstream.
- `n_eff` lands at **≈ 0.6 × the node count**, not the edge count: 9 505 edges
  carried the precision of ~533 observations. Effective sample size scales with
  nodes, so collecting more edges among the same actors buys far less than it
  appears to.
- The jackknife tracks the truth within ~15% and errs **high** (conservative) at
  the extremes of the range tested. Read it as a corrected order of magnitude,
  not a fourth decimal.

## 4. Leakage and split design (audit) — critical — `split_designer.graph_split`

A random split of *edges* is not automatically wrong. It answers a different
question from a split of *nodes*, and the actual error is not knowing which one
was answered.

- **`transductive`** — hold out edges, every node stays visible. Answers *"a new
  link appears among actors we already know"* (friend recommendation, a new
  transaction between existing accounts). Node-level features legitimately see
  both endpoints of every test edge; that is the assumption, and it is only
  valid if deployment also scores known nodes. How non-new the test set is,
  measured over 20 random 1 200-node graphs at densities 0.005 / 0.01 / 0.05:
  both endpoints of a test edge already appear in train for **98.2% / 100.0% /
  100.0%** of test edges on average (worst single graph 96.6% / 99.9% / 100.0%).
  The test set is not a set of unseen entities and must never be described as
  one.
- **`inductive`** — hold out whole nodes; both endpoints of a test edge are
  unseen. Answers *"a new user/device/account arrives"*. The only honest setting
  when the model must generalise to new entities.

**The arithmetic that surprises everyone.** Hold out a fraction `q` of nodes and
the edges divide as `(1-q)²` train, `q²` test, `2q(1-q)` cross-boundary. Cross
edges have one endpoint on each side, answer neither question, and are dropped.
Measured against prediction on a 1 200-node graph:

| `q` (nodes held out) | train edges | test edges | dropped |
|---|---|---|---|
| 0.10 | 0.812 | 0.011 | 0.178 |
| 0.20 | 0.642 | **0.040** | **0.318** |
| 0.30 | 0.485 | 0.100 | 0.415 |
| 0.447 | 0.306 | **0.199** | **0.495** |

So holding out a fifth of the nodes yields a test set of 4% of the edges while
discarding a third of them, and reaching a 20% edge test share costs ~45% of
nodes and ~half the edges. Budget for this before promising a test-set size.

Also:

- **Temporal graphs:** split edges chronologically, not randomly, and apply
  `purge_and_embargo` when the label spans a forward window. "Predict the link
  we already saw form" is the graph form of look-ahead.
- **Bipartite:** decide which side is held out — new users, new items, or both
  (the strictest and usually the realistic one).
- **Derived similarity graphs:** the distance threshold is fitted, so it must be
  fitted on train only; a threshold chosen on the full data has already seen
  test relationships.

## 5. Graph features — fit on the training graph only (engineer)

The single most common leak in this modality: **a node's degree, centrality or
embedding computed on the full graph counts its test edges**. It is the exact
analogue of fitting a scaler on all data, and it is invisible to every
row-level check because no column looks wrong.

- Degree, betweenness, PageRank, k-core, community id: compute on the **training
  graph** and carry the mapping forward; unseen nodes need a documented fallback.
- Neighbourhood target statistics ("share of my neighbours who churned") are
  target encoding over a graph — OOF only, and note that a neighbour's label may
  post-date the prediction moment.
- Node embeddings (node2vec, GNN encoders): fit on the training graph, as a
  diagnostic probe. In `transductive` mode the embedding may see test *edges*
  only if the declared deployment question allows it — write which choice was
  made into the manifest.
- Triangle/transitivity features inherit the direction declaration from §2: on a
  mirrored edge list they are computed on a doubled graph.

## 6. Scale and honest limits

- Methods validated on 100–200-node networks do not merely get slower at 2M
  nodes — several answer a different question. Say which regime a finding came
  from.
- Network model goodness-of-fit is genuinely weak compared with, say, SEM: for
  the common latent-space and ERGM families the practical check is a posterior
  predictive comparison of a few chosen statistics, and there is little
  established science on *which* statistics. State this rather than implying the
  fit was validated.
- Communities are clusters and inherit every caution in
  `discover-eda-structure/references/clustering-reduction.md`, including the
  naming discipline in `plan-eda-dataset/references/mentoring.md`: a detected
  community is `community 7` until something outside the graph supports a name.
- Interference: when an intervention propagates along edges, units are not
  independently treated and the usual effect estimates do not apply. Flag it;
  it is a design problem, not a data-cleaning one.

## 7. Readiness

Readiness fails on: undeclared or mis-inferred direction; degree/centrality/
embeddings computed on the full graph; a `transductive` split reported as
generalisation to new entities; any interval, p-value or minimum-rows guard that
used the edge count as `n`; a derived similarity threshold fitted on all data.

## Per-task quick emphasis

| Data model | Extra must-checks |
|---|---|
| Social / interaction | direction declaration, reciprocity, node-disjoint split for new actors |
| Bipartite / user-item | which side is held out, transitivity is 0 by construction, cold-start = inductive |
| Transaction / flow | chronological edge split + purge, multi-edges are real, weights skewed |
| Knowledge / heterogeneous | every check per edge type; never pool degree across types |
| Derived similarity | threshold fitted on train only; all structure is conditional on it |
