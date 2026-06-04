# No heuristic extraction policy

## Reason

AI coding tools often implement fast-looking memory extraction with keyword rules, regexes, phrase lists, or hand-written if/else trees. That is explicitly disallowed in this project.

User feedback is open-ended, multilingual, domain-specific, and contextual. It cannot be reliably handled by enumerating phrases such as “以后”, “不要”, “喜欢”, “always”, “never”, or “prefer”.

The project should stay general by separating responsibilities:

```text
semantic understanding -> model-backed structured output or explicit user JSON
engineering code       -> validation, scope, lifecycle, audit, export
```

## Banned

- Keyword-based classification of memory type.
- Regex extraction of preference/scope/slot from natural language feedback.
- Phrase lists such as `PREFERENCE_WORDS`, `NEGATIVE_WORDS`, or `WORKFLOW_TRIGGERS`.
- Hidden branches for demo sentences.
- Fallback logic that silently guesses a memory when the extractor is unavailable.
- Deterministic natural-language rules for deciding whether something is long-term, temporary, project-specific, or a preference change.

## Allowed

- Validating a structured JSON payload.
- Selecting active memories by already structured scope fields.
- Superseding an older active memory with the same `slot + scope`.
- User-issued lifecycle commands: reset, view, edit, delete.
- Export formatting for Claude/Codex/MCP/product contexts.
- Model-backed structured extraction.
- User-confirmed structured input.

## Required behavior when no extractor is available

When no `--memory-json` and no model command are provided, the system must not guess. It should fail clearly and provide the extraction prompt so the user can send it to a model.

## Design test

When adding code, ask:

> Does this function inspect natural-language feedback and decide meaning with hand-written rules?

If yes, it is probably violating this policy.

## Relationship to project positioning

This policy also prevents the project from becoming a brittle demo-specific memory MCP. The goal is not to pass one script by matching phrases; the goal is to produce governed workstyle memory that can survive new users, new domains, and new tools.
