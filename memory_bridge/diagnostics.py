"""Local diagnostic export for reproducible demos and reviews."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .context_builder import build_context_markdown
from .store import MemoryStore


def export_diagnostic_bundle(store: MemoryStore, output_path: str | Path) -> Path:
    """Write a local diagnostic zip.

    The bundle may include user-provided feedback text. It should be reviewed
    before sharing publicly.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    memories = store.list(status="all")
    active = [item for item in memories if item.status == "active"]
    evidence = store.evidence_events(limit=1000)
    events = store.events(limit=1000)

    memory_cards = []
    for memory in memories:
        evidence_ids = ", ".join(ref.id for ref in memory.evidence_refs) or "-"
        memory_cards.append(
            "\n".join(
                [
                    f"## {memory.id}",
                    f"Status: {memory.status}",
                    f"Layer: {memory.layer}",
                    f"Type: {memory.type}",
                    f"Scope: {memory.scope.key()}",
                    f"Slot: {memory.slot}",
                    f"Source event: {memory.source_event_id or '-'}",
                    f"Evidence refs: {evidence_ids}",
                    f"Content: {memory.content}",
                    f"Rationale: {memory.rationale}",
                    "",
                ]
            )
        )

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "memories.json",
            json.dumps([memory.to_dict() for memory in memories], ensure_ascii=False, indent=2),
        )
        archive.writestr(
            "evidence_events.json",
            json.dumps([event.to_dict() for event in evidence], ensure_ascii=False, indent=2),
        )
        archive.writestr(
            "memory_events.json",
            json.dumps(events, ensure_ascii=False, indent=2),
        )
        archive.writestr("memory_cards.md", "\n".join(memory_cards))
        archive.writestr("active_context.md", build_context_markdown(active))
        archive.writestr(
            "README.txt",
            "This diagnostic bundle is local and may include user-provided evidence text. Review before sharing.\n",
        )
    return output
