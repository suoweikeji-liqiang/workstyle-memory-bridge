"""@file JSON must accept Windows-created files.

Windows PowerShell 5.1's `Out-File -Encoding utf8` always writes a UTF-8 BOM,
so rejecting BOM'd files breaks the documented `--memory-json @path` flow for
PowerShell users. utf-8-sig reads both BOM and BOM-less files transparently.
"""

import json

from memory_bridge.extractor import load_json_argument

PAYLOAD = {"memories": []}


def test_load_json_argument_accepts_bom_file(tmp_path):
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(PAYLOAD).encode("utf-8"))
    assert load_json_argument(f"@{path}") == PAYLOAD


def test_load_json_argument_accepts_plain_file(tmp_path):
    path = tmp_path / "plain.json"
    path.write_bytes(json.dumps(PAYLOAD).encode("utf-8"))
    assert load_json_argument(f"@{path}") == PAYLOAD


def test_load_json_argument_accepts_inline_string():
    assert load_json_argument('{"memories": []}') == PAYLOAD
