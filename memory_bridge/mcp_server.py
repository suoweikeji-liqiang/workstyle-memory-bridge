"""Optional MCP adapter for Workstyle Memory Bridge.

Install MCP support separately, then run:
    python -m memory_bridge.mcp_server

The core package stays stdlib-only. This adapter is intentionally thin: MCP tools
call the same store/resolver/context/export functions used by the CLI.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Union

from .context_builder import (
    ContextCriteria,
    available_scope_values,
    build_context_explanation_markdown,
    explain_context_request,
    respond_to_context_request,
)
from .deletion_verifier import verify_deleted_memory
from .doctor import run_doctor
from .exporters import export_instruction_file, server_instructions
from .extractor import ExtractorUnavailable, existing_memory_digest, extract_from_feedback
from .resolver import apply_drafts, preview_drafts
from .scenario import (
    prepare_scenario_drafts,
    scenario_prompt,
    scenario_source_ids,
    scenario_status as scenario_memory_status,
    select_l1_sources,
)
from .schemas import CreatedFrom, Scope
from .store import MemoryStore

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover - optional dependency
    FastMCP = None  # type: ignore


def _store() -> MemoryStore:
    return MemoryStore(os.environ.get("MEMORY_BRIDGE_DB"))


def _criteria(
    project: Optional[str] = None,
    tool: Optional[str] = None,
    task_type: Optional[str] = None,
    session_id: Optional[str] = None,
    product: Optional[str] = None,
    domain: Optional[str] = None,
    user_id: Optional[str] = None,
) -> ContextCriteria:
    return ContextCriteria(
        project=project,
        tool=tool,
        task_type=task_type,
        session_id=session_id,
        product=product,
        domain=domain,
        user_id=user_id,
    )


def _task_context(
    project: Optional[str] = None,
    tool: Optional[str] = None,
    task_type: Optional[str] = None,
    session_id: Optional[str] = None,
    product: Optional[str] = None,
    domain: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    return {
        "project": project,
        "tool": tool,
        "task_type": task_type,
        "session_id": session_id,
        "product": product,
        "domain": domain,
        "user_id": user_id,
    }


def _non_empty(data: dict) -> dict:
    return {key: value for key, value in data.items() if value is not None}


def create_server():
    if FastMCP is None:
        raise RuntimeError("MCP dependency is not installed. Try: pip install 'mcp>=1.0.0'")

    # Instructions ride the MCP handshake: hosts that surface them give every
    # fresh session the always-on memories and scoped vocabulary at time zero,
    # with no instruction-file export step.
    mcp = FastMCP(
        "workstyle-memory-governance",
        instructions=server_instructions(_store().list(status="active")),
    )

    @mcp.tool()
    def reset_memory() -> str:
        """Clear all memories and evidence events for reproducible testing."""
        store = _store()
        store.reset(actor="mcp")
        return "Memory cleared. Active memories: 0"

    @mcp.tool()
    def view_memory(status: str = "active") -> str:
        """View memories by status: active, superseded, archived, deleted, or all."""
        store = _store()
        return json.dumps([m.to_dict() for m in store.list(status=status)], ensure_ascii=False, indent=2)

    @mcp.tool()
    def remember_feedback(
        feedback: str,
        memory_json: Optional[Union[str, Dict[str, Any]]] = None,
        project: Optional[str] = None,
        tool: Optional[str] = None,
        task_type: Optional[str] = None,
        session_id: Optional[str] = None,
        product: Optional[str] = None,
        domain: Optional[str] = None,
        user_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> str:
        """Save how the user wants you to work as a governed workstyle memory.

        YOU are the extractor. Generate `memory_json` yourself from the user's
        feedback and pass it — do NOT call with only `feedback` expecting the
        server to extract (there is no built-in extractor; that path errors
        unless MEMORY_BRIDGE_LLM_COMMAND is set for headless runs). If you do
        omit it, this returns an extraction prompt so you can retry with
        `memory_json` rather than falling back to another memory system.

        Pass `memory_json` as a JSON object (preferred) or a JSON string —
        both are accepted.

        `memory_json` shape:
          {"memories": [{
            "type": "preference|workflow|project_rule|temporary|fact|anti_preference",
            "scope": {"level": "global|project|tool|task_type|session|product_user",
                      "task_type": "..."},
            "slot": "<stable key>", "content": "...", "rationale": "...",
            "confidence": 0.0-1.0}]}

        Avoid duplicates: first call `view_memory`; if this updates an existing
        memory, reuse its exact `slot` and `scope` so the old one is superseded.

        Set `dry_run=True` to preview the proposed memories and which active
        memory each would supersede, without writing. Call again with
        `dry_run=False` once the user confirms.
        """
        # Accept memory_json as a JSON object OR a JSON string: the model tends to
        # send an object, and some MCP clients auto-parse JSON-looking strings into
        # objects. Tolerating both avoids a catch-22 where neither form validates.
        if memory_json is None:
            payload = None
        elif isinstance(memory_json, str):
            payload = json.loads(memory_json)
        else:
            payload = memory_json
        context = _task_context(
            project=project,
            tool=tool,
            task_type=task_type,
            session_id=session_id,
            product=product,
            domain=domain,
            user_id=user_id,
        )
        store = _store()
        existing = None if payload else existing_memory_digest(store.list(status="active"))
        try:
            drafts = extract_from_feedback(
                feedback,
                task_context=context,
                memory_json=payload,
                existing_memories=existing,
            )
        except ExtractorUnavailable as exc:
            return json.dumps(
                {
                    "status": "needs_memory_json",
                    "message": (
                        "No server-side extractor is configured. You (the calling "
                        "assistant) are the extractor: read extraction_prompt, produce "
                        "the JSON it asks for, and call remember_feedback again with that "
                        "JSON as `memory_json`. Reuse an existing slot+scope if this "
                        "updates a known memory. Do not fall back to another memory store."
                    ),
                    "extraction_prompt": exc.prompt,
                },
                ensure_ascii=False,
                indent=2,
            )
        if dry_run:
            preview = preview_drafts(store, drafts)
            return json.dumps(
                {
                    "dry_run": True,
                    "previews": [
                        {
                            "proposed": item.draft.to_dict(),
                            "would_supersede": [old.to_dict() for old in item.would_supersede],
                        }
                        for item in preview.previews
                    ],
                    "existing_scope_values": available_scope_values(store),
                    "hint": (
                        "Before confirming, compare each proposed scope value with "
                        "existing_scope_values. If a proposal is a variant of an existing "
                        "value (e.g. 'bugfix' vs the stored 'bug-fix'), re-call with the "
                        "exact existing value so future reads match and the old memory is "
                        "superseded instead of duplicated."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        evidence = store.create_evidence("user_feedback", feedback, metadata=context)
        ref = store.evidence_ref_for(evidence)
        for draft in drafts:
            if not draft.source_event_id:
                draft.source_event_id = evidence.id
            if not draft.evidence_refs:
                draft.evidence_refs = [ref]
            if not draft.created_from.message_excerpt and not draft.created_from.task_context:
                draft.created_from = CreatedFrom(
                    session_id=session_id,
                    message_excerpt=feedback[:240],
                    task_context=_non_empty(context),
                )
        result = apply_drafts(store, drafts, actor="mcp")
        return json.dumps(
            {
                "inserted": [m.to_dict() for m in result.inserted],
                "superseded": [m.to_dict() for m in result.superseded],
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    def inspect_memory(memory_id: str) -> str:
        """Inspect a memory with evidence refs and lifecycle events."""
        store = _store()
        memory = store.get(memory_id)
        if not memory:
            return f"Memory not found: {memory_id}"
        evidence = []
        for ref in memory.evidence_refs:
            event = store.get_evidence(ref.id)
            evidence.append(event.to_dict() if event else ref.to_dict())
        lifecycle = [event for event in store.events(limit=1000) if event.get("memory_id") == memory_id]
        scenario_status = (
            scenario_memory_status(store, memory).to_dict()
            if memory.layer == "L2_scenario"
            else None
        )
        return json.dumps(
            {
                "memory": memory.to_dict(),
                "evidence": evidence,
                "lifecycle": lifecycle,
                "scenario_status": scenario_status,
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    def build_context(
        project: Optional[str] = None,
        tool: Optional[str] = None,
        task_type: Optional[str] = None,
        session_id: Optional[str] = None,
        product: Optional[str] = None,
        domain: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 12,
    ) -> str:
        """Return relevant active workstyle memories for the current task context.

        Scope is matched exactly. The response also lists stored scope values
        this call did NOT match — scoped memories you could reach by calling
        again with one of those exact values (never invent a variant). Pass the
        dimensions you know (especially task_type) so scoped memories can fire.
        """
        store = _store()
        return respond_to_context_request(
            store,
            _criteria(
                project=project,
                tool=tool,
                task_type=task_type,
                session_id=session_id,
                product=product,
                domain=domain,
                user_id=user_id,
            ),
            limit=limit,
            actor="mcp",
        )

    @mcp.tool()
    def why_used(request_id: Optional[int] = None) -> str:
        """Explain the latest or selected build_context recall result.

        Shows which returned memories matched the request, the structured
        ranking signals used for ordering, and scoped memory values still out
        of reach for the same criteria.
        """
        store = _store()
        return build_context_explanation_markdown(
            explain_context_request(store, request_id=request_id)
        )

    @mcp.tool()
    def build_scenario(
        scenario_json: Optional[Union[str, Dict[str, Any]]] = None,
        project: Optional[str] = None,
        tool: Optional[str] = None,
        task_type: Optional[str] = None,
        session_id: Optional[str] = None,
        product: Optional[str] = None,
        domain: Optional[str] = None,
        user_id: Optional[str] = None,
        source_limit: int = 12,
        dry_run: bool = True,
    ) -> str:
        """Create or preview an L2 scenario playbook from matching active L1 memories.

        YOU are the scenario assembler. First call without `scenario_json` to
        get the exact source L1 memories and a model-ready prompt. Then generate
        one L2_scenario JSON memory and call again with dry_run=True. Show the
        preview to the user; commit with dry_run=False only after confirmation.

        The server does not summarize L1 memories itself and never uses keyword
        rules. It only validates the draft, attaches source_memory_refs and L0
        evidence refs, and later marks the scenario stale if a source L1 changes
        or is deleted.
        """
        store = _store()
        criteria = _criteria(
            project=project,
            tool=tool,
            task_type=task_type,
            session_id=session_id,
            product=product,
            domain=domain,
            user_id=user_id,
        )
        sources = select_l1_sources(store, criteria, limit=source_limit)
        if not sources:
            return json.dumps(
                {
                    "status": "no_sources",
                    "message": "No matching active L1 memories found for this scope.",
                    "criteria": criteria.to_dict(),
                },
                ensure_ascii=False,
                indent=2,
            )

        if scenario_json is None:
            return json.dumps(
                {
                    "status": "needs_scenario_json",
                    "message": (
                        "Assemble one L2_scenario memory from the source memories, "
                        "then call build_scenario again with scenario_json. Do not "
                        "add new preferences that are not in the sources."
                    ),
                    "criteria": criteria.to_dict(),
                    "source_memories": [source.to_dict() for source in sources],
                    "scenario_prompt": scenario_prompt(sources, criteria),
                },
                ensure_ascii=False,
                indent=2,
            )

        payload = json.loads(scenario_json) if isinstance(scenario_json, str) else scenario_json
        if dry_run:
            drafts = prepare_scenario_drafts(payload, sources, criteria)
            preview = preview_drafts(store, drafts)
            return json.dumps(
                {
                    "dry_run": True,
                    "previews": [
                        {
                            "proposed": item.draft.to_dict(),
                            "would_supersede": [old.to_dict() for old in item.would_supersede],
                        }
                        for item in preview.previews
                    ],
                    "source_memory_ids": [source.id for source in sources],
                    "hint": "Show this preview to the user and commit only after confirmation.",
                },
                ensure_ascii=False,
                indent=2,
            )

        source_ids = [source.id for source in sources]
        evidence = store.create_evidence(
            "manual_note",
            "L2 scenario playbook accepted from active L1 memories: " + ", ".join(source_ids),
            metadata={**criteria.to_dict(), "source_memory_ids": source_ids},
        )
        drafts = prepare_scenario_drafts(
            payload,
            sources,
            criteria,
            evidence_ref=store.evidence_ref_for(evidence),
        )
        result = apply_drafts(store, drafts, actor="mcp")
        return json.dumps(
            {
                "inserted": [m.to_dict() for m in result.inserted],
                "superseded": [m.to_dict() for m in result.superseded],
                "source_memory_ids": {
                    memory.id: scenario_source_ids(memory) for memory in result.inserted
                },
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    def scenario_status(memory_id: Optional[str] = None) -> str:
        """Report whether L2 scenarios are fresh or stale against their source L1 memories."""
        store = _store()
        if memory_id:
            records = [store.get(memory_id)]
        else:
            records = [m for m in store.list(status="active") if m.layer == "L2_scenario"]
        found = [record for record in records if record is not None]
        if not found:
            return "No scenario memories found."
        return json.dumps(
            [scenario_memory_status(store, record).to_dict() for record in found],
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    def edit_memory(
        memory_id: str,
        content: Optional[str] = None,
        rationale: Optional[str] = None,
        slot: Optional[str] = None,
        memory_type: Optional[str] = None,
        layer: Optional[str] = None,
        confidence: Optional[float] = None,
        status: Optional[str] = None,
        scope_json: Optional[str] = None,
    ) -> str:
        """Edit an existing memory. Use this for transparent user control."""
        store = _store()
        record = store.get(memory_id)
        if not record:
            return f"Memory not found: {memory_id}"
        if content is not None:
            record.content = content
        if rationale is not None:
            record.rationale = rationale
        if slot is not None:
            record.slot = slot
        if memory_type is not None:
            record.type = memory_type
        if layer is not None:
            record.layer = layer
        if confidence is not None:
            record.confidence = confidence
        if status is not None:
            record.status = status
        if scope_json is not None:
            record.scope = Scope.from_dict(json.loads(scope_json))
        store.update(record, actor="mcp", note="manual edit via MCP")
        return json.dumps(record.to_dict(), ensure_ascii=False, indent=2)

    @mcp.tool()
    def delete_memory(memory_id: str) -> str:
        """Delete a memory so it stops being selected or exported."""
        record = _store().soft_delete(memory_id, actor="mcp")
        return f"Deleted: {memory_id}" if record else f"Memory not found: {memory_id}"

    @mcp.tool()
    def verify_deletion(
        memory_id: str,
        project: Optional[str] = None,
        tool: Optional[str] = None,
        task_type: Optional[str] = None,
        session_id: Optional[str] = None,
        product: Optional[str] = None,
        domain: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 12,
    ) -> str:
        """Verify a deleted memory is absent from context and export projections."""
        report = verify_deleted_memory(
            _store(),
            memory_id,
            _criteria(
                project=project,
                tool=tool,
                task_type=task_type,
                session_id=session_id,
                product=product,
                domain=domain,
                user_id=user_id,
            ),
            limit=limit,
        )
        return report.text()

    @mcp.tool()
    def memory_doctor() -> str:
        """Health-check the memory store: lifecycle issues plus recall health.

        Call this FIRST when the user asks why a stored memory did not fire or
        was not applied. It cross-references the read-path audit
        (context_requests) with stored scopes and reports facts only — scoped
        memories never returned despite logged requests, and requested scope
        values that matched nothing. YOU judge the semantics: if a requested
        label and a stored value name the same kind of work, propose a governed
        fix (edit_memory, or remember_feedback with dry_run) and let the user
        confirm. Never silently rewrite memories.
        """
        return run_doctor(_store()).text()

    @mcp.tool()
    def export_instructions(target: str, path: str, include_scoped: bool = False) -> str:
        """Write workstyle memories into a managed CLAUDE.md / AGENTS.md section.

        By default only global-scope memories are inlined, so this always-on file
        stays small no matter how many preferences accumulate. Task/project/tool
        -scoped memories are NOT inlined — they load on demand via build_context.
        Set include_scoped=True only if you deliberately want everything inlined.
        """
        store = _store()
        memories = store.list(status="active")
        output_path = export_instruction_file(
            path, memories, target=target, global_only=not include_scoped
        )
        if include_scoped:
            return f"Exported {len(memories)} memories to {output_path}"
        inlined = sum(1 for memory in memories if memory.scope.level == "global")
        scoped = len(memories) - inlined
        message = f"Exported {inlined} global memories to {output_path}"
        if scoped:
            message += f"; {scoped} scoped kept out (load on demand via build_context)"
        return message

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
