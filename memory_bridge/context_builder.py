"""Build portable context from active memories.

Selection is based on explicit scope metadata, not text keyword matching.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

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


def select_memories(store: MemoryStore, criteria: ContextCriteria, limit: int = 12) -> List[MemoryRecord]:
    active = store.list(status="active")
    selected = [memory for memory in active if scope_matches(memory.scope, criteria)]
    selected.sort(
        key=lambda m: (m.scope.specificity(), m.confidence, m.valid_from),
        reverse=True,
    )
    selected = selected[:limit]
    store.mark_used(selected)
    return selected


def build_context_markdown(memories: Iterable[MemoryRecord]) -> str:
    memories = list(memories)
    if not memories:
        return "No active workstyle memories matched this context."
    lines = [
        "# Active Workstyle Memories",
        "",
        "Use these only when they are relevant to the current task. User instructions in the current task override these memories.",
        "",
    ]
    for memory in memories:
        lines.append(f"- ({memory.type}, scope={memory.scope.key()}, slot={memory.slot}) {memory.content}")
    return "\n".join(lines)


def build_context_json(memories: Iterable[MemoryRecord]) -> str:
    return json.dumps([memory.to_dict() for memory in memories], ensure_ascii=False, indent=2)
