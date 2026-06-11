"""The always-on instruction file must stay small as preferences accumulate.

export_instruction_file inlines only global-scope memories by default; scoped
ones (task_type/project/tool) are left for on-demand build_context, so the
always-loaded CLAUDE.md / AGENTS.md does not grow without bound. A note keeps
the omission transparent rather than silent.
"""

from memory_bridge.exporters import export_instruction_file
from memory_bridge.resolver import apply_drafts
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def _seed(store: MemoryStore) -> None:
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="preference",
                scope=Scope(level="global"),
                slot="answer_style",
                content="GLOBAL-ALWAYS-RELEVANT",
                rationale="r",
                confidence=0.9,
            ),
            MemoryDraft(
                type="workflow",
                scope=Scope(level="task_type", task_type="bug-fix"),
                slot="bugfix_comm",
                content="SCOPED-ONLY-FOR-BUGFIX",
                rationale="r",
                confidence=0.9,
            ),
        ],
        actor="test",
    )


def test_default_export_inlines_only_global_with_note(tmp_path):
    store = MemoryStore(str(tmp_path / "e.sqlite"))
    _seed(store)
    out = export_instruction_file(tmp_path / "CLAUDE.md", store.list(status="active"), target="claude")
    text = out.read_text(encoding="utf-8")

    assert "GLOBAL-ALWAYS-RELEVANT" in text          # global is on the "wall"
    assert "SCOPED-ONLY-FOR-BUGFIX" not in text       # scoped stays in the "drawer"
    assert "scoped" in text and "build_context" in text  # omission is transparent


def test_all_scopes_export_inlines_everything(tmp_path):
    store = MemoryStore(str(tmp_path / "e.sqlite"))
    _seed(store)
    out = export_instruction_file(
        tmp_path / "CLAUDE.md", store.list(status="active"), target="claude", global_only=False
    )
    text = out.read_text(encoding="utf-8")
    assert "GLOBAL-ALWAYS-RELEVANT" in text
    assert "SCOPED-ONLY-FOR-BUGFIX" in text


def test_default_export_lists_scoped_vocabulary(tmp_path):
    """Zero-time vocabulary: a fresh session must learn the exact stored scope
    values from its instruction file, before any tool call, so its FIRST
    build_context can use the right key instead of an invented variant.
    (Field data: hosts improvised ops-guidance/code-edit/debugging and the
    response-time hint alone was not re-acted on without prompting.)"""
    store = MemoryStore(str(tmp_path / "e.sqlite"))
    _seed(store)
    out = export_instruction_file(tmp_path / "CLAUDE.md", store.list(status="active"), target="claude")
    text = out.read_text(encoding="utf-8")
    assert "task_type: bug-fix" in text  # the exact stored key is on the wall
    assert "exact value" in text  # and the instruction to reuse it verbatim


def test_vocabulary_covers_every_scoped_dimension(tmp_path):
    store = MemoryStore(str(tmp_path / "e.sqlite"))
    _seed(store)
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="project_rule",
                scope=Scope(level="project", project="acme-rocket"),
                slot="review_policy",
                content="SCOPED-ONLY-FOR-ACME",
                rationale="r",
                confidence=0.9,
            )
        ],
        actor="test",
    )
    out = export_instruction_file(tmp_path / "CLAUDE.md", store.list(status="active"), target="claude")
    text = out.read_text(encoding="utf-8")
    assert "task_type: bug-fix" in text
    assert "project: acme-rocket" in text


def test_no_vocabulary_block_without_scoped_memories(tmp_path):
    store = MemoryStore(str(tmp_path / "e.sqlite"))
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="preference",
                scope=Scope(level="global"),
                slot="answer_style",
                content="GLOBAL-ALWAYS-RELEVANT",
                rationale="r",
                confidence=0.9,
            )
        ],
        actor="test",
    )
    out = export_instruction_file(tmp_path / "CLAUDE.md", store.list(status="active"), target="claude")
    text = out.read_text(encoding="utf-8")
    assert "task_type:" not in text
    assert "scoped" not in text
