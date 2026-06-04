# WASC scoring map

This project is designed around the WASC continuous-use testing structure.

## Scoring strategy

| Dimension | Weight | Implementation response |
|---|---:|---|
| Reproducibility | 10 | `reset`, `view`, `inspect`, `edit`, `delete`, audit events, demo script. |
| Effective memory extraction | 20 | Model/user JSON produces typed records: `preference`, `workflow`, `project_rule`, `temporary`, `fact`, `anti_preference`; v0.3 attaches L0 evidence. |
| Memory application | 25 | `build_context` selects relevant active memories by explicit scope and exports them into Claude/Codex/MCP contexts. |
| Update and retirement | 20 | Slot + scope conflict resolution supersedes old active memory instead of accumulating conflicts; `verify-deletion` proves deletion. |
| User control and transparency | 10 | Memory cards show type, layer, scope, slot, content, rationale, confidence, evidence refs, supersedes, usage status. |
| Real usability | 15 | Primary demo is real developer/founder workflow, not an abstract memory mechanism. |

## Canonical 8-step script

Use:

```bash
bash scripts/demo_8_steps.sh
```

The script demonstrates:

1. reset memory;
2. first task without memory;
3. user feedback creates a structured memory and L0 evidence event;
4. view and inspect memory;
5. second task uses memory;
6. changed preference supersedes the old memory;
7. third task uses the updated memory;
8. deleted memory is verified absent from context and export projections.

## Demo principle

The demo should not try to prove that the system remembers many things. It should prove that memory changes collaboration in a controlled, inspectable way.

The strongest video sequence is:

```text
empty memory -> feedback -> memory card with evidence -> next task adapts -> preference changes -> superseded record -> delete -> verify absent
```
