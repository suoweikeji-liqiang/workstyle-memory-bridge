"""Guardrails against slipping into brittle heuristic extraction.

These tests are intentionally modest; they are a tripwire, not a complete
static analyzer. The policy is documented in policies/no_heuristic_extraction.md.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "memory_bridge"


def parse_module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_extractor_does_not_import_regex():
    tree = parse_module(CORE / "extractor.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "re" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "re"


def test_extractor_has_no_keyword_branching_against_feedback():
    tree = parse_module(CORE / "extractor.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            left = ast.unparse(node.left) if hasattr(ast, "unparse") else ""
            comparators = [ast.unparse(c) if hasattr(ast, "unparse") else "" for c in node.comparators]
            expression = " ".join([left] + comparators)
            assert "feedback" not in expression or not any(
                isinstance(op, (ast.In, ast.NotIn)) for op in node.ops
            )


def test_no_rules_module_or_keyword_table_in_core():
    banned_names = {"rules.py", "heuristics.py", "keyword_extractor.py"}
    found = {path.name for path in CORE.glob("*.py")}
    assert banned_names.isdisjoint(found)
