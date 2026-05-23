"""
test_swarm_skill_extract.py
===========================
Offline tests for swarm_skill_extract. Uses a synthetic trace jsonl.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".sifta_state").mkdir()
    (tmp_path / "skills").mkdir()
    yield tmp_path


@pytest.fixture
def fresh_extract(chdir_tmp):
    for mod in list(sys.modules):
        if mod.startswith("swarm_skill_extract") or mod.startswith("swarm_skill_ingest"):
            del sys.modules[mod]
    import swarm_skill_extract  # noqa
    return swarm_skill_extract


def _write_trace(state: Path, name: str, row: dict) -> str:
    """Drop a single row into a synthetic organ jsonl. Returns its hash."""
    import hashlib
    canonical = json.dumps({k: v for k, v in row.items() if k != "hash"}, sort_keys=True, separators=(",", ":"))
    row["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    (state / name).write_text(json.dumps(row) + "\n")
    return row["hash"]


def test_find_trace_by_hash_exact_and_prefix(fresh_extract, chdir_tmp):
    h = _write_trace(chdir_tmp / ".sifta_state", "terminal_organ.jsonl", {
        "type": "TERMINAL_RESULT",
        "command": "echo hi",
        "exit_code": 0,
        "stdout": "hi",
        "ts": 1700000000.0,
        "prev": "0" * 64,
    })
    assert fresh_extract.find_trace_by_hash(h)["hash"] == h
    assert fresh_extract.find_trace_by_hash(h[:12])["hash"] == h
    assert fresh_extract.find_trace_by_hash("nope") is None


def test_extract_writes_skill_and_logs(fresh_extract, chdir_tmp):
    h = _write_trace(chdir_tmp / ".sifta_state", "file_organ.jsonl", {
        "type": "FILE_LIST",
        "path": ".",
        "tool_name": "list_dir",
        "ts": 1700000001.0,
        "prev": "0" * 64,
    })
    res = fresh_extract.extract_skill_from_trace(
        trace_hash=h,
        name="list current dir",
        description="list all files in cwd",
        when_to_use="user asks what is in this directory",
    )
    assert res["ok"]
    path = Path(res["path"])
    assert path.exists()
    body = path.read_text()
    assert "list-current-dir" in body  # slug
    assert "list_dir" in body
    assert h in body  # trace hash anchored in the skill

    log = (Path(".sifta_state") / "skill_ingest.jsonl").read_text().splitlines()
    types_ = [json.loads(line)["type"] for line in log if line.strip()]
    assert "SKILL_EXTRACT" in types_


def test_extract_missing_trace_returns_error(fresh_extract):
    res = fresh_extract.extract_skill_from_trace("deadbeef", "x")
    assert res["ok"] is False
    assert "not found" in res["error"]


def test_extract_dedupes_slug_when_same_name(fresh_extract, chdir_tmp):
    h1 = _write_trace(chdir_tmp / ".sifta_state", "terminal_organ.jsonl", {
        "type": "TERMINAL_RESULT", "command": "echo 1", "exit_code": 0,
        "ts": 1700000010.0, "prev": "0" * 64,
    })
    # Second row in a second file (so hashes differ)
    h2 = _write_trace(chdir_tmp / ".sifta_state", "file_organ.jsonl", {
        "type": "FILE_LIST", "path": ".", "ts": 1700000011.0, "prev": "0" * 64,
    })
    r1 = fresh_extract.extract_skill_from_trace(h1, "duplicate-name", "a", "b")
    r2 = fresh_extract.extract_skill_from_trace(h2, "duplicate-name", "a", "b")
    assert r1["ok"] and r2["ok"]
    assert r1["slug"] != r2["slug"]
    assert Path(r1["path"]).exists() and Path(r2["path"]).exists()
