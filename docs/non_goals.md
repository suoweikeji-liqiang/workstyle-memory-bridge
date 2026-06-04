# Non-goals

The project should stay small and sharp. These are explicit non-goals for the initial competition-ready version.

## Do not build a universal memory platform

Avoid turning the project into a broad platform that remembers every message, page, document, or user fact. This space is already crowded and is not the best WASC wedge.

## Do not build a full knowledge graph

Temporal graphs are useful, but the MVP only needs lifecycle fields:

- `status`
- `supersedes`
- `valid_from`
- `valid_until`
- `scope`
- `slot`

A graph database is not required for the first version.

## Do not build a full AI coding agent

This project should improve Claude, Codex, and other agents. It should not replace them.

## Do not hide memory in prompts only

A hidden prompt is not user-controllable memory. Every active memory must be viewable, editable, deletable, and excluded from future context after deletion.

## Do not use heuristic extraction

No keyword rules, regex extraction, phrase tables, or demo-specific branching for semantic memory extraction.

## Do not optimize for remembering more

Optimize for remembering the right workstyle rule, applying it at the right scope, updating it when it changes, and forgetting it when deleted.

## Do not build a long-task context compression platform

Layered memory systems and task canvases are useful references, but v0.3 only borrows lightweight traceability:

```text
L0 event -> L1 atom -> inspectable memory card
```

Do not add Mermaid task canvases, hybrid retrieval, background conversation capture, or automatic persona generation for the competition MVP.
