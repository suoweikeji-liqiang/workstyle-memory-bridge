"""The read path must leave evidence.

memory_events audits writes; nothing audited reads, so "why didn't my memory
fire last Tuesday" was unanswerable from the store. Every build_context request
now logs its criteria, what it returned, and how many scoped memories it could
not reach. Append-only; cleared by reset for reproducible runs.
"""

import json
import zipfile

from memory_bridge.cli import main
from memory_bridge.context_builder import ContextCriteria, respond_to_context_request
from memory_bridge.diagnostics import export_diagnostic_bundle
from memory_bridge.resolver import apply_drafts
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(str(tmp_path / "log.sqlite"))


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
        ],
        actor="test",
    )


def test_context_request_is_logged_with_criteria_and_outcome(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    respond_to_context_request(
        store, ContextCriteria(task_type="bug-fix"), limit=12, actor="mcp"
    )
    rows = store.context_requests()
    assert len(rows) == 1
    row = rows[0]
    assert row["actor"] == "mcp"
    assert row["criteria"] == {"task_type": "bug-fix"}
    assert row["matched_count"] == 2  # global + bug-fix
    assert len(row["returned_ids"]) == 2
    assert row["unmatched_count"] == 0
    assert row["timestamp"]


def test_unreachable_scoped_memories_are_counted_in_the_log(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    respond_to_context_request(store, ContextCriteria(), limit=12, actor="cli")
    row = store.context_requests()[0]
    assert row["unmatched_count"] == 1  # the bug-fix memory was out of reach


def test_requests_are_returned_newest_first(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    respond_to_context_request(store, ContextCriteria(), limit=12, actor="cli")
    respond_to_context_request(
        store, ContextCriteria(task_type="bug-fix"), limit=12, actor="mcp"
    )
    rows = store.context_requests()
    assert [row["actor"] for row in rows] == ["mcp", "cli"]


def test_cli_json_format_also_logs(tmp_path, capsys):
    db = str(tmp_path / "cli.sqlite")
    _seed(MemoryStore(db))
    assert main(["--db", db, "build-context", "--format", "json"]) == 0
    capsys.readouterr()
    rows = MemoryStore(db).context_requests()
    assert len(rows) == 1
    assert rows[0]["actor"] == "cli"


def test_context_log_command_prints_requests(tmp_path, capsys):
    db = str(tmp_path / "cli.sqlite")
    _seed(MemoryStore(db))
    assert main(["--db", db, "build-context", "--task-type", "bug-fix"]) == 0
    capsys.readouterr()
    assert main(["--db", db, "context-log"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["criteria"] == {"task_type": "bug-fix"}


def test_why_used_command_explains_latest_request(tmp_path, capsys):
    db = str(tmp_path / "cli.sqlite")
    _seed(MemoryStore(db))
    assert main(["--db", db, "build-context", "--task-type", "bug-fix"]) == 0
    capsys.readouterr()

    assert main(["--db", db, "why-used"]) == 0
    output = capsys.readouterr().out

    assert "Context Recall Explanation" in output
    assert "criteria: task_type=bug-fix" in output
    assert "bugfix-structure" in output
    assert "exact scope match on task_type=bug-fix" in output
    assert "rank signals" in output


def test_why_used_json_format(tmp_path, capsys):
    db = str(tmp_path / "cli.sqlite")
    _seed(MemoryStore(db))
    assert main(["--db", db, "build-context", "--task-type", "bug-fix"]) == 0
    capsys.readouterr()

    assert main(["--db", db, "why-used", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "ok"
    assert payload["request"]["criteria"] == {"task_type": "bug-fix"}
    assert payload["returned"][0]["scope_reason"]


def test_why_used_reports_when_no_request_exists(tmp_path, capsys):
    db = str(tmp_path / "cli.sqlite")

    assert main(["--db", db, "why-used"]) == 1
    output = capsys.readouterr().out

    assert "No build_context request has been logged yet" in output


def test_reset_clears_context_requests(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    respond_to_context_request(store, ContextCriteria(), limit=12, actor="cli")
    assert store.context_requests()
    store.reset(actor="test")
    assert store.context_requests() == []


def test_diagnostic_bundle_includes_context_requests(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    respond_to_context_request(store, ContextCriteria(), limit=12, actor="cli")
    bundle = export_diagnostic_bundle(store, tmp_path / "diag.zip")
    with zipfile.ZipFile(bundle) as archive:
        rows = json.loads(archive.read("context_requests.json"))
    assert rows and rows[0]["actor"] == "cli"
