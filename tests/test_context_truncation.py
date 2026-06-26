"""Truncation must be observable, not silent.

When more memories match a scope than the limit allows, build_context shows the
top ones AND reports how many were withheld, so a caller never mistakes a capped
view for the whole picture.
"""

from memory_bridge.context_builder import (
    ContextCriteria,
    build_context_markdown,
    select_memories,
    select_memories_with_total,
)
from memory_bridge.resolver import apply_drafts
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def _seed_global(store: MemoryStore, count: int) -> None:
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="preference",
                scope=Scope(level="global"),
                slot=f"slot_{i}",
                content=f"pref {i}",
                rationale="r",
                confidence=0.9,
            )
            for i in range(count)
        ],
        actor="test",
    )


def test_total_reflects_matches_before_limit(tmp_path):
    store = MemoryStore(str(tmp_path / "t.sqlite"))
    _seed_global(store, 5)
    selected, total = select_memories_with_total(store, ContextCriteria(), limit=2)
    assert len(selected) == 2
    assert total == 5  # all five matched; only two shown


def test_markdown_reports_withheld_count(tmp_path):
    store = MemoryStore(str(tmp_path / "t.sqlite"))
    _seed_global(store, 5)
    selected, total = select_memories_with_total(store, ContextCriteria(), limit=2)
    rendered = build_context_markdown(selected, truncated_count=total - len(selected))
    assert "3 more" in rendered
    assert "JIT-ranked" in rendered
    assert "narrow the scope" in rendered


def test_no_note_when_nothing_withheld(tmp_path):
    store = MemoryStore(str(tmp_path / "t.sqlite"))
    _seed_global(store, 2)
    selected = select_memories(store, ContextCriteria(), limit=12)
    rendered = build_context_markdown(selected, truncated_count=0)
    assert "more memory" not in rendered


def test_jit_ranking_prefers_actionable_type_with_same_scope(tmp_path):
    store = MemoryStore(str(tmp_path / "t.sqlite"))
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="preference",
                scope=Scope(level="global"),
                slot="soft-style",
                content="Prefer concise answers",
                rationale="r",
                confidence=0.9,
            ),
            MemoryDraft(
                type="anti_preference",
                scope=Scope(level="global"),
                slot="avoid-style",
                content="Do not bury the answer under background",
                rationale="r",
                confidence=0.9,
            ),
        ],
        actor="test",
    )

    selected, _ = select_memories_with_total(store, ContextCriteria(), limit=1)

    assert selected[0].slot == "avoid-style"


def test_jit_ranking_keeps_scope_specificity_ahead_of_type(tmp_path):
    store = MemoryStore(str(tmp_path / "t.sqlite"))
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="anti_preference",
                scope=Scope(level="global"),
                slot="global-hard-rule",
                content="Global hard rule",
                rationale="r",
                confidence=1.0,
            ),
            MemoryDraft(
                type="fact",
                scope=Scope(level="task_type", task_type="bug-fix"),
                slot="bugfix-local-fact",
                content="Bug-fix local fact",
                rationale="r",
                confidence=0.2,
            ),
        ],
        actor="test",
    )

    selected, _ = select_memories_with_total(
        store, ContextCriteria(task_type="bug-fix"), limit=1
    )

    assert selected[0].slot == "bugfix-local-fact"


def test_jit_ranking_lightly_rotates_otherwise_equal_memories(tmp_path):
    store = MemoryStore(str(tmp_path / "t.sqlite"))
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="preference",
                scope=Scope(level="global"),
                slot="overused",
                content="Already seen often",
                rationale="r",
                confidence=0.9,
            ),
            MemoryDraft(
                type="preference",
                scope=Scope(level="global"),
                slot="fresh",
                content="Seen less often",
                rationale="r",
                confidence=0.9,
            ),
        ],
        actor="test",
    )
    overused = next(memory for memory in store.list(status="active") if memory.slot == "overused")
    overused.usage_count = 10
    store.update(overused, actor="test", note="seed usage")

    selected, _ = select_memories_with_total(store, ContextCriteria(), limit=1)

    assert selected[0].slot == "fresh"
