"""Memory health checks that avoid natural-language heuristics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .context_builder import collect_scope_values
from .schemas import MemoryRecord
from .store import MemoryStore


@dataclass
class DoctorReport:
    issues: List[str] = field(default_factory=list)
    hygiene: List[str] = field(default_factory=list)
    host: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def text(self) -> str:
        sections: List[str] = []
        if self.ok:
            sections.append("Memory doctor: OK. No blocking lifecycle or recall issues found.")
        else:
            sections.append(
                "Memory doctor found issues:\n" + "\n".join(f"- {issue}" for issue in self.issues)
            )
        if self.hygiene:
            sections.append(
                "Memory hygiene observations:\n"
                + "\n".join(f"- {item}" for item in self.hygiene)
            )
        if self.host:
            sections.append(
                "Host integration observations:\n"
                + "\n".join(f"- {item}" for item in self.host)
            )
        return "\n\n".join(sections)


def run_doctor(store: MemoryStore) -> DoctorReport:
    report = DoctorReport()
    active = store.list(status="active")
    requests = store.context_requests(limit=1000)
    buckets: Dict[str, List[str]] = defaultdict(list)

    for memory in active:
        buckets[f"{memory.slot}|{memory.scope.key()}"].append(memory.id)
        if len(memory.content) > 600:
            report.hygiene.append(
                f"{memory.id} content is long ({len(memory.content)} chars). Consider summarizing."
            )
        _check_single_memory_hygiene(report, memory, requests)

    for key, ids in buckets.items():
        if len(ids) > 1:
            report.issues.append(f"multiple active memories for {key}: {', '.join(ids)}")

    _check_scenario_hygiene(report, store, active)
    _check_recall_health(report, active, requests)
    _check_host_integration(report, active, requests)
    return report


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _has_scoped_context(memory: MemoryRecord) -> bool:
    context = memory.created_from.task_context
    scoped_keys = ("project", "tool", "task_type", "session_id", "product", "domain", "user_id")
    return any(context.get(key) for key in scoped_keys)


def _check_single_memory_hygiene(
    report: DoctorReport,
    memory: MemoryRecord,
    requests: List[Dict[str, Any]],
) -> None:
    now = datetime.now(timezone.utc)
    valid_until = _parse_time(memory.valid_until)
    if valid_until and valid_until < now:
        report.issues.append(
            f"{memory.id} is active but valid_until={memory.valid_until} is in the past. "
            "Archive or delete it so expired memory stops applying."
        )

    if memory.type == "temporary" and not memory.valid_until:
        report.hygiene.append(
            f"{memory.id} is temporary but has no valid_until. Add an expiry, "
            "archive it, or narrow it to a session scope."
        )
    if memory.type == "temporary" and memory.scope.level != "session":
        report.hygiene.append(
            f"{memory.id} is temporary at scope={memory.scope.key()}. Temporary memories "
            "are safer at session scope unless the user explicitly confirmed otherwise."
        )
    if memory.type == "project_rule" and memory.scope.level == "global":
        report.hygiene.append(
            f"{memory.id} is a project_rule at global scope. Confirm that this is truly "
            "cross-project, or narrow its scope."
        )
    if memory.scope.level == "global" and _has_scoped_context(memory):
        report.hygiene.append(
            f"{memory.id} was created from scoped task context but stored as global. "
            "Confirm that the broad scope is intentional."
        )
    if memory.confidence < 0.5:
        report.hygiene.append(
            f"{memory.id} has low confidence ({memory.confidence:.2f}). Confirm, "
            "edit, or archive it before relying on it."
        )
    if not memory.source_event_id and not memory.evidence_refs:
        report.hygiene.append(
            f"{memory.id} has no source evidence refs. Add evidence when possible, "
            "or treat it as a manual legacy memory."
        )

    opportunities = sum(1 for request in requests if request["timestamp"] > memory.created_at)
    if memory.usage_count == 0 and opportunities >= 3:
        report.hygiene.append(
            f"{memory.id} has never been returned across {opportunities} later "
            "context request(s). Check scope, rank limit, or archive it."
        )


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


def _check_scenario_hygiene(
    report: DoctorReport,
    store: MemoryStore,
    active: List[MemoryRecord],
) -> None:
    from .scenario import scenario_status

    for memory in active:
        if memory.layer != "L2_scenario":
            continue
        status = scenario_status(store, memory)
        if status.fresh:
            continue
        report.hygiene.append(
            f"{memory.id} is a stale L2 scenario. build_context will fall back to L1 "
            f"memories. Reasons: {'; '.join(status.reasons)}"
        )


def _latest_memory_update(active: List[MemoryRecord]) -> str | None:
    if not active:
        return None
    return max(memory.updated_at for memory in active)


def _check_host_integration(
    report: DoctorReport,
    active: List[MemoryRecord],
    requests: List[Dict[str, Any]],
) -> None:
    scoped = [memory for memory in active if memory.scope.level != "global"]
    if not active:
        report.host.append("No active memories are stored yet; host recall cannot be verified.")
        return
    if not requests:
        report.host.append(
            "No build_context request has been logged. The store may be healthy, "
            "but host integration is unverified until a real task calls build_context."
        )
        return

    latest_update = _latest_memory_update(active)
    if latest_update and not any(request["timestamp"] > latest_update for request in requests):
        report.host.append(
            "No build_context request has been logged after the latest active memory update. "
            "An open host session may still be relying on an older MCP instruction snapshot "
            "or exported instruction file; call build_context to refresh runtime context."
        )

    if scoped:
        scoped_dims = collect_scope_values(scoped)
        used_dims = {
            dim
            for request in requests
            for dim, value in (request.get("criteria") or {}).items()
            if value is not None
        }
        missing_dims = sorted(dim for dim in scoped_dims if dim not in used_dims)
        if missing_dims:
            report.host.append(
                "Scoped memories exist, but recent build_context requests never passed "
                f"these scope dimension(s): {', '.join(missing_dims)}. The host may be "
                "calling build_context too generically."
            )
        if all(not request.get("criteria") for request in requests):
            report.host.append(
                "Scoped memories exist, but all logged build_context requests were global "
                "/ empty criteria. Scoped memory cannot fire until the host passes task, "
                "project, tool, product, domain, user, or session scope."
            )
    if not any(request.get("actor") == "mcp" for request in requests):
        report.host.append(
            "No MCP-origin build_context request is logged. CLI recall works, but the "
            "actual MCP host path has not been observed in this store."
        )
