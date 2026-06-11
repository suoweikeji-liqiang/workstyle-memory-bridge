"""Memory health checks that avoid natural-language heuristics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from .context_builder import collect_scope_values
from .schemas import MemoryRecord
from .store import MemoryStore


@dataclass
class DoctorReport:
    issues: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def text(self) -> str:
        if self.ok:
            return "Memory doctor: OK. No lifecycle or schema issues found."
        return "Memory doctor found issues:\n" + "\n".join(f"- {issue}" for issue in self.issues)


def run_doctor(store: MemoryStore) -> DoctorReport:
    report = DoctorReport()
    active = store.list(status="active")
    buckets: Dict[str, List[str]] = defaultdict(list)

    for memory in active:
        buckets[f"{memory.slot}|{memory.scope.key()}"].append(memory.id)
        if len(memory.content) > 600:
            report.issues.append(
                f"{memory.id} content is long ({len(memory.content)} chars). Consider summarizing."
            )

    for key, ids in buckets.items():
        if len(ids) > 1:
            report.issues.append(f"multiple active memories for {key}: {', '.join(ids)}")

    _check_recall_health(report, active, store.context_requests(limit=1000))
    return report


def _check_recall_health(
    report: DoctorReport,
    active: List[MemoryRecord],
    requests: List[Dict[str, Any]],
) -> None:
    """Cross-reference the read-path audit with stored scopes.

    Facts only — no similarity scoring, no value mapping. Whether a requested
    label and a stored value name the same kind of work is a semantic call the
    host AI / user makes; any fix goes through the governed edit path.
    """
    # Dead scoped memories: requests happened after creation, none returned it.
    # Globals are skipped (they match every request) and so is a store with no
    # logged requests yet — silence without opportunity is not an incident.
    for memory in active:
        if memory.scope.level == "global" or memory.usage_count > 0:
            continue
        opportunities = sum(1 for r in requests if r["timestamp"] > memory.created_at)
        if opportunities:
            report.issues.append(
                f"{memory.id} (slot={memory.slot}, scope={memory.scope.key()}) was returned "
                f"0 times across {opportunities} context request(s) since it was created — "
                "no request used its scope value. Re-scope it via a governed edit, or use "
                "its exact value when calling build_context."
            )

    # Unmet demand: requested values with no matching memory, counted per value.
    # Only dimensions the store actually organizes by are reported; a project
    # value finding no memory is noise when no memory is project-scoped at all.
    stored = collect_scope_values(active)
    unmet: Dict[Tuple[str, str], int] = defaultdict(int)
    for request in requests:
        for dim, value in request["criteria"].items():
            if dim in stored and value not in stored[dim]:
                unmet[(dim, value)] += 1
    by_dim: Dict[str, List[str]] = defaultdict(list)
    for (dim, value), count in sorted(unmet.items(), key=lambda item: (-item[1], item[0])):
        by_dim[dim].append(f"{value} (x{count})")
    for dim, entries in by_dim.items():
        report.issues.append(
            f"requested {dim} values with no matching memory: {', '.join(entries)}; "
            f"stored values: {', '.join(stored[dim])}. If a requested label names the same "
            "kind of work as a stored value, align them (edit the memory scope or reuse the "
            "stored label when calling build_context)."
        )
