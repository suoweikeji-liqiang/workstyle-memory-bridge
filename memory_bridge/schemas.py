"""Typed schemas for Workstyle Memory Bridge.

The project intentionally keeps semantic decisions outside deterministic code.
Allowed deterministic logic in this module: shape validation, status checks,
scope keys, evidence references, and serialization. Do not add content keyword
classifiers here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

MEMORY_TYPES = {
    "preference",
    "workflow",
    "project_rule",
    "temporary",
    "fact",
    "anti_preference",
}

SCOPE_LEVELS = {
    "global",
    "project",
    "tool",
    "task_type",
    "session",
    "product_user",
}

MEMORY_STATUSES = {"active", "superseded", "archived", "deleted"}

MEMORY_LAYERS = {
    "L1_atom",
    "L2_scenario",
    "L3_profile",
}

EVIDENCE_KINDS = {
    "user_feedback",
    "user_correction",
    "task_fragment",
    "manual_note",
    "system_import",
}

REQUIRED_SCOPE_FIELDS = {
    "project": "project",
    "tool": "tool",
    "task_type": "task_type",
    "session": "session_id",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ValidationError(ValueError):
    """Raised when a memory payload violates the schema."""


@dataclass(frozen=True)
class Scope:
    """Where a memory is allowed to apply.

    The scope is explicit metadata. It is not inferred by keyword matching.
    """

    level: str = "global"
    project: Optional[str] = None
    tool: Optional[str] = None
    task_type: Optional[str] = None
    session_id: Optional[str] = None
    product: Optional[str] = None
    domain: Optional[str] = None
    user_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "Scope":
        if not data:
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        clean = {k: v for k, v in data.items() if k in allowed}
        scope = cls(**clean)
        scope.validate()
        return scope

    def validate(self) -> None:
        if self.level not in SCOPE_LEVELS:
            raise ValidationError(f"Invalid scope.level: {self.level!r}")
        required = REQUIRED_SCOPE_FIELDS.get(self.level)
        if required and not getattr(self, required):
            raise ValidationError(f"scope.level={self.level!r} requires scope.{required}")
        if self.level == "product_user" and not (self.product or self.domain or self.user_id):
            raise ValidationError(
                "scope.level='product_user' requires at least one of product/domain/user_id"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "project": self.project,
            "tool": self.tool,
            "task_type": self.task_type,
            "session_id": self.session_id,
            "product": self.product,
            "domain": self.domain,
            "user_id": self.user_id,
        }

    def key(self) -> str:
        """Canonical key used for exact conflict resolution."""
        parts = [self.level]
        for attr in ("project", "tool", "task_type", "session_id", "product", "domain", "user_id"):
            value = getattr(self, attr)
            if value:
                parts.append(f"{attr}={value}")
        return "|".join(parts)

    def specificity(self) -> int:
        return sum(1 for v in self.to_dict().values() if v)


@dataclass
class CreatedFrom:
    session_id: Optional[str] = None
    message_excerpt: Optional[str] = None
    task_context: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "CreatedFrom":
        if not data:
            return cls()
        return cls(
            session_id=data.get("session_id"),
            message_excerpt=data.get("message_excerpt"),
            task_context=dict(data.get("task_context") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "message_excerpt": self.message_excerpt,
            "task_context": self.task_context,
        }


@dataclass(frozen=True)
class EvidenceRef:
    """A compact pointer from an abstract memory to its source event."""

    id: str
    kind: str
    excerpt: str
    created_at: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceRef":
        ref = cls(
            id=str(data.get("id") or ""),
            kind=str(data.get("kind") or "manual_note"),
            excerpt=str(data.get("excerpt") or ""),
            created_at=str(data.get("created_at") or utc_now()),
        )
        ref.validate()
        return ref

    def validate(self) -> None:
        if not self.id:
            raise ValidationError("evidence_ref.id is required")
        if self.kind not in EVIDENCE_KINDS:
            raise ValidationError(f"Invalid evidence_ref.kind: {self.kind!r}")
        if not self.created_at:
            raise ValidationError("evidence_ref.created_at is required")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "excerpt": self.excerpt,
            "created_at": self.created_at,
        }


@dataclass
class EvidenceEvent:
    """L0 source event: original feedback, correction, or task fragment."""

    id: str
    kind: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceEvent":
        event = cls(
            id=str(data.get("id") or ""),
            kind=str(data.get("kind") or "user_feedback"),
            text=str(data.get("text") or ""),
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at") or utc_now()),
        )
        event.validate()
        return event

    def validate(self) -> None:
        if not self.id:
            raise ValidationError("evidence_event.id is required")
        if self.kind not in EVIDENCE_KINDS:
            raise ValidationError(f"Invalid evidence_event.kind: {self.kind!r}")
        if not self.text:
            raise ValidationError("evidence_event.text is required")

    def ref(self, max_excerpt_chars: int = 160) -> EvidenceRef:
        excerpt = self.text[:max_excerpt_chars]
        return EvidenceRef(id=self.id, kind=self.kind, excerpt=excerpt, created_at=self.created_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class MemoryDraft:
    """Candidate memory produced by a semantic extractor or explicit user input."""

    type: str
    scope: Scope
    slot: str
    content: str
    rationale: str
    confidence: float = 0.8
    layer: str = "L1_atom"
    created_from: CreatedFrom = field(default_factory=CreatedFrom)
    valid_until: Optional[str] = None
    source_event_id: Optional[str] = None
    evidence_refs: List[EvidenceRef] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryDraft":
        draft = cls(
            type=data.get("type", ""),
            layer=data.get("layer", "L1_atom"),
            scope=Scope.from_dict(data.get("scope")),
            slot=data.get("slot", ""),
            content=data.get("content", ""),
            rationale=data.get("rationale", ""),
            confidence=float(data.get("confidence", 0.8)),
            created_from=CreatedFrom.from_dict(data.get("created_from")),
            valid_until=data.get("valid_until"),
            source_event_id=data.get("source_event_id"),
            evidence_refs=[EvidenceRef.from_dict(item) for item in data.get("evidence_refs", [])],
        )
        draft.validate()
        return draft

    def validate(self) -> None:
        if self.type not in MEMORY_TYPES:
            raise ValidationError(f"Invalid memory.type: {self.type!r}")
        if self.layer not in MEMORY_LAYERS:
            raise ValidationError(f"Invalid memory.layer: {self.layer!r}")
        self.scope.validate()
        if not self.slot or not isinstance(self.slot, str):
            raise ValidationError("memory.slot is required")
        if not self.content or not isinstance(self.content, str):
            raise ValidationError("memory.content is required")
        if not self.rationale or not isinstance(self.rationale, str):
            raise ValidationError("memory.rationale is required")
        if not 0 <= self.confidence <= 1:
            raise ValidationError("memory.confidence must be between 0 and 1")
        for ref in self.evidence_refs:
            ref.validate()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "layer": self.layer,
            "scope": self.scope.to_dict(),
            "slot": self.slot,
            "content": self.content,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "created_from": self.created_from.to_dict(),
            "valid_until": self.valid_until,
            "source_event_id": self.source_event_id,
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
        }


@dataclass
class MemoryRecord:
    id: str
    type: str
    scope: Scope
    slot: str
    content: str
    rationale: str
    confidence: float
    layer: str = "L1_atom"
    status: str = "active"
    supersedes: Optional[str] = None
    valid_from: str = field(default_factory=utc_now)
    valid_until: Optional[str] = None
    created_from: CreatedFrom = field(default_factory=CreatedFrom)
    source_event_id: Optional[str] = None
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    last_used_at: Optional[str] = None
    usage_count: int = 0
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_draft(
        cls,
        draft: MemoryDraft,
        memory_id: str,
        supersedes: Optional[str] = None,
        valid_from: Optional[str] = None,
    ) -> "MemoryRecord":
        return cls(
            id=memory_id,
            type=draft.type,
            layer=draft.layer,
            scope=draft.scope,
            slot=draft.slot,
            content=draft.content,
            rationale=draft.rationale,
            confidence=draft.confidence,
            status="active",
            supersedes=supersedes,
            valid_from=valid_from or utc_now(),
            valid_until=draft.valid_until,
            created_from=draft.created_from,
            source_event_id=draft.source_event_id,
            evidence_refs=list(draft.evidence_refs),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryRecord":
        record = cls(
            id=data["id"],
            type=data["type"],
            layer=data.get("layer", "L1_atom"),
            scope=Scope.from_dict(data.get("scope")),
            slot=data["slot"],
            content=data["content"],
            rationale=data.get("rationale", ""),
            confidence=float(data.get("confidence", 0.8)),
            status=data.get("status", "active"),
            supersedes=data.get("supersedes"),
            valid_from=data.get("valid_from") or utc_now(),
            valid_until=data.get("valid_until"),
            created_from=CreatedFrom.from_dict(data.get("created_from")),
            source_event_id=data.get("source_event_id"),
            evidence_refs=[EvidenceRef.from_dict(item) for item in data.get("evidence_refs", [])],
            last_used_at=data.get("last_used_at"),
            usage_count=int(data.get("usage_count", 0)),
            created_at=data.get("created_at") or utc_now(),
            updated_at=data.get("updated_at") or utc_now(),
        )
        record.validate()
        return record

    def validate(self) -> None:
        if self.status not in MEMORY_STATUSES:
            raise ValidationError(f"Invalid memory.status: {self.status!r}")
        MemoryDraft(
            type=self.type,
            layer=self.layer,
            scope=self.scope,
            slot=self.slot,
            content=self.content,
            rationale=self.rationale or "record validation",
            confidence=self.confidence,
            created_from=self.created_from,
            valid_until=self.valid_until,
            source_event_id=self.source_event_id,
            evidence_refs=self.evidence_refs,
        ).validate()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "layer": self.layer,
            "scope": self.scope.to_dict(),
            "scope_key": self.scope.key(),
            "slot": self.slot,
            "content": self.content,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "status": self.status,
            "supersedes": self.supersedes,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "created_from": self.created_from.to_dict(),
            "source_event_id": self.source_event_id,
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
            "last_used_at": self.last_used_at,
            "usage_count": self.usage_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


MEMORY_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["memories"],
    "properties": {
        "memories": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "scope", "slot", "content", "rationale", "confidence"],
                "properties": {
                    "type": {"enum": sorted(MEMORY_TYPES)},
                    "layer": {"enum": sorted(MEMORY_LAYERS)},
                    "scope": {
                        "type": "object",
                        "required": ["level"],
                        "properties": {
                            "level": {"enum": sorted(SCOPE_LEVELS)},
                            "project": {"type": ["string", "null"]},
                            "tool": {"type": ["string", "null"]},
                            "task_type": {"type": ["string", "null"]},
                            "session_id": {"type": ["string", "null"]},
                            "product": {"type": ["string", "null"]},
                            "domain": {"type": ["string", "null"]},
                            "user_id": {"type": ["string", "null"]},
                        },
                    },
                    "slot": {"type": "string"},
                    "content": {"type": "string"},
                    "rationale": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "valid_until": {"type": ["string", "null"]},
                    "created_from": {"type": "object"},
                    "source_event_id": {"type": ["string", "null"]},
                    "evidence_refs": {"type": "array"},
                },
            },
        }
    },
}


def parse_memory_drafts(payload: Dict[str, Any]) -> List[MemoryDraft]:
    """Parse a JSON payload containing one or more memory drafts."""
    if "memories" in payload:
        raw_items = payload["memories"]
    else:
        raw_items = [payload]
    if not isinstance(raw_items, Iterable):
        raise ValidationError("payload.memories must be a list")
    drafts = [MemoryDraft.from_dict(dict(item)) for item in raw_items]
    return drafts
