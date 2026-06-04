# Claude Code instructions

This repository is for **Workstyle Memory Bridge**, a lightweight Traceable Workstyle Memory Governance MCP / CLI Skill.

## North star

One feedback event should improve future collaboration across Claude, Codex, MCP clients, and product assistants while remaining inspectable, editable, reversible, and traceable to source evidence.

## Stay focused

Do not turn this project into:

- a generic memory MCP;
- a knowledge graph platform;
- a project memory bank clone;
- a full coding agent;
- a long-task context compression system;
- a second brain / note capture app.

The sharp wedge is:

```text
user feedback -> structured workstyle memory -> evidence refs -> scoped context -> next-task adaptation -> update/delete proof
```

## Hard rule

Do not add keyword matching, regex extraction, phrase tables, handcrafted classifiers, or demo-specific branches for semantic extraction.

The core may perform:

- JSON schema validation;
- explicit scope matching;
- slot + scope supersede logic;
- user-command lifecycle changes;
- evidence event linking;
- inspect/diagnostic export;
- export formatting;
- audit logging.

Semantic extraction must be model-backed structured output or explicit JSON supplied by a user/tool. If no extractor is configured, return the extraction prompt instead of guessing.

## Keep it lightweight

SQLite + CLI + optional MCP adapter is enough for the initial versions. Add dependencies only when they directly improve WASC scoring, daily self-use, or product embedding.
