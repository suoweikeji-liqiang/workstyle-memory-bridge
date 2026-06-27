# Workstyle Memory Bridge

**Version 0.6.4**

> One feedback, cross-tool effect, viewable, editable, deletable, and traceable.

Workstyle Memory Bridge is a lightweight **workstyle memory governance** MCP/CLI.
It lets AI coding assistants remember how you want them to collaborate, then
apply those preferences later without turning into a generic personal memory
system.

It is for:

- collaboration preferences;
- workflow rules;
- project or task-specific working conventions;
- traceable memory updates and deletion proof.

It is not a second brain, chat archive, vector database, knowledge graph, or
"remember everything" memory layer.

## What Makes It Different

- **Governed memory**: every memory is structured, scoped, inspectable, editable,
  and deletable.
- **Traceability**: memories can point back to L0 evidence events: the feedback
  or correction that created them.
- **Supersede instead of pile-up**: new memory with the same `slot + scope`
  replaces the old active rule.
- **Deletion proof**: `verify-deletion` checks store, context, and export
  projections.
- **No heuristic extraction**: core code does not use keyword rules or regexes to
  decide memory meaning.
- **Host-aware recall**: `why-used` and `doctor` explain what fired, what missed,
  and whether the host is actually calling `build_context`.

The sharp wedge is:

```text
feedback -> governed workstyle memory -> source evidence -> scoped context
-> visible behavior change -> editable/deletable proof
```

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e '.[mcp,test]'
```

Run tests:

```bash
.venv/bin/pytest -q
```

## Recommended Use: MCP Host

Add the server to Claude Code, Codex, or another MCP client:

```json
{
  "mcpServers": {
    "workstyle-memory": {
      "command": "python",
      "args": ["-m", "memory_bridge.mcp_server"],
      "env": {
        "MEMORY_BRIDGE_DB": "/path/to/workstyle-memory.sqlite"
      }
    }
  }
}
```

At MCP handshake time the server sends:

- global workstyle memories;
- exact scoped vocabulary for `build_context`;
- memory routing rules so host-native memory does not duplicate this store;
- snapshot semantics: the store is authoritative after mid-session edits/deletes.

For best behavior, install or reference `skill/SKILL.md` in the host.

## Typical Flow

```text
User feedback
  -> host extracts structured memory JSON
  -> remember_feedback(dry_run=True)
  -> user confirms
  -> remember_feedback(dry_run=False)
  -> later task calls build_context
  -> why_used / doctor explain recall when needed
  -> edit/delete are previewed before mutation
```

For natural-language edits or deletes, the host chooses candidate memory IDs
after `view_memory` / `inspect_memory` / `build_context`, then calls
`preview_memory_edit` or `preview_memory_delete`. The preview writes nothing;
commit only after user confirmation.

## CLI Inspection Bench

```bash
memory-bridge reset
memory-bridge view [--status all]
memory-bridge inspect <memory_id>
memory-bridge build-context --task-type feature-development
memory-bridge why-used
memory-bridge doctor
memory-bridge preview-edit <memory_id> --content "..."
memory-bridge edit <memory_id> --content "..."
memory-bridge preview-delete <memory_id>
memory-bridge delete <memory_id>
memory-bridge verify-deletion <memory_id> --task-type feature-development
memory-bridge export-diagnostic --output diagnostic.zip
```

The CLI is intentionally an inspection and governance bench. Without
`--memory-json` or `MEMORY_BRIDGE_LLM_COMMAND`, `ingest-feedback` prints a
model-ready extraction prompt and writes nothing.

## Demo

```bash
bash scripts/demo_8_steps.sh
```

The demo covers reset, first task, feedback extraction, evidence inspection,
recall, preference change via supersede, third-task recall, and deletion proof.

## Design Boundaries

Core semantic extraction must be model-backed structured output or explicit
user-provided JSON. Deterministic code may validate schema, resolve
`slot + scope` conflicts, match explicit scopes, audit lifecycle events, export
contexts, and verify deletion. It must not infer memory meaning with keywords,
regexes, or phrase lists.

See:

- `policies/no_heuristic_extraction.md`
- `docs/positioning.md`
- `docs/non_goals.md`
- `docs/tencentdb_agent_memory_reference.md`
- `docs/real_usage_and_failure_modes.md`
- `docs/integrations.md`

## License

MIT-0. See `LICENSE`.
