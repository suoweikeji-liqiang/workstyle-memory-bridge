"""Optional MCP adapter for Workstyle Memory Bridge.

Install MCP support separately, then run:
    python -m memory_bridge.mcp_server

The core package stays stdlib-only. This adapter is intentionally thin: MCP tools
call the same store/resolver/context/export functions used by the CLI.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from .context_builder import ContextCriteria, build_context_markdown, select_memories
from .deletion_verifier import verify_deleted_memory
from .exporters import export_instruction_file
from .extractor import existing_memory_digest, extract_from_feedback
from .resolver import apply_drafts
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

    mcp = FastMCP("workstyle-memory-governance")

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
        memory_json: Optional[str] = None,
        project: Optional[str] = None,
        tool: Optional[str] = None,
        task_type: Optional[str] = None,
        session_id: Optional[str] = None,
        product: Optional[str] = None,
        domain: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Convert explicit user feedback into governed workstyle memory.

        `memory_json` may contain structured extractor output. If absent, the
        configured model-backed extractor is used. No heuristic fallback exists.
        """
        payload = json.loads(memory_json) if memory_json else None
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
        drafts = extract_from_feedback(
            feedback,
            task_context=context,
            memory_json=payload,
            existing_memories=existing,
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
        return json.dumps(
            {"memory": memory.to_dict(), "evidence": evidence, "lifecycle": lifecycle},
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
        """Return relevant active workstyle memories for the current task context."""
        memories = select_memories(
            _store(),
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
        return build_context_markdown(memories)

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
    def export_instructions(
        target: str,
        path: str,
        project: Optional[str] = None,
        tool: Optional[str] = None,
        task_type: Optional[str] = None,
        session_id: Optional[str] = None,
        product: Optional[str] = None,
        domain: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 12,
    ) -> str:
        """Export selected memories into a managed CLAUDE.md or AGENTS.md section."""
        memories = select_memories(
            _store(),
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
        output_path = export_instruction_file(path, memories, target=target)
        return f"Exported {len(memories)} memories to {output_path}"

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
