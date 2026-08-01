"""Pure-logic core of a tool-security harness.

Implements the three pieces `deploy-ai-environments/references/
security-governance.md` specifies as testable: an egress allowlist that
resolves the real hostname instead of trusting a substring match, a
schema-first argument validator that rejects unknown fields, and a durable
HITL checkpoint that survives a simulated restart and escalates on timeout.

Everything here is stdlib-only and free of import-time side effects, so the
smoke test can import and exercise it offline. Model wiring (if any) lives
in ``agent.py`` and is never imported from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit


# --------------------------------------------------------------------------
# Egress allowlist: deny by default, match the real hostname
# --------------------------------------------------------------------------


@dataclass
class EgressPolicy:
    """Deny-by-default outbound network policy.

    Matches the URL's actual parsed hostname against the allowlist, not a
    substring or suffix of the raw URL string -- a naive ``url.endswith(domain)``
    or ``domain in url`` check is exactly what lets a lookalike host
    ("docs.myapp.com.attacker.com", or "notdocs.myapp.com") slip through.
    """

    allowed_hosts: frozenset[str]

    def allows(self, url: str) -> bool:
        host = urlsplit(url).hostname
        if host is None:
            return False
        return host.lower() in self.allowed_hosts


# --------------------------------------------------------------------------
# Schema-first argument validation: reject unknown fields, don't guess
# --------------------------------------------------------------------------


@dataclass
class SchemaResult:
    valid: bool
    errors: tuple[str, ...]


@dataclass
class ToolSchema:
    """A strict, additionalProperties=false-shaped argument schema.

    ``required``/``optional`` map field name -> expected Python type. A call
    is valid only if every required field is present, every present field's
    type matches, and NO field outside required+optional appears at all.
    """

    required: dict[str, type] = field(default_factory=dict)
    optional: dict[str, type] = field(default_factory=dict)

    def validate(self, args: dict) -> SchemaResult:
        errors: list[str] = []
        known = {**self.required, **self.optional}

        for name in self.required:
            if name not in args:
                errors.append(f"missing required field: {name!r}")

        for name, value in args.items():
            if name not in known:
                errors.append(f"unknown field rejected: {name!r}")
                continue
            expected_type = known[name]
            if not isinstance(value, expected_type):
                errors.append(
                    f"field {name!r} expected {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )

        return SchemaResult(valid=not errors, errors=tuple(errors))


# --------------------------------------------------------------------------
# HITL checkpoint: durable across a restart, timeout escalates
# --------------------------------------------------------------------------


@dataclass
class Checkpoint:
    checkpoint_id: str
    action_description: str
    status: str = "pending"  # pending | approved | rejected | escalated | timed_out
    created_at: float = 0.0
    reviewer_note: str | None = None


class CheckpointStore:
    """Durable-by-construction: wraps a plain dict passed in from outside.

    "Surviving a restart" is demonstrated by constructing a SECOND
    CheckpointStore around the SAME backing dict -- the state lives outside
    any one CheckpointStore instance, the way a real deployment would use
    Redis/Postgres instead of a process-local variable.
    """

    def __init__(self, backing: dict[str, Checkpoint] | None = None) -> None:
        self._backing = backing if backing is not None else {}

    def create(self, checkpoint_id: str, action_description: str, now: float) -> Checkpoint:
        cp = Checkpoint(checkpoint_id=checkpoint_id, action_description=action_description,
                         created_at=now)
        self._backing[checkpoint_id] = cp
        return cp

    def get(self, checkpoint_id: str) -> Checkpoint:
        return self._backing[checkpoint_id]

    def resolve(self, checkpoint_id: str, status: str, reviewer_note: str | None = None) -> Checkpoint:
        """Approve/reject/escalate. A checkpoint already in a resolved
        terminal state (approved/rejected) is immune to further mutation --
        a late-firing timeout check must not overwrite a human's decision
        that already landed.
        """
        cp = self._backing[checkpoint_id]
        if cp.status in ("approved", "rejected"):
            return cp
        cp.status = status
        if reviewer_note is not None:
            cp.reviewer_note = reviewer_note
        return cp

    def check_timeout(self, checkpoint_id: str, now: float, timeout_s: float) -> Checkpoint:
        """Escalate a still-pending checkpoint whose wait has exceeded
        timeout_s. A no-op on anything already resolved or escalated.
        """
        cp = self._backing[checkpoint_id]
        if cp.status == "pending" and (now - cp.created_at) >= timeout_s:
            cp.status = "escalated"
        return cp
