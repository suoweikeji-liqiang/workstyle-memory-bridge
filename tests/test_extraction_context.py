"""The extraction prompt must surface existing active memories.

This is the anti-accumulation fix at the capture step: the model can only
reuse an existing slot+scope (so the resolver supersedes the old memory) if it
is told which memories already exist. These tests pin that the digest is
compact and that both the model path and the manual-paste path include it.

They are deterministic — no LLM is invoked.
"""

import pytest

from memory_bridge.extractor import (
    ExtractorUnavailable,
    build_extraction_prompt,
    existing_memory_digest,
    extract_from_feedback,
)
from memory_bridge.schemas import MemoryDraft, Scope


def _draft(slot: str, task_type: str, content: str) -> MemoryDraft:
    return MemoryDraft(
        type="workflow",
        scope=Scope(level="task_type", task_type=task_type),
        slot=slot,
        content=content,
        rationale="test",
        confidence=0.9,
    )


def test_digest_is_compact_and_capped():
    records = [_draft(f"slot_{i}", "planning", "x" * 500) for i in range(60)]
    digest = existing_memory_digest(records, limit=50)

    assert len(digest) == 50  # capped
    item = digest[0]
    assert set(item) == {"slot", "scope", "type", "content"}
    assert len(item["content"]) <= 160  # content trimmed
    assert "task_type" in item["scope"] and "project" not in item["scope"]  # nulls stripped


def test_prompt_includes_existing_slot_and_scope():
    digest = existing_memory_digest([_draft("technical_plan_structure", "technical_planning", "old rule")])
    prompt = build_extraction_prompt("更新一下方案结构", existing_memories=digest)

    assert "technical_plan_structure" in prompt
    assert "technical_planning" in prompt
    assert "supersedes" in prompt or "supersede" in prompt


def test_prompt_omits_block_when_no_existing_memories():
    prompt = build_extraction_prompt("first feedback ever")
    assert "Currently stored active memories" not in prompt


def test_manual_paste_path_also_includes_existing_memories():
    """No configured extractor -> prompt is raised for manual paste; it must
    still carry the existing-memory context so the human/model can align keys."""
    digest = existing_memory_digest([_draft("technical_plan_structure", "technical_planning", "old rule")])
    with pytest.raises(ExtractorUnavailable) as exc:
        extract_from_feedback("更新方案结构", existing_memories=digest, llm_command=None)
    assert "technical_plan_structure" in exc.value.prompt


def test_explicit_memory_json_ignores_existing_memories():
    payload = {
        "memories": [
            {
                "type": "preference",
                "scope": {"level": "global"},
                "slot": "tone",
                "content": "简洁",
                "rationale": "user said so",
                "confidence": 0.9,
            }
        ]
    }
    drafts = extract_from_feedback(
        "无所谓",
        memory_json=payload,
        existing_memories=[{"slot": "x", "scope": {"level": "global"}, "type": "fact", "content": "y"}],
    )
    assert len(drafts) == 1 and drafts[0].slot == "tone"
