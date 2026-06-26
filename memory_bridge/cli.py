"""Command line interface for Workstyle Memory Bridge."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from .context_builder import (
    ContextCriteria,
    available_scope_values,
    build_context_explanation_markdown,
    explain_context_request,
    respond_to_context_request,
)
from .deletion_verifier import verify_deleted_memory
from .diagnostics import export_diagnostic_bundle
from .doctor import run_doctor
from .exporters import export_instruction_file
from .extractor import (
    ExtractorUnavailable,
    existing_memory_digest,
    extract_from_feedback,
    load_json_argument,
)
from .resolver import PreviewResult, apply_drafts, preview_drafts
from .scenario import (
    load_scenario_json,
    prepare_scenario_drafts,
    scenario_prompt,
    scenario_source_ids,
    scenario_status,
    select_l1_sources,
)
from .schemas import CreatedFrom, Scope, ValidationError
from .store import MemoryStore


def _store(args: argparse.Namespace) -> MemoryStore:
    return MemoryStore(args.db)


def _criteria(args: argparse.Namespace) -> ContextCriteria:
    return ContextCriteria(
        project=getattr(args, "project", None),
        tool=getattr(args, "tool", None),
        task_type=getattr(args, "task_type", None),
        session_id=getattr(args, "session_id", None),
        product=getattr(args, "product", None),
        domain=getattr(args, "domain", None),
        user_id=getattr(args, "user_id", None),
    )


def _task_context(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "project": getattr(args, "project", None),
        "tool": getattr(args, "tool", None),
        "task_type": getattr(args, "task_type", None),
        "session_id": getattr(args, "session_id", None),
        "product": getattr(args, "product", None),
        "domain": getattr(args, "domain", None),
        "user_id": getattr(args, "user_id", None),
    }


def _non_empty_context(args: argparse.Namespace) -> Dict[str, Any]:
    return {key: value for key, value in _task_context(args).items() if value is not None}


def cmd_reset(args: argparse.Namespace) -> int:
    store = _store(args)
    store.reset(actor="cli")
    print("Memory cleared. Active memories: 0")
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    store = _store(args)
    memories = store.list(status=args.status)
    if args.format == "json":
        print(json.dumps([m.to_dict() for m in memories], ensure_ascii=False, indent=2))
        return 0
    if not memories:
        print("No memories found.")
        return 0
    for memory in memories:
        print(f"[{memory.status}] {memory.id} :: {memory.slot}")
        print(f"  layer: {memory.layer}")
        print(f"  type: {memory.type}")
        print(f"  scope: {memory.scope.key()}")
        print(f"  content: {memory.content}")
        print(f"  rationale: {memory.rationale}")
        print(f"  confidence: {memory.confidence:.2f}")
        print(f"  source_event_id: {memory.source_event_id or '-'}")
        print(f"  supersedes: {memory.supersedes or '-'}")
        print()
    return 0


def _print_preview(preview: PreviewResult) -> None:
    print("DRY RUN — nothing written.\n")
    for index, item in enumerate(preview.previews, start=1):
        draft = item.draft
        print(f"Proposed memory {index}:")
        print(f"  type: {draft.type}")
        print(f"  scope: {draft.scope.key()}")
        print(f"  slot: {draft.slot}")
        print(f"  content: {draft.content}")
        print(f"  rationale: {draft.rationale}")
        print(f"  confidence: {draft.confidence:.2f}")
        if item.would_supersede:
            print("  would supersede:")
            for old in item.would_supersede:
                print(f"    - {old.id}: {old.content}")
        else:
            print("  would supersede: (none — new slot)")
        print()


def cmd_ingest_feedback(args: argparse.Namespace) -> int:
    store = _store(args)
    memory_json: Optional[Dict[str, Any]] = None
    existing: Optional[List[Dict[str, Any]]] = None
    if args.memory_json:
        memory_json = load_json_argument(args.memory_json)
    else:
        existing = existing_memory_digest(store.list(status="active"))
    try:
        drafts = extract_from_feedback(
            args.feedback,
            task_context=_task_context(args),
            memory_json=memory_json,
            llm_command=args.llm_command,
            existing_memories=existing,
        )
    except ExtractorUnavailable as exc:
        print(str(exc), file=sys.stderr)
        print("\n--- Extraction prompt to send to a model ---\n", file=sys.stderr)
        print(exc.prompt, file=sys.stderr)
        return 2

    if args.dry_run:
        _print_preview(preview_drafts(store, drafts))
        available = available_scope_values(store)
        if available:
            print("Existing scope values in use (reuse the exact value if a proposal is a variant):")
            for dim, found in available.items():
                print(f"  {dim}: {', '.join(found)}")
        return 0

    evidence = store.create_evidence(
        kind="user_feedback",
        text=args.feedback,
        metadata=_task_context(args),
    )
    evidence_ref = store.evidence_ref_for(evidence)
    for draft in drafts:
        if not draft.source_event_id:
            draft.source_event_id = evidence.id
        if not draft.evidence_refs:
            draft.evidence_refs = [evidence_ref]
        if not draft.created_from.message_excerpt and not draft.created_from.task_context:
            draft.created_from = CreatedFrom(
                session_id=getattr(args, "session_id", None),
                message_excerpt=args.feedback[:240],
                task_context=_non_empty_context(args),
            )
    result = apply_drafts(store, drafts, actor="cli")
    print(f"Inserted: {len(result.inserted)}")
    print(f"Superseded: {len(result.superseded)}")
    for memory in result.inserted:
        print(f"- {memory.id}: {memory.content}")
        print(f"  evidence: {memory.source_event_id or '-'}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    store = _store(args)
    memory = store.get(args.memory_id)
    if not memory:
        print(f"Memory not found: {args.memory_id}", file=sys.stderr)
        return 1

    lines: List[str] = [
        "Memory Card",
        "-----------",
        f"ID: {memory.id}",
        f"Status: {memory.status}",
        f"Layer: {memory.layer}",
        f"Type: {memory.type}",
        f"Scope: {memory.scope.key()}",
        f"Slot: {memory.slot}",
        f"Supersedes: {memory.supersedes or '-'}",
        f"Source event: {memory.source_event_id or '-'}",
        f"Content: {memory.content}",
        f"Rationale: {memory.rationale}",
        "",
        "Evidence",
        "--------",
    ]
    if memory.evidence_refs:
        for ref in memory.evidence_refs:
            lines.append(f"- {ref.id} ({ref.kind})")
            lines.append(f"  excerpt: {ref.excerpt}")
            event = store.get_evidence(ref.id)
            if event:
                lines.append(f"  created_at: {event.created_at}")
                lines.append(f"  metadata: {json.dumps(event.metadata, ensure_ascii=False)}")
    else:
        lines.append("- No evidence refs attached.")

    if memory.layer == "L2_scenario":
        status = scenario_status(store, memory)
        lines.extend(["", "Scenario Sources", "----------------"])
        lines.append(f"Fresh: {'yes' if status.fresh else 'no'}")
        if status.source_refs:
            for ref in status.source_refs:
                lines.append(f"- {ref.id} @ {ref.updated_at} ({ref.status})")
        else:
            lines.append("- No source L1 refs recorded.")
        if status.reasons:
            lines.append("Stale reasons:")
            for reason in status.reasons:
                lines.append(f"- {reason}")

    lifecycle = [event for event in store.events(limit=1000) if event.get("memory_id") == memory.id]
    lines.extend(["", "Lifecycle", "---------"])
    if lifecycle:
        for event in reversed(lifecycle):
            lines.append(f"- {event['timestamp']} :: {event['action']} :: {event.get('note') or ''}")
    else:
        lines.append("- No lifecycle events found.")
    print("\n".join(lines))
    return 0


def cmd_build_context(args: argparse.Namespace) -> int:
    store = _store(args)
    print(
        respond_to_context_request(
            store, _criteria(args), limit=args.limit, actor="cli", fmt=args.format
        )
    )
    return 0


def cmd_build_scenario(args: argparse.Namespace) -> int:
    store = _store(args)
    criteria = _criteria(args)
    sources = select_l1_sources(store, criteria, limit=args.source_limit)
    if not sources:
        print("No matching active L1 memories found for this scope.", file=sys.stderr)
        return 1

    if not args.scenario_json:
        print(
            "No --scenario-json provided. Send this prompt to a model, review the JSON, "
            "then rerun build-scenario with --scenario-json:",
            file=sys.stderr,
        )
        print("\n--- L2 scenario prompt ---\n", file=sys.stderr)
        print(scenario_prompt(sources, criteria), file=sys.stderr)
        return 2

    payload = load_scenario_json(args.scenario_json)
    if args.dry_run:
        drafts = prepare_scenario_drafts(payload, sources, criteria)
        _print_preview(preview_drafts(store, drafts))
        print("Source L1 memories:")
        for source in sources:
            print(f"- {source.id}: {source.slot} ({source.scope.key()})")
        return 0

    source_ids = [source.id for source in sources]
    evidence = store.create_evidence(
        kind="manual_note",
        text=(
            "L2 scenario playbook accepted from active L1 memories: "
            + ", ".join(source_ids)
        ),
        metadata={**criteria.to_dict(), "source_memory_ids": source_ids},
    )
    drafts = prepare_scenario_drafts(
        payload,
        sources,
        criteria,
        evidence_ref=store.evidence_ref_for(evidence),
    )
    result = apply_drafts(store, drafts, actor="cli")
    print(f"Inserted: {len(result.inserted)}")
    print(f"Superseded: {len(result.superseded)}")
    for memory in result.inserted:
        print(f"- {memory.id}: {memory.slot}")
        print(f"  layer: {memory.layer}")
        print(f"  sources: {', '.join(scenario_source_ids(memory))}")
        print(f"  evidence: {memory.source_event_id or '-'}")
    return 0


def cmd_scenario_status(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.memory_id:
        memories = [store.get(args.memory_id)]
    else:
        memories = [m for m in store.list(status="active") if m.layer == "L2_scenario"]
    found = [memory for memory in memories if memory is not None]
    if not found:
        print("No scenario memories found.", file=sys.stderr)
        return 1
    reports = [scenario_status(store, memory) for memory in found]
    if args.format == "json":
        print(json.dumps([report.to_dict() for report in reports], ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(report.text() for report in reports))
    return 0 if all(report.fresh for report in reports) else 1


def cmd_context_log(args: argparse.Namespace) -> int:
    store = _store(args)
    print(json.dumps(store.context_requests(limit=args.limit), ensure_ascii=False, indent=2))
    return 0


def cmd_why_used(args: argparse.Namespace) -> int:
    store = _store(args)
    explanation = explain_context_request(store, request_id=args.request_id)
    if args.format == "json":
        print(json.dumps(explanation, ensure_ascii=False, indent=2))
    else:
        print(build_context_explanation_markdown(explanation))
    return 0 if explanation.get("status") == "ok" else 1


def cmd_delete(args: argparse.Namespace) -> int:
    store = _store(args)
    record = store.soft_delete(args.memory_id, actor="cli")
    if not record:
        print(f"Memory not found: {args.memory_id}", file=sys.stderr)
        return 1
    print(f"Deleted: {record.id}")
    return 0


def cmd_verify_deletion(args: argparse.Namespace) -> int:
    store = _store(args)
    report = verify_deleted_memory(store, args.memory_id, _criteria(args), limit=args.limit)
    print(report.text())
    return 0 if report.ok else 1


def cmd_edit(args: argparse.Namespace) -> int:
    store = _store(args)
    record = store.get(args.memory_id)
    if not record:
        print(f"Memory not found: {args.memory_id}", file=sys.stderr)
        return 1
    if args.content is not None:
        record.content = args.content
    if args.rationale is not None:
        record.rationale = args.rationale
    if args.slot is not None:
        record.slot = args.slot
    if args.type is not None:
        record.type = args.type
    if args.layer is not None:
        record.layer = args.layer
    if args.confidence is not None:
        record.confidence = args.confidence
    if args.status is not None:
        record.status = args.status
    if args.scope_json is not None:
        record.scope = Scope.from_dict(load_json_argument(args.scope_json))
    try:
        store.update(record, actor="cli", note="manual edit")
    except ValidationError as exc:
        print(f"Invalid edit: {exc}", file=sys.stderr)
        return 2
    print(f"Updated: {record.id}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    store = _store(args)
    memories = store.list(status="active")
    path = export_instruction_file(
        args.path, memories, target=args.target, global_only=not args.all_scopes
    )
    if args.all_scopes:
        print(f"Exported {len(memories)} memories to {path}")
        return 0
    inlined = sum(1 for m in memories if m.scope.level == "global")
    scoped = len(memories) - inlined
    message = f"Exported {inlined} global memories to {path}"
    if scoped:
        message += f" ({scoped} scoped kept out — they load on demand via build-context)"
    print(message)
    return 0


def cmd_export_diagnostic(args: argparse.Namespace) -> int:
    store = _store(args)
    path = export_diagnostic_bundle(store, args.output)
    print(f"Diagnostic bundle written to {path}")
    print("Review before sharing: the bundle may include user-provided evidence text.")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    store = _store(args)
    report = run_doctor(store)
    print(report.text())
    return 0 if report.ok else 1


def cmd_events(args: argparse.Namespace) -> int:
    store = _store(args)
    print(json.dumps(store.events(limit=args.limit), ensure_ascii=False, indent=2))
    return 0


def add_scope_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project")
    parser.add_argument("--tool")
    parser.add_argument("--task-type")
    parser.add_argument("--session-id")
    parser.add_argument("--product")
    parser.add_argument("--domain")
    parser.add_argument("--user-id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory-bridge")
    parser.add_argument("--db", default=None, help="SQLite path. Defaults to ~/.memory_bridge/memory_bridge.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("reset")
    p.set_defaults(func=cmd_reset)

    p = sub.add_parser("view")
    p.add_argument("--status", default="active", choices=["active", "superseded", "archived", "deleted", "all"])
    p.add_argument("--format", default="text", choices=["text", "json"])
    p.set_defaults(func=cmd_view)

    p = sub.add_parser("ingest-feedback")
    p.add_argument("--feedback", required=True)
    p.add_argument("--memory-json", help="Structured JSON string, or @path to JSON file")
    p.add_argument("--llm-command", help="External command that reads prompt from stdin and returns JSON")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview proposed memories and what they would supersede, without writing",
    )
    add_scope_args(p)
    p.set_defaults(func=cmd_ingest_feedback)

    p = sub.add_parser("inspect")
    p.add_argument("memory_id")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("build-context")
    add_scope_args(p)
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--format", default="markdown", choices=["markdown", "json"])
    p.set_defaults(func=cmd_build_context)

    p = sub.add_parser("build-scenario")
    add_scope_args(p)
    p.add_argument("--source-limit", type=int, default=12)
    p.add_argument("--scenario-json", help="Structured L2 memory JSON string, or @path")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the L2 scenario and what it would supersede, without writing",
    )
    p.set_defaults(func=cmd_build_scenario)

    p = sub.add_parser("scenario-status")
    p.add_argument("memory_id", nargs="?")
    p.add_argument("--format", default="text", choices=["text", "json"])
    p.set_defaults(func=cmd_scenario_status)

    p = sub.add_parser("delete")
    p.add_argument("memory_id")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("verify-deletion")
    p.add_argument("memory_id")
    add_scope_args(p)
    p.add_argument("--limit", type=int, default=12)
    p.set_defaults(func=cmd_verify_deletion)

    p = sub.add_parser("edit")
    p.add_argument("memory_id")
    p.add_argument("--content")
    p.add_argument("--rationale")
    p.add_argument("--slot")
    p.add_argument("--type")
    p.add_argument("--layer")
    p.add_argument("--confidence", type=float)
    p.add_argument("--status", choices=["active", "superseded", "archived", "deleted"])
    p.add_argument("--scope-json", help="Scope JSON string, or @path")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("export")
    p.add_argument("target", choices=["claude", "codex"])
    p.add_argument("--path", required=True)
    p.add_argument(
        "--all-scopes",
        action="store_true",
        help="Inline all active memories. Default: only global ones; scoped memories load on demand via build-context.",
    )
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("export-diagnostic")
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_export_diagnostic)

    p = sub.add_parser("doctor")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("events")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_events)

    p = sub.add_parser(
        "context-log",
        help="Read-path audit: when context was requested, with what scope, and what it got",
    )
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_context_log)

    p = sub.add_parser(
        "why-used",
        help="Explain the latest or selected build-context recall result",
    )
    p.add_argument("--request-id", type=int)
    p.add_argument("--format", default="text", choices=["text", "json"])
    p.set_defaults(func=cmd_why_used)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
