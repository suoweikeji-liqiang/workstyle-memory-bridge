# Setup

Two ways to run Workstyle Memory Bridge — pick by what you want to see:

- **Host-connected (recommended; the evaluation path).** An AI host (Claude
  Code, Codex, or any MCP client) connects to the MCP server. The host
  extracts preferences from your feedback, recalls scoped memories at task
  start, and applies them to real tasks. Memory *application* — the thing
  that matters — is only observable on this path.
- **CLI (inspection bench).** `view` / `inspect` / `context-log` / `doctor` /
  `verify-deletion` show what is stored and when it was recalled, and prove
  deletion. The
  bare CLI does **not** extract memories by itself: there is deliberately no
  built-in extractor (see `policies/no_heuristic_extraction.md`), so
  `ingest-feedback` without `--memory-json` prints a model-ready extraction
  prompt and writes nothing.

## 1. Install

```bash
python -m venv .venv
.venv/bin/pip install -e '.[mcp]'      # Windows: .venv\Scripts\pip install -e .[mcp]
```

## 2. Connect a host (Claude Code example)

Add to the project's `.mcp.json` (or `claude mcp add workstyle-memory -- python -m memory_bridge.mcp_server`):

```json
{
  "mcpServers": {
    "workstyle-memory": {
      "command": "python",
      "args": ["-m", "memory_bridge.mcp_server"],
      "env": { "MEMORY_BRIDGE_DB": "C:/eval/wasc-eval.sqlite" }
    }
  }
}
```

At the MCP handshake the server ships instructions computed from the live
store: always-on global memories, the scoped-vocabulary index, memory-routing
rules (workstyle preferences belong here, never duplicated into host native
memory), and snapshot semantics (the store is authoritative for mid-session
edits). **No instruction-file export is needed to get started.**

Optionally install the skill guidance from `skill/SKILL.md` into your host's
skill directory for capture/recall etiquette.

## 3. Clean-room mode (evaluation)

All state lives in one SQLite file. Point `MEMORY_BRIDGE_DB` at a fresh path
(as in the snippet above) to start from blank without touching any existing
store, then confirm:

```bash
MEMORY_BRIDGE_DB=C:/eval/wasc-eval.sqlite memory-bridge reset
MEMORY_BRIDGE_DB=C:/eval/wasc-eval.sqlite memory-bridge view   # -> empty
```

The CLI also accepts `--db <path>` per command.

## 4. The 8-step evaluation structure

CLI walkthrough (mechanism view, isolated `.demo/` database):

```bash
bash scripts/demo_8_steps.sh
```

It covers: reset → first task → mixed feedback (durable workflow preference
**plus** a one-off detail typed `temporary` so it never leaks into later
tasks) → view/inspect with evidence → second task applies the memory → 
preference change supersedes the old version → third task uses the new rule →
delete + `verify-deletion` proof.

Host-connected version — run the same structure conversationally; the tools
map 1:1 to the judge script:

| Judge step | MCP tool |
|---|---|
| 清空记忆 | `reset_memory` |
| 查看记忆 | `view_memory` / `inspect_memory` |
| 用户反馈 | host extracts → `remember_feedback` (`dry_run` first) |
| 再次任务 | host calls `build_context` with the task's scope |
| 偏好变化 | `remember_feedback` with same slot+scope → supersede |
| 删除后复测 | `delete_memory` + `verify_deletion` |
| 为什么没生效 | `memory_doctor` |

## 5. CLI inspection bench

```bash
memory-bridge view [--status all]
memory-bridge inspect <memory_id>        # memory card + evidence + lifecycle
memory-bridge context-log                # read-path audit: who asked, what matched
memory-bridge doctor                     # lifecycle + recall health
memory-bridge verify-deletion <memory_id> --task-type <value>
memory-bridge export claude --path <CLAUDE.md>   # optional always-on wall
```

## Optional headless extraction (no host)

Set an external command that reads the extraction prompt from stdin and
returns JSON matching the schema:

```bash
export MEMORY_BRIDGE_LLM_COMMAND='your-json-producing-llm-command'
memory-bridge ingest-feedback --feedback "以后做方案先给北极星和 MVP"
```

The project intentionally ships no keyword-based fallback extractor.

## Run tests

```bash
pip install -e '.[test]'
pytest -q
```

## Optional diagnostic export

```bash
memory-bridge export-diagnostic --output diagnostic.zip
```

Review the bundle before sharing. It may include user-provided feedback text.
