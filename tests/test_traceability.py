from memory_bridge.resolver import apply_draft
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def test_memory_records_keep_source_evidence(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    event = store.create_evidence(
        "user_feedback",
        "以后给我技术方案时，先讲北极星和边界。",
        metadata={"task_type": "technical_planning"},
    )
    ref = store.evidence_ref_for(event)
    result = apply_draft(
        store,
        MemoryDraft(
            type="workflow",
            layer="L1_atom",
            scope=Scope(level="task_type", task_type="technical_planning"),
            slot="technical_plan_structure",
            content="技术方案先讲北极星和边界。",
            rationale="explicit user feedback",
            confidence=0.9,
            source_event_id=event.id,
            evidence_refs=[ref],
        ),
    )

    memory = store.get(result.inserted[0].id)
    assert memory is not None
    assert memory.layer == "L1_atom"
    assert memory.source_event_id == event.id
    assert memory.evidence_refs[0].id == event.id

    loaded_event = store.get_evidence(event.id)
    assert loaded_event is not None
    assert "北极星" in loaded_event.text


def test_reset_clears_evidence_events(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.create_evidence("user_feedback", "test", metadata={})
    assert len(store.evidence_events()) == 1
    store.reset()
    assert store.evidence_events() == []
