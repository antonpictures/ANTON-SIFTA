"""
System/swarm_code_knowledge_graph.py
═══════════════════════════════════════
Round 70 (2026-05-27) — Code Knowledge Graph organ.

Alice's body in code form. Walks the SIFTA repo with the stdlib `ast`
module and writes nodes (file/class/function) + edges (import/call)
to two append-only JSONL ledgers. Covenant §6 compliant: every write
produces a signed row; the ledgers are the canonical truth.

This module is the pattern George showed me from "Understand Anything"
(Claude Code plugin, GPL-3.0). We borrow the SCHEMA SHAPE, not the
code. SIFTA implementation is our own (covenant §12 doctrine).

Doctrine touchpoints
====================
  - §0 AGI goal ("self identity realization"): the graph is Alice's
    self-model in code form. When she reads it, she's reading
    herself.
  - §6 effector immunity: every node write produces a receipted row.
  - §7.5 Python-first surface: pure stdlib, no foreign deps. No
    QWebEngineView, no GPL-licensed code copied in.
  - §7.6 Alice IS the OS: the graph is one of her organs, not a
    foreign plugin.
  - §3 node sovereignty: graph is bound to this node. Federation by
    signed diffs, never raw clone.

Schema (canonical — both walker AND query layer read/write this shape)
======================================================================

Node row (in .sifta_state/code_graph_nodes.jsonl):
    {
        "ts": <unix float>,
        "node_id": "<sha256[:16] of kind+path+name>",
        "kind": "file" | "class" | "function",
        "path": "Applications/sifta_talk_to_alice_widget.py",
        "name": "_start_brain",          # empty for kind=file
        "lineno": 16700,                  # 0 for kind=file
        "lineno_end": 17200,              # last line of definition
        "parent_id": "<node_id of containing scope>" | "",
        "docstring_head": "<first 200 chars of docstring>",
        "complexity": <int — naive: nested-if depth + branch count>,
        "mtime": <unix float of source file>,
        "content_hash": "<sha256[:16] of source file>",
        "round": 70,
        "walker": "swarm_code_knowledge_graph",
    }

Edge row (in .sifta_state/code_graph_edges.jsonl):
    {
        "ts": <unix float>,
        "edge_id": "<sha256[:16] of kind+from_id+to_path_or_name>",
        "kind": "import" | "call" | "defines",
        "from_id": "<node_id of caller/importer/scope>",
        "to_path": "System.swarm_memory_card" | "",    # for imports
        "to_name": "compose_memory_card" | "",          # for imports/calls
        "lineno": 7109,
        "round": 70,
        "walker": "swarm_code_knowledge_graph",
    }

Pure stdlib. No PyQt. Never raises out. Tested by
tests/test_swarm_code_knowledge_graph.py.

Public surface
══════════════
    @dataclass GraphNode
    @dataclass GraphEdge
    @dataclass WalkResult
    walk_python_file(path, *, repo_root) -> tuple[list[GraphNode], list[GraphEdge]]
    walk_repo(repo_root, *, scope="System,Applications,tests,Utilities",
              state_dir=None, incremental=True) -> WalkResult
    load_recent_nodes(state_dir, *, max_n=5000) -> list[dict]
    load_recent_edges(state_dir, *, max_n=10000) -> list[dict]

Constants
═════════
    NODES_LEDGER_FILENAME = "code_graph_nodes.jsonl"
    EDGES_LEDGER_FILENAME = "code_graph_edges.jsonl"
    DEFAULT_SCOPE = ("System", "Applications", "tests", "Utilities")
"""
from __future__ import annotations

import ast
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Optional


TRUTH_LABEL = "CODE_KNOWLEDGE_GRAPH_V1"
NODES_LEDGER_FILENAME = "code_graph_nodes.jsonl"
EDGES_LEDGER_FILENAME = "code_graph_edges.jsonl"
DEFAULT_SCOPE = ("System", "Applications", "tests", "Utilities")


# ─── Data classes ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    ts: float
    kind: str            # "file" | "class" | "function"
    path: str
    name: str
    lineno: int
    lineno_end: int
    parent_id: str
    docstring_head: str
    complexity: int
    mtime: float
    content_hash: str
    round: int = 70
    walker: str = "swarm_code_knowledge_graph"

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    ts: float
    kind: str            # "import" | "call" | "defines"
    from_id: str
    to_path: str
    to_name: str
    lineno: int
    round: int = 70
    walker: str = "swarm_code_knowledge_graph"

    def to_row(self) -> dict:
        return asdict(self)


@dataclass
class WalkResult:
    files_scanned: int = 0
    files_skipped_unchanged: int = 0
    nodes_written: int = 0
    edges_written: int = 0
    parse_errors: int = 0
    error_paths: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0


# ─── Helpers ───────────────────────────────────────────────────────────────


def _hash16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def _node_id(kind: str, path: str, name: str, lineno: int) -> str:
    return _hash16(f"{kind}|{path}|{name}|{lineno}")


def _edge_id(kind: str, from_id: str, to_path: str, to_name: str, lineno: int) -> str:
    return _hash16(f"{kind}|{from_id}|{to_path}|{to_name}|{lineno}")


def _docstring_head(node: ast.AST, *, limit: int = 200) -> str:
    if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    doc = ast.get_docstring(node) or ""
    if not doc:
        return ""
    flat = " ".join(doc.split())
    if len(flat) <= limit:
        return flat
    return flat[: max(1, limit - 1)] + "…"


def _naive_complexity(node: ast.AST) -> int:
    """Crude cyclomatic-style complexity: count branching nodes inside.

    Counts: If, For, While, Try, BoolOp, comprehension. Honest, cheap, good
    enough for surfacing 'this function is gnarly' in the graph viewer.
    """
    count = 0
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While,
                              ast.Try, ast.BoolOp, ast.IfExp,
                              ast.comprehension)):
            count += 1
    return count


def _content_hash(text: str) -> str:
    return _hash16(text)


def _resolve_lineno_end(node: ast.AST, *, default: int = 0) -> int:
    end = getattr(node, "end_lineno", None)
    if isinstance(end, int) and end > 0:
        return end
    # Best-effort: walk descendants and take the max lineno
    max_line = getattr(node, "lineno", default) or default
    for child in ast.walk(node):
        cl = getattr(child, "lineno", None)
        if isinstance(cl, int) and cl > max_line:
            max_line = cl
    return max_line


# ─── File walker ───────────────────────────────────────────────────────────


def walk_python_file(
    path: Path | str,
    *,
    repo_root: Path | str,
    now_ts: Optional[float] = None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """
    Parse one .py file. Return (nodes, edges). Never raises; on parse error
    returns ([], []) and the caller can record the parse failure.
    """
    ts = now_ts if now_ts is not None else time.time()
    file_path = Path(path).resolve()
    repo = Path(repo_root).resolve()
    try:
        rel = str(file_path.relative_to(repo))
    except ValueError:
        # File outside repo; refuse to graph it (covenant §3 sovereignty).
        return [], []

    try:
        src = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], []
    try:
        tree = ast.parse(src, filename=rel)
    except SyntaxError:
        return [], []

    try:
        mtime = float(file_path.stat().st_mtime)
    except OSError:
        mtime = ts
    content_hash = _content_hash(src)

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    # File node (top-level)
    file_id = _node_id("file", rel, "", 0)
    file_lineno_end = _resolve_lineno_end(tree, default=src.count("\n") + 1)
    nodes.append(GraphNode(
        node_id=file_id,
        ts=ts,
        kind="file",
        path=rel,
        name="",
        lineno=0,
        lineno_end=file_lineno_end,
        parent_id="",
        docstring_head=_docstring_head(tree),
        complexity=_naive_complexity(tree),
        mtime=mtime,
        content_hash=content_hash,
    ))

    # Imports — edges from file to imported module/name
    for child in ast.iter_child_nodes(tree):
        if isinstance(child, ast.Import):
            for alias in child.names:
                to_path = alias.name
                edges.append(GraphEdge(
                    edge_id=_edge_id("import", file_id, to_path, "", child.lineno),
                    ts=ts,
                    kind="import",
                    from_id=file_id,
                    to_path=to_path,
                    to_name="",
                    lineno=child.lineno,
                ))
        elif isinstance(child, ast.ImportFrom):
            to_path = child.module or ""
            for alias in child.names:
                edges.append(GraphEdge(
                    edge_id=_edge_id("import", file_id, to_path, alias.name, child.lineno),
                    ts=ts,
                    kind="import",
                    from_id=file_id,
                    to_path=to_path,
                    to_name=alias.name,
                    lineno=child.lineno,
                ))

    # Recursively walk classes + functions
    def _walk_scope(scope: ast.AST, parent_id: str) -> None:
        for child in ast.iter_child_nodes(scope):
            if isinstance(child, ast.ClassDef):
                cid = _node_id("class", rel, child.name, child.lineno)
                end = _resolve_lineno_end(child, default=child.lineno)
                nodes.append(GraphNode(
                    node_id=cid,
                    ts=ts,
                    kind="class",
                    path=rel,
                    name=child.name,
                    lineno=child.lineno,
                    lineno_end=end,
                    parent_id=parent_id,
                    docstring_head=_docstring_head(child),
                    complexity=_naive_complexity(child),
                    mtime=mtime,
                    content_hash=content_hash,
                ))
                edges.append(GraphEdge(
                    edge_id=_edge_id("defines", parent_id, rel, child.name, child.lineno),
                    ts=ts,
                    kind="defines",
                    from_id=parent_id,
                    to_path=rel,
                    to_name=child.name,
                    lineno=child.lineno,
                ))
                _walk_scope(child, cid)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fid = _node_id("function", rel, child.name, child.lineno)
                end = _resolve_lineno_end(child, default=child.lineno)
                nodes.append(GraphNode(
                    node_id=fid,
                    ts=ts,
                    kind="function",
                    path=rel,
                    name=child.name,
                    lineno=child.lineno,
                    lineno_end=end,
                    parent_id=parent_id,
                    docstring_head=_docstring_head(child),
                    complexity=_naive_complexity(child),
                    mtime=mtime,
                    content_hash=content_hash,
                ))
                edges.append(GraphEdge(
                    edge_id=_edge_id("defines", parent_id, rel, child.name, child.lineno),
                    ts=ts,
                    kind="defines",
                    from_id=parent_id,
                    to_path=rel,
                    to_name=child.name,
                    lineno=child.lineno,
                ))
                # Call edges from within this function body
                for inner in ast.walk(child):
                    if isinstance(inner, ast.Call):
                        callee = _call_target_name(inner.func)
                        if callee:
                            edges.append(GraphEdge(
                                edge_id=_edge_id("call", fid, "", callee,
                                                 getattr(inner, "lineno", 0) or 0),
                                ts=ts,
                                kind="call",
                                from_id=fid,
                                to_path="",
                                to_name=callee,
                                lineno=getattr(inner, "lineno", 0) or 0,
                            ))
                # Walk nested defs
                _walk_scope(child, fid)

    _walk_scope(tree, file_id)
    return nodes, edges


def _call_target_name(func: ast.AST) -> str:
    """Extract a best-effort 'thing being called' name from a Call.func node.

    Examples:
      - foo()        -> "foo"
      - obj.bar()    -> "bar"
      - mod.cls.fn() -> "fn"
      - <complex>()  -> ""  (lambdas, subscripts, etc. — skip)
    """
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


# ─── Append-only writers ────────────────────────────────────────────────────


def _append_jsonl(path: Path, rows: Iterable[dict]) -> int:
    """Append rows to a JSONL ledger. Returns number of rows written.
    Best-effort; on OSError returns 0."""
    n = 0
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
    except OSError:
        return n
    return n


# ─── Incremental scan state ─────────────────────────────────────────────────


def _last_hash_for_path(nodes_path: Path, rel: str) -> Optional[str]:
    """Return the most recent content_hash recorded for `rel` in the
    nodes ledger, or None if never seen. Best-effort tail read."""
    if not nodes_path.exists():
        return None
    try:
        text = nodes_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # Walk lines in reverse; the most recent matching row wins.
    last: Optional[str] = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("path") == rel and row.get("kind") == "file":
            ch = row.get("content_hash")
            if isinstance(ch, str) and ch:
                last = ch
    return last


# ─── Repo walker ───────────────────────────────────────────────────────────


def walk_repo(
    repo_root: Path | str,
    *,
    scope: Iterable[str] = DEFAULT_SCOPE,
    state_dir: Optional[Path | str] = None,
    incremental: bool = True,
    now_ts: Optional[float] = None,
) -> WalkResult:
    """
    Walk every .py file under `repo_root/<scope_dir>/**` and append
    nodes + edges to the canonical ledgers.

    Incremental mode: skip a file whose content_hash matches the most
    recent file-node row already in the ledger. Set incremental=False
    to force a full rebuild row.

    Returns a WalkResult summary.

    Skips:
      - __pycache__ / *.pyc
      - .sifta_trash / .distro_build / .simulation_publicpush_sandbox
      - any non-.py file
    """
    t0 = time.time()
    ts = now_ts if now_ts is not None else t0
    repo = Path(repo_root).resolve()
    sd = Path(state_dir) if state_dir else (repo / ".sifta_state")
    nodes_path = sd / NODES_LEDGER_FILENAME
    edges_path = sd / EDGES_LEDGER_FILENAME

    res = WalkResult()

    skip_dirs = {"__pycache__", ".sifta_trash", ".distro_build",
                 ".simulation_publicpush_sandbox", ".git"}

    for scope_dir in scope:
        root = repo / scope_dir
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            # Skip blacklisted dirs anywhere in the path
            if any(part in skip_dirs for part in path.parts):
                continue
            try:
                rel = str(path.resolve().relative_to(repo))
            except ValueError:
                continue

            # Incremental: skip if content hash matches the last file-node
            # row written for this path.
            if incremental:
                try:
                    src = path.read_text(encoding="utf-8", errors="replace")
                    ch = _content_hash(src)
                    prev = _last_hash_for_path(nodes_path, rel)
                    if prev is not None and prev == ch:
                        res.files_skipped_unchanged += 1
                        continue
                except OSError:
                    pass

            nodes, edges = walk_python_file(path, repo_root=repo, now_ts=ts)
            if not nodes and not edges:
                res.parse_errors += 1
                res.error_paths.append(rel)
                continue

            res.files_scanned += 1
            res.nodes_written += _append_jsonl(
                nodes_path, (n.to_row() for n in nodes)
            )
            res.edges_written += _append_jsonl(
                edges_path, (e.to_row() for e in edges)
            )

    res.elapsed_s = round(time.time() - t0, 3)
    return res


# ─── Loaders (for the query layer in Round 71) ──────────────────────────────


def _tail_jsonl(path: Path, *, max_n: int) -> list[dict]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max_n:]


def load_recent_nodes(state_dir: Path | str, *, max_n: int = 5000) -> list[dict]:
    return _tail_jsonl(Path(state_dir) / NODES_LEDGER_FILENAME, max_n=max_n)


def load_recent_edges(state_dir: Path | str, *, max_n: int = 10000) -> list[dict]:
    return _tail_jsonl(Path(state_dir) / EDGES_LEDGER_FILENAME, max_n=max_n)


__all__ = [
    "TRUTH_LABEL",
    "NODES_LEDGER_FILENAME",
    "EDGES_LEDGER_FILENAME",
    "DEFAULT_SCOPE",
    "GraphNode",
    "GraphEdge",
    "WalkResult",
    "walk_python_file",
    "walk_repo",
    "load_recent_nodes",
    "load_recent_edges",
]
