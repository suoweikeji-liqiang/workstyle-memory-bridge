from memory_bridge.context_builder import ContextCriteria, build_context_markdown, select_memories
from memory_bridge.resolver import apply_draft
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def test_deleted_memory_is_not_selected_or_exported(tmp_path):
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

    before = select_memories(store, ContextCriteria(task_type="technical_planning"))
    assert len(before) == 1

    store.soft_delete(memory_id)
    after = select_memories(store, ContextCriteria(task_type="technical_planning"))
    assert after == []

    markdown = build_context_markdown(after)
    assert "技术方案先讲北极星" not in markdown


def test_global_memory_matches_any_context(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    apply_draft(
        store,
        MemoryDraft(
            type="preference",
            scope=Scope(level="global"),
            slot="answer_style",
            content="默认先给结论，再给细节。",
            rationale="explicit user feedback",
            confidence=0.9,
        ),
    )
    selected = select_memories(store, ContextCriteria(task_type="code_review", project="demo"))
    assert len(selected) == 1
