# Workstyle Memory Bridge

**Version 0.6.2**

> 一次反馈，多工具生效，可查看、可撤销、可进化、可溯源。  
> One feedback, cross-tool effect, viewable, reversible, evolvable, and traceable.

Workstyle Memory Bridge 是一个轻量级的 **工作方式记忆治理系统（Workstyle Memory Governance MCP/CLI）**。它让 AI 记住你希望它如何协作，并在后续任务中自动应用这些偏好，同时保持完全的透明度和可控性。

**它不是**：个人知识库、聊天记录存档、通用 RAG、或”记住一切”的 memory MCP。

**它专注于**：AI 如何记住你的协作偏好，并在后续任务中可验证地应用它们。

## 核心特性 / Core Features

**工作方式治理，而非通用记忆** —— 专注记录协作偏好、工作流和项目规则，而非事实和笔记。

- **智能替换** —— 相同 `slot + scope` 的新记忆会替换旧的，避免冲突堆积
- **完全可溯源** —— 每条记忆追溯到产生它的原始反馈事件
- **可验证删除** —— `verify-deletion` 确认记忆在所有投影中真正停用
- **零启发式规则** —— 语义判断交给模型，内核只做结构和生命周期管理
- **跨工具生效** —— 一处记录，在 Claude、Codex、MCP 客户端等多工具中应用
- **零时上下文** —— MCP 握手时自动注入，无需手动导出

## 为什么需要它 / Why It Matters

传统 AI 工具每次对话都像第一次见面。即使你反复强调"代码审查时先看安全问题"或"技术方案先讲北极星再给 MVP"，下次它还是会忘记。

Workstyle Memory Bridge 解决这个问题：它把你的协作偏好结构化存储，自动应用到后续任务，同时确保：
- 偏好变化时会替换旧规则，而非堆积冲突
- 每条记忆都能追溯到产生它的原始反馈
- 删除后能验证它真的停止生效了

## 与同类项目的区别

记忆赛道已经有几个成熟对手。本项目不和它们正面拼"记得更多、记得更准"，**切口是"治理"——记得干净、改得了、删得掉、查得回**。

| 对手 | 它的绝活 | 它不解决的问题（本项目的位置） |
|---|---|---|
| [mem0](https://github.com/mem0ai/mem0) | 工业级 memory layer，2026-04 新算法 LongMemEval 94.8，已接 Claude Code / Cursor skills | **ADD-only 不 update**——记忆只增不减，偏好变化时会新旧共存冲突；无 verify-deletion |
| [LangMem](https://github.com/langchain-ai/langmem) | LangGraph 原生，hot-path + background manager 双模式 | 强绑 LangGraph 生态；namespace 是字符串，没有 slot+scope 治理；无 supersede |
| [Letta (MemGPT)](https://github.com/letta-ai/letta) | self-improving agent 平台，memory blocks + Letta Code CLI | block 粒度太粗（human / persona 两块），不区分偏好类型；自带 runtime，不是 MCP 插件 |
| [Zep](https://github.com/getzep/zep) | temporal knowledge graph（Graphiti），fact 带 valid_at/invalid_at | 已转 cloud-first，社区版 deprecated；图谱复杂度高，对单用户协作偏好是杀鸡用牛刀 |
| Cline Memory Bank | Cline 内置，零配置 | 纯手工 markdown 维护——WASC 规则明确扣分 |

**差异化坐标**：slot + scope + supersede（同键替换不堆叠）+ L0 证据链（每条记忆可下钻到原始反馈）+ verify-deletion（跨投影验证删除生效）+ 零启发式（语义判断交给模型）。这是目前**没人占的格子**。

更多定位说明见：[`docs/positioning.md`](docs/positioning.md)，真实使用踩坑和失败模式对照见：[`docs/real_usage_and_failure_modes.md`](docs/real_usage_and_failure_modes.md)。

## 记忆层次架构 / Memory Layers

借鉴分层记忆系统（如 TencentDB-Agent-Memory）的核心思想：**抽象记忆必须能下钻到来源证据**。本项目实现轻量的 L0-L3 工作方式记忆层次：

| Layer | 含义 |
|---|---|
| L0 event | 原始用户反馈、修正或任务片段 |
| L1 atom | 单条结构化工作方式记忆 |
| L2 scenario | 由一组 L1 汇编出的场景协作 playbook |
| L3 profile | 更高层的用户/团队协作画像（非 MVP 默认路径） |

当前版本重点实现 **L0 evidence events + L1 memory atoms**，并提供轻量 **L2 scenario playbook**：L2 不从聊天记录自动生成，也不做用户画像；它只从已确认的 active L1 记忆汇编，保留 `source_memory_refs` 和 L0 `evidence_refs`。如果来源 L1 被更新、替换或删除，L2 会变成 stale，`build-context` 会回退到 L1。

参考边界见：[`docs/tencentdb_agent_memory_reference.md`](docs/tencentdb_agent_memory_reference.md)。

## 设计原则：零启发式规则 / Zero Heuristic Rules

本项目明确禁止使用关键词匹配、正则表达式、或手写规则来判断记忆语义。

**原因**：用户表达方式、语言、领域无法穷举。硬编码规则短期看似快速，但会导致系统不可维护、不可泛化、不可评测。

### 禁止 ❌

- 用关键词判断记忆类型（如看到”以后”就判定为长期偏好）
- 用正则或字符串包含关系从反馈中抽取语义
- 用手写规则推断 scope、slot、偏好变化或删除意图

### 允许 ✅

- **Schema validation**：校验 JSON 字段、类型、scope
- **Explicit scope matching**：按已知的 project、tool、task_type 等元数据选择记忆
- **Lifecycle rules**：同 slot + scope 只保留一个 active，新记忆替换旧记忆
- **Model-backed extraction**：由模型按 JSON schema 输出结构化记忆
- **User-confirmed input**：用户或工具直接提供 memory JSON

**一句话原则**：语义判断交给模型或用户；工程代码只做结构、生命周期和可验证治理。

完整政策见：[`policies/no_heuristic_extraction.md`](policies/no_heuristic_extraction.md)。

## 核心能力 / Core Capabilities

- **`reset`**：清空记忆，支持从空白状态开始
- **`view`**：查看 active / superseded / archived / deleted / all 记忆
- **`inspect`**：查看单条记忆的完整信息卡片、证据来源和生命周期
- **`ingest-feedback`**：将用户反馈转化为结构化记忆
- **`build-context`**：根据 scope 生成上下文；返回命中的记忆，并列出未命中的 scoped 记忆及其精确 scope 值
- **`build-scenario`**：从匹配的 active L1 记忆生成/预览/确认轻量 L2 场景 playbook；没有 `--scenario-json` 时只打印模型 prompt，不自动总结
- **`scenario-status`**：检查 L2 playbook 是否仍与来源 L1 同步；来源 L1 变化后会报告 stale
- **`context-log`**：查看记忆召回审计日志（每次 build-context 调用、命中结果、未命中统计）
- **`why-used`**：解释最新或指定一次 build-context 为什么返回这些记忆，包括 scope 命中原因和排序信号
- **`edit`**：修改记忆内容、scope、slot、confidence、status
- **`delete`**：删除记忆，删除后不再进入上下文
- **`verify-deletion`**：验证被删除记忆不会再进入 context 或投影文件
- **`doctor`**：
  - **生命周期检查**：发现重复 active、过长内容等问题
  - **召回健康检查**：分析哪些 scoped 记忆从未被召回、哪些请求的 scope 值无匹配记忆
  - 只报告事实，不做语义判断；修订由宿主 AI 通过治理通道完成
- **`export claude`**：导出到 `CLAUDE.md` 的 managed section
- **`export codex`**：导出到 `AGENTS.md` 的 managed section
- **`export-diagnostic`**：导出诊断包（记忆、证据、事件），便于复现和调试
- **MCP Server**：通过 MCP 协议暴露上述能力，支持 AI host 自动调用
  - **零时上下文**：MCP 握手时自动注入全局记忆和 scope 词汇表，无需手动导出
  - **记忆路由规则**：工作方式偏好只存在此系统中，避免在 host native memory 中重复

## 快速开始 / Quick Start

### 1. 安装

```bash
cd workstyle-memory-bridge
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[mcp]'
```

### 2. 连接 AI Host（推荐）

**主推使用方式**：通过 MCP 协议连接 AI host（Claude Code、Codex 等），让 AI 自动处理记忆提取和应用。

以 Claude Code 为例，添加到项目的 `.mcp.json`：

```json
{
  "mcpServers": {
    "workstyle-memory": {
      "command": "python",
      "args": ["-m", "memory_bridge.mcp_server"],
      "env": {
        "MEMORY_BRIDGE_DB": "/path/to/your/memory.sqlite"
      }
    }
  }
}
```

或使用命令：

```bash
claude mcp add workstyle-memory -- python -m memory_bridge.mcp_server
```

连接后，MCP 握手时会自动注入：
- 全局记忆（始终生效的偏好）
- Scoped 记忆的词汇表（让 AI 知道有哪些 task_type 等）
- 记忆路由规则（工作方式偏好只存储在此系统中）

可选：将 `skill/SKILL.md` 安装到 host 的 skill 目录以获得更好的提取和召回策略。

### 3. 使用示例

连接 AI host 后，你可以自然地给出反馈：

```
你：以后给技术方案时，先讲北极星和边界，再给 MVP，不要上来堆完整架构
AI：[自动调用 remember_feedback，生成结构化记忆]

你：开始写 feature-X 的技术方案
AI：[自动调用 build_context，应用相关记忆，按你的偏好输出方案]
```

### 4. CLI 检查工具

CLI 主要用于检查和诊断：

```bash
# 查看所有记忆
memory-bridge view

# 查看单条记忆详情（包括证据来源）
memory-bridge inspect <memory_id>

# 查看召回日志
memory-bridge context-log

# 解释最新一次召回为什么用了这些记忆
memory-bridge why-used

# 生成 L2 场景 playbook（先打印 prompt；确认 JSON 后再写入）
memory-bridge build-scenario --task-type technical_planning
memory-bridge build-scenario --task-type technical_planning --scenario-json @scenario.json --dry-run
memory-bridge build-scenario --task-type technical_planning --scenario-json @scenario.json

# 检查 L2 是否因来源 L1 变化而 stale
memory-bridge scenario-status

# 健康检查
memory-bridge doctor

# 验证删除
memory-bridge delete <memory_id>
memory-bridge verify-deletion <memory_id> --task-type technical_planning
```

### 5. 独立环境测试

使用独立数据库测试（不影响现有记忆）：

```bash
export MEMORY_BRIDGE_DB=/tmp/test-memory.sqlite
memory-bridge reset
memory-bridge view  # 确认为空
```

或在每个命令中指定：

```bash
memory-bridge --db /tmp/test.sqlite view
```

完整设置说明见：[`SETUP.md`](SETUP.md)。

## 记忆类型 / Memory Types

系统支持多种记忆类型，每种有不同的生命周期：

- **`preference`**：用户偏好（如代码风格、输出格式）
- **`workflow`**：工作流程规则（如技术方案结构、代码审查顺序）
- **`project_rule`**：项目特定规则（如命名约定、架构决策）
- **`temporary`**：临时记忆，仅在当前 session 有效，不会泄漏到后续任务
- **`fact`**：事实性信息
- **`anti_preference`**：明确不想要的行为

每种类型可以设置不同的 scope（global、task_type、project 等），控制记忆的应用范围。

## 集成方式 / Integration Patterns

### 核心原则

```
Memory Store 是源头
CLAUDE.md / AGENTS.md / MCP context 是投影
```

**不要手动维护导出文件的 managed section**。要修改记忆，请修改 SQLite 中的记录：

```bash
memory-bridge view
memory-bridge edit <memory_id> --content "..."
memory-bridge delete <memory_id>
```

### MCP 集成（推荐）

通过 MCP 协议，AI host 可以：
- 握手时自动获取全局记忆和 scope 词汇表
- 运行时调用 `build_context` 获取相关记忆
- 自动提取用户反馈并调用 `remember_feedback`
- 调用 `why_used` 解释单次召回结果
- 查询召回日志，用 `memory_doctor` 诊断长期问题

召回排序只使用结构化 metadata：L2 新鲜度、scope 精确度、memory type、confidence、轻量 usage balance、recency。它不会读取记忆正文做关键词匹配。

### 文件导出（备用）

对于不支持 MCP instructions 的 host，可以导出到指令文件：

```bash
memory-bridge export claude --path ./CLAUDE.md
memory-bridge export codex --path ./AGENTS.md
```

导出的内容是只读投影，源头仍是 SQLite 数据库。

详细集成设计见：[`docs/integrations.md`](docs/integrations.md)。

## 测试 / Testing

运行完整测试套件：

```bash
pip install -e '.[test]'
pytest -q
```

### 8 步连续使用测试

标准测试脚本演示完整生命周期：

```bash
bash scripts/demo_8_steps.sh
```

覆盖场景：
1. 清空记忆（reset）
2. 首次任务（无记忆）
3. 用户反馈（生成结构化记忆 + L0 证据）
4. 查看和溯源记忆（view/inspect）
5. 再次任务（应用记忆）
6. 偏好变化（supersede 旧记忆）
7. 第三次任务（应用新规则）
8. 删除验证（verify-deletion）

该脚本也演示了 `temporary` 类型记忆的正确隔离：session-scoped 临时细节不会泄漏到后续任务。

## 项目结构 / Project Structure

```text
workstyle-memory-bridge/
├── memory_bridge/          # 核心实现
│   ├── schemas.py          # 记忆和证据 schema
│   ├── store.py            # SQLite 存储层
│   ├── extractor.py        # 语义提取（模型驱动）
│   ├── resolver.py         # 冲突解决和 supersede 逻辑
│   ├── context_builder.py  # 上下文构建和召回
│   ├── exporters.py        # CLAUDE.md/AGENTS.md 导出
│   ├── deletion_verifier.py # 删除验证
│   ├── doctor.py           # 健康检查和召回诊断
│   ├── diagnostics.py      # 诊断包导出
│   ├── mcp_server.py       # MCP 协议服务器
│   └── cli.py              # CLI 入口
├── docs/                   # 文档
│   ├── positioning.md      # 定位说明
│   ├── integrations.md     # 集成方式
│   ├── tencentdb_agent_memory_reference.md
│   └── non_goals.md        # 明确不做什么
├── policies/               # 设计原则
│   └── no_heuristic_extraction.md
├── skill/                  # MCP skill 指导
│   └── SKILL.md
├── scripts/
│   └── demo_8_steps.sh     # 标准测试脚本
├── tests/                  # 测试套件
├── SETUP.md                # 详细设置指南
├── CHANGELOG.md            # 版本历史
└── README.md
```

## 设计边界 / Design Boundaries

本项目专注于工作方式记忆治理，明确不做：

- 通用个人记忆平台
- 完整知识图谱
- 聊天记录归档
- 向量数据库
- 多 agent 反思系统
- Web 管理后台
- 跨设备云同步

详见：[`docs/non_goals.md`](docs/non_goals.md)。

## 核心验证目标

系统设计确保以下关键能力：

1. **它真的记住了**：反馈后生成结构化记忆 + L0 证据
2. **它真的用了**：第二次任务自动应用，无需重复说明
3. **它真的改了**：偏好变化后旧规则被替换（不是堆积）
4. **它真的忘了**：删除后通过 verify-deletion 证明不再生效
5. **它真的可追溯**：每条抽象记忆都能下钻到来源反馈

## License

MIT-0 License. See [LICENSE](LICENSE) for details.

## Contributing

欢迎贡献！请确保：
- 遵循零启发式规则原则（见 `policies/no_heuristic_extraction.md`）
- 添加测试覆盖新功能
- 更新相关文档

## Changelog

详细版本历史见 [CHANGELOG.md](CHANGELOG.md)。
