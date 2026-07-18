"""Shared handoff schema for the four EDA skills.

These dataclasses are the *contract* passed between the orchestrator
(``plan-eda-dataset``) and the three stage skills (``audit-eda-data-quality``,
``discover-eda-structure``, ``engineer-select-eda-features``). They are the
manifests listed in ``references/output-contract.md``.

Design notes
------------
- Standard-library only (``dataclasses`` + ``json``), so any skill can emit or
  read a manifest without importing another skill's ``scripts/`` package. The
  utilities in the stage skills accept and return plain ``dict`` shapes that
  match these dataclasses, which keeps the four skills interconnected without
  hard import coupling.
- Everything is JSON-serialisable. Use :func:`to_dict` / :func:`save_manifests`.

This module records decisions and evidence. It does not train models, tune
hyper-parameters, or report a test metric as an EDA result.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------- #
# Vocabularies
# --------------------------------------------------------------------------- #

SEVERITY = ("info", "low", "medium", "high", "critical")
CLAIM_KINDS = ("fact", "interpretation", "hypothesis", "missing")
READINESS = ("ready", "ready_with_accepted_limitations", "not_ready")
SPLIT_STRATEGIES = (
    "stratified_random",
    "group",
    "chronological",
    "rolling",
    "spatial",
    "source_holdout",
    "nested_cv",
)


# --------------------------------------------------------------------------- #
# 1. Dataset contract
# --------------------------------------------------------------------------- #

@dataclass
class DatasetContract:
    """What the dataset is and what decision it supports."""

    unit_of_observation: str
    intended_decision: str
    modality: str = "tabular"
    target: Optional[str] = None
    prediction_horizon: Optional[str] = None
    keys: List[str] = field(default_factory=list)
    group_keys: List[str] = field(default_factory=list)
    time_column: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    collection_window: Optional[str] = None
    allowed_values: Dict[str, Any] = field(default_factory=dict)
    cost_fp_fn: Optional[str] = None
    constraints: List[str] = field(default_factory=list)  # privacy/fairness/latency
    readiness_criteria: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    version: Optional[str] = None


# --------------------------------------------------------------------------- #
# 2. Data-quality report
# --------------------------------------------------------------------------- #

@dataclass
class Finding:
    """A single evidence-backed data-quality finding."""

    issue: str
    evidence: str
    severity: str = "medium"
    affected_scope: Optional[str] = None
    likely_cause: Optional[str] = None
    recommended_action: Optional[str] = None
    validation_check: Optional[str] = None
    claim_kind: str = "fact"
    status: str = "open"


@dataclass
class DataQualityReport:
    findings: List[Finding] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    questions_for_next_stage: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# 3. Split manifest
# --------------------------------------------------------------------------- #

@dataclass
class SplitManifest:
    strategy: str = "stratified_random"
    seed: Optional[int] = None
    time_boundaries: Dict[str, Any] = field(default_factory=dict)
    group_key: Optional[str] = None
    embargo: Optional[str] = None
    row_counts: Dict[str, int] = field(default_factory=dict)
    class_rates: Dict[str, Any] = field(default_factory=dict)
    overlap_checks: Dict[str, Any] = field(default_factory=dict)
    rationale: Optional[str] = None


# --------------------------------------------------------------------------- #
# 4. Feature manifest
# --------------------------------------------------------------------------- #

@dataclass
class FeatureSpec:
    name: str
    source_columns: List[str] = field(default_factory=list)
    formula: Optional[str] = None
    kind: str = "engineering"  # extraction | engineering | selection
    dtype: Optional[str] = None
    unit: Optional[str] = None
    allowed_range: Optional[Any] = None
    availability_time: Optional[str] = None  # relative to prediction cutoff
    fit_scope: str = "train_or_fold"
    missing_rule: Optional[str] = None
    encoding_scaling: Optional[str] = None
    leakage_risk: str = "unknown"
    hypothesis: Optional[str] = None


@dataclass
class FeatureManifest:
    features: List[FeatureSpec] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# 5. Transformation manifest
# --------------------------------------------------------------------------- #

@dataclass
class TransformationStep:
    name: str
    operation: str
    fit_scope: str = "train_or_fold"  # never validation/test
    order: int = 0
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransformationManifest:
    steps: List[TransformationStep] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# 6. Selection report
# --------------------------------------------------------------------------- #

@dataclass
class SelectionRecord:
    feature: str
    decision: str = "kept"  # kept | dropped
    evidence: Dict[str, Any] = field(default_factory=dict)  # method -> value
    stability: Optional[Any] = None
    redundancy_group: Optional[str] = None
    cost: Optional[str] = None
    availability: Optional[str] = None
    leakage_risk: str = "unknown"
    subgroup_impact: Optional[str] = None
    reversible: bool = True
    caveat: Optional[str] = None


@dataclass
class SelectionReport:
    records: List[SelectionRecord] = field(default_factory=list)
    method_order: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# 7. Sampling manifest
# --------------------------------------------------------------------------- #

@dataclass
class SamplingManifest:
    algorithm: str = "none"
    params: Dict[str, Any] = field(default_factory=dict)
    fold_scope: str = "train_partition_within_fold"
    original_counts: Dict[str, int] = field(default_factory=dict)
    resampled_counts: Dict[str, int] = field(default_factory=dict)
    synthetic_provenance: Optional[str] = None
    validation_test_prevalence: Optional[Any] = None  # natural / deployment


# --------------------------------------------------------------------------- #
# 8. Diagnostic report
# --------------------------------------------------------------------------- #

@dataclass
class DiagnosticReport:
    protocol: Optional[str] = None  # baseline/probe + split protocol
    out_of_fold_results: Dict[str, Any] = field(default_factory=dict)
    ablations: List[Dict[str, Any]] = field(default_factory=list)
    error_slices: Dict[str, Any] = field(default_factory=dict)
    forbidden_interpretations: List[str] = field(
        default_factory=lambda: [
            "No SHAP, importance, correlation, MI, or cluster result is causal.",
            "A test metric is not reported as an EDA result.",
        ]
    )


# --------------------------------------------------------------------------- #
# 9. Dataset card
# --------------------------------------------------------------------------- #

@dataclass
class DatasetCard:
    provenance: Optional[str] = None
    intended_use: Optional[str] = None
    exclusions: List[str] = field(default_factory=list)
    representativeness: Optional[str] = None
    privacy_fairness_risks: List[str] = field(default_factory=list)
    known_limitations: List[str] = field(default_factory=list)
    forbidden_uses: List[str] = field(default_factory=list)
    version: Optional[str] = None


# --------------------------------------------------------------------------- #
# Readiness verdict
# --------------------------------------------------------------------------- #

@dataclass
class ReadinessVerdict:
    verdict: str = "not_ready"  # one of READINESS
    passed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    blocking_evidence: Optional[str] = None
    smallest_corrective_experiment: Optional[str] = None
    accepted_exceptions: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Serialisation helpers
# --------------------------------------------------------------------------- #

def _default(o: Any) -> Any:
    if isinstance(o, (_dt.date, _dt.datetime)):
        return o.isoformat()
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return dataclasses.asdict(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serialisable")


def to_dict(obj: Any) -> Any:
    """Convert a manifest dataclass (or list/dict of them) to plain data."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    return obj


def to_json(obj: Any, indent: int = 2) -> str:
    return json.dumps(to_dict(obj), default=_default, ensure_ascii=False, indent=indent)


def save_manifests(path: str, **manifests: Any) -> str:
    """Write named manifests to a single JSON file and return the path.

    Example
    -------
    >>> save_manifests("handoff.json", dataset_contract=contract, split=split)
    """
    payload = {
        "_generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        **{name: to_dict(m) for name, m in manifests.items()},
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, default=_default, ensure_ascii=False, indent=2)
    return path


__all__ = [
    "DatasetContract",
    "Finding",
    "DataQualityReport",
    "SplitManifest",
    "FeatureSpec",
    "FeatureManifest",
    "TransformationStep",
    "TransformationManifest",
    "SelectionRecord",
    "SelectionReport",
    "SamplingManifest",
    "DiagnosticReport",
    "DatasetCard",
    "ReadinessVerdict",
    "to_dict",
    "to_json",
    "save_manifests",
    "SEVERITY",
    "CLAIM_KINDS",
    "READINESS",
    "SPLIT_STRATEGIES",
]
