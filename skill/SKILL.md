---
name: workstyle-memory-bridge
description: Traceable Workstyle Memory Governance for Claude Code, Codex, MCP clients, and provider-switched local agent setups. Use when the user explicitly asks to remember, inspect, edit, delete, verify, export, or apply durable AI collaboration/workstyle preferences; also use when explicit feedback should become governed, source-backed workstyle memory. Do not use for generic personal facts, project task tracking, session handoff summaries, or broad user profiles.
---

# Workstyle Memory Governance Skill

## What it does

Memory Bridge Skill turns explicit user feedback into structured workstyle memories and makes those memories portable across AI tools.

It is not a generic memory MCP. It is a traceable governance layer for remembering how the user wants AI to collaborate.

## North star

One feedback event should improve future collaboration across tools while remaining inspectable, editable, reversible, and traceable to source evidence.

## Memory routing (avoid duplicate stores)

Durable workstyle preferences belong in this store only — hosts must not duplicate them into their own native memory (duplicates drift on edits and survive deletion, breaking the verify-deletion guarantee). Duplicates found in native memory or instruction files are surfaced to the user with a consolidation proposal (dry-run, user confirms). Native memory remains the right place for non-workstyle facts such as project notes and todos. This rule ships in the MCP server instructions, so every host receives it at the handshake.

If `user-profile-keeper` or another profile skill is installed, use this split:
workstyle/collaboration preferences that should directly change future agent
behavior go to Memory Bridge; user background, private profile facts, and
clarification-only summaries stay in the profile system. Do not store the same
workstyle preference in both places.

## Tools

- `reset_memory`: clear all memories and evidence events for reproducible testing.
- `view_memory`: show current memory state.
- `remember_feedback`: convert feedback into structured memories and attach L0 evidence refs. Supports `dry_run` for propose-then-confirm.
- `inspect_memory`: inspect a memory card, source evidence, and lifecycle.
- `build_context`: return relevant active memories for a task. Scope matching is exact — reuse the stored scope values (the managed export section and the unmatched hint both list them) rather than inventing variants.
- `why_used`: explain the latest or selected `build_context` result: which memories were returned, why their scopes matched, and which structured ranking signals ordered them.
- `build_scenario`: assemble a lightweight L2 scenario playbook from matching active L1 memories. Call first without `scenario_json` to get source memories and a prompt; then generate JSON, preview with `dry_run=True`, show the user, and commit only after confirmation.
- `scenario_status`: report whether L2 scenario playbooks are fresh or stale against their source L1 memories.
- `edit_memory`: update a memory.
- `memory_doctor`: lifecycle + recall health report (dead scoped memories, requested scope values that matched nothing). Facts only — the host AI judges semantics and proposes governed fixes for the user to confirm.
- `delete_memory`: delete a memory so it stops being used.
- `verify_deletion`: verify a deleted memory is absent from context and Claude/Codex projections.
- `export_instructions`: write active memories into Claude/Codex instruction files.
- `export_diagnostic`: CLI-only local diagnostic bundle for review and reproduction.

## How extraction happens (the host AI is the extractor)

This skill has no built-in semantic extractor and never uses keyword rules. The
primary, low-friction path is: **the AI assistant already in the loop (Claude
Code, Codex, or an MCP client) does the extraction itself.**

When the user expresses how they want you to collaborate (a preference, a
workflow, a project rule, a correction), you should:

1. Decide — using your own judgement, not string rules — whether it is a stable,
   reusable workstyle memory or just a one-off task detail. If unsure, ask or
   propose a memory card for one-tap confirmation rather than guessing.
2. Produce a `memory_json` payload conforming to the schema below.
3. Call `remember_feedback` (MCP) / `ingest-feedback --memory-json` (CLI) with it.
   Do **not** ask the user to hand-write JSON, and do not require an external
   `MEMORY_BRIDGE_LLM_COMMAND` for everyday use — that command exists only for
   headless/batch runs.

To keep memory governed instead of accumulating, before emitting a draft inspect
the current memories (`view_memory` / `build_context`). If the new feedback
updates, narrows, or overrides an existing memory, **reuse that memory's exact
`slot` and `scope`** so the resolver supersedes the old version. The CLI/MCP also
inject the current active memories into the extraction prompt to make this
reuse reliable. Only choose a new slot for a genuinely new topic.

Fallbacks (not the everyday path): the user/tooling may supply explicit
`memory_json` directly, or set `MEMORY_BRIDGE_LLM_COMMAND` for an external model.
If neither is configured and no host AI acts, the CLI prints the extraction
prompt for manual paste — it never guesses.

## When to capture, and propose-then-confirm

Two capture triggers, both driven by you (the host AI), never by core code:

1. **Explicit** — the user says "记住这个" / "remember this". Extract and apply.
2. **Proactive** — you judge that feedback looks like a durable, reusable
   workstyle preference. Do **not** silently write it. Propose a memory card and
   let the user confirm with one reply.

For the proactive case, use the dry-run preview so the proposal is honest about
its effect instead of guessed:

- `remember_feedback(..., dry_run=True)` (MCP) / `ingest-feedback --dry-run` (CLI)
  returns the proposed memory and **which active memory it would supersede**,
  writing nothing.
- Show that to the user ("记成一条 X，会替换现有的 Y，要吗？"). On confirmation,
  call again with `dry_run=False` to commit.

Every write stays reversible via `delete_memory` + `verify_deletion`, so a wrong
capture is cheap to undo. Prefer one proposed memory at a time: dry-run previews
each draft against the current store, not against other drafts in the same batch.

## L2 scenario playbooks

Use L2 only when a task type or scenario has multiple active L1 memories and the
raw atom list is getting noisy. L2 is a convenience layer, not a new memory
source:

1. Call `build_scenario` with the exact scope (for example
   `task_type="technical_planning"`) and no `scenario_json`.
2. Assemble one `L2_scenario` JSON memory from the returned source L1 records.
   Do not add preferences that are not present in the sources.
3. Call `build_scenario(..., scenario_json=..., dry_run=True)`.
4. Show the preview and supersede effect to the user.
5. Commit with `dry_run=False` only after confirmation.

Fresh L2 scenarios are preferred by `build_context`, and their covered L1 atoms
are not repeated. If any source L1 changes, is superseded, or is deleted, the L2
becomes stale and `build_context` falls back to the L1 records.

## Read-path ranking and debugging

`build_context` ranks matching memories using structured metadata only:
fresh L2 scenarios first, then scope specificity, memory type priority,
confidence, a light usage-count balance, and recency. It must not inspect
memory content or use keyword rules to decide relevance.

When a memory seems missing or the ordering feels surprising:

1. Call `why_used` to explain the latest `build_context` result.
2. Check whether scoped values were omitted or drifted from stored values.
3. Use `memory_doctor` for aggregate recall-health facts across many requests.

## Memory types

- `preference`: stable user preference.
- `workflow`: how the user wants work to be done.
- `project_rule`: project-specific convention.
- `temporary`: short-lived task/session constraint.
- `fact`: stable work-relevant fact. Do not use this for irrelevant personal trivia.
- `anti_preference`: something the user explicitly dislikes.

## Workstyle layers

- `L0_event`: original user feedback, correction, or task fragment.
- `L1_atom`: one governed workstyle memory.
- `L2_scenario`: scenario/task-type workflow playbook assembled from source L1 memories.
- `L3_profile`: broad user/team collaboration profile; not a default MVP behavior driver.

MVP focuses on L0 evidence events, L1 atoms, and lightweight L2 scenarios assembled from confirmed L1 memories. L3 remains a boundary marker and must not become broad user profiling. L2/L3 must be model-backed or user-confirmed, never heuristic-generated.

## Memory lifecycle

1. New memory is inserted as `active`.
2. If it has the same `slot + scope` as an active memory, the old memory becomes `superseded`.
3. Deleted memories become `deleted` and must not be selected or exported.
4. User can view/inspect/edit/delete memory at any time.
5. Deletion can be verified with `verify-deletion`.

## No heuristic extraction

This skill must not use keyword matching or handcrafted rules to infer memory type, scope, slot, or preference changes. Semantic extraction must be model-backed structured output or explicit user-provided JSON.

## Evaluation script

Use `scripts/demo_8_steps.sh` to demonstrate:

1. reset;
2. first task;
3. feedback;
4. view and inspect generated memory;
5. second task uses memory;
6. changed preference supersedes old memory;
7. third task uses updated memory;
8. deleted memory is verified absent from context and exports.
