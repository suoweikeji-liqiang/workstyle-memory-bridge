# Workstyle Memory Bridge 试用指南（v0.6.2）

**一句话**：让 AI 记住"你希望它怎么干活"，而且记忆**可查、可改、可删、删了能证明**——Claude Code、Codex 等工具共用同一份。

它只管一类东西：你的**工作方式偏好**（比如"写方案先给结论再展开"、"修 bug 按现象→原因→修法的顺序汇报"）。它不是聊天记录存档，不是知识库，不会偷偷记你没让它记的事。

## 安装（约 2 分钟）

前提：Python 3.11+，以及 Claude Code（或任意 MCP 客户端）。

```bash
# 用收到的 whl 文件安装（压缩包里就有，无需访问任何仓库）
pip install workstyle_memory_bridge-0.6.2-py3-none-any.whl "mcp>=1.0.0"
```

接入 Claude Code：在项目根目录建（或编辑）`.mcp.json`：

```json
{
  "mcpServers": {
    "workstyle-memory": {
      "command": "python",
      "args": ["-m", "memory_bridge.mcp_server"]
    }
  }
}
```

新开一个 Claude Code 会话即生效——AI 在会话开始时就会自动"自带"你的记忆和使用规则（MCP 握手注入，**不需要改你的 CLAUDE.md**）。

## 5 分钟体验路线

1. **存一条**：对 AI 说——"记住：以后给我写方案，先给结论再展开。" AI 会提议要存的内容，你确认。
2. **看一眼**：终端跑 `memory-bridge view`——能看到这条记忆的类型、适用范围、置信度，以及你的**原话证据**。
3. **验效果**：新开会话，让它随便写个方案——看它是否不用提醒就先给结论。
4. **改主意**：再说——"调整一下，只有写周报时才需要那么简洁。" 旧记忆会被**替换**而不是叠加（`view --status superseded` 能看到旧版留档）。
5. **删干净**：`memory-bridge delete <id>`，然后 `memory-bridge verify-deletion <id>`——六项检查逐项证明它真的不再生效。
6. **这次为什么这样生效？**：`memory-bridge why-used`——解释最新一次召回用了哪些记忆、scope 怎么命中、排序信号是什么。
7. **经常没生效？**：`memory-bridge doctor`——它会告诉你长期召回健康问题（比如记忆的适用范围和实际任务对不上），而不用你猜。

## 常用命令速查

```bash
memory-bridge view              # 现在记了什么
memory-bridge inspect <id>      # 单条记忆：内容 + 证据 + 生命周期
memory-bridge context-log       # 每次记忆被取用的审计记录
memory-bridge why-used          # 最新一次召回为什么用了这些记忆
memory-bridge doctor            # 健康检查：死记忆、叫错名的调用
memory-bridge reset             # 全部清空，从零开始
```

## 数据与隐私

所有数据只存在你本机的一个 SQLite 文件里（`~/.memory_bridge/memory_bridge.sqlite`），**没有任何网络上传**。想完全隔离试用，设环境变量 `MEMORY_BRIDGE_DB` 指向任意新路径即可。

## 反馈

用着别扭、记忆没生效、存了不该存的——都想听。最好附上：

```bash
memory-bridge export-diagnostic --output diagnostic.zip
```

（导出前可自行检查，包里可能含你的反馈原文。）发给我即可。

> 仓库目前未公开，源码和最新版本开源后另行提供；现阶段一切以收到的 whl 包为准。
