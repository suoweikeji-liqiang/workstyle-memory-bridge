# Workstyle Memory Bridge 试用指南（v0.6.4）

一句话：让 AI 记住“你希望它怎么干活”，并且记忆可查、可改、可删、可证明删除。

它只管工作方式偏好：输出结构、代码审查顺序、修 bug 汇报方式、项目协作规则等。它不是聊天记录存档，也不是个人知识库。

## 安装

```bash
pip install workstyle_memory_bridge-0.6.4-py3-none-any.whl "mcp>=1.0.0"
```

接入 Claude Code 或其他 MCP 客户端：

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

新会话开始时，MCP 握手会带上全局记忆、scope 词汇表和使用规则；不需要手改 `CLAUDE.md`。

## 5 分钟体验

1. 对 AI 说：“记住：以后写方案先给结论再展开。”
2. AI 应先预览要保存的记忆；你确认后再写入。
3. 运行 `memory-bridge view` 和 `memory-bridge inspect <id>` 查看内容和证据。
4. 新任务开始时，AI 调 `build_context` 并按记忆调整输出。
5. 改主意时，用同一 `slot + scope` supersede 旧记忆，而不是叠加冲突。
6. 删除前可先 `preview-delete <id>`，确认后 `delete <id>`。
7. 用 `verify-deletion <id>` 证明它不再进入上下文或导出投影。

## 常用命令

```bash
memory-bridge view [--status all]
memory-bridge inspect <id>
memory-bridge why-used
memory-bridge doctor
memory-bridge preview-edit <id> --content "..."
memory-bridge preview-delete <id>
memory-bridge verify-deletion <id> --task-type <value>
memory-bridge export-diagnostic --output diagnostic.zip
```

## 隔离试用

```bash
export MEMORY_BRIDGE_DB=/tmp/workstyle-memory-test.sqlite
memory-bridge reset
```

所有数据默认在本机 SQLite 文件中。诊断包可能包含反馈原文，分享前请先检查。
