"""Preview governed memory edits and deletes before mutation.

The host AI may understand a user's natural-language request and choose the
candidate memory IDs. This module does not interpret natural language; it only
turns explicit IDs and structured edit fields into an inspectable preview.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .schemas import MemoryRecord, Scope
from .store import MemoryStore


EDIT_FIELDS = {
    "content",
    "rationale",
    "slot",
    "type",
    "memory_type",
    "layer",
    "confidence",
    "status",
    "scope",
    "scope_json",
}


def _memory_card(store: MemoryStore, memory: MemoryRecord) -> Dict[str, Any]:
    evidence = []
    for ref in memory.evidence_refs:
        event = store.get_evidence(ref.id)
        evidence.append(event.to_dict() if event else ref.to_dict())
    return {
        "id": memory.id,
        "status": memory.status,
        "type": memory.type,
        "layer": memory.layer,
        "scope": memory.scope.to_dict(),
        "scope_key": memory.scope.key(),
        "slot": memory.slot,
        "content": memory.content,
        "rationale": memory.rationale,
        "confidence": memory.confidence,
        "source_event_id": memory.source_event_id,
        "evidence": evidence,
        "usage_count": memory.usage_count,
        "last_used_at": memory.last_used_at,
        "updated_at": memory.updated_at,
    }


def preview_delete(
    store: MemoryStore,
    memory_ids: Iterable[str],
    user_request: Optional[str] = None,
) -> Dict[str, Any]:
    candidates = []
    missing = []
    for memory_id in memory_ids:
        memory = store.get(memory_id)
        if memory is None:
            missing.append(memory_id)
            continue
        card = _memory_card(store, memory)
        if memory.status != "active":
            card["warning"] = f"memory status is {memory.status}; deleting it may be redundant"
        candidates.append(card)
    return {
        "action": "delete",
        "dry_run": True,
        "user_request": user_request,
        "candidates": candidates,
        "missing_ids": missing,
        "will_write": False,
        "confirmation_required": True,
        "confirm_instruction": (
            "Show these candidates and evidence to the user. If the user confirms, "
            "call delete_memory / memory-bridge delete for each intended ID."
        ),
    }


def _apply_updates(record: MemoryRecord, updates: Dict[str, Any]) -> MemoryRecord:
    edited = MemoryRecord.from_dict(record.to_dict())
    clean = {key: value for key, value in updates.items() if value is not None}
    unsupported = sorted(set(clean) - EDIT_FIELDS)
    if unsupported:
        raise ValueError(f"Unsupported edit field(s): {', '.join(unsupported)}")

    if "content" in clean:
        edited.content = str(clean["content"])
    if "rationale" in clean:
        edited.rationale = str(clean["rationale"])
    if "slot" in clean:
        edited.slot = str(clean["slot"])
    if "type" in clean:
        edited.type = str(clean["type"])
    if "memory_type" in clean:
        edited.type = str(clean["memory_type"])
    if "layer" in clean:
        edited.layer = str(clean["layer"])
    if "confidence" in clean:
        edited.confidence = float(clean["confidence"])
    if "status" in clean:
        edited.status = str(clean["status"])
    if "scope" in clean:
        edited.scope = Scope.from_dict(dict(clean["scope"]))
    if "scope_json" in clean:
        edited.scope = Scope.from_dict(dict(clean["scope_json"]))
    edited.validate()
    return edited


def preview_edit(
    store: MemoryStore,
    memory_id: str,
    updates: Dict[str, Any],
    user_request: Optional[str] = None,
) -> Dict[str, Any]:
    memory = store.get(memory_id)
    if memory is None:
        return {
            "action": "edit",
            "dry_run": True,
            "user_request": user_request,
            "candidate": None,
            "missing_ids": [memory_id],
            "will_write": False,
            "confirmation_required": True,
        }
    edited = _apply_updates(memory, updates)
    return {
        "action": "edit",
        "dry_run": True,
        "user_request": user_request,
        "before": _memory_card(store, memory),
        "after": edited.to_dict(),
        "will_write": False,
        "confirmation_required": True,
        "confirm_instruction": (
            "Show the before/after diff to the user. If the user confirms, call "
            "edit_memory / memory-bridge edit with the same structured fields."
        ),
    }


def format_control_preview(preview: Dict[str, Any]) -> str:
    action = preview.get("action")
    lines = [
        f"Memory control preview: {action}",
        "DRY RUN - nothing written.",
    ]
    if preview.get("user_request"):
        lines.append(f"User request: {preview['user_request']}")

    missing = preview.get("missing_ids") or []
    if missing:
        lines.append("Missing IDs: " + ", ".join(missing))

    if action == "delete":
        candidates = preview.get("candidates") or []
        if not candidates:
            lines.append("No delete candidates found.")
        for index, item in enumerate(candidates, start=1):
            lines.append(f"{index}. {item['id']} :: {item['slot']}")
            lines.append(f"   status/type/scope: {item['status']} / {item['type']} / {item['scope_key']}")
            lines.append(f"   content: {item['content']}")
            lines.append(f"   evidence: {item.get('source_event_id') or '-'}")
            if item.get("warning"):
                lines.append(f"   warning: {item['warning']}")
    elif action == "edit" and preview.get("before"):
        before = preview["before"]
        after = preview["after"]
        lines.append(f"Candidate: {before['id']} :: {before['slot']}")
        for field in ("content", "rationale", "slot", "type", "layer", "confidence", "status"):
            if before.get(field) != after.get(field):
                lines.append(f"- {field}: {before.get(field)!r} -> {after.get(field)!r}")
        if before.get("scope") != after.get("scope"):
            lines.append(f"- scope: {before.get('scope')} -> {after.get('scope')}")
    else:
        lines.append("No edit candidate found.")

    if preview.get("confirm_instruction"):
        lines.extend(["", preview["confirm_instruction"]])
    return "\n".join(lines)
