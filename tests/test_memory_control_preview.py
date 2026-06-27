import json

from memory_bridge.cli import main
from memory_bridge.memory_control import preview_delete, preview_edit
from memory_bridge.resolver import apply_drafts
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(str(tmp_path / "control.sqlite"))


def _seed(store: MemoryStore) -> str:
    evidence = store.create_evidence(
        "user_feedback",
        "以后代码审查先说风险。",
        metadata={"task_type": "code-review"},
    )
    draft = MemoryDraft(
        type="workflow",
        scope=Scope(level="task_type", task_type="code-review"),
        slot="review-order",
        content="代码审查先说风险。",
        rationale="explicit user feedback",
        confidence=0.9,
        source_event_id=evidence.id,
        evidence_refs=[store.evidence_ref_for(evidence)],
    )
    return apply_drafts(store, [draft], actor="test").inserted[0].id


def test_preview_delete_shows_candidate_and_writes_nothing(tmp_path):
    store = _store(tmp_path)
    memory_id = _seed(store)

    preview = preview_delete(store, [memory_id], user_request="删掉代码审查那条")

    assert preview["dry_run"] is True
    assert preview["will_write"] is False
    assert preview["candidates"][0]["id"] == memory_id
    assert preview["candidates"][0]["evidence"]
    assert store.get(memory_id).status == "active"


def test_preview_delete_reports_missing_ids(tmp_path):
    store = _store(tmp_path)
    memory_id = _seed(store)

    preview = preview_delete(store, [memory_id, "mem_missing"])

    assert [item["id"] for item in preview["candidates"]] == [memory_id]
    assert preview["missing_ids"] == ["mem_missing"]


def test_preview_edit_validates_before_after_and_writes_nothing(tmp_path):
    store = _store(tmp_path)
    memory_id = _seed(store)

    preview = preview_edit(
        store,
        memory_id,
        {"content": "代码审查按严重程度先说风险。", "confidence": 0.8},
        user_request="改一下代码审查那条",
    )

    assert preview["dry_run"] is True
    assert preview["before"]["content"] == "代码审查先说风险。"
    assert preview["after"]["content"] == "代码审查按严重程度先说风险。"
    assert preview["after"]["confidence"] == 0.8
    assert store.get(memory_id).content == "代码审查先说风险。"


def test_cli_preview_delete_json(tmp_path, capsys):
    db = str(tmp_path / "control.sqlite")
    memory_id = _seed(MemoryStore(db))

    assert main(["--db", db, "preview-delete", memory_id, "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["action"] == "delete"
    assert payload["candidates"][0]["id"] == memory_id
    assert MemoryStore(db).get(memory_id).status == "active"


def test_cli_preview_edit_text(tmp_path, capsys):
    db = str(tmp_path / "control.sqlite")
    memory_id = _seed(MemoryStore(db))

    assert main(["--db", db, "preview-edit", memory_id, "--content", "风险优先。"]) == 0
    output = capsys.readouterr().out

    assert "Memory control preview: edit" in output
    assert "DRY RUN" in output
    assert "风险优先" in output
    assert MemoryStore(db).get(memory_id).content == "代码审查先说风险。"
