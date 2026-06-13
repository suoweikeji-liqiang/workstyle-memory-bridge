#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/.demo/memory.sqlite"
mkdir -p "$ROOT/.demo"

# Use python3 or the venv python if available
if [ -f "$ROOT/.venv/bin/python3" ]; then
  PYTHON="$ROOT/.venv/bin/python3"
elif command -v python3 &> /dev/null; then
  PYTHON="python3"
else
  PYTHON="python"
fi

MB="$PYTHON -m memory_bridge.cli --db $DB"

cd "$ROOT"

printf '\n[1] reset memory\n'
$MB reset

printf '\n[2] first task, no memory yet\n'
echo 'Task: 帮我设计一个功能：给 develop_os 加一个 issue triage agent。'
echo 'Expected: no workstyle memory is available yet.'

printf '\n[3] user feedback -> structured memory + L0 evidence event\n'
echo 'The feedback mixes a DURABLE workflow preference with a one-off task detail'
echo '(cc Zhang San on this plan). Extraction must separate them: the durable part'
echo 'becomes a workflow memory; the one-off part is typed temporary with session'
echo 'scope, so it can never leak into later tasks.'
OUT1="$($MB ingest-feedback \
  --task-type technical_planning \
  --feedback '以后给我技术方案时，先讲北极星和边界，再给 MVP，不要上来堆完整架构。风险要前置。输出控制在 6 段以内。对了，这份方案写完抄送一下张三。' \
  --memory-json '{
    "memories": [{
      "type": "workflow",
      "layer": "L1_atom",
      "scope": {"level": "task_type", "task_type": "technical_planning"},
      "slot": "technical_plan_structure",
      "content": "技术方案应先讲北极星和边界，再给 MVP；避免一开始堆完整架构；风险前置；输出控制在 6 段以内。",
      "rationale": "用户明确给出后续技术方案的协作方式。",
      "confidence": 0.92
    }, {
      "type": "temporary",
      "layer": "L1_atom",
      "scope": {"level": "session", "session_id": "demo-session-1"},
      "slot": "cc_zhangsan_this_plan",
      "content": "本次方案完成后抄送张三（仅本次任务有效）。",
      "rationale": "一次性任务信息，不是长期偏好。",
      "confidence": 0.9
    }]
  }')"
printf '%s\n' "$OUT1"
FIRST_ID="$(printf '%s\n' "$OUT1" | awk '/^- mem_/ {gsub(":", "", $2); print $2; exit}')"

printf '\n[3b] (path B) extraction prompt now carries the existing memory\n'
echo 'When NO --memory-json is given, the model-backed path is used. The prompt'
echo 'now includes current active memories so the model reuses the same slot+scope'
echo 'on updates (instead of creating a conflicting one). No extractor is configured'
echo 'here, so the CLI prints the model-ready prompt and writes nothing:'
printf '\n'
$MB ingest-feedback \
  --task-type technical_planning \
  --feedback '风险其实可以放后面一点' 2>&1 \
  | awk '/Currently stored active memories/{f=1} /^Task context:/{f=0} f' || true

printf '\n[4] view and inspect memory\n'
$MB view
if [ -n "$FIRST_ID" ]; then
  $MB inspect "$FIRST_ID"
fi

printf '\n[5] second task should use memory\n'
echo 'Task: 帮我评估 Memory Bridge 要不要接入 Claude 和 Codex。'
echo 'Note: the durable workflow memory applies below; the temporary cc-ZhangSan'
echo 'item does NOT (session scope) -- one-off details never leak into new tasks.'
$MB build-context --task-type technical_planning

printf '\n[6] preference changes -> propose-then-confirm, then supersede\n'
UPDATE_FEEDBACK='调整一下：产品方案仍然要简洁，但代码实现类任务可以详细。风险不要第一段，放在 MVP 后面。'
UPDATE_JSON='{
    "memories": [{
      "type": "workflow",
      "layer": "L1_atom",
      "scope": {"level": "task_type", "task_type": "technical_planning"},
      "slot": "technical_plan_structure",
      "content": "技术/产品方案先讲北极星和边界，再讲 MVP，风险放在 MVP 后；整体保持简洁。代码实现类任务允许展开细节。",
      "rationale": "用户调整了风险位置和代码实现类任务的详细程度。",
      "confidence": 0.94
    }]
}'

printf '\n[6a] (path C) dry-run preview: what would be remembered and superseded\n'
$MB ingest-feedback --task-type technical_planning \
  --feedback "$UPDATE_FEEDBACK" --memory-json "$UPDATE_JSON" --dry-run

printf '\n[6b] user confirms -> commit (old memory is superseded)\n'
OUT2="$($MB ingest-feedback --task-type technical_planning \
  --feedback "$UPDATE_FEEDBACK" --memory-json "$UPDATE_JSON")"
printf '%s\n' "$OUT2"
ACTIVE_ID="$(printf '%s\n' "$OUT2" | awk '/^- mem_/ {gsub(":", "", $2); print $2; exit}')"

printf '\n[7] third task should use updated memory\n'
echo 'Task: 帮我设计 Memory Bridge 的 MCP tools。'
$MB build-context --task-type technical_planning

printf '\n[8] delete active memory and verify it stops applying\n'
if [ -n "$ACTIVE_ID" ]; then
  $MB delete "$ACTIVE_ID"
  $MB verify-deletion "$ACTIVE_ID" --task-type technical_planning
fi

if [ "${RUN_DIAGNOSTIC:-0}" = "1" ]; then
  printf '\n[extra] export diagnostic bundle\n'
  $MB export-diagnostic --output "$ROOT/.demo/diagnostic.zip"
fi

printf '\nDemo complete. Set RUN_DIAGNOSTIC=1 to also create .demo/diagnostic.zip.\n'
