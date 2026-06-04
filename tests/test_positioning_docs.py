from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_positioning_doc_keeps_project_out_of_generic_memory_mcp():
    text = (ROOT / "docs" / "positioning.md").read_text(encoding="utf-8")
    assert "not" in text.lower()
    assert "generic memory MCP" in text
    assert "Workstyle-first" in text
    assert "Governance-first" in text
    assert "Evaluation-first" in text


def test_non_goals_explicitly_prevent_scope_creep():
    text = (ROOT / "docs" / "non_goals.md").read_text(encoding="utf-8")
    required = [
        "universal memory platform",
        "full knowledge graph",
        "full AI coding agent",
        "heuristic extraction",
    ]
    for phrase in required:
        assert phrase in text


def test_root_agent_instructions_preserve_no_heuristic_and_positioning():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "not a generic memory MCP" in text
    assert "Do not implement core semantic memory extraction" in text
    assert "feedback -> governed workstyle memory" in text


def test_v03_traceability_positioning_is_documented():
    text = (ROOT / "docs" / "positioning.md").read_text(encoding="utf-8")
    assert "Traceability-first" in text
    assert "L0_event" in text
    assert "source-backed" in text


def test_tencent_reference_boundary_exists():
    text = (ROOT / "docs" / "tencentdb_agent_memory_reference.md").read_text(encoding="utf-8")
    assert "TencentDB-Agent-Memory" in text
    assert "What not to copy" in text
    assert "L0 event" in text
