#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/.demo/memory.sqlite"
mkdir -p "$ROOT/.demo"

MB="python -m memory_bridge.cli --db $DB"

cd "$ROOT"

printf '\n[1] reset memory\n'
$MB reset

printf '\n[2] first task, no memory yet\n'
echo 'Task: 帮我设计一个功能：给 develop_os 加一个 issue triage agent。'
echo 'Expected: no workstyle memory is available yet.'

printf '\n[3] user feedback -> structured memory + L0 evidence event\n'
OUT1="$($MB ingest-feedback \
  --task-type technical_planning \
  --feedback '以后给我技术方案时，先讲北极星和边界，再给 MVP，不要上来堆完整架构。风险要前置。输出控制在 6 段以内。' \
  --memory-json '{
    "memories": [{
      "type": "workflow",
      "layer": "L1_atom",
      "scope": {"level": "task_type", "task_type": "technical_planning"},
      "slot": "technical_plan_structure",
      "content": "技术方案应先讲北极星和边界，再给 MVP；避免一开始堆完整架构；风险前置；输出控制在 6 段以内。",
      "rationale": "用户明确给出后续技术方案的协作方式。",
      "confidence": 0.92
    }]
  }')"
printf '%s\n' "$OUT1"
FIRST_ID="$(printf '%s\n' "$OUT1" | awk '/^- mem_/ {gsub(":", "", $2); print $2; exit}')"

printf '\n[4] view and inspect memory\n'
$MB view
if [ -n "$FIRST_ID" ]; then
  $MB inspect "$FIRST_ID"
fi

printf '\n[5] second task should use memory\n'
echo 'Task: 帮我评估 Memory Bridge 要不要接入 Claude 和 Codex。'
$MB build-context --task-type technical_planning

printf '\n[6] preference changes -> supersede old memory\n'
OUT2="$($MB ingest-feedback \
  --task-type technical_planning \
  --feedback '调整一下：产品方案仍然要简洁，但代码实现类任务可以详细。风险不要第一段，放在 MVP 后面。' \
  --memory-json '{
    "memories": [{
      "type": "workflow",
      "layer": "L1_atom",
      "scope": {"level": "task_type", "task_type": "technical_planning"},
      "slot": "technical_plan_structure",
      "content": "技术/产品方案先讲北极星和边界，再讲 MVP，风险放在 MVP 后；整体保持简洁。代码实现类任务允许展开细节。",
      "rationale": "用户调整了风险位置和代码实现类任务的详细程度。",
      "confidence": 0.94
    }]
  }')"
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
