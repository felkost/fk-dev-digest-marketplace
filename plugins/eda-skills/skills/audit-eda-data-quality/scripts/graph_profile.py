"""Graph / network audit: what is one row, and what is the graph really made of?

Relational data arrives as an edge list, and almost every default assumption
about it is wrong in a way that is cheap to check and expensive to miss:

- **The unit of observation is not the row.** An edge list of `n` nodes holds up
  to `n(n-1)/2` dyads, but the information is carried by the `n` nodes. Rows are
  dependent by construction -- every edge touching node `i` shares whatever `i`
  is. See ``sampling_design.dyadic_design_effect``.
- **Direction is a declaration, not a property of the file.** An undirected
  graph stored as both `(a,b)` and `(b,a)` looks directed, has exactly twice the
  edges it should, and reports half the density it should. The signature is
  reciprocity == 1.0 exactly (``directedness`` below).
- **Isolates are invisible in an edge list.** A node with no edges cannot appear
  in a list of edges, so "how many nodes are there" is unanswerable from the
  edge list alone. This is the relational form of the missing-rows problem in
  ``references/consistency-validity.md``: pass ``nodes=`` when a node table
  exists, and treat the node count as a lower bound when it does not.

What this does NOT do: community detection, centrality as features, or link
prediction. Those are ``discover``/``engineer`` concerns. The audit's job is to
establish what the object is, whether it is intact, and what the split must
respect.

Core stack (numpy, pandas, scipy.sparse). ``networkx`` is optional and only
unlocks assortativity; everything else degrades to a documented ``None``.
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd

# Triangle counting is O(n * d^2)-ish via a sparse matrix cube; above this many
# edges we report `skipped` rather than quietly hanging an audit.
_TRIANGLE_EDGE_CAP = 2_000_000


def _coded(edges: pd.DataFrame, src: str, dst: str,
           nodes: Optional[Iterable] = None):
    """Map node labels to 0..n-1 and return (codes_src, codes_dst, labels)."""
    seen = pd.Index(pd.unique(pd.concat([edges[src], edges[dst]], ignore_index=True)))
    labels = seen if nodes is None else pd.Index(pd.unique(pd.Series(list(nodes)))).union(seen)
    lookup = pd.Series(np.arange(len(labels)), index=labels)
    return (lookup.reindex(edges[src]).to_numpy(),
            lookup.reindex(edges[dst]).to_numpy(),
            labels)


def profile_graph(
    edges: pd.DataFrame,
    src: str = "src",
    dst: str = "dst",
    directed: Optional[bool] = None,
    nodes: Optional[Iterable] = None,
) -> dict:
    """Audit an edge list. ``directed=None`` means "infer and report the evidence".

    Returns a dict with ``n_nodes``/``n_edges``/``density``, integrity counters
    (``self_loops``, ``duplicate_edges``), ``directedness``, ``degree``,
    ``components``, ``transitivity``, and a ``findings`` list of plain-language
    defects to carry into the report.
    """
    from scipy import sparse

    if edges.empty:
        return {"n_edges": 0, "findings": ["edge list is empty"]}

    i, j, labels = _coded(edges, src, dst, nodes)
    n = len(labels)
    m_raw = len(edges)
    findings: list[str] = []

    # ---- integrity -------------------------------------------------------- #
    self_loops = int((i == j).sum())
    pairs = pd.DataFrame({"i": i, "j": j})
    dup_directed = int(m_raw - len(pairs.drop_duplicates()))
    undirected_key = pd.DataFrame({"a": np.minimum(i, j), "b": np.maximum(i, j)})
    dup_undirected = int(m_raw - len(undirected_key.drop_duplicates()))

    # ---- directedness: is this really a directed graph? ------------------- #
    off = pairs[pairs.i != pairs.j]
    if len(off):
        fwd = set(map(tuple, off.to_numpy()))
        reciprocity = float(sum(1 for a, b in fwd if (b, a) in fwd) / len(fwd))
    else:
        reciprocity = float("nan")
    if directed is None:
        inferred = not (np.isfinite(reciprocity) and reciprocity >= 0.999)
    else:
        inferred = directed
    mirrored = bool(np.isfinite(reciprocity) and reciprocity >= 0.999)
    if mirrored and directed is not False:
        findings.append(
            "reciprocity is 1.000 - this is very likely an UNDIRECTED graph stored "
            "as both (a,b) and (b,a): edge count is doubled and density halved"
        )
    if directed is True and np.isfinite(reciprocity) and reciprocity >= 0.999:
        findings.append("declared directed but perfectly reciprocal - confirm the declaration")

    # ---- structure on the simple (deduplicated, loopless) graph ----------- #
    keep = undirected_key.assign(_k=1).drop_duplicates(subset=["a", "b"])
    keep = keep[keep.a != keep.b]
    a, b = keep.a.to_numpy(), keep.b.to_numpy()
    m_simple = len(keep)

    A = sparse.coo_matrix((np.ones(m_simple), (a, b)), shape=(n, n)).tocsr()
    A = A + A.T                                   # symmetric, simple
    A.data[:] = 1.0

    deg = np.asarray(A.sum(axis=1)).ravel()
    n_comp, comp_labels = sparse.csgraph.connected_components(A, directed=False)
    comp_sizes = np.bincount(comp_labels)
    isolates_in_list = int((deg == 0).sum())

    max_dyads = n * (n - 1) / 2
    density = float(m_simple / max_dyads) if max_dyads > 0 else float("nan")

    # ---- transitivity (global clustering coefficient) --------------------- #
    if m_simple <= _TRIANGLE_EDGE_CAP:
        triangles = float((A @ A).multiply(A).sum() / 6.0)
        triples = float((deg * (deg - 1) / 2).sum())
        transitivity = float(3 * triangles / triples) if triples > 0 else float("nan")
    else:
        triangles, transitivity = float("nan"), float("nan")
        findings.append(f"transitivity skipped: {m_simple} edges over the {_TRIANGLE_EDGE_CAP} cap")

    # ---- assortativity (optional) ----------------------------------------- #
    assortativity = None
    try:
        import warnings

        import networkx as nx

        g = nx.Graph()
        g.add_nodes_from(range(n))
        g.add_edges_from(zip(a.tolist(), b.tolist()))
        with warnings.catch_warnings():
            # degenerate degree variance (regular graph) divides by zero -> nan,
            # which is an answer, not something an audit should print a warning about
            warnings.simplefilter("ignore")
            val = float(nx.degree_assortativity_coefficient(g))
        assortativity = val if np.isfinite(val) else None
    except Exception:
        pass                                       # optional dep absent, or graph too small

    # ---- findings --------------------------------------------------------- #
    if self_loops:
        findings.append(f"{self_loops} self-loops - decide explicitly: meaningful or artefact")
    if dup_undirected and not mirrored:
        # when the graph is perfectly mirrored the "duplicates" ARE the mirror; reporting
        # both would state one fact twice and invite deduplicating a correct edge list
        findings.append(
            f"{dup_undirected} duplicate edges (undirected key) - a multigraph, a repeated "
            "measurement, or a join that multiplied rows; they are not automatically a defect"
        )
    if nodes is None:
        findings.append(
            "node count inferred from the edge list: isolates are invisible by construction - "
            "pass nodes= from a node table, or treat n_nodes as a lower bound"
        )
    elif isolates_in_list:
        findings.append(f"{isolates_in_list} isolated nodes carry no edge - keep or drop deliberately")
    if n_comp > 1:
        findings.append(
            f"{n_comp} connected components, largest holds {comp_sizes.max() / n:.1%} of nodes - "
            "a split that ignores components can put a whole component in test"
        )
    if np.isfinite(density) and density > 0.5:
        findings.append(f"density {density:.3f} - unusually dense; confirm this is a real graph, not a join artefact")

    return {
        "n_nodes": int(n),
        "n_edges_raw": int(m_raw),
        "n_edges_simple": int(m_simple),
        "max_dyads": int(max_dyads),
        "density": density,
        "self_loops": self_loops,
        "duplicate_edges": {"directed_key": dup_directed, "undirected_key": dup_undirected},
        "directedness": {
            "declared": directed,
            "inferred_directed": bool(inferred),
            "reciprocity": reciprocity,
            "perfectly_mirrored": mirrored,
        },
        "degree": {
            "mean": float(deg.mean()), "median": float(np.median(deg)),
            "max": int(deg.max()), "p99": float(np.quantile(deg, 0.99)),
            "isolates_in_edge_list": isolates_in_list,
        },
        "components": {
            "count": int(n_comp),
            "largest_share": float(comp_sizes.max() / n),
            "singletons": int((comp_sizes == 1).sum()),
        },
        "transitivity": transitivity,
        "degree_assortativity": assortativity,
        "findings": findings,
    }
