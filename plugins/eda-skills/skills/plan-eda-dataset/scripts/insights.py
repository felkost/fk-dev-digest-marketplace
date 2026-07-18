"""Persistent project insights — user corrections that outlive one session.

When the user says "in our data, do X instead of Y" ("use DBSCAN here, the
clusters are density-shaped", "never impute pressure — a missing reading means
the sensor was off"), that is domain knowledge the skills cannot re-derive from
the data. This module stores such rules in a human-editable ``insights.md`` so
the next session applies them instead of re-asking or silently repeating the
correction.

The file is markdown first: the user can read, edit, or delete entries by hand.
Parsing is tolerant -- unknown fields are kept, malformed blocks are skipped.

Precedence (enforced by the SKILL, documented here):
  1. **Hard invariants win over insights.** An insight may not authorise fitting
     on test, resampling validation/test, or reporting a test metric as an EDA
     result. :func:`append_insight` flags such rules as ``conflicts_invariant``
     and they are never returned as applicable.
  2. Otherwise a matching insight overrides the skill's default method choice.
  3. An insight is scoped: it applies to the named stage/method, not globally.

Standard library only.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
from typing import Iterable, Optional

DEFAULT_PATH = "insights.md"

STATUSES = ("active", "superseded", "conflicts_invariant")

_HEADER = """# EDA insights — project rules from the user

Domain rules and corrections that the skills apply automatically. Each entry is
scoped to a stage/method. Edit or delete entries by hand; set `status:
superseded` to retire one without losing the history.

Hard leakage invariants (fit on train only, natural validation/test prevalence,
sealed test) are NOT overridable here — such an entry is recorded with
`status: conflicts_invariant` and is not applied.
"""

# Phrases that would authorise breaking a hard invariant. Deliberately narrow:
# this catches the classic asks, and the SKILL requires human review anyway.
_INVARIANT_PATTERNS = (
    r"\bfit\b.{0,30}\b(on|using)\b.{0,20}\b(test|holdout|validation|all data|whole dataset|full data)\b",
    r"\b(навчати|фітити|фітимо|тренувати)\b.{0,30}\b(на|по)\b.{0,20}\b(тест|усіх даних|всіх даних|валідац)",
    r"\b(resample|balance|oversample|undersample|smote)\b.{0,30}\b(test|validation|holdout)\b",
    r"\b(ресемпл|балансув)\w*\b.{0,30}\b(тест|валідац)",
    r"\b(tune|optimi[sz]e|select|choose)\b.{0,30}\bon\b.{0,15}\btest\b",
    r"\b(тюнити|підбирати|обирати)\b.{0,30}\bна\b.{0,15}\bтест",
    r"\breport\b.{0,30}\btest (metric|score)\b.{0,30}\bas\b.{0,20}\bresult\b",
    r"\b(ignore|skip|disable|remove)\b.{0,25}\b(the )?(split|leakage)\b.{0,15}\b(check|rule)s?\b",
    r"\b(ігнорувати|вимкнути|пропустити)\b.{0,25}\b(leakage|витік|спліт|split)",
)


def _conflicts_invariant(text: str) -> bool:
    low = " ".join(text.lower().split())
    return any(re.search(p, low) for p in _INVARIANT_PATTERNS)


def _slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)[:n].strip("-") or "insight"


def append_insight(rule: str, scope: str, why: str = "", source: str = "user",
                   path: str = DEFAULT_PATH, date: Optional[str] = None) -> dict:
    """Append one user rule to ``insights.md`` (created if absent).

    Parameters
    ----------
    rule : the instruction, as an imperative ("use DBSCAN, not KMeans").
    scope : stage/method it governs, e.g. ``"discover-eda-structure/clustering"``.
    why : the domain rationale -- the part that makes the rule reusable later.
    source : who said it (default ``"user"``).

    Returns the stored entry. If the rule would break a hard invariant, it is
    still recorded (for the audit trail) but with ``status='conflicts_invariant'``
    and is never applied by :func:`applicable`.
    """
    date = date or _dt.date.today().isoformat()
    status = "conflicts_invariant" if _conflicts_invariant(f"{rule} {why}") else "active"
    entry = {"id": f"{date}-{_slug(rule)}", "date": date, "scope": scope,
             "status": status, "rule": rule.strip(), "why": why.strip(),
             "source": source.strip()}

    new_file = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as fh:
        if new_file:
            fh.write(_HEADER)
        fh.write(
            f"\n---\n\n### {entry['date']} | {scope} | {status}\n\n"
            f"- **rule:** {entry['rule']}\n"
            f"- **why:** {entry['why'] or '(not stated -- ask before relying on this)'}\n"
            f"- **source:** {entry['source']}\n"
        )
    return entry


def load_insights(path: str = DEFAULT_PATH) -> list[dict]:
    """Parse ``insights.md`` into entries. Missing file -> empty list."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    entries = []
    for block in re.split(r"^### ", text, flags=re.M)[1:]:
        lines = block.splitlines()
        head = [p.strip() for p in lines[0].split("|")]
        entry = {"date": head[0] if head else "",
                 "scope": head[1] if len(head) > 1 else "",
                 "status": head[2] if len(head) > 2 else "active"}
        for m in re.finditer(r"^-\s+\*\*(\w+):\*\*\s*(.+)$", block, flags=re.M):
            entry[m.group(1).lower()] = m.group(2).strip()
        if entry.get("rule"):
            entry.setdefault("id", f"{entry['date']}-{_slug(entry['rule'])}")
            entries.append(entry)
    return entries


def applicable(scope: str, path: str = DEFAULT_PATH,
               insights: Optional[Iterable[dict]] = None) -> list[dict]:
    """Active insights governing ``scope``.

    Matching is prefix-based on the ``stage/method`` path, so scope
    ``"discover-eda-structure/clustering"`` picks up both a stage-wide rule
    (``"discover-eda-structure"``) and the method-specific one. Entries that
    conflict with a hard invariant are never returned.
    """
    items = list(insights) if insights is not None else load_insights(path)
    scope = scope.strip("/")
    out = []
    for e in items:
        if e.get("status") != "active":
            continue
        s = e.get("scope", "").strip("/")
        if s and (scope == s or scope.startswith(s + "/") or s.startswith(scope + "/")):
            out.append(e)
    return out


def format_for_prompt(entries: Iterable[dict]) -> str:
    """Render entries as a short block to restate before acting on a stage.

    Restating the rule (and its source) is what lets the user catch a stale or
    misapplied insight before it silently shapes the analysis.
    """
    entries = list(entries)
    if not entries:
        return "(no recorded project insights for this scope)"
    lines = []
    for e in entries:
        lines.append(f"- [{e.get('date','')}] {e['rule']}"
                     + (f" — why: {e['why']}" if e.get("why") else "")
                     + f" (source: {e.get('source','user')})")
    return "\n".join(lines)


def supersede(insight_id: str, path: str = DEFAULT_PATH) -> bool:
    """Mark an entry ``superseded`` in place. Returns True if one changed.

    Use when the user revises a rule: the old text stays readable in the file
    (the reasoning history is often why the new rule makes sense).
    """
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    changed = False
    out_blocks = []
    parts = re.split(r"(^### .*$)", text, flags=re.M)
    for i, part in enumerate(parts):
        if part.startswith("### ") and i + 1 < len(parts):
            head = [p.strip() for p in part[4:].split("|")]
            body = parts[i + 1]
            m = re.search(r"^-\s+\*\*rule:\*\*\s*(.+)$", body, flags=re.M)
            if m and head and f"{head[0]}-{_slug(m.group(1))}" == insight_id:
                part = f"### {head[0]} | {head[1] if len(head)>1 else ''} | superseded"
                changed = True
        out_blocks.append(part)
    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("".join(out_blocks))
    return changed


__all__ = ["append_insight", "load_insights", "applicable", "format_for_prompt",
           "supersede", "DEFAULT_PATH", "STATUSES"]
