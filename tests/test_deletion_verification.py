from memory_bridge.context_builder import ContextCriteria
from memory_bridge.deletion_verifier import verify_deleted_memory
from memory_bridge.resolver import apply_draft
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def test_verify_deleted_memory_checks_context_and_exports(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    result = apply_draft(
        store,
        MemoryDraft(
            type="workflow",
            scope=Scope(level="task_type", task_type="technical_planning"),
            slot="technical_plan_structure",
            content="技术方案先讲北极星。",
            rationale="explicit user feedback",
            confidence=0.9,
        ),
    )
    memory_id = result.inserted[0].id

    failing = verify_deleted_memory(store, memory_id, ContextCriteria(task_type="technical_planning"))
    assert not failing.ok

    store.soft_delete(memory_id)
    passing = verify_deleted_memory(store, memory_id, ContextCriteria(task_type="technical_planning"))
    assert passing.ok
    assert "Verification: PASS" in passing.text()


def test_report_discloses_instructions_snapshot_limit(tmp_path):
    """verify-deletion proves the store, context, and export projections are
    clean — but MCP server instructions are computed at session start, so a
    session opened before the deletion still holds the old snapshot until its
    next handshake. The report must disclose this projection honestly instead
    of overclaiming."""
    store = MemoryStore(tmp_path / "memory.sqlite")
    result = apply_draft(
        store,
        MemoryDraft(
            type="workflow",
            scope=Scope(level="task_type", task_type="technical_planning"),
            slot="technical_plan_structure",
            content="技术方案先讲北极星。",
            rationale="explicit user feedback",
            confidence=0.9,
        ),
    )
    memory_id = result.inserted[0].id
    store.soft_delete(memory_id)
    report = verify_deleted_memory(store, memory_id, ContextCriteria(task_type="technical_planning"))
    text = report.text()
    assert "NOTE" in text
    assert "session start" in text
    assert report.ok  # the disclosure is a note, not a failure
