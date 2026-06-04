"""Dry-run preview powers the propose-then-confirm flow.

A proposal must show the real supersede effect without writing, so the user can
confirm before anything changes. These tests pin: (1) preview never mutates the
store, (2) it reports the exact active memory a draft would supersede, and
(3) the CLI --dry-run path writes nothing.
"""

import argparse

from memory_bridge.cli import cmd_ingest_feedback
from memory_bridge.resolver import apply_draft, preview_drafts
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def _draft(content: str, slot: str = "technical_plan_structure") -> MemoryDraft:
    return MemoryDraft(
        type="workflow",
        scope=Scope(level="task_type", task_type="technical_planning"),
        slot=slot,
        content=content,
        rationale="explicit user feedback",
        confidence=0.9,
    )


def test_preview_does_not_write(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    apply_draft(store, _draft("先北极星再 MVP。"))

    before = len(store.list(status="all"))
    preview_drafts(store, [_draft("风险放最前面。")])
    after = len(store.list(status="all"))

    assert before == after  # zero side effects


def test_preview_reports_would_supersede(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    seeded = apply_draft(store, _draft("先北极星再 MVP。")).inserted[0]

    result = preview_drafts(store, [_draft("风险放最前面。")])

    assert len(result.previews) == 1
    assert result.total_supersede() == 1
    assert result.previews[0].would_supersede[0].id == seeded.id


def test_preview_new_slot_supersedes_nothing(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    apply_draft(store, _draft("先北极星再 MVP。"))

    result = preview_drafts(store, [_draft("提交信息用 conventional commits。", slot="commit_style")])

    assert result.total_supersede() == 0
    assert result.previews[0].would_supersede == []


def test_cli_dry_run_writes_nothing(tmp_path, capsys):
    db = str(tmp_path / "memory.sqlite")
    seed_json = (
        '{"memories":[{"type":"workflow","scope":{"level":"task_type",'
        '"task_type":"technical_planning"},"slot":"technical_plan_structure",'
        '"content":"先北极星再 MVP","rationale":"seed","confidence":0.9}]}'
    )
    base = dict(
        db=db, feedback="风险放最前面", memory_json=seed_json, llm_command=None,
        project=None, tool=None, task_type="technical_planning", session_id=None,
        product=None, domain=None, user_id=None,
    )
    # commit one memory first
    cmd_ingest_feedback(argparse.Namespace(dry_run=False, **base))
    active_before = len(MemoryStore(db).list(status="all"))

    # dry-run a conflicting feedback
    cmd_ingest_feedback(argparse.Namespace(dry_run=True, **base))
    out = capsys.readouterr().out

    assert "DRY RUN" in out
    assert "would supersede" in out
    assert len(MemoryStore(db).list(status="all")) == active_before  # nothing written
