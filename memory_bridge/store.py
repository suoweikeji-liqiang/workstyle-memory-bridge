"""SQLite store for memory records, source evidence, and audit events."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .schemas import EvidenceEvent, EvidenceRef, MemoryRecord, utc_now

DEFAULT_DB_PATH = Path(os.environ.get("MEMORY_BRIDGE_DB", "~/.memory_bridge/memory_bridge.sqlite")).expanduser()


class MemoryStore:
    def __init__(self, path: Optional[str | Path] = None) -> None:
        self.path = Path(path).expanduser() if path else DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                layer TEXT NOT NULL DEFAULT 'L1_atom',
                scope_json TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                slot TEXT NOT NULL,
                content TEXT NOT NULL,
                rationale TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,
                supersedes TEXT,
                valid_from TEXT NOT NULL,
                valid_until TEXT,
                created_from_json TEXT NOT NULL,
                source_event_id TEXT,
                evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                last_used_at TEXT,
                usage_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memories_active_slot_scope
                ON memories(status, slot, scope_key);

            CREATE TABLE IF NOT EXISTS memory_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                memory_id TEXT,
                before_json TEXT,
                after_json TEXT,
                actor TEXT,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS evidence_events (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                text TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self._ensure_memory_columns()
        self.conn.commit()

    def _ensure_memory_columns(self) -> None:
        existing = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(memories)").fetchall()
        }
        additions = {
            "layer": "ALTER TABLE memories ADD COLUMN layer TEXT NOT NULL DEFAULT 'L1_atom'",
            "source_event_id": "ALTER TABLE memories ADD COLUMN source_event_id TEXT",
            "evidence_refs_json": "ALTER TABLE memories ADD COLUMN evidence_refs_json TEXT NOT NULL DEFAULT '[]'",
        }
        for column, statement in additions.items():
            if column not in existing:
                self.conn.execute(statement)

    def reset(self, actor: str = "system", note: str = "reset memory") -> None:
        self.conn.execute("DELETE FROM memories")
        self.conn.execute("DELETE FROM memory_events")
        self.conn.execute("DELETE FROM evidence_events")
        self.conn.execute(
            "INSERT INTO memory_events(timestamp, action, actor, note) VALUES (?, ?, ?, ?)",
            (utc_now(), "reset", actor, note),
        )
        self.conn.commit()

    def create_evidence(
        self,
        kind: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
    ) -> EvidenceEvent:
        event = EvidenceEvent(
            id=event_id or f"ev_{uuid.uuid4().hex[:12]}",
            kind=kind,
            text=text,
            metadata=dict(metadata or {}),
        )
        event.validate()
        self.conn.execute(
            """
            INSERT INTO evidence_events(id, kind, text, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.kind,
                event.text,
                json.dumps(event.metadata, ensure_ascii=False),
                event.created_at,
            ),
        )
        self.conn.commit()
        return event

    def evidence_ref_for(self, event: EvidenceEvent) -> EvidenceRef:
        return event.ref()

    def get_evidence(self, event_id: str) -> Optional[EvidenceEvent]:
        row = self.conn.execute("SELECT * FROM evidence_events WHERE id = ?", (event_id,)).fetchone()
        return self._row_to_evidence(row) if row else None

    def evidence_events(self, limit: int = 100) -> List[EvidenceEvent]:
        rows = self.conn.execute(
            "SELECT * FROM evidence_events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_evidence(row) for row in rows]

    def insert(self, record: MemoryRecord, actor: str = "system", note: str = "insert") -> None:
        record.validate()
        data = record.to_dict()
        self.conn.execute(
            """
            INSERT INTO memories (
                id, type, layer, scope_json, scope_key, slot, content, rationale, confidence,
                status, supersedes, valid_from, valid_until, created_from_json,
                source_event_id, evidence_refs_json,
                last_used_at, usage_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.type,
                record.layer,
                json.dumps(record.scope.to_dict(), ensure_ascii=False),
                record.scope.key(),
                record.slot,
                record.content,
                record.rationale,
                record.confidence,
                record.status,
                record.supersedes,
                record.valid_from,
                record.valid_until,
                json.dumps(record.created_from.to_dict(), ensure_ascii=False),
                record.source_event_id,
                json.dumps([ref.to_dict() for ref in record.evidence_refs], ensure_ascii=False),
                record.last_used_at,
                record.usage_count,
                record.created_at,
                record.updated_at,
            ),
        )
        self._event("insert", record.id, None, data, actor, note)
        self.conn.commit()

    def list(self, status: Optional[str] = "active") -> List[MemoryRecord]:
        if status == "all" or status is None:
            rows = self.conn.execute("SELECT * FROM memories ORDER BY updated_at DESC").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM memories WHERE status = ? ORDER BY updated_at DESC", (status,)
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def find_active_by_slot_scope(self, slot: str, scope_key: str) -> List[MemoryRecord]:
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE status = 'active' AND slot = ? AND scope_key = ? ORDER BY updated_at DESC",
            (slot, scope_key),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def update(self, record: MemoryRecord, actor: str = "system", note: str = "update") -> None:
        before = self.get(record.id)
        record.updated_at = utc_now()
        record.validate()
        self.conn.execute(
            """
            UPDATE memories SET
                type = ?, layer = ?, scope_json = ?, scope_key = ?, slot = ?, content = ?, rationale = ?,
                confidence = ?, status = ?, supersedes = ?, valid_from = ?, valid_until = ?,
                created_from_json = ?, source_event_id = ?, evidence_refs_json = ?,
                last_used_at = ?, usage_count = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                record.type,
                record.layer,
                json.dumps(record.scope.to_dict(), ensure_ascii=False),
                record.scope.key(),
                record.slot,
                record.content,
                record.rationale,
                record.confidence,
                record.status,
                record.supersedes,
                record.valid_from,
                record.valid_until,
                json.dumps(record.created_from.to_dict(), ensure_ascii=False),
                record.source_event_id,
                json.dumps([ref.to_dict() for ref in record.evidence_refs], ensure_ascii=False),
                record.last_used_at,
                record.usage_count,
                record.updated_at,
                record.id,
            ),
        )
        self._event(
            "update",
            record.id,
            before.to_dict() if before else None,
            record.to_dict(),
            actor,
            note,
        )
        self.conn.commit()

    def soft_delete(self, memory_id: str, actor: str = "system", note: str = "delete") -> Optional[MemoryRecord]:
        record = self.get(memory_id)
        if not record:
            return None
        before = record.to_dict()
        record.status = "deleted"
        record.valid_until = utc_now()
        record.updated_at = utc_now()
        self.update(record, actor=actor, note=note)
        self._event("delete", memory_id, before, record.to_dict(), actor, note)
        self.conn.commit()
        return record

    def mark_used(self, records: Iterable[MemoryRecord]) -> None:
        now = utc_now()
        for record in records:
            self.conn.execute(
                "UPDATE memories SET last_used_at = ?, usage_count = usage_count + 1, updated_at = ? WHERE id = ?",
                (now, now, record.id),
            )
        self.conn.commit()

    def events(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM memory_events ORDER BY event_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord.from_dict(
            {
                "id": row["id"],
                "type": row["type"],
                "layer": row["layer"],
                "scope": json.loads(row["scope_json"]),
                "slot": row["slot"],
                "content": row["content"],
                "rationale": row["rationale"],
                "confidence": row["confidence"],
                "status": row["status"],
                "supersedes": row["supersedes"],
                "valid_from": row["valid_from"],
                "valid_until": row["valid_until"],
                "created_from": json.loads(row["created_from_json"]),
                "source_event_id": row["source_event_id"],
                "evidence_refs": json.loads(row["evidence_refs_json"] or "[]"),
                "last_used_at": row["last_used_at"],
                "usage_count": row["usage_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    def _row_to_evidence(self, row: sqlite3.Row) -> EvidenceEvent:
        return EvidenceEvent.from_dict(
            {
                "id": row["id"],
                "kind": row["kind"],
                "text": row["text"],
                "metadata": json.loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
        )

    def _event(
        self,
        action: str,
        memory_id: Optional[str],
        before: Optional[Dict[str, Any]],
        after: Optional[Dict[str, Any]],
        actor: str,
        note: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO memory_events(timestamp, action, memory_id, before_json, after_json, actor, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now(),
                action,
                memory_id,
                json.dumps(before, ensure_ascii=False) if before else None,
                json.dumps(after, ensure_ascii=False) if after else None,
                actor,
                note,
            ),
        )
