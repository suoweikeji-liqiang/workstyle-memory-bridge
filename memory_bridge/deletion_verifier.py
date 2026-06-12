"""Deletion verification for WASC-style repeatable tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .context_builder import ContextCriteria, build_context_markdown, select_memories
from .exporters import managed_section
from .store import MemoryStore


@dataclass
class DeletionVerificationReport:
    memory_id: str
    checks: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def pass_check(self, message: str) -> None:
        self.checks.append(f"PASS: {message}")

    def fail_check(self, message: str) -> None:
        self.failures.append(f"FAIL: {message}")

    def note(self, message: str) -> None:
        self.notes.append(f"NOTE: {message}")

    def text(self) -> str:
        lines = [f"Deletion verification for {self.memory_id}"]
        lines.extend(self.checks)
        lines.extend(self.failures)
        lines.extend(self.notes)
        lines.append("Verification: PASS" if self.ok else "Verification: FAIL")
        return "\n".join(lines)


def verify_deleted_memory(
    store: MemoryStore,
    memory_id: str,
    criteria: ContextCriteria,
    limit: int = 12,
) -> DeletionVerificationReport:
    report = DeletionVerificationReport(memory_id=memory_id)
    record = store.get(memory_id)
    if record is None:
        report.fail_check("memory does not exist, so deletion cannot be verified")
        return report

    if record.status == "deleted":
        report.pass_check("memory status is deleted")
    else:
        report.fail_check(f"memory status is {record.status!r}, not deleted")

    active = store.list(status="active")
    if all(item.id != memory_id for item in active):
        report.pass_check("memory is absent from active memory list")
    else:
        report.fail_check("memory is still present in active memory list")

    selected = select_memories(store, criteria, limit=limit)
    if all(item.id != memory_id for item in selected):
        report.pass_check("memory is absent from build-context selection")
    else:
        report.fail_check("memory is still selected for build-context")

    context_text = build_context_markdown(selected)
    if memory_id not in context_text and record.content not in context_text:
        report.pass_check("memory content/id are absent from build-context output")
    else:
        report.fail_check("memory content/id still appear in build-context output")

    claude_projection = managed_section(selected, target="claude")
    codex_projection = managed_section(selected, target="codex")
    if memory_id not in claude_projection and record.content not in claude_projection:
        report.pass_check("memory is absent from Claude export projection")
    else:
        report.fail_check("memory still appears in Claude export projection")
    if memory_id not in codex_projection and record.content not in codex_projection:
        report.pass_check("memory is absent from Codex export projection")
    else:
        report.fail_check("memory still appears in Codex export projection")

    # Honest disclosure: one projection cannot be checked from here. MCP server
    # instructions are computed at session start, so a session opened before
    # this deletion still holds the old snapshot until its next handshake; the
    # instructions text itself tells hosts the store is authoritative.
    report.note(
        "MCP server instructions are a session start snapshot: sessions opened "
        "before this deletion may still carry the memory until their next "
        "handshake. In-session, hosts are instructed to treat the store as "
        "authoritative over the snapshot."
    )

    return report
