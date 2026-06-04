# Workstyle Memory Governance Skill

## What it does

Memory Bridge Skill turns explicit user feedback into structured workstyle memories and makes those memories portable across AI tools.

It is not a generic memory MCP. It is a traceable governance layer for remembering how the user wants AI to collaborate.

## North star

One feedback event should improve future collaboration across tools while remaining inspectable, editable, reversible, and traceable to source evidence.

## Tools

- `reset_memory`: clear all memories and evidence events for reproducible testing.
- `view_memory`: show current memory state.
- `remember_feedback`: convert feedback into structured memories and attach L0 evidence refs.
- `inspect_memory`: inspect a memory card, source evidence, and lifecycle.
- `build_context`: return relevant active memories for a task.
- `edit_memory`: update a memory.
- `delete_memory`: delete a memory so it stops being used.
- `verify_deletion`: verify a deleted memory is absent from context and Claude/Codex projections.
- `export_instructions`: write active memories into Claude/Codex instruction files.
- `export_diagnostic`: CLI-only local diagnostic bundle for review and reproduction.

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
