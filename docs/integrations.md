# Integrations

## Source of truth

The SQLite memory store is the source of truth. External integrations should consume generated context or managed instruction sections.

```text
memory store -> context builder -> Claude/Codex/MCP/product assistant
```

## Claude Code

Export relevant active memories into a managed section of `CLAUDE.md`:

```bash
memory-bridge export claude --path ./CLAUDE.md --task-type technical_planning
```

The generated section is bounded by:

```markdown
<!-- memory-bridge:begin -->
...
<!-- memory-bridge:end -->
```

Manual content outside that section is preserved.

## Codex

Export relevant active memories into a managed section of `AGENTS.md`:

```bash
memory-bridge export codex --path ./AGENTS.md --task-type technical_planning
```

Do not hand-edit the managed section. Edit the underlying memory record instead:

```bash
memory-bridge view
memory-bridge edit <memory_id> --content "..."
memory-bridge delete <memory_id>
```

## MCP clients

The MCP server is intentionally a thin adapter over the same core store/resolver/context logic used by the CLI.

Install optional dependencies:

```bash
pip install -e '.[mcp]'
python -m memory_bridge.mcp_server
```

Recommended tools:

- `reset_memory`
- `view_memory`
- `remember_feedback`
- `inspect_memory`
- `build_context`
- `why_used`
- `memory_doctor`
- `edit_memory`
- `delete_memory`
- `verify_deletion`
- `export_instructions`

Use `why_used` when a single task's recall result looks surprising. It explains
the most recent (or selected) `build_context` request using the same store data:
scope match reason, returned memory order, and structured rank signals. Use
`memory_doctor` for aggregate recall-health facts across many requests.

## Product embedding

For product assistants, treat Workstyle Memory Bridge as a personalization layer, not as the product database.

Suggested API mapping:

```http
POST   /memory/feedback
GET    /memory/context?user_id=&task_type=&project=&product=&domain=
GET    /memory/list
PATCH  /memory/{id}
DELETE /memory/{id}
POST   /memory/reset
```

Example product memory:

```yaml
type: workflow
scope:
  level: product_user
  product: equicore
  domain: hvac_fault_diagnosis
  user_id: team_alpha
slot: alarm_diagnosis_order
content: 报警分析先看实时值，再看 24 小时趋势，最后给原因排序；日报先列异常，再写概述。
rationale: 用户明确给出团队诊断与日报工作方式。
```
