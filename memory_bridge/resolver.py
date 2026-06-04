"""Conflict resolution and memory lifecycle operations.

This module resolves conflicts by explicit schema keys: slot + scope_key.
It must not inspect natural-language content to guess user intent.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from .schemas import MemoryDraft, MemoryRecord, utc_now
from .store import MemoryStore


@dataclass
class MutationResult:
    inserted: List[MemoryRecord] = field(default_factory=list)
    superseded: List[MemoryRecord] = field(default_factory=list)
    deleted: List[MemoryRecord] = field(default_factory=list)

    def changed(self) -> bool:
        return bool(self.inserted or self.superseded or self.deleted)


def apply_draft(store: MemoryStore, draft: MemoryDraft, actor: str = "user") -> MutationResult:
    """Insert a draft and supersede any active memory with same slot+scope.

    This is the core anti-accumulation mechanism: one active memory per
    slot/scope pair unless the user explicitly chooses a different slot/scope.
    """
    result = MutationResult()
    now = utc_now()
    active_conflicts = store.find_active_by_slot_scope(draft.slot, draft.scope.key())
    supersedes_id: Optional[str] = None

    for old in active_conflicts:
        old.status = "superseded"
        old.valid_until = now
        store.update(old, actor=actor, note="superseded by newer memory with same slot+scope")
        result.superseded.append(old)
        if supersedes_id is None:
            supersedes_id = old.id

    new_record = MemoryRecord.from_draft(
        draft,
        memory_id=f"mem_{uuid.uuid4().hex[:12]}",
        supersedes=supersedes_id,
        valid_from=now,
    )
    store.insert(new_record, actor=actor, note="memory draft accepted")
    result.inserted.append(new_record)
    return result


def apply_drafts(store: MemoryStore, drafts: List[MemoryDraft], actor: str = "user") -> MutationResult:
    aggregate = MutationResult()
    for draft in drafts:
        result = apply_draft(store, draft, actor=actor)
        aggregate.inserted.extend(result.inserted)
        aggregate.superseded.extend(result.superseded)
        aggregate.deleted.extend(result.deleted)
    return aggregate
