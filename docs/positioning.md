# Positioning: Traceable Workstyle Memory Governance MCP

## Core position

Workstyle Memory Bridge is **not** a generic memory MCP.

It is a lightweight governance layer that turns explicit user feedback into portable, inspectable, editable, deletable, **source-backed workstyle memories** for Claude, Codex, MCP clients, and product assistants.

North star:

> One feedback event should improve future collaboration across tools while remaining inspectable, editable, reversible, and traceable.

## Why this is not “another memory MCP”

The MCP memory space already has many projects focused on broad personal memory, semantic recall, knowledge graphs, long-task context compression, and project memory banks. A generic `add/search/delete memory` server is no longer a sharp entry point.

This project deliberately chooses a narrower and more testable wedge:

> **How does user feedback become a verifiable and traceable change in the next collaboration?**

That makes it suitable for WASC-style continuous-use evaluation and for daily use with coding agents.

## Differentiation pillars

### 1. Workstyle-first

Store how the user wants AI to collaborate, not everything the AI sees.

In scope:

- response style preferences;
- planning and coding workflows;
- project-specific collaboration rules;
- tool-specific conventions;
- product/user/team workflow preferences;
- explicit corrections and anti-preferences.

Out of scope for MVP:

- full chat history archives;
- personal life memory;
- generic note capture;
- broad RAG knowledge base;
- automatic scraping of tool histories;
- “remember everything” products.

### 2. Governance-first

The important unit is not a sentence in a memory bank. It is a governed record:

```yaml
id: mem_xxx
layer: L1_atom
type: workflow
scope: task_type=technical_planning
slot: technical_plan_structure
status: active | superseded | archived | deleted
source_event_id: ev_xxx
evidence_refs:
  - id: ev_xxx
    kind: user_feedback
content: ...
rationale: ...
confidence: 0.92
supersedes: mem_old
valid_from: ...
valid_until: ...
```

The resolver handles lifecycle using explicit schema keys:

```text
same slot + same scope -> old active memory is superseded
```

This prevents the system from endlessly accumulating conflicting memories.

### 3. Traceability-first

v0.3 adds a lightweight Workstyle L0-L3 framing:

| Layer | Meaning |
|---|---|
| L0_event | original user feedback, correction, or task fragment |
| L1_atom | one governed workstyle memory |
| L2_scenario | a user-confirmed scenario playbook assembled from source L1 memories |
| L3_profile | broad user/team collaboration profile; not a default MVP behavior driver |

The MVP implements L0 evidence events, L1 atoms, and a lightweight optional L2 scenario layer. L2 is not a background summarizer and not a new extraction source: it is a model/user-confirmed playbook assembled from active L1 memories, with `source_memory_refs` back to those L1 records and evidence refs back to L0. If a source L1 changes, is superseded, or is deleted, the L2 scenario becomes stale and the read path falls back to L1.

L3 remains a boundary marker, not a core MVP feature. It should not become a broad user-profile system or silently drive all tasks.

Traceability goal:

```text
memory card -> evidence_refs -> original feedback event -> lifecycle events
```

### 4. Evaluation-first

The product must make five moments observable:

1. user feedback creates structured memory;
2. the memory can be inspected back to source evidence;
3. the next task uses that memory without repeated instruction;
4. changed preference supersedes the old memory;
5. deleted memory stops affecting context and exports.

The included `scripts/demo_8_steps.sh` is the canonical test harness.

### 5. Projection-first

The memory store is the source of truth. Tool-specific instruction files are projections:

```text
SQLite memory store
  -> build_context
  -> CLAUDE.md
  -> AGENTS.md
  -> MCP tool result
  -> product assistant context
```

Claude/Codex files should not become the source of truth. They are managed sections that can be regenerated.

### 6. No heuristic extraction

Do not classify feedback with keyword matching, regexes, phrase lists, or hand-authored heuristic trees.

Semantic extraction must come from either:

- model-backed structured output; or
- explicit user/upstream JSON.

The application code owns validation, lifecycle, scoping, evidence linking, export, and auditability.

## Product wedge

Primary wedge:

> Developers and builders who use multiple AI coding agents and repeatedly have to explain the same collaboration preferences.

Secondary wedge:

> Product teams embedding AI assistants that should adapt to each user/team workflow without becoming a black-box personal memory system.

Example product extension:

- HVAC operations assistant remembers each operator/team’s diagnostic and reporting workflow.
- Project assistant remembers planning/review style per project or team.
- Support assistant remembers account-specific communication conventions.

## Naming guidance

Preferred phrases:

- workstyle memory;
- feedback-to-memory;
- memory governance;
- traceable memory card;
- inspectable adaptation;
- deletion-verifiable memory;
- Claude/Codex instruction projection;
- competition-ready continuous-use harness.

Avoid leading with:

- universal AI memory;
- remember everything;
- generic semantic memory MCP;
- knowledge graph memory platform;
- personal second brain;
- long-task context compression platform.
