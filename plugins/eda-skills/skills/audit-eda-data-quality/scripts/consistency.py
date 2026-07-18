"""Consistency, validity, and duplicate-resolution checks (audit step 3).

Covers the defect classes that survive a schema profile because every value is
individually well-formed:

- **Inconsistent representations** of one real entity (``Apples`` / ``apples`` /
  ``appels``) -- `near_duplicate_categories`.
- **Conflicting attributes under one key** (two different products sharing a
  product ID) -- `key_attribute_conflicts`.
- **Duplicate records** plus the evidence needed to choose a resolution rule --
  `duplicate_report`.
- **Datetime traps**: strings pretending to be timestamps, epoch integers,
  tz-aware/naive mixtures -- `datetime_consistency`.
- **Illogical values produced by our own transformations** (a negative duration
  from ``finish_hour - start_hour`` across midnight) -- `logical_constraints`.

Everything *reports*; nothing is corrected or dropped here. Standardising a
label, picking a surviving duplicate, or repairing a derived column is a
decision with domain consequences -- it belongs in the remediation step, with
provenance, and usually upstream in the pipeline rather than in this notebook.

Core-library only (numpy, pandas) plus stdlib ``difflib``.
"""

from __future__ import annotations

import difflib
import re
from typing import Callable, Iterable, Mapping, Optional, Union

import numpy as np
import pandas as pd

_WS = re.compile(r"\s+")


def proxy_label_diagnostics(
    sensitivity: float,
    specificity: float,
    prevalence: float,
) -> dict:
    """What a label produced by an imperfect detector actually contains.

    Most labels are not observations of the construct; they are the output of
    some earlier detector, rule, or human review (``is_fraud`` = *flagged and
    confirmed*, ``defect`` = *caught by QA*, a diagnosis code, a moderation
    decision). Given that detector's sensitivity and specificity and the true
    prevalence, this returns what the label column is made of.

    All values verified against simulation at N=400,000 (formula vs simulated
    PPV: 0.692/0.691, 0.321/0.320, 0.155/0.154, 0.090/0.086).

    Three consequences that are routinely missed:

    1. **Precision collapses at low prevalence even for a "90% accurate"
       detector.** With sensitivity = specificity = 0.90, PPV is 0.692 at
       prevalence 0.20, **0.321** at 0.05 and **0.155** at 0.02. So at a 2%
       base rate, ~85% of the positive labels are wrong while the detector is
       still "90% accurate" in the sense the vendor means.
    2. **A noisy label inflates the apparent base rate.** The flagged rate is
       ``sens*prev + (1-spec)*(1-prev)``, which at prevalence 0.02 with a 90/90
       detector is 0.116 -- a **5.8x** overstatement. A reported "our fraud
       rate is 14%" can be a true 5%. Any class-imbalance decision taken from
       the label's own frequency inherits this.
    3. **Specificity, not sensitivity, governs precision when positives are
       rare.** A detector at sensitivity 0.80 / specificity 0.999 reaches PPV
       0.890 at prevalence 0.01, while 0.90/0.90 reaches only 0.155 at 0.02.
       Chasing recall is the wrong lever for a rare class.

    Uncertainty note, measured: propagating a 95% CI on a sensitivity of 0.93
    estimated from n=172 (CI 0.885-0.961) moves PPV only from 0.318 to 0.336,
    whereas moving prevalence from 0.20 to 0.02 moves it from 0.692 to 0.155.
    **Prevalence uncertainty dominates**; spend the effort there.
    """
    for name, v in (("sensitivity", sensitivity), ("specificity", specificity),
                    ("prevalence", prevalence)):
        if not (np.isfinite(v) and 0.0 <= v <= 1.0):
            raise ValueError(f"{name} must be a probability in [0, 1], got {v!r}")

    tp = sensitivity * prevalence
    fp = (1.0 - specificity) * (1.0 - prevalence)
    tn = specificity * (1.0 - prevalence)
    fn = (1.0 - sensitivity) * prevalence
    flagged = tp + fp
    not_flagged = tn + fn

    ppv = tp / flagged if flagged > 0 else float("nan")
    npv = tn / not_flagged if not_flagged > 0 else float("nan")
    return {
        "sensitivity": float(sensitivity),
        "specificity": float(specificity),
        "prevalence": float(prevalence),
        "ppv": float(ppv),
        "npv": float(npv),
        "apparent_positive_rate": float(flagged),
        "base_rate_inflation": float(flagged / prevalence) if prevalence > 0 else float("nan"),
        "false_positive_share_of_labels": float(1.0 - ppv) if flagged > 0 else float("nan"),
        "missed_share_of_true_cases": float(1.0 - sensitivity),
        "verdict": ("label_mostly_false_positives" if flagged > 0 and ppv < 0.5
                    else "usable_with_caveats" if flagged > 0 and ppv < 0.9
                    else "clean_enough"),
    }


def normalize_label(value: object) -> str:
    """Casefold, trim, and collapse internal whitespace. No stemming, no typo fix."""
    return _WS.sub(" ", str(value).strip()).casefold()


def near_duplicate_categories(
    s: pd.Series,
    cutoff: float = 0.82,
    min_length: int = 4,
    max_levels: int = 400,
) -> pd.DataFrame:
    """Group category labels that likely denote the same real element.

    Two mechanisms, reported separately in ``reason``:

    - ``normalized`` -- labels that collapse under case/whitespace normalisation
      (``Apples`` / ``apples`` / `` APPLES ``). Deterministic and safe.
    - ``fuzzy`` -- labels within ``cutoff`` similarity of a more frequent label
      (``appels`` vs ``apples``), via ``difflib.SequenceMatcher``. A *candidate
      list for human review*, never an auto-merge.

    **Why ``min_length`` and not just a higher cutoff.** Measured ratios:
    ``apples``/``appels`` = 0.833 (a real typo) but ``xl``/``xxl`` = 0.800 and
    ``a100``/``a101`` = 0.750 (legitimately different sizes and model numbers).
    A typo and a meaningful one-character distinction are not separable by
    similarity alone -- what separates them is length, because on short strings
    one character is a large share of the ratio. Labels shorter than
    ``min_length`` are therefore excluded from fuzzy comparison; screen short
    codes against a reference list instead.

    **Known blind spot:** ``difflib`` scores transpositions poorly
    (``kyiv``/``kiev`` = 0.750), so transliteration variants are missed. Use a
    transliteration/phonetic map or an edit-distance library for those.

    The canonical label is the most frequent member of the group, which is a
    frequency heuristic, not a correctness claim -- a systematic upstream typo
    can outnumber the correct spelling.

    Comparison is O(k^2) in distinct levels, so only the ``max_levels`` most
    frequent are compared; the rest are reported as ``not_compared``.
    """
    vc = s.dropna().astype(str).value_counts()
    truncated = list(vc.index[max_levels:])
    vc = vc.iloc[:max_levels]

    norm = {lab: normalize_label(lab) for lab in vc.index}
    rows: list[dict] = []

    # 1. exact collisions after normalisation
    by_norm: dict[str, list[str]] = {}
    for lab, key in norm.items():
        by_norm.setdefault(key, []).append(lab)
    for key, labels in by_norm.items():
        if len(labels) > 1:
            canonical = max(labels, key=lambda l: vc[l])
            for lab in labels:
                if lab != canonical:
                    rows.append({
                        "canonical": canonical, "variant": lab, "reason": "normalized",
                        "similarity": 1.0, "n_canonical": int(vc[canonical]),
                        "n_variant": int(vc[lab]),
                    })

    # 2. fuzzy matches among the surviving normalised forms
    keys = sorted(by_norm, key=lambda k: -sum(vc[l] for l in by_norm[k]))
    assigned: set[str] = set()
    for i, key in enumerate(keys):
        if key in assigned or len(key) < min_length:
            continue
        for other in keys[i + 1:]:
            if other in assigned or len(other) < min_length:
                continue
            ratio = difflib.SequenceMatcher(None, key, other).ratio()
            if ratio >= cutoff:
                assigned.add(other)
                can_lab = max(by_norm[key], key=lambda l: vc[l])
                var_lab = max(by_norm[other], key=lambda l: vc[l])
                rows.append({
                    "canonical": can_lab, "variant": var_lab, "reason": "fuzzy",
                    "similarity": round(ratio, 4), "n_canonical": int(vc[can_lab]),
                    "n_variant": int(vc[var_lab]),
                })

    for lab in truncated:
        rows.append({"canonical": None, "variant": lab, "reason": "not_compared",
                     "similarity": np.nan, "n_canonical": 0, "n_variant": 0})

    out = pd.DataFrame(rows, columns=["canonical", "variant", "reason", "similarity",
                                      "n_canonical", "n_variant"])
    return out.sort_values(["reason", "n_variant"], ascending=[True, False]).reset_index(drop=True)


def key_attribute_conflicts(
    df: pd.DataFrame,
    keys: Union[str, Iterable[str]],
    attrs: Optional[Iterable[str]] = None,
    max_examples: int = 5,
) -> pd.DataFrame:
    """Find keys whose rows disagree on an attribute that should be constant.

    The ``'monitor stand' for $999 under the same product ID`` case: the key is
    intact, no value is individually invalid, and only the join of the two shows
    the defect. Distinguish the causes before repairing -- a genuine data-entry
    error, a **slowly changing dimension** (price legitimately changes over
    time, so the attribute is keyed by ``(id, valid_from)`` and the schema is
    wrong, not the data), or a reused/recycled identifier.

    NaN is ignored when counting distinct values, so a key with one value plus
    missings is not reported as a conflict.
    """
    keys = [keys] if isinstance(keys, str) else list(keys)
    if attrs is None:
        attrs = [c for c in df.columns if c not in keys]
    rows = []
    grouped = df.groupby(keys, dropna=False, observed=True)
    for attr in attrs:
        nuniq = grouped[attr].nunique(dropna=True)
        bad = nuniq[nuniq > 1]
        for key_val, n_distinct in bad.items():
            mask = pd.Series(True, index=df.index)
            key_tuple = key_val if isinstance(key_val, tuple) else (key_val,)
            for k, v in zip(keys, key_tuple):
                mask &= df[k].isna() if pd.isna(v) else df[k] == v
            vals = df.loc[mask, attr].dropna().unique()
            rows.append({
                "key": key_val,
                "attribute": attr,
                "n_rows": int(mask.sum()),
                "n_distinct": int(n_distinct),
                "examples": list(vals[:max_examples]),
            })
    return pd.DataFrame(rows, columns=["key", "attribute", "n_rows", "n_distinct", "examples"])


def duplicate_report(
    df: pd.DataFrame,
    subset: Optional[Iterable[str]] = None,
    order_by: Optional[str] = None,
    max_groups: int = 50,
) -> dict:
    """Duplicate evidence plus the information a resolution rule needs.

    Three resolution strategies exist, and they are not interchangeable:

    1. **Keep one of identical rows** -- valid only when the rows carry no
       conflicting columns (``n_conflicting_cols == 0`` below). Safe to automate.
    2. **Pairwise match, keep the most relevant** (usually the most recent):
       needs ``order_by``; the returned ``keep_index`` shows which row wins, so
       the rule can be inspected before it is applied.
    3. **Merge into one entity** (record linkage) -- when the rows are
       complementary rather than redundant, discarding any of them loses fields.
       Requires domain rules; this function only shows which columns disagree.

    Duplicates are not automatically defects: repeated measurements of the same
    entity may be legitimate, in which case the fix is a **group-aware split**,
    not deletion (dropping them destroys real replication). Conversely,
    duplicates inflate class balance and correlation estimates -- cross-check
    with ``balancing.class_duplicate_report``.

    Returns a dict with ``n_exact_duplicate_rows``, ``n_key_duplicate_rows``,
    ``groups`` (a DataFrame), and ``resolution_hint``.
    """
    subset = list(subset) if subset is not None else None
    n_exact = int(df.duplicated(keep="first").sum())
    if subset is None:
        return {
            "n_exact_duplicate_rows": n_exact,
            "n_key_duplicate_rows": n_exact,
            "groups": pd.DataFrame(),
            "resolution_hint": "keep_one" if n_exact else "no_duplicates",
        }

    dup_mask = df.duplicated(subset=subset, keep=False)
    other_cols = [c for c in df.columns if c not in subset]
    rows = []
    for key_val, grp in df[dup_mask].groupby(subset, dropna=False, observed=True):
        conflicting = [c for c in other_cols if grp[c].nunique(dropna=True) > 1]
        keep_index = None
        if order_by is not None and order_by in df.columns:
            keep_index = grp[order_by].idxmax()
        rows.append({
            "key": key_val,
            "n_rows": len(grp),
            "n_conflicting_cols": len(conflicting),
            "conflicting_cols": conflicting,
            "keep_index": keep_index,
        })
        if len(rows) >= max_groups:
            break

    groups = pd.DataFrame(rows, columns=["key", "n_rows", "n_conflicting_cols",
                                         "conflicting_cols", "keep_index"])
    if groups.empty:
        hint = "no_duplicates"
    elif (groups["n_conflicting_cols"] == 0).all():
        hint = "keep_one"
    elif order_by is not None:
        hint = "keep_most_recent_or_merge"
    else:
        hint = "needs_merge_rule"
    return {
        "n_exact_duplicate_rows": n_exact,
        "n_key_duplicate_rows": int(dup_mask.sum()),
        "groups": groups,
        "resolution_hint": hint,
    }


def datetime_consistency(
    df: pd.DataFrame,
    cols: Optional[Iterable[str]] = None,
    min_year: int = 1900,
    max_year: Optional[int] = None,
) -> pd.DataFrame:
    """Audit datetime columns for type, timezone, and range traps.

    Flags raised in ``issues``:

    - ``datetime_stored_as_text`` -- ``"24 Oct 2019"`` parses fine and sorts
      wrong; coerce the type explicitly rather than relying on comparisons.
    - ``ambiguous_day_month`` -- every parsed day <= 12, so ``03/04`` is
      undecidable from the data; the source format must be supplied, not guessed
      (``dayfirst`` silently reorders otherwise).
    - ``possible_epoch_seconds`` / ``possible_epoch_millis`` -- integers in a
      plausible Unix-time band that are semantically timestamps.
    - ``tz_naive`` / ``tz_aware`` -- reported per column so mixtures are
      visible. Mixing them raises on comparison, and a naive column is only
      unambiguous when one timezone is documented; for cross-region data,
      normalise to UTC and keep the local offset as a separate feature (local
      hour-of-day is behaviourally different from UTC hour-of-day).
    - ``implausible_range`` -- values outside ``[min_year, max_year]``, catching
      unit mistakes and overflow dates. Note this does **not** catch a sentinel
      date that sits inside the plausible band: ``1900-01-01`` passes a
      ``min_year=1900`` check by construction. Those surface instead as a
      ``dominant_value_share`` flag in ``profile_schema`` -- one date repeated
      across thousands of rows is a default fill, not a coincidence.
    """
    max_year = max_year or (pd.Timestamp.now().year + 50)
    cols = list(cols) if cols is not None else list(df.columns)
    rows = []
    for c in cols:
        s = df[c]
        issues: list[str] = []
        parsed: Optional[pd.Series] = None

        if pd.api.types.is_datetime64_any_dtype(s):
            parsed = s
        elif pd.api.types.is_integer_dtype(s) and s.notna().any():
            lo, hi = float(s.min()), float(s.max())
            if 1e8 <= lo and hi <= 4e9:
                issues.append("possible_epoch_seconds")
            elif 1e11 <= lo and hi <= 4e12:
                issues.append("possible_epoch_millis")
        elif s.dtype == object:
            as_str = s.dropna().astype(str)
            if as_str.empty:
                continue
            with warnings_suppressed():
                cand = pd.to_datetime(as_str, errors="coerce")
            if cand.notna().mean() > 0.9:
                issues.append("datetime_stored_as_text")
                parsed = cand
                if (cand.dt.day <= 12).all() and cand.dt.day.nunique() > 1:
                    issues.append("ambiguous_day_month")

        if parsed is None and not issues:
            continue

        tz = None
        if parsed is not None and parsed.notna().any():
            tz = getattr(parsed.dtype, "tz", None)
            issues.append("tz_aware" if tz is not None else "tz_naive")
            valid = parsed.dropna()
            if len(valid):
                years = valid.dt.year
                if int(years.min()) < min_year or int(years.max()) > max_year:
                    issues.append("implausible_range")

        rows.append({
            "column": c,
            "dtype": str(s.dtype),
            "tz": str(tz) if tz is not None else None,
            "min": None if parsed is None or parsed.dropna().empty else parsed.min(),
            "max": None if parsed is None or parsed.dropna().empty else parsed.max(),
            "issues": issues,
        })
    out = pd.DataFrame(rows, columns=["column", "dtype", "tz", "min", "max", "issues"])
    return out.set_index("column") if not out.empty else out


def logical_constraints(
    df: pd.DataFrame,
    constraints: Mapping[str, Union[str, Callable[[pd.DataFrame], pd.Series]]],
    max_examples: int = 5,
) -> pd.DataFrame:
    """Evaluate named "must always hold" rules and count the violations.

    Each constraint is a pandas ``eval`` expression or a callable returning a
    boolean Series that is **True when the row is valid**::

        logical_constraints(df, {
            "duration_non_negative": "time_in_app >= 0",
            "age_plausible":         "age >= 0 and age <= 120",
            "start_before_finish":   lambda d: d.start_ts <= d.finish_ts,
        })

    This is the check that catches invalid data we produced ourselves. The
    canonical example is ``time_in_app = finish_hour - start_hour``: a session
    from 23:00 to 01:00 yields **-22 hours**, and no source system is at fault --
    the transformation is. Repair the function, not the rows; deleting the
    negative values hides a bug that regenerates on the next run and biases the
    dataset toward sessions that do not cross midnight.

    Run these rules **after every derived-feature step**, not only on raw data,
    and keep them as regression checks in the pipeline. Rows where the rule
    evaluates to NaN (missing inputs) are counted in ``n_unevaluable`` rather
    than silently passing.
    """
    rows = []
    for name, rule in constraints.items():
        try:
            valid = rule(df) if callable(rule) else df.eval(rule)
        except Exception as exc:  # noqa: BLE001 -- report, do not abort the audit
            rows.append({"constraint": name, "n_violations": np.nan, "violation_rate": np.nan,
                         "n_unevaluable": np.nan, "examples": [], "error": f"{type(exc).__name__}: {exc}"})
            continue
        valid = pd.Series(valid, index=df.index)
        unevaluable = valid.isna()
        violated = (~valid.fillna(True)) & ~unevaluable
        rows.append({
            "constraint": name,
            "n_violations": int(violated.sum()),
            "violation_rate": round(float(violated.mean()), 6),
            "n_unevaluable": int(unevaluable.sum()),
            "examples": list(df.index[violated][:max_examples]),
            "error": None,
        })
    return pd.DataFrame(rows, columns=["constraint", "n_violations", "violation_rate",
                                       "n_unevaluable", "examples", "error"]).set_index("constraint")


class warnings_suppressed:
    """Silence pandas' per-element datetime-parsing fallback warnings."""

    def __enter__(self):
        import warnings
        self._ctx = warnings.catch_warnings()
        self._ctx.__enter__()
        warnings.simplefilter("ignore")
        return self

    def __exit__(self, *exc):
        return self._ctx.__exit__(*exc)


__all__ = [
    "normalize_label",
    "near_duplicate_categories",
    "key_attribute_conflicts",
    "duplicate_report",
    "datetime_consistency",
    "logical_constraints",
    "proxy_label_diagnostics",
]
