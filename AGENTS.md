# Instructions for AI coding agents

## Project north star

Build a lightweight **Traceable Workstyle Memory Governance MCP / CLI Skill**: user feedback becomes structured, inspectable, editable, deletable, source-backed workstyle memory that can be reused across Claude, Codex, MCP tools, and product assistants.

The project is not a generic memory MCP. It should prove that explicit user feedback can create a verifiable and traceable change in future collaboration.

## Strategic positioning

Do not drift into these crowded categories:

- universal personal memory;
- semantic memory search;
- project memory bank;
- full knowledge graph memory;
- long-task context compression platform;
- second brain / note capture;
- full AI coding agent.

Keep the wedge sharp:

```text
feedback -> governed workstyle memory -> source evidence -> scoped context -> visible behavior change -> editable/deletable proof
```

## Traceability constraint

Every memory created from user feedback should be traceable to an L0 evidence event when possible.

Allowed deterministic traceability logic:

- create an evidence event for explicit user feedback;
- attach `source_event_id` and `evidence_refs` to extracted drafts;
- inspect memory with source evidence and lifecycle events;
- export a diagnostic bundle for local reproduction.

Do not use traceability as an excuse to capture everything automatically. MVP memory creation remains feedback-driven and user-visible.

## Non-negotiable extraction constraint

Do not implement core semantic memory extraction with keyword rules, regexes, phrase lists, or handcrafted heuristics.

Banned examples:

```python
if "以后" in feedback: ...
if "不要" in feedback: ...
re.search(..., feedback)
KEYWORDS = {"preference": [...]}
```

Allowed deterministic logic:

- schema validation;
- explicit scope matching from already structured metadata;
- slot + scope conflict resolution;
- status transitions: active / superseded / archived / deleted;
- user-issued reset/view/edit/delete commands;
- evidence linking;
- export formatting;
- audit event recording.

Semantic extraction must be model-backed structured output or explicit user-provided JSON. If no extractor is configured, fail clearly and print the model prompt. Do not add a heuristic fallback.

## Keep it small

Prefer stdlib and simple SQLite. Do not add vector DB, graph DB, web UI, multi-agent orchestration, or background sync unless there is a clear WASC scoring or daily self-use reason.

## Competition scoring focus

The code should make these five moments obvious:

1. feedback creates structured memory;
2. memory can be inspected back to source evidence;
3. next task uses memory;
4. changed preference supersedes old memory;
5. deleted memory stops affecting output and exports.

## Documentation to preserve

Do not remove or weaken:

- `docs/positioning.md`
- `docs/tencentdb_agent_memory_reference.md`
- `docs/non_goals.md`
- `policies/no_heuristic_extraction.md`
- `scripts/demo_8_steps.sh`
- tests that prevent heuristic extraction or positioning drift
