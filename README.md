# Workstyle Memory Bridge

> 一次反馈，多工具生效，可查看、可撤销、可进化、可溯源。

Workstyle Memory Bridge 是一个轻量级 **Workstyle Memory Governance MCP / CLI Skill**：把用户在真实工作中的反馈转成结构化“工作方式记忆”，并把这些记忆投影到 Claude、Codex、MCP 客户端和产品内助手。

它不是个人知识库，不是聊天记录存档，不是万能 RAG，也不是“记住一切”的通用 memory MCP。它只关注一件事：

> **AI 如何记住你希望它怎样协作，并在后续任务里可验证地减少重复说明。**

## 30 秒看懂 / In 30 seconds

**不是又一个记忆 MCP。** 它是关于「**你想要 AI 怎么和你协作**」的治理层。每条偏好都是一条有类型的记录,它：

- **替换而非堆叠** —— 同 `slot + scope` 的新记忆会 supersede 旧的,不会越记越乱;
- **可溯源** —— 每条记忆都能下钻到产生它的那次反馈事件(L0 evidence);
- **删除可被证明** —— `verify-deletion` 跨上下文与 Claude/Codex 投影确认它真的停用了;
- **内核从不猜测** —— 语义只来自模型或你的显式 JSON,**刻意零关键字/正则规则**;
- **一处反馈、处处生效** —— 一个共享库,Claude、Codex、Antigravity 一起变懂你。

> Not another memory MCP. It is a **governance layer for how you want AI to work with you** — every preference is a typed record that **supersedes instead of piling up**, **traces back to the feedback that created it**, and can be **deleted with proof**. The core never guesses: all meaning comes from the model or your explicit input — **zero keyword rules, by design**. One shared store, and Claude, Codex, and Antigravity all adapt.

**🎬 视频开场白（抖音 / B站 / YouTube）**

> 「大多数 AI,每次见你都像第一次。
> 这个不一样——你教它一次,它就记住了你**怎么干活**。
> 而且它记的每一条,你都能看见、能改、能删——还能**亲眼验证**删掉后它真的不再用了。」

## 北极星

让 AI 把用户在真实工作中的反馈，自动沉淀成结构化、可治理、可迁移、可溯源的工作方式记忆；同一条反馈可以在 Claude、Codex、MCP 工具和产品助手中生效；用户可以随时查看、编辑、删除，并能追溯每条记忆来自哪次反馈；删除后记忆必须停止生效。

## 为什么不是“又一个 Memory MCP”

MCP 记忆方向已经有很多通用项目：个人记忆、语义召回、项目 memory bank、知识图谱、长期 agent memory 等。这个项目故意不和它们正面拼“记得更多”。

本项目的切口是：

> **用户反馈如何变成一次可治理、可复测、可撤销的工作方式改变。**

核心差异化：

| 普通 memory MCP | Workstyle Memory Bridge |
|---|---|
| 记 facts / notes / chat history | 记协作方式、偏好、工作流、项目规则 |
| add/search/delete | reset/view/edit/delete/supersede/build-context/export |
| 越记越多 | 冲突时替换、归档或删除 |
| 语义搜索优先 | slot + scope + lifecycle 治理优先 |
| 很难现场复测 | 内置 WASC 8 步连续测试 |
| 容易黑箱 | memory card + evidence refs + rationale + audit events |
| 容易靠规则触发 | 明确禁止 heuristic extraction |

更多定位说明见：[`docs/positioning.md`](docs/positioning.md)。

## v0.3：可溯源记忆治理

v0.3 借鉴了 TencentDB-Agent-Memory 这类分层记忆系统的关键思想：**抽象记忆必须能下钻到来源证据**。但本项目不复制完整长任务记忆基础设施，只做 Workstyle 版的轻量 L0-L3：

| Layer | 本项目含义 |
|---|---|
| L0 event | 原始用户反馈、修正或任务片段 |
| L1 atom | 单条结构化工作方式记忆 |
| L2 scenario | 某类任务/场景下的协作方式 |
| L3 profile | 更高层的用户/团队协作画像 |

当前 MVP 重点实现 **L0 evidence events + L1 memory atoms**。每条由 `ingest-feedback` 生成的记忆都会自动挂上 `source_event_id` 和 `evidence_refs`，可通过 `inspect` 查看来源、证据和生命周期。参考边界见：[`docs/tencentdb_agent_memory_reference.md`](docs/tencentdb_agent_memory_reference.md)。

## 关键约束：抑制规则匹配和启发式堆砌

本项目明确禁止把核心记忆能力实现成关键词规则、正则匹配、if/else 穷举或手写启发式分类器。

原因：用户表达、语言、领域和工作流无法穷举。硬编码规则一开始看起来快，但很快会变成不可维护、不可泛化、不可评测的系统。

### 禁止

- 用关键词判断记忆类型，例如看到“以后”就直接判定为长期偏好。
- 用正则或字符串包含关系从反馈中抽取语义。
- 用手写规则推断 scope、slot、偏好变化或删除意图。
- 针对比赛 demo 写固定 case 的隐藏分支。
- 为了通过某个测试脚本而塞入一次性规则。

### 允许

- Schema validation：校验 JSON 字段、类型、confidence、scope。
- Explicit scope matching：按用户/模型已经给出的 project、tool、task_type、session、product、domain 等元数据选择记忆。
- Lifecycle rules：同一个 slot + scope 只保留一个 active memory，新记忆自动 supersede 旧记忆。
- User command handling：reset、view、edit、delete 这类明确操作。
- Model-backed semantic extraction：由模型按 JSON schema 输出结构化记忆。
- User-confirmed structured input：用户或上游工具直接提供 memory JSON。

一句话：**语义判断交给模型或用户确认；工程代码只做结构、生命周期和可验证治理。**

完整政策见：[`policies/no_heuristic_extraction.md`](policies/no_heuristic_extraction.md)。

## MVP 能力

- `reset`：清空记忆，支持比赛从空白状态复测。
- `view`：查看 active / superseded / archived / deleted / all 记忆。
- `inspect`：查看单条记忆的 memory card、证据来源和生命周期。
- `ingest-feedback`：把用户反馈转成结构化记忆。
- `build-context`：根据显式 scope 生成给 Claude/Codex/产品助手使用的上下文；每次返回都会列出本次**没有**命中的 scoped 记忆及其精确 scope 值，杜绝"静默不召回"。
- `context-log`：读路径审计。每次 build-context 的调用参数、命中结果、未命中数量都有记录，"为什么没用我的记忆"可以直接查证。
- `edit`：修改记忆内容、scope、slot、confidence、status。
- `delete`：删除记忆，删除后不再进入上下文和导出文件。
- `verify-deletion`：验证被删除记忆不会再进入 context 或 Claude/Codex 投影。
- `export claude`：导出到 `CLAUDE.md` 的 managed section。
- `export codex`：导出到 `AGENTS.md` 的 managed section。
- `doctor`：生命周期检查（重复 active、过长内容）+ 召回健康检查——哪些 scoped 记忆有机会却从未被返回、哪些被请求的 scope 值无记忆可匹配。只报事实；语义判断和修订提案由宿主 AI 走治理通道（dry-run → 用户确认 → supersede）。也作为 MCP 工具 `memory_doctor` 暴露给宿主。
- `export-diagnostic`：导出本地诊断包，包含记忆、证据和事件，便于复测。
- optional MCP server：让 MCP 客户端通过同一套核心逻辑调用记忆能力。

## 快速开始

```bash
cd workstyle-memory-bridge
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
```

清空记忆：

```bash
memory-bridge reset
```

写入一条结构化记忆：

```bash
memory-bridge ingest-feedback \
  --feedback "以后给我技术方案时，先讲北极星和边界，再给 MVP，不要上来堆完整架构。风险放在 MVP 后。" \
  --memory-json '{
    "memories": [{
      "type": "workflow",
      "scope": {"level": "task_type", "task_type": "technical_planning"},
      "slot": "technical_plan_structure",
      "content": "技术方案应先讲北极星和边界，再给 MVP；避免一开始堆完整架构；风险放在 MVP 后。",
      "rationale": "用户明确给出后续技术方案的协作方式。",
      "confidence": 0.92
    }]
  }'
```

查看和溯源记忆：

```bash
memory-bridge view
memory-bridge inspect <memory_id>
```

构建上下文：

```bash
memory-bridge build-context --task-type technical_planning
```

导出给 Claude Code：

```bash
memory-bridge export claude --path ./CLAUDE.md --task-type technical_planning
```

导出给 Codex：

```bash
memory-bridge export codex --path ./AGENTS.md --task-type technical_planning
```

## 语义抽取方式

**首选路径（自用主路径）：让正在对话的 AI 自己抽取。** 你在 Claude Code / Codex / MCP 客户端里随口给出协作偏好，宿主 AI 自行判断这是不是一条可复用的工作方式记忆，按 schema 产出 `memory_json`，直接调用 `ingest-feedback --memory-json`（CLI）或 `remember_feedback`（MCP）。你不需要手写 JSON，也不需要为日常使用配置外部模型命令。

为了不让记忆越堆越多，宿主 AI 在抽取前应先看当前记忆（`view` / `build-context`）；若本次反馈是在更新某条已有记忆，就**复用它精确的 `slot` 和 `scope`**，让 resolver 替换旧记忆。CLI/MCP 也会把当前 active 记忆注入抽取 prompt，让这种复用更可靠。

兜底路径（非日常）：

1. `--memory-json`：用户或上游工具显式提供结构化记忆 JSON。
2. `MEMORY_BRIDGE_LLM_COMMAND` / `--llm-command`：外部模型命令从 stdin 读取 prompt，输出 JSON（适合无人值守 / 批处理）。

如果以上都没有、也没有宿主 AI 接手，CLI 会打印 extraction prompt，让你复制到任意模型中生成结构化 JSON。

无论走哪条，core 里都不写启发式抽取规则——语义判断只交给模型或用户确认。

## 标准 8 步比赛剧本

运行：

```bash
bash scripts/demo_8_steps.sh
```

剧本覆盖：

1. 清空记忆
2. 首次任务
3. 用户反馈
4. 查看记忆
5. 再次任务应用记忆
6. 偏好变化并 supersede 旧记忆
7. 第三次任务应用新规则
8. 删除后复测，并用 `verify-deletion` 确认不再使用该记忆

删除后验证：

```bash
memory-bridge delete <memory_id>
memory-bridge verify-deletion <memory_id> --task-type technical_planning
```

导出诊断包：

```bash
memory-bridge export-diagnostic --output diagnostic.zip
```

评分对应关系见：[`docs/wasc_scoring_map.md`](docs/wasc_scoring_map.md)。

## Claude / Codex / MCP / 产品嵌入

集成设计见：[`docs/integrations.md`](docs/integrations.md)。

核心原则：

```text
Memory Store 是源头
CLAUDE.md / AGENTS.md / MCP context / product context 是投影
```

不要手动维护导出的 managed section。要修改记忆，请修改 SQLite 中的 memory record：

```bash
memory-bridge view
memory-bridge edit <memory_id> --content "..."
memory-bridge delete <memory_id>
```

## 项目结构

```text
project-root/
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── CHANGELOG.md
├── docs/
│   ├── positioning.md
│   ├── wasc_scoring_map.md
│   ├── integrations.md
│   ├── tencentdb_agent_memory_reference.md
│   └── non_goals.md
├── skill/
│   └── SKILL.md
├── memory_bridge/
│   ├── schemas.py
│   ├── store.py
│   ├── extractor.py
│   ├── resolver.py
│   ├── context_builder.py
│   ├── exporters.py
│   ├── diagnostics.py
│   ├── deletion_verifier.py
│   ├── doctor.py
│   ├── mcp_server.py
│   └── cli.py
├── scripts/
│   └── demo_8_steps.sh
├── tests/
│   ├── test_memory_lifecycle.py
│   ├── test_context_and_delete.py
│   ├── test_deletion_verification.py
│   ├── test_traceability.py
│   ├── test_no_heuristic_extraction_policy.py
│   └── test_positioning_docs.py
├── policies/
│   └── no_heuristic_extraction.md
├── SETUP.md
└── LICENSE
```

## 明确非目标

第一版不要急着做大。详见：[`docs/non_goals.md`](docs/non_goals.md)。

尤其不要做：

- 通用个人记忆平台；
- 完整知识图谱；
- 全量聊天记录同步；
- 自动读取所有 Claude/Codex 历史；
- 多 agent 自我反思系统；
- Web 大后台；
- 向量库；
- 跨设备云同步；
- 复杂权限系统；
- “自动理解用户全部人生偏好”。

先把这四个瞬间做扎实：

1. 它真的记住了：反馈后生成结构化记忆。
2. 它真的用了：第二次任务不用重复说明。
3. 它真的改了：偏好变化后旧规则被替换。
4. 它真的忘了：删除后不再影响输出。
5. 它真的可追溯：每条抽象记忆都能查回来源反馈。
