# Changelog

## 0.3.0

Traceability update after reviewing layered agent-memory systems such as TencentDB-Agent-Memory.

- Upgraded north star to: one feedback, multi-tool effect, viewable, reversible, evolvable, and traceable.
- Added lightweight L0-L3 workstyle memory framing.
- Added `evidence_events` table for L0 source events.
- Added `source_event_id` and `evidence_refs` on memory records.
- Added `inspect` command for memory card + evidence + lifecycle.
- Added `verify-deletion` command for WASC deletion proof.
- Added `export-diagnostic` command for local reproducibility bundles.
- Updated MCP adapter with inspect and deletion verification tools.
- Added TencentDB-Agent-Memory reference boundary doc.
- Kept the core lightweight: no vector DB, graph DB, OpenClaw plugin, long-task canvas, or heuristic extraction.

## 0.2.0

Positioning update after competitive MCP landscape review.

- Repositioned project as **Workstyle Memory Governance MCP**, not a generic memory MCP.
- Added docs for positioning, WASC scoring, integrations, and non-goals.
- Strengthened guardrails against drifting into universal memory, knowledge graph memory, or project memory-bank clones.
- Expanded MCP adapter plan to include edit/export style operations.
- Kept the core lightweight: SQLite, CLI, optional MCP adapter, no vector DB, no graph DB, no heuristic extraction.

## 0.1.0

Initial package.

- CLI memory lifecycle.
- SQLite memory store.
- Structured memory schema.
- Slot + scope supersede resolver.
- Claude/Codex exporters.
- Optional MCP adapter.
- WASC 8-step demo script.
- No-heuristic extraction policy and tests.
