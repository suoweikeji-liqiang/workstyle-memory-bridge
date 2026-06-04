"""Read-path self-correction for scope-value drift.

Scope is matched exactly, so a memory stored under `task_type=bug-fix` is missed
when the caller asks for `task_type=bugfix`. Rather than silently returning
nothing, build_context surfaces the scope values the store actually uses, so the
caller (or host AI) can realign to the exact value. Matching itself stays exact —
no normalization, no fuzzy matching.
"""

import json

from memory_bridge.cli import main
from memory_bridge.context_builder import (
    ContextCriteria,
    available_scope_values,
    build_context_markdown,
    select_memories,
)
from memory_bridge.resolver import apply_drafts
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(str(tmp_path / "scope.sqlite"))


def _bugfix_memory(store: MemoryStore) -> None:
    draft = MemoryDraft(
        type="workflow",
        scope=Scope(level="task_type", task_type="bug-fix"),
        slot="bug-fix-communication-structure",
        content="现象 -> 原因 -> 思路 -> 为什么能解决 -> 风险",
        rationale="user pref",
        confidence=0.95,
    )
    apply_drafts(store, [draft], actor="test")


def test_available_scope_values_collects_distinct_nonnull(tmp_path):
    store = _store(tmp_path)
    _bugfix_memory(store)
    values = available_scope_values(store)
    assert values == {"task_type": ["bug-fix"]}  # only non-null dimensions, exact value


def test_mismatched_scope_value_misses_but_hint_surfaces_stored_value(tmp_path):
    store = _store(tmp_path)
    _bugfix_memory(store)

    # caller drifts to 'bugfix' (no hyphen) -> exact match misses
    selected = select_memories(store, ContextCriteria(task_type="bugfix"))
    assert selected == []

    # the empty render must reveal the real stored value so the caller realigns
    available = available_scope_values(store)
    rendered = build_context_markdown(selected, available_scopes=available)
    assert "bug-fix" in rendered
    assert "task_type" in rendered

    # and the correct value still selects it (matching stays exact, not broken)
    assert len(select_memories(store, ContextCriteria(task_type="bug-fix"))) == 1


def test_empty_without_available_is_backward_compatible(tmp_path):
    rendered = build_context_markdown([])
    assert rendered == "No active workstyle memories matched this context."


def _memory_json(task_type: str, content: str) -> str:
    return json.dumps(
        {
            "memories": [
                {
                    "type": "workflow",
                    "scope": {"level": "task_type", "task_type": task_type},
                    "slot": "bugfix_comm",
                    "content": content,
                    "rationale": "r",
                    "confidence": 0.9,
                }
            ]
        }
    )


def test_dry_run_write_path_surfaces_existing_scope_values(tmp_path, capsys):
    """Write-path prevention: a dry-run proposal whose scope drifts ('bugfix')
    must show the existing stored value ('bug-fix') so the caller realigns
    before committing a duplicate."""
    db = str(tmp_path / "cli.sqlite")
    assert main(["--db", db, "ingest-feedback", "--task-type", "bug-fix",
                 "--feedback", "f", "--memory-json", _memory_json("bug-fix", "v1")]) == 0
    capsys.readouterr()  # drop commit output

    rc = main(["--db", db, "ingest-feedback", "--task-type", "bugfix",
               "--feedback", "f2", "--memory-json", _memory_json("bugfix", "v2"), "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Existing scope values" in out
    assert "bug-fix" in out  # the stored value is surfaced for realignment
