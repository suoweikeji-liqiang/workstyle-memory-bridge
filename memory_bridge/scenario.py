"""L2 scenario playbooks assembled from governed L1 memories.

This module deliberately avoids semantic summarization. It selects source L1
records by explicit scope metadata, builds model/user-facing prompts, records
source memory refs, and checks whether a scenario is stale because its source
records changed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .context_builder import ContextCriteria, scope_matches
from .extractor import load_json_argument
from .schemas import CreatedFrom, EvidenceRef, MemoryDraft, MemoryRecord, Scope, parse_memory_drafts
from .store import MemoryStore

SCENARIO_SOURCE_REFS_KEY = "source_memory_refs"
SCENARIO_KIND_KEY = "assembled_from_l1"


@dataclass(frozen=True)
class ScenarioSourceRef:
    id: str
    updated_at: str
    status: str = "active"

    @classmethod
    def from_memory(cls, memory: MemoryRecord) -> "ScenarioSourceRef":
        return cls(id=memory.id, updated_at=memory.updated_at, status=memory.status)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScenarioSourceRef":
        return cls(
            id=str(data.get("id") or ""),
            updated_at=str(data.get("updated_at") or ""),
            status=str(data.get("status") or "active"),
        )

    def to_dict(self) -> Dict[str, str]:
        return {"id": self.id, "updated_at": self.updated_at, "status": self.status}


@dataclass
class ScenarioStatus:
    scenario_id: str
    fresh: bool
    source_refs: List[ScenarioSourceRef] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "fresh": self.fresh,
            "source_refs": [ref.to_dict() for ref in self.source_refs],
            "reasons": self.reasons,
        }

    def text(self) -> str:
        state = "fresh" if self.fresh else "stale"
        lines = [f"Scenario {self.scenario_id}: {state}"]
        if self.source_refs:
            lines.append("Source memories:")
            lines.extend(f"- {ref.id} @ {ref.updated_at} ({ref.status})" for ref in self.source_refs)
        else:
            lines.append("Source memories: none recorded")
        if self.reasons:
            lines.append("Reasons:")
            lines.extend(f"- {reason}" for reason in self.reasons)
        return "\n".join(lines)


def scenario_source_refs(memory: MemoryRecord) -> List[ScenarioSourceRef]:
    raw_refs = memory.created_from.task_context.get(SCENARIO_SOURCE_REFS_KEY, [])
    if not isinstance(raw_refs, list):
        return []
    return [ScenarioSourceRef.from_dict(dict(item)) for item in raw_refs]


def scenario_source_ids(memory: MemoryRecord) -> List[str]:
    return [ref.id for ref in scenario_source_refs(memory) if ref.id]


def scenario_status(store: MemoryStore, scenario: MemoryRecord) -> ScenarioStatus:
    refs = scenario_source_refs(scenario)
    reasons: List[str] = []
    if scenario.layer != "L2_scenario":
        reasons.append(f"memory layer is {scenario.layer!r}, not 'L2_scenario'")
    if not refs:
        reasons.append("no source L1 memory refs recorded")
    for ref in refs:
        source = store.get(ref.id)
        if source is None:
            reasons.append(f"source memory {ref.id} is missing")
            continue
        if source.status != "active":
            reasons.append(f"source memory {ref.id} status is {source.status!r}, not active")
        if source.updated_at != ref.updated_at:
            reasons.append(
                f"source memory {ref.id} changed: recorded updated_at={ref.updated_at}, "
                f"current updated_at={source.updated_at}"
            )
    return ScenarioStatus(scenario_id=scenario.id, fresh=not reasons, source_refs=refs, reasons=reasons)


def select_l1_sources(store: MemoryStore, criteria: ContextCriteria, limit: int = 12) -> List[MemoryRecord]:
    """Select active L1 memories for scenario assembly by explicit scope only."""
    sources = [
        memory
        for memory in store.list(status="active")
        if memory.layer == "L1_atom" and scope_matches(memory.scope, criteria)
    ]
    sources.sort(
        key=lambda memory: (memory.scope.specificity(), memory.confidence, memory.valid_from),
        reverse=True,
    )
    return sources[:limit]


def scenario_prompt(sources: Iterable[MemoryRecord], criteria: ContextCriteria) -> str:
    source_payload = [
        {
            "id": memory.id,
            "type": memory.type,
            "scope": memory.scope.to_dict(),
            "slot": memory.slot,
            "content": memory.content,
            "rationale": memory.rationale,
            "confidence": memory.confidence,
            "evidence_refs": [ref.to_dict() for ref in memory.evidence_refs],
        }
        for memory in sources
    ]
    scope = _scope_from_criteria(criteria).to_dict()
    return f"""
You are assembling an L2 scenario playbook for Workstyle Memory Bridge.

Goal:
Create one L2_scenario memory that composes the source L1_atom memories into a
short, executable playbook for this task context. Do not introduce new user
preferences. Do not infer personality traits. Preserve the source constraints.

Output JSON only, in this shape:
{{
  "memories": [{{
    "type": "workflow",
    "layer": "L2_scenario",
    "scope": {json.dumps(scope, ensure_ascii=False)},
    "slot": "scenario_<stable_scope_value>_playbook",
    "content": "Scenario: ...\\nSteps:\\n1. ...\\nConstraints:\\n- ...\\nAnti-patterns:\\n- ...",
    "rationale": "Assembled from active L1 memories for this explicit scope.",
    "confidence": 0.8
  }}]
}}

Task context:
{json.dumps(criteria.to_dict(), ensure_ascii=False, indent=2)}

Source L1 memories:
{json.dumps(source_payload, ensure_ascii=False, indent=2)}
""".strip()


def _scope_from_criteria(criteria: ContextCriteria) -> Scope:
    if criteria.task_type:
        return Scope(level="task_type", task_type=criteria.task_type)
    if criteria.project:
        return Scope(level="project", project=criteria.project)
    if criteria.tool:
        return Scope(level="tool", tool=criteria.tool)
    if criteria.session_id:
        return Scope(level="session", session_id=criteria.session_id)
    if criteria.product or criteria.domain or criteria.user_id:
        return Scope(
            level="product_user",
            product=criteria.product,
            domain=criteria.domain,
            user_id=criteria.user_id,
        )
    return Scope(level="global")


def load_scenario_json(value: str) -> Dict[str, Any]:
    return load_json_argument(value)


def prepare_scenario_drafts(
    payload: Dict[str, Any],
    sources: List[MemoryRecord],
    criteria: ContextCriteria,
    evidence_ref: Optional[EvidenceRef] = None,
) -> List[MemoryDraft]:
    """Parse L2 drafts and attach deterministic source refs/evidence refs."""
    drafts = parse_memory_drafts(payload)
    source_refs = [ScenarioSourceRef.from_memory(source).to_dict() for source in sources]
    source_evidence = _dedupe_evidence_refs(
        ref for source in sources for ref in source.evidence_refs
    )
    for draft in drafts:
        draft.layer = "L2_scenario"
        if draft.scope.level == "global" and criteria.to_dict():
            draft.scope = _scope_from_criteria(criteria)
        context = dict(draft.created_from.task_context)
        context[SCENARIO_KIND_KEY] = True
        context[SCENARIO_SOURCE_REFS_KEY] = source_refs
        draft.created_from = CreatedFrom(
            session_id=draft.created_from.session_id,
            message_excerpt=draft.created_from.message_excerpt,
            task_context=context,
        )
        refs = list(draft.evidence_refs)
        if evidence_ref:
            refs.append(evidence_ref)
            draft.source_event_id = draft.source_event_id or evidence_ref.id
        refs.extend(source_evidence)
        draft.evidence_refs = _dedupe_evidence_refs(refs)
        draft.validate()
    return drafts


def _dedupe_evidence_refs(refs: Iterable[EvidenceRef]) -> List[EvidenceRef]:
    seen = set()
    result: List[EvidenceRef] = []
    for ref in refs:
        if ref.id in seen:
            continue
        seen.add(ref.id)
        result.append(ref)
    return result
