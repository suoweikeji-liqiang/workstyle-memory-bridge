"""Silent non-recall must be visible.

Global memories match every call, so a call that omits (or drifts on) a scoped
dimension still returns a non-empty result — and nothing told the caller that
scoped memories existed at all. The empty-branch hint never fires once a single
global memory exists. Every response now reports the scoped memories it did NOT
match, with their exact stored scope values, so the host AI can re-call with the
right key. Matching stays exact — enumeration only, no fuzzy matching.
"""

from memory_bridge.cli import main
from memory_bridge.context_builder import (
    ContextCriteria,
    respond_to_context_request,
    unmatched_scope_summary,
)
from memory_bridge.resolver import apply_drafts
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(str(tmp_path / "hint.sqlite"))


def _seed(store: MemoryStore) -> None:
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="preference",
                scope=Scope(level="global"),
                slot="doc-location",
                content="文档放项目目录",
                rationale="r",
                confidence=0.9,
            ),
            MemoryDraft(
                type="workflow",
                scope=Scope(level="task_type", task_type="bug-fix"),
                slot="bugfix-structure",
                content="现象 -> 原因 -> 修法",
                rationale="r",
                confidence=0.9,
            ),
            MemoryDraft(
                type="workflow",
                scope=Scope(level="task_type", task_type="feature-development"),
                slot="feature-restraint",
                content="能不加就不加",
                rationale="r",
                confidence=0.9,
            ),
        ],
        actor="test",
    )


def test_global_only_call_reports_unmatched_scoped_memories(tmp_path):
    """The incident this guards against: a call with no task_type returns the
    globals 'successfully' while scoped memories silently never fire."""
    store = _store(tmp_path)
    _seed(store)
    text = respond_to_context_request(store, ContextCriteria(), limit=12, actor="test")
    assert "文档放项目目录" in text  # globals still served
    assert "did NOT match" in text
    assert "bug-fix" in text
    assert "feature-development" in text


def test_matched_dimension_value_not_counted_as_unmatched(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    count, values = unmatched_scope_summary(store, ContextCriteria(task_type="bug-fix"))
    assert count == 1  # only the feature-development memory is out of reach
    assert values == {"task_type": ["feature-development"]}


def test_variant_value_drift_surfaces_stored_value_in_nonempty_response(tmp_path):
    """Drift case: globals make the response non-empty, so the old empty-branch
    hint never fires; the appendix must carry the stored value instead."""
    store = _store(tmp_path)
    _seed(store)
    text = respond_to_context_request(
        store, ContextCriteria(task_type="bugfix"), limit=12, actor="test"
    )
    assert "bug-fix" in text


def test_no_appendix_when_everything_matched(tmp_path):
    store = _store(tmp_path)
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="preference",
                scope=Scope(level="global"),
                slot="s",
                content="c",
                rationale="r",
                confidence=0.9,
            )
        ],
        actor="test",
    )
    text = respond_to_context_request(store, ContextCriteria(), limit=12, actor="test")
    assert "did NOT match" not in text


def test_empty_store_keeps_plain_miss_message(tmp_path):
    store = _store(tmp_path)
    text = respond_to_context_request(store, ContextCriteria(), limit=12, actor="test")
    assert text == "No active workstyle memories matched this context."


def test_cli_build_context_carries_the_hint(tmp_path, capsys):
    db = str(tmp_path / "cli.sqlite")
    _seed(MemoryStore(db))
    assert main(["--db", db, "build-context"]) == 0
    out = capsys.readouterr().out
    assert "feature-development" in out
