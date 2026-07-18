"""Semantic schema profiling (audit step 2).

Infer a *role* per column (not just the storage dtype) and flag mixed types,
numeric-coded categories, sentinel values, and whitespace/case variants. Nothing
here mutates data or drops rows -- it produces evidence for remediation.

Core-library only (numpy, pandas).
"""

from __future__ import annotations

import re
import warnings
from typing import Iterable, Optional

import numpy as np
import pandas as pd

SENTINELS = {
    "", "na", "n/a", "n.a.", "n\\a", "nan", "none", "null", "nil", "unknown", "unk",
    "?", "-", "--", "missing", "not applicable", "not available",
    # Excel / DB / export dialects -- these survive when data does not arrive
    # via read_csv (Excel, JSON, database drivers), whose own na_values list
    # would have converted them already.
    "#na", "#n/a", "#n/a n/a", "<na>", "<null>", "(null)", "undefined", "void",
}
NUMERIC_SENTINELS = {-1, -9, -99, -999, -9999, 9999, 99999}

# Byte sequences that appear when UTF-8 text is decoded as latin-1/cp1252 (or
# the reverse), plus the Unicode replacement character. A single occurrence is
# enough to suspect an encoding mismatch upstream.
MOJIBAKE_MARKERS = ("�", "Ã¢", "Ã©", "Ã¨", "Ã¯", "Ã¼", "Ã¶", "Ã±", "â€™",
                    "â€œ", "â€\x9d", "â€“", "Ð¾", "Ð°", "Ñ\x80", "ï»¿")


def infer_semantic_role(s: pd.Series, id_hint: bool = False) -> str:
    """Return a coarse semantic role for a column."""
    non_null = s.dropna()
    n = len(non_null)
    if n == 0:
        return "empty"
    nunique = int(non_null.nunique())

    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if pd.api.types.is_bool_dtype(s) or nunique <= 2:
        return "binary"
    if pd.api.types.is_numeric_dtype(s):
        frac_unique = nunique / n
        if id_hint or (pd.api.types.is_integer_dtype(s) and frac_unique > 0.98):
            return "identifier"
        if pd.api.types.is_integer_dtype(s) and non_null.min() >= 0 and nunique < 100:
            return "count"
        return "continuous"

    # object / string columns
    as_str = non_null.astype(str)
    # datetime disguised as text (only worth trying on date-looking strings)
    if as_str.str.contains(r"\d{1,4}[-/.:]\d", regex=True).mean() > 0.5:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(as_str, errors="coerce")
        if parsed.notna().mean() > 0.9:
            return "datetime_text"
    # multi-label / list-like cells
    if as_str.str.contains(r"[;,|]").mean() > 0.3 or as_str.str.match(r"^\s*[\(\[].*[\)\]]\s*$").mean() > 0.3:
        return "multi_label_or_list"
    avg_len = as_str.str.len().mean()
    if avg_len > 40 or (nunique / n > 0.8 and avg_len > 15):
        return "free_text"
    return "nominal"


def count_non_finite(s: pd.Series) -> int:
    """Number of +/-inf values. ``pd.isna`` does NOT count these as missing.

    An inf slips through every missing-rate report as "0% missing" and then
    silently turns mean/std/quantiles into NaN, so it is flagged separately.
    """
    if not pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
        return 0
    with np.errstate(invalid="ignore"):
        return int(np.isinf(s.to_numpy(dtype="float64", na_value=np.nan)).sum())


def detect_issues(s: pd.Series, dominant_threshold: float = 0.5) -> list[str]:
    """Flag mixed types, numeric-coded categories, sentinels, case/space variants.

    ``dominant_threshold``: share above which a single repeated value is
    reported as a placeholder-default candidate (an upstream system writing a
    constant instead of a missing marker: ``email@company.com``, ``1900-01-01``,
    ``0``). It is a prompt to check provenance, not a defect by itself.
    """
    issues: list[str] = []
    non_null = s.dropna()
    if len(non_null) == 0:
        return ["all_missing"]

    n_inf = count_non_finite(s)
    if n_inf:
        issues.append(f"non_finite_values:{n_inf}")

    # A constant column carries no information; a near-constant one is often an
    # upstream default written in place of a missing value.
    vc = non_null.value_counts()
    if vc.size == 1:
        issues.append("constant_value")
    elif len(non_null) >= 10 and float(vc.iloc[0]) / len(non_null) >= dominant_threshold:
        issues.append(f"dominant_value_share:{round(float(vc.iloc[0]) / len(non_null), 3)}")

    if s.dtype == object:
        types = non_null.map(type).nunique()
        if types > 1:
            issues.append("mixed_python_types")
        as_str = non_null.astype(str)
        low = as_str.str.strip().str.lower()
        if low.isin(SENTINELS).any():
            issues.append("string_sentinels")
        # numbers stored as text
        coerced = pd.to_numeric(as_str, errors="coerce")
        if coerced.notna().mean() > 0.95:
            issues.append("numeric_stored_as_text")
        # whitespace / case collapse
        if low.nunique() < as_str.nunique():
            issues.append("case_or_whitespace_variants")
        # decoding mismatch upstream (UTF-8 read as latin-1/cp1252 or reverse)
        if as_str.str.contains("|".join(map(re.escape, MOJIBAKE_MARKERS)), regex=True).any():
            issues.append("encoding_artifacts")
        # embedded newlines/tabs break CSV round-trips and token counts
        if as_str.str.contains(r"[\r\n\t]", regex=True).any():
            issues.append("embedded_newlines_or_tabs")

    if pd.api.types.is_numeric_dtype(s):
        finite = non_null[np.isfinite(non_null.to_numpy(dtype="float64", na_value=np.nan))]
        vals = set(np.unique(finite.values)) & NUMERIC_SENTINELS if len(finite) else set()
        if vals:
            issues.append(f"possible_numeric_sentinels:{sorted(vals)}")
        # small integer set that is really a category code
        if pd.api.types.is_integer_dtype(s) and non_null.nunique() <= 15 and non_null.min() >= 0:
            issues.append("integer_may_be_category_code")
    return issues


def profile_schema(
    df: pd.DataFrame,
    target: Optional[str] = None,
    id_columns: Iterable[str] = (),
) -> pd.DataFrame:
    """Build a per-column semantic schema table.

    Returns a DataFrame indexed by column with role, dtype, missingness,
    ``n_inf`` (reported apart from ``n_missing``, which never counts inf),
    cardinality, an example value, and a list of detected issues.
    """
    id_columns = set(id_columns)
    rows = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        non_null = s.dropna()
        role = infer_semantic_role(s, id_hint=col in id_columns)
        if col == target:
            role = f"target/{role}"
        rows.append(
            {
                "column": col,
                "role": role,
                "dtype": str(s.dtype),
                "n_missing": int(s.isna().sum()),
                "missing_rate": round(float(s.isna().mean()), 4) if n else 0.0,
                "n_inf": count_non_finite(s),
                "n_unique": int(non_null.nunique()),
                "example": None if non_null.empty else non_null.iloc[0],
                "issues": detect_issues(s),
            }
        )
    return pd.DataFrame(rows).set_index("column")


__all__ = [
    "infer_semantic_role",
    "detect_issues",
    "count_non_finite",
    "profile_schema",
    "SENTINELS",
    "MOJIBAKE_MARKERS",
]
