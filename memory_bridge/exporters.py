"""Export active memories into tool-native instruction files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .context_builder import build_context_markdown
from .schemas import MemoryRecord

BEGIN = "<!-- memory-bridge:begin -->"
END = "<!-- memory-bridge:end -->"


def managed_section(memories: Iterable[MemoryRecord], target: str) -> str:
    title = "Claude Code" if target == "claude" else "Codex"
    body = build_context_markdown(memories)
    return f"""{BEGIN}
# Workstyle Memory Bridge for {title}

{body}

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


def export_instruction_file(path: str | Path, memories: Iterable[MemoryRecord], target: str) -> Path:
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    cleaned = strip_existing_section(existing)
    section = managed_section(memories, target=target)
    final = section if not cleaned else f"{section}\n\n{cleaned}"
    path.write_text(final + "\n", encoding="utf-8")
    return path
