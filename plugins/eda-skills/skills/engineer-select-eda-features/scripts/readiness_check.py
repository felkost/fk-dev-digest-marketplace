"""Final dataset-readiness gate (engineer step 8).

Runs structural / pipeline / statistical checks on the produced dataset and
returns a verdict: ``ready``, ``ready_with_accepted_limitations``, or
``not_ready``. Any high-severity leakage, label, identity, or split defect forces
``not_ready`` and names the smallest corrective experiment.

Core-library only (numpy, pandas).
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd


def run_structural_checks(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    key_cols: Optional[Sequence[str]] = None,
    group: Optional[str] = None,
    expected_columns: Optional[Sequence[str]] = None,
) -> dict:
    """Return a dict of check name -> (passed: bool, evidence: str)."""
    checks: dict[str, tuple[bool, str]] = {}

    if expected_columns is not None:
        missing = set(expected_columns) - set(train_df.columns)
        checks["schema_columns_present"] = (not missing, f"missing={sorted(missing)}")

    checks["columns_match_train_test"] = (
        list(train_df.columns) == list(test_df.columns),
        "train/test column sets differ" if list(train_df.columns) != list(test_df.columns) else "ok",
    )

    if key_cols:
        merged = train_df[list(key_cols)].merge(test_df[list(key_cols)], how="inner")
        n = len(merged)
        checks["no_key_overlap"] = (n == 0, f"{n} shared keys across splits")

    if group:
        overlap = set(train_df[group]) & set(test_df[group])
        checks["no_group_overlap"] = (not overlap, f"{len(overlap)} shared groups")

    # unseen categorical levels in test that never appear in train
    obj_cols = train_df.select_dtypes(include=["object", "category"]).columns
    unseen = {c: sorted(set(test_df[c].dropna()) - set(train_df[c].dropna()))[:5]
              for c in obj_cols if c in test_df}
    unseen = {c: v for c, v in unseen.items() if v}
    checks["unseen_categories_handled"] = (
        len(unseen) == 0, f"unseen levels: {unseen}" if unseen else "none (or handle explicitly)",
    )
    return checks


def label_mapping_consistency(*mappings: dict, names: Optional[Sequence[str]] = None) -> dict:
    """Verify that class->index mappings agree across splits/artifacts.

    Folder-derived mappings (torchvision ``ImageFolder.class_to_idx``) are
    rebuilt per split: a class folder missing from one split silently shifts
    every later index, so the same integer label means different classes in
    train and test -- no error is raised anywhere. Pass each split's mapping
    (and the persisted dataset-card mapping); any difference is a blocker.
    """
    names = list(names) if names else [f"mapping_{i}" for i in range(len(mappings))]
    ref_name, ref = names[0], mappings[0]
    differences = []
    for name, m in zip(names[1:], mappings[1:]):
        missing = sorted(set(ref) - set(m))
        extra = sorted(set(m) - set(ref))
        shifted = sorted(k for k in set(ref) & set(m) if ref[k] != m[k])
        if missing or extra or shifted:
            differences.append({"mapping": name, "vs": ref_name,
                                "missing_classes": missing, "extra_classes": extra,
                                "index_shifted": shifted})
    return {"consistent": not differences, "differences": differences,
            "n_classes_reference": len(ref)}


def readiness_gate(check_results: dict, accepted: Sequence[str] = (),
                   blocking_evidence: Optional[str] = None,
                   corrective_experiment: Optional[str] = None) -> dict:
    """Combine check results into a verdict.

    ``check_results`` maps name -> (passed: bool, evidence: str). Failed checks
    not present in ``accepted`` block readiness.
    """
    passed = [k for k, (ok, _) in check_results.items() if ok]
    failed = [k for k, (ok, _) in check_results.items() if not ok]
    blocking = [k for k in failed if k not in set(accepted)]

    if not failed:
        verdict = "ready"
    elif not blocking:
        verdict = "ready_with_accepted_limitations"
    else:
        verdict = "not_ready"

    return {
        "verdict": verdict,
        "passed": passed,
        "failed": failed,
        "accepted_exceptions": list(accepted),
        "blocking_evidence": blocking_evidence or "; ".join(
            f"{k}: {check_results[k][1]}" for k in blocking
        ) or None,
        "smallest_corrective_experiment": corrective_experiment,
    }


__all__ = ["run_structural_checks", "readiness_gate", "label_mapping_consistency"]
