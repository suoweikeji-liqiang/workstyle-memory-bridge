"""Zero-time context must ride the MCP handshake itself.

MCP servers can ship `instructions` that hosts surface in the system prompt.
Computing them at server start (= session start) from the live store means
every client gets the always-on memories and the scoped vocabulary without any
instruction-file export — installs work out of the box, and the text refreshes
each new session instead of waiting for a manual re-export.
"""

import pytest

from memory_bridge.exporters import server_instructions
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


def test_instructions_inline_globals_and_list_scoped_vocabulary(tmp_path):
    store = MemoryStore(str(tmp_path / "i.sqlite"))
    _seed(store)
    text = server_instructions(store.list(status="active"))
    assert "GLOBAL-ALWAYS-RELEVANT" in text  # always-on memories ride along
    assert "SCOPED-ONLY-FOR-BUGFIX" not in text  # contents stay in the store
    assert "task_type: bug-fix" in text  # but the exact key is announced
    assert "exact" in text  # with the reuse-verbatim instruction


def test_instructions_on_empty_store_invite_capture(tmp_path):
    store = MemoryStore(str(tmp_path / "i.sqlite"))
    text = server_instructions(store.list(status="active"))
    assert "remember_feedback" in text


def test_create_server_computes_instructions_from_live_store(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    db = str(tmp_path / "i.sqlite")
    monkeypatch.setenv("MEMORY_BRIDGE_DB", db)
    _seed(MemoryStore(db))
    from memory_bridge.mcp_server import create_server

    server = create_server()
    text = server.instructions or ""
    assert "GLOBAL-ALWAYS-RELEVANT" in text
    assert "task_type: bug-fix" in text
