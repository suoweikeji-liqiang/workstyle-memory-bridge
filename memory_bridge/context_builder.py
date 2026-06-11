"""Build portable context from active memories.

Selection is based on explicit scope metadata, not text keyword matching.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Tuple

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


def _matching_sorted(store: MemoryStore, criteria: ContextCriteria) -> List[MemoryRecord]:
    active = store.list(status="active")
    matched = [memory for memory in active if scope_matches(memory.scope, criteria)]
    matched.sort(
        key=lambda m: (m.scope.specificity(), m.confidence, m.valid_from),
        reverse=True,
    )
    return matched


def select_memories_with_total(
    store: MemoryStore, criteria: ContextCriteria, limit: int = 12
) -> "tuple[List[MemoryRecord], int]":
    """Return (selected, total_matched).

    total_matched is the count of scope-matching active memories *before* the
    limit cap, so callers can report how many relevant memories were not shown
    instead of truncating silently.
    """
    matched = _matching_sorted(store, criteria)
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
        lines.append(f"- ({memory.type}, scope={memory.scope.key()}, slot={memory.slot}) {memory.content}")
    if truncated_count > 0:
        lines.append("")
        lines.append(
            f"> {truncated_count} more memory(ies) also matched this scope but were not shown "
            "(showing the most specific/recent first). Raise the limit or narrow the scope to see them."
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
