from memory_bridge.context_builder import ContextCriteria, respond_to_context_request
from memory_bridge.doctor import run_doctor
from memory_bridge.resolver import apply_drafts
from memory_bridge.scenario import prepare_scenario_drafts, select_l1_sources
from memory_bridge.schemas import CreatedFrom, MemoryDraft, Scope
from memory_bridge.store import MemoryStore


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(str(tmp_path / "doctor.sqlite"))


def test_expired_active_memory_is_a_blocking_lifecycle_issue(tmp_path):
    store = _store(tmp_path)
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="workflow",
                scope=Scope(level="global"),
                slot="expired",
                content="old rule",
                rationale="test",
                confidence=0.9,
                valid_until="2000-01-01T00:00:00+00:00",
            )
        ],
        actor="test",
    )

    report = run_doctor(store)

    assert not report.ok
    assert any("valid_until" in issue for issue in report.issues)


def test_hygiene_observations_do_not_make_doctor_fail(tmp_path):
    store = _store(tmp_path)
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="temporary",
                scope=Scope(level="global"),
                slot="temporary-global",
                content="use this during the current investigation",
                rationale="test",
                confidence=0.4,
                created_from=CreatedFrom(task_context={"task_type": "bug-fix"}),
            )
        ],
        actor="test",
    )

    report = run_doctor(store)
    text = report.text()

    assert report.ok
    assert "Memory hygiene observations" in text
    assert "temporary" in text
    assert "low confidence" in text
    assert "stored as global" in text


def test_host_observations_report_unverified_integration_without_failing(tmp_path):
    store = _store(tmp_path)
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="workflow",
                scope=Scope(level="task_type", task_type="feature-development"),
                slot="feature-flow",
                content="use the feature flow",
                rationale="test",
                confidence=0.9,
            )
        ],
        actor="test",
    )

    report = run_doctor(store)
    text = report.text()

    assert report.ok
    assert "Host integration observations" in text
    assert "No build_context request has been logged" in text


def test_host_observations_notice_generic_cli_only_requests(tmp_path):
    store = _store(tmp_path)
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="workflow",
                scope=Scope(level="task_type", task_type="feature-development"),
                slot="feature-flow",
                content="use the feature flow",
                rationale="test",
                confidence=0.9,
            )
        ],
        actor="test",
    )
    respond_to_context_request(store, ContextCriteria(), limit=12, actor="cli")

    report = run_doctor(store)
    text = report.text()

    assert not report.ok  # recall health still flags the dead scoped memory
    assert "calling build_context too generically" in text
    assert "No MCP-origin build_context request" in text


def test_stale_l2_scenario_is_reported_as_hygiene(tmp_path):
    store = _store(tmp_path)
    apply_drafts(
        store,
        [
            MemoryDraft(
                type="workflow",
                scope=Scope(level="task_type", task_type="technical_planning"),
                slot="north-star",
                content="先讲北极星。",
                rationale="test",
                confidence=0.9,
            )
        ],
        actor="test",
    )
    sources = select_l1_sources(store, ContextCriteria(task_type="technical_planning"))
    scenario = apply_drafts(
        store,
        prepare_scenario_drafts(
            {
                "memories": [
                    {
                        "type": "workflow",
                        "layer": "L2_scenario",
                        "scope": {"level": "task_type", "task_type": "technical_planning"},
                        "slot": "scenario_technical_planning",
                        "content": "Scenario: technical_planning\nSteps:\n1. 先讲北极星。",
                        "rationale": "Assembled from active L1 memories.",
                        "confidence": 0.8,
                    }
                ]
            },
            sources,
            ContextCriteria(task_type="technical_planning"),
        ),
        actor="test",
    ).inserted[0]

    source = sources[0]
    source.content = "先讲 MVP。"
    store.update(source, actor="test", note="source changed")

    text = run_doctor(store).text()

    assert scenario.id in text
    assert "stale L2 scenario" in text
