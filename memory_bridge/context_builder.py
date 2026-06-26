"""Build portable context from active memories.

Selection is based on explicit scope metadata, not text keyword matching.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .schemas import MemoryRecord, Scope
from .store import MemoryStore


@dataclass(frozen=True)
class ContextCriteria:
    project: Optional[str] = None
    tool: Optional[str] = None
    task_type: Optional[str] = None
    session_id: Optional[str] = None
    product: Optional[str] = None
    domain: Optional[str] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        return {key: value for key, value in asdict(self).items() if value is not None}

    def to_scope(self) -> Scope:
        return Scope(
            level="session" if self.session_id else "global",
            project=self.project,
            tool=self.tool,
            task_type=self.task_type,
            session_id=self.session_id,
            product=self.product,
            domain=self.domain,
            user_id=self.user_id,
        )


def scope_matches(scope: Scope, criteria: ContextCriteria) -> bool:
    if scope.level == "global":
        return True
    if scope.level == "project":
        return bool(criteria.project and scope.project == criteria.project)
    if scope.level == "tool":
        return bool(criteria.tool and scope.tool == criteria.tool)
    if scope.level == "task_type":
        return bool(criteria.task_type and scope.task_type == criteria.task_type)
    if scope.level == "session":
        return bool(criteria.session_id and scope.session_id == criteria.session_id)
    if scope.level == "product_user":
        checks = []
        if scope.product:
            checks.append(criteria.product == scope.product)
        if scope.domain:
            checks.append(criteria.domain == scope.domain)
        if scope.user_id:
            checks.append(criteria.user_id == scope.user_id)
        return bool(checks) and all(checks)
    return False


SCOPE_DIMENSIONS = ("project", "tool", "task_type", "session_id", "product", "domain", "user_id")

LAYER_PRIORITY = {
    "L2_scenario": 2,
    "L1_atom": 1,
    "L3_profile": 0,
}

TYPE_PRIORITY = {
    "anti_preference": 5,
    "project_rule": 4,
    "temporary": 3,
    "workflow": 3,
    "preference": 2,
    "fact": 1,
}

USAGE_BALANCE_CAP = 5


def collect_scope_values(memories: Iterable[MemoryRecord]) -> Dict[str, List[str]]:
    """Distinct non-null scope values per dimension, exact as stored.

    The store is the only vocabulary source: callers (and host AIs) reuse these
    exact values instead of inventing a variant (e.g. 'bugfix' vs the stored
    'bug-fix') that would miss the exact scope match. No normalization is
    applied here; matching stays exact in scope_matches.
    """
    values: Dict[str, set] = {dim: set() for dim in SCOPE_DIMENSIONS}
    for memory in memories:
        data = memory.scope.to_dict()
        for dim in SCOPE_DIMENSIONS:
            value = data.get(dim)
            if value:
                values[dim].add(value)
    return {dim: sorted(found) for dim, found in values.items() if found}


def available_scope_values(store: MemoryStore) -> Dict[str, List[str]]:
    """Scope vocabulary across all active memories."""
    return collect_scope_values(store.list(status="active"))


def unmatched_scope_summary(
    store: MemoryStore, criteria: ContextCriteria
) -> Tuple[int, Dict[str, List[str]]]:
    """Active memories this call cannot reach, with their exact scope values.

    Globals match every call, so a response can look successful while scoped
    memories silently never fire — because the dimension was omitted, or its
    value drifted from the stored one. Enumerating the unmatched stored values
    lets the host AI re-call with an exact key; matching itself stays exact.
    """
    unmatched = [
        memory
        for memory in store.list(status="active")
        if not scope_matches(memory.scope, criteria)
    ]
    return len(unmatched), collect_scope_values(unmatched)


def _usage_balance(memory: MemoryRecord) -> int:
    """Lightly rotate otherwise equal memories without burying important ones."""
    return -min(max(memory.usage_count, 0), USAGE_BALANCE_CAP)


def memory_priority_parts(memory: MemoryRecord) -> Dict[str, Any]:
    """Structured ranking signals used by the read path.

    This deliberately uses only governed metadata. It does not inspect memory
    content, slots, or keywords, keeping semantic extraction outside core code.
    """
    return {
        "layer_priority": LAYER_PRIORITY.get(memory.layer, 0),
        "scope_specificity": memory.scope.specificity(),
        "type_priority": TYPE_PRIORITY.get(memory.type, 0),
        "confidence": memory.confidence,
        "usage_balance": _usage_balance(memory),
        "valid_from": memory.valid_from,
    }


def memory_priority_key(memory: MemoryRecord) -> Tuple[Any, ...]:
    parts = memory_priority_parts(memory)
    return (
        parts["layer_priority"],
        parts["scope_specificity"],
        parts["type_priority"],
        parts["confidence"],
        parts["usage_balance"],
        parts["valid_from"],
    )


def _matching_sorted(store: MemoryStore, criteria: ContextCriteria) -> List[MemoryRecord]:
    active = store.list(status="active")
    matched = [memory for memory in active if scope_matches(memory.scope, criteria)]
    matched.sort(key=memory_priority_key, reverse=True)
    return matched


def _compose_context_records(store: MemoryStore, matched: List[MemoryRecord]) -> List[MemoryRecord]:
    """Prefer fresh L2 scenarios, then include uncovered lower-level memories."""
    from .scenario import scenario_source_ids, scenario_status

    fresh_scenarios: List[MemoryRecord] = []
    stale_scenario_ids = set()
    for memory in matched:
        if memory.layer != "L2_scenario":
            continue
        status = scenario_status(store, memory)
        if status.fresh:
            fresh_scenarios.append(memory)
        else:
            stale_scenario_ids.add(memory.id)

    covered_l1_ids = {
        source_id
        for scenario in fresh_scenarios
        for source_id in scenario_source_ids(scenario)
    }
    selected: List[MemoryRecord] = []
    for memory in matched:
        if memory.id in stale_scenario_ids:
            continue
        if memory.id in covered_l1_ids:
            continue
        selected.append(memory)
    return selected


def select_memories_with_total(
    store: MemoryStore, criteria: ContextCriteria, limit: int = 12
) -> "tuple[List[MemoryRecord], int]":
    """Return (selected, total_matched).

    total_matched is the count of scope-matching active memories *before* the
    limit cap, so callers can report how many relevant memories were not shown
    instead of truncating silently.
    """
    matched = _compose_context_records(store, _matching_sorted(store, criteria))
    selected = matched[:limit]
    store.mark_used(selected)
    return selected, len(matched)


def select_memories(store: MemoryStore, criteria: ContextCriteria, limit: int = 12) -> List[MemoryRecord]:
    selected, _ = select_memories_with_total(store, criteria, limit=limit)
    return selected


def build_context_markdown(
    memories: Iterable[MemoryRecord],
    available_scopes: Optional[Dict[str, List[str]]] = None,
    truncated_count: int = 0,
) -> str:
    memories = list(memories)
    if not memories:
        base = "No active workstyle memories matched this context."
        if not available_scopes:
            return base
        lines = [
            base,
            "",
            "Active memories use the scope values below. If one fits the current",
            "task, call build_context again with that exact value (scope is matched",
            "exactly — reuse the stored value rather than a variant):",
        ]
        for dim, found in available_scopes.items():
            lines.append(f"- {dim}: {', '.join(found)}")
        return "\n".join(lines)
    lines = [
        "# Active Workstyle Memories",
        "",
        "Use these only when they are relevant to the current task. User instructions in the current task override these memories.",
        "",
    ]
    for memory in memories:
        if memory.layer == "L2_scenario":
            lines.append(f"## Scenario Playbook: {memory.slot}")
            lines.append(f"- type: {memory.type}")
            lines.append(f"- scope: {memory.scope.key()}")
            lines.append("")
            lines.append(memory.content)
            lines.append("")
        else:
            lines.append(f"- ({memory.type}, scope={memory.scope.key()}, slot={memory.slot}) {memory.content}")
    if truncated_count > 0:
        lines.append("")
        lines.append(
            f"> {truncated_count} more memory(ies) also matched this scope but were not shown "
            "(showing JIT-ranked memories first). Raise the limit or narrow the scope to see them."
        )
    return "\n".join(lines)


def build_context_json(memories: Iterable[MemoryRecord]) -> str:
    return json.dumps([memory.to_dict() for memory in memories], ensure_ascii=False, indent=2)


def respond_to_context_request(
    store: MemoryStore,
    criteria: ContextCriteria,
    limit: int,
    actor: str,
    fmt: str = "markdown",
) -> str:
    """Serve one read-path request: select, log it, and render.

    The single implementation behind the CLI `build-context` command and the
    MCP `build_context` tool, so the unmatched-scope hint and the
    context_requests audit row stay consistent across entry points. Projection
    and verification paths (export, verify-deletion) call the selector directly
    and are deliberately NOT logged as context requests.
    """
    memories, total = select_memories_with_total(store, criteria, limit=limit)
    unmatched_count, unmatched_values = unmatched_scope_summary(store, criteria)
    store.log_context_request(
        actor=actor,
        criteria=criteria.to_dict(),
        matched_count=total,
        returned_ids=[memory.id for memory in memories],
        unmatched_count=unmatched_count,
    )
    if fmt == "json":
        return build_context_json(memories)
    available = available_scope_values(store) if not memories else None
    text = build_context_markdown(
        memories, available_scopes=available, truncated_count=total - len(memories)
    )
    if memories and unmatched_count:
        lines = [
            f"> {unmatched_count} scoped active memory(ies) did NOT match this call and were not included.",
            "> If a stored value below fits the current task, call build_context again with that",
            "> exact value (scope matching is exact — reuse stored values, never invent variants):",
        ]
        for dim, found in sorted(unmatched_values.items()):
            lines.append(f"> - {dim}: {', '.join(found)}")
        text = text + "\n\n" + "\n".join(lines)
    return text


def _criteria_from_dict(data: Dict[str, Any]) -> ContextCriteria:
    return ContextCriteria(
        **{key: data.get(key) for key in SCOPE_DIMENSIONS if data.get(key) is not None}
    )


def _describe_criteria(criteria: Dict[str, Any]) -> str:
    if not criteria:
        return "global / no scoped criteria"
    return ", ".join(f"{key}={value}" for key, value in sorted(criteria.items()))


def _scope_match_reason(scope: Scope, criteria: ContextCriteria) -> str:
    if scope.level == "global":
        return "global scope matches every build_context request"

    criteria_data = criteria.to_dict()
    matched = []
    for dim in SCOPE_DIMENSIONS:
        value = scope.to_dict().get(dim)
        if value:
            matched.append(f"{dim}={value}")

    if matched:
        return "exact scope match on " + ", ".join(matched)
    if scope_matches(scope, criteria):
        return f"scope level {scope.level} matched criteria {_describe_criteria(criteria_data)}"
    return f"scope level {scope.level} does not currently match criteria {_describe_criteria(criteria_data)}"


def explain_context_request(
    store: MemoryStore, request_id: Optional[int] = None
) -> Dict[str, Any]:
    """Explain the latest or selected read-path request without changing usage stats."""
    requests = store.context_requests(limit=1000 if request_id is not None else 1)
    if not requests:
        return {
            "status": "no_context_requests",
            "message": "No build_context request has been logged yet.",
        }

    request = requests[0]
    if request_id is not None:
        found = [row for row in requests if row.get("request_id") == request_id]
        if not found:
            return {
                "status": "request_not_found",
                "message": f"Context request not found: {request_id}",
            }
        request = found[0]

    criteria = _criteria_from_dict(request.get("criteria") or {})
    returned = []
    missing_ids = []
    for position, memory_id in enumerate(request.get("returned_ids") or [], start=1):
        memory = store.get(memory_id)
        if not memory:
            missing_ids.append(memory_id)
            continue
        returned.append(
            {
                "rank": position,
                "memory": memory.to_dict(),
                "scope_reason": _scope_match_reason(memory.scope, criteria),
                "priority": memory_priority_parts(memory),
            }
        )

    current_unmatched_count, current_unmatched_values = unmatched_scope_summary(store, criteria)
    return {
        "status": "ok",
        "request": request,
        "criteria_description": _describe_criteria(request.get("criteria") or {}),
        "returned": returned,
        "missing_returned_ids": missing_ids,
        "current_unmatched_count": current_unmatched_count,
        "current_unmatched_scope_values": current_unmatched_values,
    }


def build_context_explanation_markdown(explanation: Dict[str, Any]) -> str:
    status = explanation.get("status")
    if status != "ok":
        return str(explanation.get("message") or "No context explanation available.")

    request = explanation["request"]
    lines = [
        "# Context Recall Explanation",
        "",
        f"- request_id: {request['request_id']}",
        f"- timestamp: {request['timestamp']}",
        f"- actor: {request['actor']}",
        f"- criteria: {explanation['criteria_description']}",
        f"- matched_count: {request['matched_count']}",
        f"- returned_count: {len(explanation['returned'])}",
        f"- logged_unmatched_count: {request['unmatched_count']}",
        "",
    ]

    if not explanation["returned"]:
        lines.append("No memories were returned for this request.")
    else:
        lines.append("Returned memories:")
        for item in explanation["returned"]:
            memory = item["memory"]
            priority = item["priority"]
            lines.append(f"{item['rank']}. {memory['id']} :: {memory['slot']}")
            lines.append(
                f"   - type/layer/scope: {memory['type']} / {memory['layer']} / {memory['scope_key']}"
            )
            lines.append(f"   - reason: {item['scope_reason']}")
            lines.append(
                "   - rank signals: "
                f"layer={priority['layer_priority']}, "
                f"scope={priority['scope_specificity']}, "
                f"type={priority['type_priority']}, "
                f"confidence={priority['confidence']:.2f}, "
                f"usage_balance={priority['usage_balance']}, "
                f"valid_from={priority['valid_from']}"
            )
            lines.append(f"   - content: {memory['content']}")

    if explanation["missing_returned_ids"]:
        lines.extend(["", "Returned IDs no longer present in the store:"])
        for memory_id in explanation["missing_returned_ids"]:
            lines.append(f"- {memory_id}")

    unmatched_values = explanation["current_unmatched_scope_values"]
    if unmatched_values:
        lines.extend(
            [
                "",
                "Currently unreachable scoped memory values for the same criteria:",
            ]
        )
        for dim, found in sorted(unmatched_values.items()):
            lines.append(f"- {dim}: {', '.join(found)}")

    return "\n".join(lines)
