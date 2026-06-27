# Setup

Use Workstyle Memory Bridge through an MCP host. Use the CLI to inspect,
diagnose, and prove lifecycle behavior.

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e '.[mcp,test]'
```

## Connect An MCP Host

Example `.mcp.json`:

```json
{
  "mcpServers": {
    "workstyle-memory": {
      "command": "python",
      "args": ["-m", "memory_bridge.mcp_server"],
      "env": { "MEMORY_BRIDGE_DB": "/tmp/workstyle-memory.sqlite" }
    }
  }
}
```

At handshake, the server sends global memories, scoped vocabulary, and memory
routing rules. Mid-session edits/deletes should be followed by fresh
`build_context`; the store is authoritative over the handshake snapshot.

## Clean-Room Test

```bash
MEMORY_BRIDGE_DB=/tmp/wmb-clean.sqlite memory-bridge reset
MEMORY_BRIDGE_DB=/tmp/wmb-clean.sqlite memory-bridge view
```

The CLI also accepts `--db <path>` per command.

## 8-Step Demo

```bash
bash scripts/demo_8_steps.sh
```

The script covers reset, first task, feedback -> memory + evidence,
view/inspect, recall, supersede, updated recall, and deletion verification.

## CLI Bench

```bash
memory-bridge view [--status all]
memory-bridge inspect <memory_id>
memory-bridge context-log
memory-bridge why-used
memory-bridge doctor
memory-bridge preview-edit <memory_id> --content "..."
memory-bridge preview-delete <memory_id>
memory-bridge verify-deletion <memory_id> --task-type <value>
memory-bridge export-diagnostic --output diagnostic.zip
```

## Headless Extraction

The project ships no keyword fallback extractor. Without a host, provide
structured JSON yourself or configure an external command:

```bash
export MEMORY_BRIDGE_LLM_COMMAND='your-json-producing-llm-command'
memory-bridge ingest-feedback --feedback "以后做方案先给北极星和 MVP"
```

## Tests

```bash
pytest -q
```
