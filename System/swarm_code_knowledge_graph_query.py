"""Query API for Alice's code knowledge graph ledgers.

Round 72 (2026-05-27). Pure stdlib read layer over
``System.swarm_code_knowledge_graph``. The walker writes append-only node and
edge rows; this organ lets Alice ask grounded questions against those receipts:
which definitions match a phrase, who depends on a symbol/module, and what a
git diff may affect.

No Qt. No ledger mutation. Never raises out of the public API.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, Mapping

from System import swarm_code_knowledge_graph as graph


DEFAULT_STATE_DIR = ".sifta_state"


def _norm(value: object) -> str:
    return str(value or "").strip()


def _case(value: object) -> str:
    return _norm(value).casefold()


def _path_to_module(path: str) -> str:
    text = _norm(path).replace("\\", "/")
    if text.endswith(".py"):
        text = text[:-3]
    if text.endswith("/__init__"):
        text = text[: -len("/__init__")]
    return text.replace("/", ".")


def _latest_nodes_by_id(rows: Iterable[Mapping[str, object]]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in rows:
        node_id = _norm(row.get("node_id"))
        if not node_id:
            continue
        prior = latest.get(node_id)
        if prior is None or float(row.get("ts") or 0.0) >= float(prior.get("ts") or 0.0):
            latest[node_id] = dict(row)
    return latest


def _node_label(row: Mapping[str, object]) -> str:
    name = _norm(row.get("name"))
    path = _norm(row.get("path"))
    if name:
        return f"{path}:{name}"
    return path


def find_by_substring(
    query: str,
    *,
    state_dir: Path | str = DEFAULT_STATE_DIR,
    kinds: Iterable[str] | None = None,
    limit: int = 50,
    max_nodes: int = 5000,
) -> list[dict]:
    """Return latest graph nodes whose path/name/docstring contains ``query``.

    Rows are decorated with ``score``, ``match_fields``, and ``label``. Empty
    query returns an empty list.
    """
    needle = _case(query)
    if not needle:
        return []
    allowed = {_case(k) for k in kinds or () if _case(k)}
    nodes = _latest_nodes_by_id(graph.load_recent_nodes(state_dir, max_n=max_nodes))
    hits: list[dict] = []
    for row in nodes.values():
        kind = _case(row.get("kind"))
        if allowed and kind not in allowed:
            continue
        fields = {
            "name": _case(row.get("name")),
            "path": _case(row.get("path")),
            "docstring_head": _case(row.get("docstring_head")),
        }
        match_fields = tuple(name for name, value in fields.items() if needle in value)
        if not match_fields:
            continue
        score = 0
        if fields["name"] == needle:
            score += 100
        if "name" in match_fields:
            score += 40
        if "path" in match_fields:
            score += 20
        if "docstring_head" in match_fields:
            score += 10
        decorated = dict(row)
        decorated["score"] = score
        decorated["match_fields"] = match_fields
        decorated["label"] = _node_label(row)
        hits.append(decorated)
    hits.sort(
        key=lambda row: (
            -int(row.get("score") or 0),
            _case(row.get("path")),
            int(row.get("lineno") or 0),
            _case(row.get("name")),
        )
    )
    return hits[: max(0, int(limit))]


def find_dependents_of(
    target: str,
    *,
    state_dir: Path | str = DEFAULT_STATE_DIR,
    limit: int = 100,
    max_nodes: int = 5000,
    max_edges: int = 10000,
) -> dict:
    """Find graph nodes with import/call edges pointing at ``target``.

    ``target`` may be a module path (``System.foo``), file path
    (``System/foo.py``), or symbol/function name.
    """
    raw_target = _norm(target)
    if not raw_target:
        return {"target": target, "dependents": [], "edges": [], "count": 0}
    target_cf = raw_target.casefold()
    target_module_cf = _path_to_module(raw_target).casefold()
    target_name_cf = Path(raw_target).stem.casefold() if "/" in raw_target else target_cf

    nodes = _latest_nodes_by_id(graph.load_recent_nodes(state_dir, max_n=max_nodes))
    edges = graph.load_recent_edges(state_dir, max_n=max_edges)
    matched_edges: list[dict] = []
    dependents: dict[str, dict] = {}
    for edge in edges:
        kind = _case(edge.get("kind"))
        to_path = _case(edge.get("to_path"))
        to_name = _case(edge.get("to_name"))
        edge_matches = False
        if kind == "import":
            edge_matches = (
                to_path == target_cf
                or to_path == target_module_cf
                or f"{to_path}.{to_name}".strip(".") == target_module_cf
                or (to_name and to_name == target_name_cf)
            )
        elif kind == "call":
            edge_matches = to_name == target_name_cf or to_name == target_cf
        else:
            edge_matches = to_path == target_cf or to_name == target_name_cf
        if not edge_matches:
            continue
        matched = dict(edge)
        from_id = _norm(edge.get("from_id"))
        from_node = nodes.get(from_id, {})
        matched["from_node"] = {
            "node_id": from_id,
            "kind": from_node.get("kind", ""),
            "path": from_node.get("path", ""),
            "name": from_node.get("name", ""),
            "lineno": from_node.get("lineno", 0),
            "label": _node_label(from_node) if from_node else from_id,
        }
        matched_edges.append(matched)
        if from_id and from_node:
            dependent = dict(from_node)
            dependent["label"] = _node_label(from_node)
            dependents[from_id] = dependent

    ordered_edges = sorted(
        matched_edges,
        key=lambda row: (
            _case(row.get("from_node", {}).get("path") if isinstance(row.get("from_node"), dict) else ""),
            int(row.get("lineno") or 0),
            _case(row.get("kind")),
        ),
    )[: max(0, int(limit))]
    ordered_dependents = sorted(
        dependents.values(),
        key=lambda row: (_case(row.get("path")), int(row.get("lineno") or 0), _case(row.get("name"))),
    )[: max(0, int(limit))]
    return {
        "target": raw_target,
        "dependents": ordered_dependents,
        "edges": ordered_edges,
        "count": len(ordered_dependents),
        "edge_count": len(ordered_edges),
    }


def changed_paths_from_git(
    git_sha: str,
    *,
    repo_root: Path | str = ".",
) -> list[str]:
    """Return changed file paths from git. Best-effort, never raises."""
    repo = Path(repo_root)
    sha = _norm(git_sha)
    if not sha:
        return []
    if sha.casefold() in {"worktree", "working_tree", "working-tree", "unstaged"}:
        cmd = ["git", "diff", "--name-only"]
    elif sha.casefold() in {"staged", "index"}:
        cmd = ["git", "diff", "--cached", "--name-only"]
    else:
        cmd = ["git", "diff", "--name-only", f"{sha}..HEAD"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    out: list[str] = []
    for line in proc.stdout.splitlines():
        path = line.strip()
        if path and path not in out:
            out.append(path)
    return out


def find_impact_of_diff(
    git_sha: str,
    *,
    repo_root: Path | str = ".",
    state_dir: Path | str = DEFAULT_STATE_DIR,
    max_nodes: int = 5000,
    max_edges: int = 10000,
    limit_per_file: int = 50,
) -> dict:
    """Estimate impacted graph nodes/dependents for files changed since git_sha."""
    changed = changed_paths_from_git(git_sha, repo_root=repo_root)
    nodes = _latest_nodes_by_id(graph.load_recent_nodes(state_dir, max_n=max_nodes))
    by_path: dict[str, list[dict]] = {}
    for row in nodes.values():
        path = _norm(row.get("path"))
        if path:
            by_path.setdefault(path, []).append(dict(row))

    impacted_files: list[dict] = []
    for path in changed:
        local_nodes = sorted(
            by_path.get(path, []),
            key=lambda row: (int(row.get("lineno") or 0), _case(row.get("kind")), _case(row.get("name"))),
        )
        module_name = _path_to_module(path)
        dependents = find_dependents_of(
            module_name,
            state_dir=state_dir,
            limit=limit_per_file,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )
        impacted_files.append(
            {
                "path": path,
                "module": module_name,
                "node_count": len(local_nodes),
                "nodes": local_nodes[: max(0, int(limit_per_file))],
                "dependents": dependents["dependents"],
                "dependent_count": dependents["count"],
            }
        )
    return {
        "git_sha": _norm(git_sha),
        "changed_paths": changed,
        "changed_count": len(changed),
        "files": impacted_files,
    }


def code_persona_summary(
    *,
    state_dir: Path | str = DEFAULT_STATE_DIR,
    max_nodes: int = 5000,
    max_edges: int = 10000,
    top_n: int = 8,
) -> dict:
    """Summarize Alice's code-body shape from graph ledgers.

    "Persona" here is not role-play. It is a receipt-backed structural profile:
    which organ layers exist, how many files/classes/functions they contain,
    which functions are most complex, and which nodes sit at the highest graph
    degree. Pure read-only.
    """
    nodes = _latest_nodes_by_id(graph.load_recent_nodes(state_dir, max_n=max_nodes))
    edges = graph.load_recent_edges(state_dir, max_n=max_edges)

    kind_counts: dict[str, int] = {}
    layer_counts: dict[str, int] = {}
    path_counts: dict[str, int] = {}
    for row in nodes.values():
        kind = _norm(row.get("kind")) or "unknown"
        path = _norm(row.get("path"))
        layer = path.split("/", 1)[0] if path else "Other"
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
        if path:
            path_counts[path] = path_counts.get(path, 0) + 1

    out_degree: dict[str, int] = {}
    in_degree: dict[str, int] = {}
    import_targets: dict[str, int] = {}
    call_targets: dict[str, int] = {}
    node_name_index: dict[str, str] = {}
    module_index: dict[str, str] = {}
    for node_id, row in nodes.items():
        name = _case(row.get("name"))
        path = _case(row.get("path"))
        if name:
            node_name_index.setdefault(name, node_id)
        if path and not _norm(row.get("name")):
            module_index.setdefault(_path_to_module(path), node_id)

    for edge in edges:
        from_id = _norm(edge.get("from_id"))
        kind = _case(edge.get("kind"))
        to_path = _case(edge.get("to_path"))
        to_name = _case(edge.get("to_name"))
        if from_id:
            out_degree[from_id] = out_degree.get(from_id, 0) + 1
        resolved_to = ""
        if kind == "call" and to_name:
            resolved_to = node_name_index.get(to_name, "")
            call_targets[to_name] = call_targets.get(to_name, 0) + 1
        elif kind == "import":
            target = f"{to_path}.{to_name}".strip(".") if to_name else to_path
            if target:
                import_targets[target] = import_targets.get(target, 0) + 1
            resolved_to = module_index.get(to_path, "")
        if resolved_to:
            in_degree[resolved_to] = in_degree.get(resolved_to, 0) + 1

    def _decorated_node(row: Mapping[str, object], **extra: object) -> dict:
        data = {
            "node_id": _norm(row.get("node_id")),
            "kind": _norm(row.get("kind")),
            "path": _norm(row.get("path")),
            "name": _norm(row.get("name")),
            "lineno": int(row.get("lineno") or 0),
            "label": _node_label(row),
        }
        data.update(extra)
        return data

    complex_functions: list[dict] = []
    for row in nodes.values():
        if _case(row.get("kind")) != "function":
            continue
        complexity = int(row.get("complexity") or 0)
        complex_functions.append(_decorated_node(row, complexity=complexity))
    complex_functions.sort(
        key=lambda row: (-int(row.get("complexity") or 0), _case(row.get("path")), int(row.get("lineno") or 0))
    )

    central_nodes: list[dict] = []
    for node_id, row in nodes.items():
        degree = out_degree.get(node_id, 0) + in_degree.get(node_id, 0)
        if degree <= 0:
            continue
        central_nodes.append(
            _decorated_node(
                row,
                degree=degree,
                out_degree=out_degree.get(node_id, 0),
                in_degree=in_degree.get(node_id, 0),
            )
        )
    central_nodes.sort(
        key=lambda row: (-int(row.get("degree") or 0), _case(row.get("path")), int(row.get("lineno") or 0))
    )

    top_layers = sorted(layer_counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    top_paths = sorted(path_counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    top_imports = sorted(import_targets.items(), key=lambda item: (-item[1], item[0]))
    top_calls = sorted(call_targets.items(), key=lambda item: (-item[1], item[0]))
    file_count = kind_counts.get("file", 0)
    function_count = kind_counts.get("function", 0)
    class_count = kind_counts.get("class", 0)
    dominant_layer = top_layers[0][0] if top_layers else ""
    identity_sentence = (
        f"Graph shows {file_count} files, {class_count} classes, "
        f"{function_count} functions, {len(edges)} edges"
        + (f"; densest layer is {dominant_layer}." if dominant_layer else ".")
    )

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "kind_counts": kind_counts,
        "layer_counts": layer_counts,
        "top_layers": [{"layer": k, "count": v} for k, v in top_layers[: max(0, int(top_n))]],
        "top_paths": [{"path": k, "count": v} for k, v in top_paths[: max(0, int(top_n))]],
        "most_complex_functions": complex_functions[: max(0, int(top_n))],
        "most_connected_nodes": central_nodes[: max(0, int(top_n))],
        "top_import_targets": [{"target": k, "count": v} for k, v in top_imports[: max(0, int(top_n))]],
        "top_call_targets": [{"target": k, "count": v} for k, v in top_calls[: max(0, int(top_n))]],
        "identity_sentence": identity_sentence,
    }


def code_persona_prompt_block(
    *,
    state_dir: Path | str = DEFAULT_STATE_DIR,
    max_nodes: int = 5000,
    max_edges: int = 10000,
    top_n: int = 5,
) -> str:
    """Prompt-ready graph-body summary for Alice's cortex."""
    summary = code_persona_summary(
        state_dir=state_dir,
        max_nodes=max_nodes,
        max_edges=max_edges,
        top_n=top_n,
    )
    if summary["node_count"] == 0:
        return "CODE BODY PROFILE: no code graph ledger rows are available yet."
    layers = ", ".join(
        f"{row['layer']}={row['count']}" for row in summary["top_layers"]
    )
    complex_bits = ", ".join(
        f"{row['label']} complexity={row['complexity']}"
        for row in summary["most_complex_functions"][:top_n]
    )
    connected_bits = ", ".join(
        f"{row['label']} degree={row['degree']}"
        for row in summary["most_connected_nodes"][:top_n]
    )
    parts = [
        "CODE BODY PROFILE (receipt-backed, not role-play):",
        f"- {summary['identity_sentence']}",
    ]
    if layers:
        parts.append(f"- Layers: {layers}.")
    if complex_bits:
        parts.append(f"- High-complexity functions: {complex_bits}.")
    if connected_bits:
        parts.append(f"- Highly connected nodes: {connected_bits}.")
    return "\n".join(parts)


def graph_query_prompt_block(
    *,
    state_dir: Path | str = DEFAULT_STATE_DIR,
    max_nodes: int = 5000,
    max_edges: int = 10000,
) -> str:
    """Small prompt block telling Alice what graph evidence is available."""
    node_count = len(graph.load_recent_nodes(state_dir, max_n=max_nodes))
    edge_count = len(graph.load_recent_edges(state_dir, max_n=max_edges))
    if node_count == 0 and edge_count == 0:
        return "CODE KNOWLEDGE GRAPH: no recent graph ledger rows are available yet."
    return (
        "CODE KNOWLEDGE GRAPH: receipt-backed code graph rows are available. "
        f"Recent sample: nodes={node_count}, edges={edge_count}. "
        "Use System.swarm_code_knowledge_graph_query for substring, dependent, "
        "and git-diff impact questions instead of guessing from memory."
    )


__all__ = [
    "DEFAULT_STATE_DIR",
    "find_by_substring",
    "find_dependents_of",
    "changed_paths_from_git",
    "find_impact_of_diff",
    "code_persona_summary",
    "code_persona_prompt_block",
    "graph_query_prompt_block",
]
