"""Recall failures must become facts the host can act on.

Doctor cross-references the read-path audit (context_requests) with stored
scopes and reports two kinds of facts: scoped memories that had opportunities
but were never returned, and requested scope values that matched nothing.
Facts only — no similarity scoring, no value mapping. The host AI / user judges
whether a requested label and a stored value name the same kind of work, and
any fix goes through the governed edit path (dry-run, confirm, supersede).
"""

from memory_bridge.context_builder import ContextCriteria, respond_to_context_request
from memory_bridge.doctor import run_doctor
from memory_bridge.resolver import apply_drafts
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(str(tmp_path / "doc.sqlite"))


def _scoped(task_type: str, slot: str) -> MemoryDraft:
    return MemoryDraft(
        type="workflow",
        scope=Scope(level="task_type", task_type=task_type),
        slot=slot,
        content=f"memory for {task_type}",
        rationale="r",
        confidence=0.9,
    )


def test_dead_scoped_memory_is_flagged_with_opportunity_count(tmp_path):
    store = _store(tmp_path)
    apply_drafts(store, [_scoped("feature-development", "restraint")], actor="test")
    respond_to_context_request(store, ContextCriteria(task_type="code-edit"), limit=12, actor="mcp")
    respond_to_context_request(store, ContextCriteria(task_type="debugging"), limit=12, actor="mcp")

    report = run_doctor(store)
    assert not report.ok
    text = report.text()
    assert "restraint" in text
    assert "0 times" in text
    assert "2 context request(s)" in text


def test_returned_memory_is_not_flagged_as_dead(tmp_path):
    store = _store(tmp_path)
    apply_drafts(store, [_scoped("feature-development", "restraint")], actor="test")
    respond_to_context_request(
        store, ContextCriteria(task_type="feature-development"), limit=12, actor="mcp"
    )
    report = run_doctor(store)
    assert "restraint" not in report.text()


def test_no_requests_yet_means_no_dead_flag(tmp_path):
    """Day-one silence: a fresh scoped memory with zero logged requests is not
    an incident — there was no opportunity to miss it."""
    store = _store(tmp_path)
    apply_drafts(store, [_scoped("feature-development", "restraint")], actor="test")
    report = run_doctor(store)
    assert report.ok


def test_unmet_demand_is_counted_per_value(tmp_path):
    store = _store(tmp_path)
    apply_drafts(store, [_scoped("bug-fix", "bugfix_comm")], actor="test")
    respond_to_context_request(store, ContextCriteria(task_type="code-edit"), limit=12, actor="mcp")
    respond_to_context_request(store, ContextCriteria(task_type="code-edit"), limit=12, actor="mcp")

    text = run_doctor(store).text()
    assert "code-edit (x2)" in text
    assert "bug-fix" in text  # stored vocabulary shown next to the unmet demand


def test_unmet_demand_only_reported_for_dimensions_in_use(tmp_path):
    """The store has task_type drawers only; a request's project value finding
    no project memory is not noise-worthy — the user does not organize by
    project at all."""
    store = _store(tmp_path)
    apply_drafts(store, [_scoped("bug-fix", "bugfix_comm")], actor="test")
    respond_to_context_request(
        store,
        ContextCriteria(task_type="code-edit", project="some-project"),
        limit=12,
        actor="mcp",
    )
    text = run_doctor(store).text()
    assert "code-edit" in text
    assert "some-project" not in text


def test_matched_values_are_not_unmet(tmp_path):
    store = _store(tmp_path)
    apply_drafts(store, [_scoped("bug-fix", "bugfix_comm")], actor="test")
    respond_to_context_request(store, ContextCriteria(task_type="bug-fix"), limit=12, actor="mcp")
    report = run_doctor(store)
    assert report.ok


def test_healthy_store_stays_ok(tmp_path):
    store = _store(tmp_path)
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="preference",
                scope=Scope(level="global"),
                slot="style",
                content="c",
                rationale="r",
                confidence=0.9,
            )
        ],
        actor="test",
    )
    respond_to_context_request(store, ContextCriteria(), limit=12, actor="mcp")
    assert run_doctor(store).ok
