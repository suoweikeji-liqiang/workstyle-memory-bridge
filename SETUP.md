# Setup

## Requirements

- Python 3.11+
- No runtime dependency for the core CLI
- Optional: `pytest` for tests
- Optional: `mcp` for MCP adapter

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run CLI

```bash
memory-bridge reset
memory-bridge view
memory-bridge inspect <memory_id>
memory-bridge verify-deletion <memory_id> --task-type technical_planning
memory-bridge doctor
```

## Run tests

```bash
pip install -e '.[test]'
pytest -q
```

## Optional model-backed extraction

Set an external command that reads the extraction prompt from stdin and returns JSON matching the schema.

```bash
export MEMORY_BRIDGE_LLM_COMMAND='your-json-producing-llm-command'
```

Then:

```bash
memory-bridge ingest-feedback --feedback "以后做方案先给北极星和 MVP"
```

The project intentionally does not ship a keyword-based fallback extractor.

## Optional MCP adapter

```bash
pip install -e '.[mcp]'
python -m memory_bridge.mcp_server
```

The MCP adapter is thin and calls the same core functions as the CLI.

## Optional diagnostic export

```bash
memory-bridge export-diagnostic --output diagnostic.zip
```

Review the bundle before sharing. It may include user-provided feedback text.
