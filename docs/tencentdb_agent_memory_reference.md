# Reference boundary: TencentDB-Agent-Memory

TencentDB-Agent-Memory is useful as a reference because it emphasizes layered memory and traceability. This project borrows those ideas, but keeps a narrower WASC/self-use wedge.

## What to borrow

### 1. Layered memory

Use a lightweight Workstyle version:

```text
L0 event     -> original feedback/correction/task fragment
L1 atom      -> one governed workstyle memory
L2 scenario  -> task/scenario-level collaboration pattern
L3 profile   -> broad user/team collaboration profile
```

The MVP only implements L0 evidence events and L1 atoms.

### 2. Downward traceability

Every abstract memory should be inspectable:

```text
memory card -> evidence refs -> original feedback event -> lifecycle events
```

This strengthens WASC transparency and makes memory updates debuggable.

### 3. White-box debugging

Prefer simple files, JSON, CLI cards, and diagnostic bundles over hidden black-box memory state.

### 4. Diagnostic export

A local diagnostic bundle helps reproduce demo runs and review memory state. It may include user feedback text, so it must be reviewed before sharing.

## What not to copy

Do not copy the full long-task memory infrastructure in v0.3:

- no vector DB;
- no graph DB;
- no Mermaid task canvas;
- no BM25/RRF hybrid retrieval;
- no OpenClaw plugin as the main path;
- no auto-capture of all conversations;
- no automatic persona generation from weak evidence;
- no large dashboard.

## Strategic difference

| Dimension | Large agent-memory infrastructure | Workstyle Memory Bridge |
|---|---|---|
| Main goal | agent long/short-term memory platform | feedback-to-workstyle governance skill |
| Core object | conversations, logs, scenes, persona | feedback, preference, workflow, project rule |
| Retrieval | semantic/hybrid/graph recall | explicit scope + slot + status |
| Update | memory consolidation | slot/scope supersede and deletion verification |
| Demo focus | long-term agent continuity | WASC 8-step continuous-use proof |
| MVP weight | platform-like | lightweight CLI/MCP/exporter |

## v0.3 rule

Borrow **layering and traceability**. Do not copy broad infrastructure.
