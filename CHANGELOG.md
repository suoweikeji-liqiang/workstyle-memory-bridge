# Changelog

## 0.4.1

Zero-time vocabulary. Field data showed hosts improvise task_type labels on
their first call (ops-guidance, code-edit, debugging) and rarely act on the
response-time hint unprompted, so scoped memories still missed their moment.

- The exported managed section now enumerates the exact stored scope values of
  the scoped memories it keeps out, with the instruction to call
  `build_context` with that exact value when the task matches — every fresh
  session learns the vocabulary at time zero, before any tool call.
- Skill guidance updated to point hosts at the managed section's values and the
  unmatched hint instead of invented labels.

## 0.4.0

Read-path observability, driven by a week of real dogfooding: scoped memories
(`task_type=feature-development`) silently never fired because global memories
match every call, so the empty-result scope hint was unreachable and nothing
recorded what callers had asked for.

- Every `build-context` response now reports scoped active memories the call
  did NOT match, with their exact stored scope values (enumeration only —
  matching stays exact, no fuzzy rules).
- Added `context_requests` audit table: every CLI/MCP context request logs its
  criteria, returned memory ids, matched and unmatched counts.
- Added `context-log` command to query the read-path audit.
- Diagnostic bundles now include `context_requests.json`.
- `reset` also clears the read-path audit for reproducible runs.

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
