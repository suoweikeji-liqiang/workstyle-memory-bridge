"""Semantic memory extraction.

Important project constraint:
Production extraction must be model-backed or explicitly user-provided JSON.
Do not implement keyword tables, regex classifiers, or handcrafted language rules
for deciding what should be remembered. Those approaches are brittle and do not
scale across users, languages, or domains.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, List, Optional

from .schemas import MEMORY_JSON_SCHEMA, MemoryDraft, parse_memory_drafts


class ExtractorUnavailable(RuntimeError):
    def __init__(self, prompt: str) -> None:
        super().__init__(
            "No semantic extractor configured. Provide --memory-json or set MEMORY_BRIDGE_LLM_COMMAND."
        )
        self.prompt = prompt


def existing_memory_digest(records: Any, limit: int = 50) -> List[Dict[str, Any]]:
    """Compact view of current active memories for the extraction prompt.

    This is pure data assembly: it does not inspect feedback or decide which
    memory matches. The model uses the digest to reuse an existing slot+scope
    when the feedback updates a known memory, so the resolver can supersede it
    instead of accumulating a conflicting record.

    `records` is any iterable of memory records (duck-typed: slot, scope, type,
    content). The cap keeps the prompt bounded; workstyle memory sets are small.
    """
    digest: List[Dict[str, Any]] = []
    for record in list(records)[:limit]:
        scope = {k: v for k, v in record.scope.to_dict().items() if v is not None}
        digest.append(
            {
                "slot": record.slot,
                "scope": scope,
                "type": record.type,
                "content": record.content[:160],
            }
        )
    return digest


def _existing_memory_section(existing_memories: Optional[List[Dict[str, Any]]]) -> str:
    if not existing_memories:
        return ""
    listing = json.dumps(existing_memories, ensure_ascii=False, indent=2)
    return f"""

Currently stored active memories (slot + scope are the exact conflict keys):
{listing}

If this feedback updates, narrows, or overrides one of the memories above,
reuse that memory's exact slot AND scope so the store supersedes the old
version instead of keeping both. Only choose a new slot for a genuinely new
topic.""".rstrip()


def build_extraction_prompt(
    feedback: str,
    task_context: Optional[Dict[str, Any]] = None,
    existing_memories: Optional[List[Dict[str, Any]]] = None,
) -> str:
    task_context = task_context or {}
    schema = json.dumps(MEMORY_JSON_SCHEMA, ensure_ascii=False, indent=2)
    context = json.dumps(task_context, ensure_ascii=False, indent=2)
    existing_section = _existing_memory_section(existing_memories)
    return f"""
You are the semantic memory extractor for Workstyle Memory Bridge.

Goal:
Convert explicit user feedback into structured workstyle memories that can be
viewed, edited, deleted, and applied later across AI coding tools.

Rules:
- Extract only stable or explicitly scoped work-relevant memories.
- Distinguish preference, workflow, project_rule, temporary, fact, anti_preference.
- Use layer=L1_atom for single workstyle memories unless the user explicitly asks for a scenario/profile abstraction.
- Use explicit scope. Prefer task_type/project/tool/session scope over global when feedback is narrow.
- If the user changes an earlier preference, emit a memory with the same slot and scope so the resolver can supersede it.
- Do not store secrets, credentials, or private irrelevant facts.
- Do not infer hidden personal traits from weak evidence.
- Do not invent source_event_id or evidence_refs; the caller attaches L0 evidence after extraction.
- Output JSON only. No markdown.
{existing_section}

Task context:
{context}

User feedback:
{feedback}

JSON schema:
{schema}
""".strip()


def load_json_argument(value: str) -> Dict[str, Any]:
    """Load JSON from a direct string or from @path."""
    if value.startswith("@"):
        with open(value[1:], "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(value)


def extract_from_feedback(
    feedback: str,
    task_context: Optional[Dict[str, Any]] = None,
    memory_json: Optional[Dict[str, Any]] = None,
    llm_command: Optional[str] = None,
    existing_memories: Optional[List[Dict[str, Any]]] = None,
) -> List[MemoryDraft]:
    """Extract memory drafts from feedback.

    This function intentionally has only two production paths:
    1. explicit structured JSON provided by user/tooling;
    2. model-backed JSON produced by an external command.

    It does not classify feedback with handcrafted string rules.

    `existing_memories` (optional) is a digest of current active memories used
    only to help the model reuse an existing slot+scope on updates. It is
    ignored when explicit `memory_json` is supplied.
    """
    if memory_json is not None:
        return parse_memory_drafts(memory_json)

    command = llm_command or os.environ.get("MEMORY_BRIDGE_LLM_COMMAND")
    prompt = build_extraction_prompt(
        feedback, task_context=task_context, existing_memories=existing_memories
    )
    if not command:
        raise ExtractorUnavailable(prompt)

    completed = subprocess.run(
        command,
        input=prompt,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Extractor command failed: {completed.stderr.strip()}")
    payload = json.loads(completed.stdout)
    return parse_memory_drafts(payload)
