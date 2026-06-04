"""Export active memories into tool-native instruction files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .context_builder import build_context_markdown
from .schemas import MemoryRecord

BEGIN = "<!-- memory-bridge:begin -->"
END = "<!-- memory-bridge:end -->"


def managed_section(memories: Iterable[MemoryRecord], target: str, scoped_count: int = 0) -> str:
    title = "Claude Code" if target == "claude" else "Codex"
    body = build_context_markdown(memories)
    note = ""
    if scoped_count:
        note = (
            f"\n\n> {scoped_count} task/project/tool-scoped memory(ies) are kept out of this "
            "always-on file to keep it small; they load on demand via `build_context`."
        )
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
        scoped_count = len(memories) - len(inlined)
    else:
        inlined = memories
        scoped_count = 0
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    cleaned = strip_existing_section(existing)
    section = managed_section(inlined, target=target, scoped_count=scoped_count)
    final = section if not cleaned else f"{section}\n\n{cleaned}"
    path.write_text(final + "\n", encoding="utf-8")
    return path
