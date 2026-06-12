"""Export active memories into tool-native instruction files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .context_builder import build_context_markdown, collect_scope_values
from .schemas import MemoryRecord

BEGIN = "<!-- memory-bridge:begin -->"
END = "<!-- memory-bridge:end -->"


def managed_section(
    memories: Iterable[MemoryRecord], target: str, scoped: Iterable[MemoryRecord] = ()
) -> str:
    title = "Claude Code" if target == "claude" else "Codex"
    body = build_context_markdown(memories)
    scoped = list(scoped)
    note = ""
    if scoped:
        # Zero-time vocabulary: enumerate the exact stored scope values so a
        # fresh session can label its FIRST build_context call correctly,
        # instead of improvising a variant and relying on the response-time
        # hint (which field data shows hosts rarely act on unprompted).
        lines = [
            f"> {len(scoped)} task/project/tool-scoped memory(ies) are kept out of this "
            "always-on file to keep it small. They load on demand: when the current task "
            "matches one of the stored scope values below, call `build_context` with that "
            "exact value (scope matching is exact — never invent variants):",
        ]
        for dim, found in collect_scope_values(scoped).items():
            lines.append(f"> - {dim}: {', '.join(found)}")
        note = "\n\n" + "\n".join(lines)
    return f"""{BEGIN}
# Workstyle Memory Bridge for {title}

{body}{note}

These entries are managed by Memory Bridge. To inspect or change them, use:

```bash
memory-bridge view
memory-bridge edit <memory_id>
memory-bridge delete <memory_id>
```
{END}
""".strip()


def server_instructions(memories: Iterable[MemoryRecord]) -> str:
    """Zero-time context for the MCP handshake.

    Hosts that surface MCP server instructions place this in the system prompt
    at session start, so a fresh session knows the always-on memories and the
    exact scoped vocabulary before its first tool call — no instruction-file
    export required. Recomputed each server start; mid-session memory changes
    appear in the next session.
    """
    memories = list(memories)
    inlined = [m for m in memories if m.scope.level == "global"]
    scoped = [m for m in memories if m.scope.level != "global"]
    lines = ["This server governs how the user wants you to work (workstyle memories)."]
    if inlined:
        lines += [
            "",
            "Always-on global memories — follow them; explicit user instructions "
            "in the current task override:",
        ]
        lines += [f"- ({m.type}, slot={m.slot}) {m.content}" for m in inlined]
    if scoped:
        lines += [
            "",
            f"{len(scoped)} scoped memory(ies) load on demand. At task start, call "
            "build_context with the exact stored scope value that fits the task "
            "(matching is exact — never invent variants):",
        ]
        for dim, found in collect_scope_values(scoped).items():
            lines.append(f"- {dim}: {', '.join(found)}")
    if not memories:
        lines += [
            "",
            "No memories stored yet. When the user states a durable workstyle "
            "preference, capture it via remember_feedback (dry_run first unless "
            "the user explicitly says to remember).",
        ]
    # Routing ships with the server, not with one user's hand-written config:
    # hosts have a native-memory instinct, and a preference duplicated there
    # drifts on edits and survives verify-deletion.
    lines += [
        "",
        "Memory routing: durable workstyle preferences (how the user wants you "
        "to plan, write, review, communicate) belong in THIS store — capture "
        "them via remember_feedback and do NOT also write them into your own "
        "native memory; duplicate copies drift and survive deletion. If you "
        "notice the same preference both here and in native memory or an "
        "instruction file, tell the user and propose consolidating it into this "
        "store (dry_run first; the user confirms). Native memory remains the "
        "right place for non-workstyle facts such as project notes and todos.",
        "",
        "These instructions are a snapshot taken when this session started. The "
        "store is authoritative: if memories are edited or deleted during the "
        "session, trust build_context / view_memory results over this static copy.",
    ]
    return "\n".join(lines)


def strip_existing_section(text: str) -> str:
    start = text.find(BEGIN)
    end = text.find(END)
    if start == -1 or end == -1 or end < start:
        return text.strip()
    return (text[:start] + text[end + len(END) :]).strip()


def export_instruction_file(
    path: str | Path,
    memories: Iterable[MemoryRecord],
    target: str,
    global_only: bool = True,
) -> Path:
    """Write memories into a tool-native instruction file.

    By default only global-scope memories are inlined, so the always-on file
    stays small no matter how many scoped preferences accumulate. Scoped
    memories are loaded on demand via build_context instead. Pass
    global_only=False to inline everything.
    """
    memories = list(memories)
    if global_only:
        inlined = [m for m in memories if m.scope.level == "global"]
        scoped = [m for m in memories if m.scope.level != "global"]
    else:
        inlined = memories
        scoped = []
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    cleaned = strip_existing_section(existing)
    section = managed_section(inlined, target=target, scoped=scoped)
    final = section if not cleaned else f"{section}\n\n{cleaned}"
    path.write_text(final + "\n", encoding="utf-8")
    return path
