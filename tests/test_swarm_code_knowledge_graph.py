#!/usr/bin/env python3
"""Round 70 tests — Code Knowledge Graph organ.

Verifies:
  - walk_python_file produces correct nodes + edges from a synthetic file
  - file node always appears (with kind=file, name="")
  - class nodes + function nodes captured with right lineno
  - import edges (both `import X` and `from X import Y` shapes)
  - call edges from inside function bodies
  - defines edges from parent scope to child
  - parse error returns ([], []), never raises
  - incremental scan skips unchanged files (content_hash match)
  - non-incremental scan re-walks
  - real .sifta_state/ ledgers untouched under tmp_path
  - load_recent_nodes / load_recent_edges read tail correctly
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_code_knowledge_graph as ckg


SAMPLE_PY = '''"""Sample module docstring."""

import os
from pathlib import Path
from typing import List, Dict


class Greeter:
    """Greets people."""

    def __init__(self, name: str) -> None:
        self.name = name

    def hello(self) -> str:
        """Return a greeting."""
        return f"hello {self.name}"


def standalone_function(x: int) -> int:
    """Adds one."""
    result = x + 1
    Greeter("world").hello()
    return result


async def async_function(y):
    return y * 2
'''


def _write_sample(tmp_path: Path) -> Path:
    repo = tmp_path
    target_dir = repo / "System"
    target_dir.mkdir(parents=True, exist_ok=True)
    f = target_dir / "sample_mod.py"
    f.write_text(SAMPLE_PY, encoding="utf-8")
    return f


# ─── walk_python_file ──────────────────────────────────────────────────────


def test_walk_python_file_produces_file_node(tmp_path):
    f = _write_sample(tmp_path)
    nodes, edges = ckg.walk_python_file(f, repo_root=tmp_path)
    file_nodes = [n for n in nodes if n.kind == "file"]
    assert len(file_nodes) == 1
    fn = file_nodes[0]
    assert fn.path == "System/sample_mod.py"
    assert fn.name == ""
    assert fn.lineno == 0
    assert fn.docstring_head == "Sample module docstring."


def test_walk_python_file_captures_class_and_method(tmp_path):
    f = _write_sample(tmp_path)
    nodes, _edges = ckg.walk_python_file(f, repo_root=tmp_path)
    class_nodes = [n for n in nodes if n.kind == "class"]
    assert len(class_nodes) == 1
    g = class_nodes[0]
    assert g.name == "Greeter"
    assert g.docstring_head == "Greets people."
    method_nodes = [n for n in nodes if n.kind == "function" and n.name == "hello"]
    assert len(method_nodes) == 1
    h = method_nodes[0]
    assert h.parent_id == g.node_id
    assert h.docstring_head == "Return a greeting."


def test_walk_python_file_captures_standalone_and_async_functions(tmp_path):
    f = _write_sample(tmp_path)
    nodes, _edges = ckg.walk_python_file(f, repo_root=tmp_path)
    names = {n.name for n in nodes if n.kind == "function"}
    assert "standalone_function" in names
    assert "async_function" in names
    assert "hello" in names
    assert "__init__" in names


def test_walk_python_file_captures_import_edges(tmp_path):
    f = _write_sample(tmp_path)
    _nodes, edges = ckg.walk_python_file(f, repo_root=tmp_path)
    imports = [e for e in edges if e.kind == "import"]
    # `import os` -> to_path=os, to_name=""
    assert any(e.to_path == "os" and e.to_name == "" for e in imports)
    # `from pathlib import Path` -> to_path=pathlib, to_name=Path
    assert any(e.to_path == "pathlib" and e.to_name == "Path" for e in imports)
    # `from typing import List, Dict` -> two edges
    typing_targets = {e.to_name for e in imports if e.to_path == "typing"}
    assert "List" in typing_targets and "Dict" in typing_targets


def test_walk_python_file_captures_call_edges_from_function_body(tmp_path):
    f = _write_sample(tmp_path)
    nodes, edges = ckg.walk_python_file(f, repo_root=tmp_path)
    standalone = next(n for n in nodes if n.name == "standalone_function")
    calls = [e for e in edges if e.kind == "call" and e.from_id == standalone.node_id]
    callee_names = {e.to_name for e in calls}
    # `Greeter("world").hello()` produces two call nodes: Greeter and hello
    assert "Greeter" in callee_names
    assert "hello" in callee_names


def test_walk_python_file_defines_edges_present(tmp_path):
    f = _write_sample(tmp_path)
    _nodes, edges = ckg.walk_python_file(f, repo_root=tmp_path)
    defines = [e for e in edges if e.kind == "defines"]
    target_names = {e.to_name for e in defines}
    assert "Greeter" in target_names
    assert "hello" in target_names
    assert "standalone_function" in target_names


def test_walk_python_file_parse_error_returns_empty(tmp_path):
    repo = tmp_path
    target_dir = repo / "System"
    target_dir.mkdir(parents=True, exist_ok=True)
    f = target_dir / "broken.py"
    f.write_text("def x(:\n  pass\n", encoding="utf-8")  # syntax error
    nodes, edges = ckg.walk_python_file(f, repo_root=tmp_path)
    assert nodes == []
    assert edges == []


def test_walk_python_file_outside_repo_returns_empty(tmp_path):
    """Covenant §3 sovereignty — refuse to graph files outside the repo."""
    other = tmp_path / "elsewhere"
    other.mkdir(parents=True, exist_ok=True)
    f = other / "stranger.py"
    f.write_text("x = 1\n", encoding="utf-8")
    different_repo = tmp_path / "myrepo"
    different_repo.mkdir(parents=True, exist_ok=True)
    nodes, edges = ckg.walk_python_file(f, repo_root=different_repo)
    assert nodes == []
    assert edges == []


def test_walk_python_file_includes_mtime_and_content_hash(tmp_path):
    f = _write_sample(tmp_path)
    nodes, _edges = ckg.walk_python_file(f, repo_root=tmp_path)
    fn = next(n for n in nodes if n.kind == "file")
    assert isinstance(fn.mtime, float) and fn.mtime > 0
    assert isinstance(fn.content_hash, str) and len(fn.content_hash) == 16


def test_walk_python_file_naive_complexity_nonzero_on_branchy_code(tmp_path):
    repo = tmp_path
    target_dir = repo / "System"
    target_dir.mkdir(parents=True, exist_ok=True)
    f = target_dir / "branchy.py"
    f.write_text(
        "def f(x):\n"
        "    if x > 0:\n"
        "        if x > 10:\n"
        "            return 'big'\n"
        "        return 'small'\n"
        "    for i in range(x):\n"
        "        if i % 2: pass\n"
        "    return 'zero'\n",
        encoding="utf-8",
    )
    nodes, _ = ckg.walk_python_file(f, repo_root=tmp_path)
    branchy_fn = next(n for n in nodes if n.name == "f")
    assert branchy_fn.complexity >= 4  # 3 if + 1 for + at least


# ─── walk_repo ─────────────────────────────────────────────────────────────


def test_walk_repo_writes_ledgers(tmp_path):
    _write_sample(tmp_path)
    state_dir = tmp_path / ".sifta_state"
    res = ckg.walk_repo(tmp_path, state_dir=state_dir, incremental=False)
    assert res.files_scanned == 1
    assert res.nodes_written > 0
    assert res.edges_written > 0
    assert res.parse_errors == 0
    nodes_path = state_dir / ckg.NODES_LEDGER_FILENAME
    edges_path = state_dir / ckg.EDGES_LEDGER_FILENAME
    assert nodes_path.exists()
    assert edges_path.exists()


def test_walk_repo_incremental_skips_unchanged(tmp_path):
    _write_sample(tmp_path)
    state_dir = tmp_path / ".sifta_state"
    # First pass
    r1 = ckg.walk_repo(tmp_path, state_dir=state_dir, incremental=True)
    assert r1.files_scanned == 1
    # Second pass — same content
    r2 = ckg.walk_repo(tmp_path, state_dir=state_dir, incremental=True)
    assert r2.files_scanned == 0
    assert r2.files_skipped_unchanged == 1


def test_walk_repo_incremental_rewalks_after_change(tmp_path):
    f = _write_sample(tmp_path)
    state_dir = tmp_path / ".sifta_state"
    ckg.walk_repo(tmp_path, state_dir=state_dir, incremental=True)
    # Modify the file
    f.write_text(SAMPLE_PY + "\ndef added(): pass\n", encoding="utf-8")
    r2 = ckg.walk_repo(tmp_path, state_dir=state_dir, incremental=True)
    assert r2.files_scanned == 1
    # The new function should be in the latest nodes
    rows = ckg.load_recent_nodes(state_dir)
    names = [r["name"] for r in rows]
    assert "added" in names


def test_walk_repo_skips_pycache_and_distro_build(tmp_path):
    repo = tmp_path
    (repo / "System").mkdir()
    (repo / "System" / "good.py").write_text("def x(): pass\n", encoding="utf-8")
    (repo / "System" / "__pycache__").mkdir()
    (repo / "System" / "__pycache__" / "good.cpython-310.pyc").write_text("",
                                                                          encoding="utf-8")
    (repo / ".distro_build").mkdir()
    (repo / ".distro_build" / "fake.py").write_text("def y(): pass\n", encoding="utf-8")
    state_dir = repo / ".sifta_state"
    res = ckg.walk_repo(repo, state_dir=state_dir, incremental=False)
    assert res.files_scanned == 1
    rows = ckg.load_recent_nodes(state_dir)
    paths = {r["path"] for r in rows if r["kind"] == "file"}
    assert "System/good.py" in paths
    assert not any("__pycache__" in p for p in paths)
    assert not any(".distro_build" in p for p in paths)


def test_walk_repo_scope_filter(tmp_path):
    (tmp_path / "System").mkdir()
    (tmp_path / "System" / "a.py").write_text("def f(): pass\n", encoding="utf-8")
    (tmp_path / "Applications").mkdir()
    (tmp_path / "Applications" / "b.py").write_text("def g(): pass\n", encoding="utf-8")
    state_dir = tmp_path / ".sifta_state"
    res = ckg.walk_repo(tmp_path, scope=("System",), state_dir=state_dir,
                       incremental=False)
    assert res.files_scanned == 1
    rows = ckg.load_recent_nodes(state_dir)
    paths = {r["path"] for r in rows if r["kind"] == "file"}
    assert "System/a.py" in paths
    assert "Applications/b.py" not in paths


# ─── load_recent_* ─────────────────────────────────────────────────────────


def test_load_recent_nodes_empty_when_no_ledger(tmp_path):
    assert ckg.load_recent_nodes(tmp_path / ".sifta_state") == []
    assert ckg.load_recent_edges(tmp_path / ".sifta_state") == []


def test_load_recent_nodes_caps_to_max_n(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / ckg.NODES_LEDGER_FILENAME
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(20):
            fh.write(json.dumps({"i": i}) + "\n")
    rows = ckg.load_recent_nodes(state_dir, max_n=5)
    assert len(rows) == 5
    assert [r["i"] for r in rows] == [15, 16, 17, 18, 19]


# ─── Real ledger isolation ──────────────────────────────────────────────────


def test_real_ledgers_untouched(tmp_path):
    state = Path(".sifta_state")
    watch = [
        state / ckg.NODES_LEDGER_FILENAME,
        state / ckg.EDGES_LEDGER_FILENAME,
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
    ]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}

    f = _write_sample(tmp_path)
    _ = ckg.walk_python_file(f, repo_root=tmp_path)
    _ = ckg.walk_repo(tmp_path, state_dir=tmp_path / ".sifta_state",
                     incremental=False)
    _ = ckg.load_recent_nodes(tmp_path / ".sifta_state")
    _ = ckg.load_recent_edges(tmp_path / ".sifta_state")

    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}
    for k in before:
        assert before[k] == after[k], f"code_knowledge_graph mutated {k}"
