from memory_bridge.context_builder import ContextCriteria, select_memories
from memory_bridge.resolver import apply_draft
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def draft(content: str, slot: str = "technical_plan_structure") -> MemoryDraft:
    return MemoryDraft(
        type="workflow",
        scope=Scope(level="task_type", task_type="technical_planning"),
        slot=slot,
        content=content,
        rationale="explicit user feedback",
        confidence=0.9,
    )


def test_same_slot_scope_supersedes_old_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")

    first = apply_draft(store, draft("先讲北极星和边界，再给 MVP。"))
    assert len(first.inserted) == 1
    first_id = first.inserted[0].id

    second = apply_draft(store, draft("先讲北极星和边界，再给 MVP；风险放在 MVP 后。"))
    assert len(second.inserted) == 1
    assert len(second.superseded) == 1
    assert second.superseded[0].id == first_id

    active = store.list(status="active")
    superseded = store.list(status="superseded")
    assert len(active) == 1
    assert len(superseded) == 1
    assert active[0].supersedes == first_id


def test_reset_clears_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    apply_draft(store, draft("先讲北极星。"))
    assert len(store.list(status="active")) == 1
    store.reset()
    assert store.list(status="active") == []


def test_build_context_uses_explicit_scope(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    apply_draft(store, draft("技术方案先讲北极星。"))

    matched = select_memories(store, ContextCriteria(task_type="technical_planning"))
    missed = select_memories(store, ContextCriteria(task_type="code_review"))

    assert len(matched) == 1
    assert missed == []
