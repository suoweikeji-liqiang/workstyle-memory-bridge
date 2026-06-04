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
