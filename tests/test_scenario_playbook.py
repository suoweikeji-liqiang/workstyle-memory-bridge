from memory_bridge.context_builder import ContextCriteria, build_context_markdown, select_memories
from memory_bridge.resolver import apply_draft, apply_drafts
from memory_bridge.scenario import (
    prepare_scenario_drafts,
    scenario_source_ids,
    scenario_status,
    select_l1_sources,
)
from memory_bridge.schemas import MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def l1(content: str, slot: str) -> MemoryDraft:
    return MemoryDraft(
        type="workflow",
        layer="L1_atom",
        scope=Scope(level="task_type", task_type="technical_planning"),
        slot=slot,
        content=content,
        rationale="explicit user feedback",
        confidence=0.9,
    )


def test_l2_scenario_records_source_l1_refs_and_evidence(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    evidence = store.create_evidence(
        "user_feedback",
        "以后技术方案先讲北极星，风险放 MVP 后。",
        metadata={"task_type": "technical_planning"},
    )
    ref = store.evidence_ref_for(evidence)
    first = l1("技术方案先讲北极星。", "north_star_first")
    first.source_event_id = evidence.id
    first.evidence_refs = [ref]
    second = l1("风险放在 MVP 后。", "risk_after_mvp")
    second.source_event_id = evidence.id
    second.evidence_refs = [ref]
    apply_drafts(store, [first, second])

    sources = select_l1_sources(store, ContextCriteria(task_type="technical_planning"))
    scenario_payload = {
        "memories": [
            {
                "type": "workflow",
                "layer": "L2_scenario",
                "scope": {"level": "task_type", "task_type": "technical_planning"},
                "slot": "scenario_technical_planning_playbook",
                "content": "Scenario: technical_planning\nSteps:\n1. 先讲北极星。\n2. MVP 后讲风险。",
                "rationale": "Assembled from active L1 memories.",
                "confidence": 0.88,
            }
        ]
    }
    drafts = prepare_scenario_drafts(
        scenario_payload,
        sources,
        ContextCriteria(task_type="technical_planning"),
    )
    result = apply_drafts(store, drafts)
    scenario = result.inserted[0]

    assert scenario.layer == "L2_scenario"
    assert set(scenario_source_ids(scenario)) == {source.id for source in sources}
    assert scenario.evidence_refs[0].id == evidence.id
    assert scenario_status(store, scenario).fresh


def test_fresh_l2_scenario_replaces_covered_l1_in_context(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    apply_drafts(
        store,
        [
            l1("技术方案先讲北极星。", "north_star_first"),
            l1("风险放在 MVP 后。", "risk_after_mvp"),
        ],
    )
    sources = select_l1_sources(store, ContextCriteria(task_type="technical_planning"))
    drafts = prepare_scenario_drafts(
        {
            "memories": [
                {
                    "type": "workflow",
                    "layer": "L2_scenario",
                    "scope": {"level": "task_type", "task_type": "technical_planning"},
                    "slot": "scenario_technical_planning_playbook",
                    "content": "Scenario: technical_planning\nSteps:\n1. 先讲北极星。\n2. MVP 后讲风险。",
                    "rationale": "Assembled from active L1 memories.",
                    "confidence": 0.88,
                }
            ]
        },
        sources,
        ContextCriteria(task_type="technical_planning"),
    )
    scenario = apply_drafts(store, drafts).inserted[0]

    selected = select_memories(store, ContextCriteria(task_type="technical_planning"))
    assert [memory.id for memory in selected] == [scenario.id]
    markdown = build_context_markdown(selected)
    assert "Scenario Playbook" in markdown
    assert "scenario_technical_planning_playbook" in markdown


def test_stale_l2_scenario_is_not_selected(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    source = apply_draft(store, l1("技术方案先讲北极星。", "north_star_first")).inserted[0]
    drafts = prepare_scenario_drafts(
        {
            "memories": [
                {
                    "type": "workflow",
                    "layer": "L2_scenario",
                    "scope": {"level": "task_type", "task_type": "technical_planning"},
                    "slot": "scenario_technical_planning_playbook",
                    "content": "Scenario: technical_planning\nSteps:\n1. 先讲北极星。",
                    "rationale": "Assembled from active L1 memories.",
                    "confidence": 0.88,
                }
            ]
        },
        [source],
        ContextCriteria(task_type="technical_planning"),
    )
    scenario = apply_drafts(store, drafts).inserted[0]
    assert scenario_status(store, scenario).fresh

    source.content = "技术方案先讲 MVP，再讲北极星。"
    store.update(source, note="user changed source L1")

    assert not scenario_status(store, scenario).fresh
    selected = select_memories(store, ContextCriteria(task_type="technical_planning"))
    assert [memory.id for memory in selected] == [source.id]
