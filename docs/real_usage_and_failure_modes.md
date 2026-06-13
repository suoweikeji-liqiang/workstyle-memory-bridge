# Real Usage & Failure Modes

> 本文档把项目迭代过程中**真实使用踩过的坑**和**已编码进 skill / 工具的失败模式**聚拢到一处，方便评审对照"它真的在工作吗"。
> 每条都标注对应的 commit hash 和现在的处理位置。

---

## 一、真实使用驱动的迭代（dogfooding trail）

以下每个特性都不是闭门造车，而是**真实接 Claude Code / Codex 用了一段时间后**踩出来的：

| 时间 | 触发场景 | 对应 commit | 改了什么 |
|---|---|---|---|
| 2026-06-04 | Claude Code 接 MCP 后，`remember_feedback` 既不接受 object 也不接受 string 形式的 memory_json，host 被迫退回 native memory | [`954a411`](https://github.com/suoweikeji-liqiang/workstyle-memory-bridge/commit/954a411) | `memory_json` 改成 `Optional[Union[str, dict]]`，server-side 归一化。**Verified over real MCP stdio with both forms** |
| 2026-06-04 | host 在 build_context 时把 `task_type=bug-fix` 写成 `bugfix`，scope 精确匹配导致最高权重的应用路径静默失败 | [`c620d67`](https://github.com/suoweikeji-liqiang/workstyle-memory-bridge/commit/c620d67) | build_context miss 时返回 `available_scope_values`，让 host 对齐到 store 实际值 |
| 2026-06-04 | host 直接传 memory_json 绕过 extraction prompt，导致写端也会漂移（bug-fix vs bugfix） | [`ca0c660`](https://github.com/suoweikeji-liqiang/workstyle-memory-bridge/commit/ca0c660) | dry-run preview 列出已用 scope values，让 model 在 commit 前复用精确值 |
| 2026-06-10 | **一周真实使用发现**：scoped memories 永远不命中——因为 globals 匹配每个调用，response 看起来成功，task_type-scoped 记忆静默不可达 | [`eef0401`](https://github.com/suoweikeji-liqiang/workstyle-memory-bridge/commit/eef0401) | build_context response 列出未命中 scoped memories + 新增 `context_requests` 审计表 |
| 2026-06-11 | **现场数据**：host 第一次调 build_context 时即兴造 task_type 标签（ops-guidance / code-edit / debugging），不响应响应时的提示重新调一次 | [`55204c5`](https://github.com/suoweikeji-liqiang/workstyle-memory-bridge/commit/55204c5) | always-on export 段枚举精确 stored scope values，让 fresh session 第一次就知道词汇表 |
| 2026-06-11 | 用户问"加载 MCP 不就带这个了吗"——三轮 export-side 补丁后才发现握手 instructions 才是协议原生机制 | [`13d013b`](https://github.com/suoweikeji-liqiang/workstyle-memory-bridge/commit/13d013b) | server instructions 在握手时计算并下发，零时上下文，新装客户端开箱即用 |
| 2026-06-11 | 本地一个用户的 CLAUDE.md 里手写了 anti-duplicate 规则；分布式用户没这规则，会导致 host native memory 和此 store 双写，drift 后破坏 verify-deletion | [`863f473`](https://github.com/suoweikeji-liqiang/workstyle-memory-bridge/commit/863f473) | 记忆路由规则随 MCP handshake instructions 下发，每个 host 都收到 |

---

## 二、已编码的失败模式对照表

下列每一个失败模式，**都对应一个具体的 fix 和可见的处理位置**。这是项目最大的差异化资产——不是"我们不会出错"，而是"我们知道会怎么出错，并且每个错都有信号 + 治理通道"。

| # | 失败模式 | 现在怎么处理 | 检测信号 / 用户自助命令 |
|---|---|---|---|
| 1 | **host 造 task_type 标签 → 不命中** | build_context miss 时返回 `available_scope_values`；always-on export 段枚举词汇表 | `build-context` 响应里的 `available_scope_values` 字段 |
| 2 | **host 不复用 slot → supersede 失效** | dry-run preview 列出 store 已用的 scope values；extraction prompt 注入 active 记忆 | `ingest-feedback --dry-run` 的 "Existing scope values in use" 段 |
| 3 | **scoped memories 被 globals 屏蔽，静默不可达** | build_context 响应列出未命中的 scoped memories + 计数；`context_requests` 审计表 | `build-context` 响应里的 `unmatched scoped memory` 提示；`context-log` 命令 |
| 4 | **select_memories 截断无信号** | 返回 `withheld` 数量 + 查看方法 | `build-context` 响应里的 "withheld" 提示 |
| 5 | **always-on 段无限增长** | 默认只导 global-scope，scoped 走 on-demand；`--all-scopes` 可选 | `export` 命令的 managed section 透明说明 |
| 6 | **duplicates 漂移 + 跨删除存活，破坏 verify-deletion** | MCP handshake instructions 下发"工作方式偏好只入此 store，禁止重复进 native memory" | `inspect` 看记忆卡片；`verify-deletion` 跨投影检查 |
| 7 | **scoped memories 从未被返回** | doctor recall health 报告：哪些 scoped 记忆有机会却从未被返回 / 哪些请求的 scope 值无匹配 | `doctor` 命令 / `memory_doctor` MCP 工具 |
| 8 | **临时任务信息混进长期偏好** | demo 演示 durable (workflow) + temporary (session-scoped) 分离；temporary 永不进入后续任务上下文 | `view` 看 type/scope；`inspect` 看 lifecycle |

---

## 三、Claude Code / Codex 集成验证状态

- **Claude Code**：通过 `.mcp.json` 配置接通，所有 MCP 工具（reset_memory / view_memory / remember_feedback / inspect_memory / build_context / edit_memory / delete_memory / verify_deletion / memory_doctor）可用。`954a411` 已验证 stdio 双向传参。
- **Codex**：通过 `codex mcp add workstyle-memory -- python -m memory_bridge.mcp_server` 注册，同一 store 共享。
- **MCP server instructions**：握手时下发全局记忆 + scope 词汇表 + 记忆路由规则 + 快照语义声明（`13d013b`、`863f473`、`a4a7e21`）。

---

## 四、知道但还没编码的边界

诚实列出当前局限（这些是下一轮迭代的方向）：

- **MCP server instructions 是握手快照**：会话内对 store 的编辑/删除，已开的 session 仍持有旧快照。`verify-deletion` 报告已诚实披露这一点。修法是让 host 在会话内重新 build_context，但 host 是否真做，未端到端验证。
- **scope 匹配是精确字符串匹配**：不做模糊匹配（这是设计纪律，防止启发式回潮），但意味着 host 必须精确复用 stored value。我们用 `available_scope_values` 信号让 host 自对齐，但如果 host 不读这个字段，仍可能漂移。
- **没有 baseline vs with_skill 的独立评测 agent**：第 8 维"实测表现"目前是真实 dogfooding + 8 步演示，没跑过 repeated-eval 量化对比。这是下一轮要做的事。

---

*这份文档由真实使用驱动。每条记录都能在 git log 里找到对应 commit，每个失败模式都能在工具响应里找到信号。*
