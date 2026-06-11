# Workstyle Memory Governance Skill

## What it does

Memory Bridge Skill turns explicit user feedback into structured workstyle memories and makes those memories portable across AI tools.

It is not a generic memory MCP. It is a traceable governance layer for remembering how the user wants AI to collaborate.

## North star

One feedback event should improve future collaboration across tools while remaining inspectable, editable, reversible, and traceable to source evidence.

## Tools

- `reset_memory`: clear all memories and evidence events for reproducible testing.
- `view_memory`: show current memory state.
- `remember_feedback`: convert feedback into structured memories and attach L0 evidence refs. Supports `dry_run` for propose-then-confirm.
- `inspect_memory`: inspect a memory card, source evidence, and lifecycle.
- `build_context`: return relevant active memories for a task. Scope matching is exact — reuse the stored scope values (the managed export section and the unmatched hint both list them) rather than inventing variants.
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
- `L2_scenario`: scenario/task-type workflow pattern.
- `L3_profile`: broad user/team collaboration profile.

MVP focuses on L0 evidence events and L1 atoms. L2/L3 must be model-backed or user-confirmed, never heuristic-generated.

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
