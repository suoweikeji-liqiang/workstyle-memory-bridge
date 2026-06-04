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
    assert "narrow the scope" in rendered


def test_no_note_when_nothing_withheld(tmp_path):
    store = MemoryStore(str(tmp_path / "t.sqlite"))
    _seed_global(store, 2)
    selected = select_memories(store, ContextCriteria(), limit=12)
    rendered = build_context_markdown(selected, truncated_count=0)
    assert "more memory" not in rendered
