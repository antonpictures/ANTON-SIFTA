from __future__ import annotations

import json
import subprocess
from pathlib import Path

from System import swarm_code_knowledge_graph as graph
from System import swarm_code_knowledge_graph_query as query


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _seed_graph(state_dir: Path) -> None:
    _append_jsonl(
        state_dir / graph.NODES_LEDGER_FILENAME,
        [
            {
                "ts": 1.0,
                "node_id": "file_a",
                "kind": "file",
                "path": "System/alpha.py",
                "name": "",
                "lineno": 0,
                "lineno_end": 20,
                "parent_id": "",
                "docstring_head": "Alpha module for sensing.",
                "complexity": 2,
                "mtime": 1.0,
                "content_hash": "hash-a",
                "round": 70,
                "walker": "test",
            },
            {
                "ts": 1.0,
                "node_id": "fn_collect",
                "kind": "function",
                "path": "System/alpha.py",
                "name": "collect_signal",
                "lineno": 4,
                "lineno_end": 9,
                "parent_id": "file_a",
                "docstring_head": "Collects owner sensor signal.",
                "complexity": 1,
                "mtime": 1.0,
                "content_hash": "hash-a",
                "round": 70,
                "walker": "test",
            },
            {
                "ts": 1.0,
                "node_id": "file_b",
                "kind": "file",
                "path": "Applications/beta.py",
                "name": "",
                "lineno": 0,
                "lineno_end": 30,
                "parent_id": "",
                "docstring_head": "Beta app imports alpha.",
                "complexity": 0,
                "mtime": 1.0,
                "content_hash": "hash-b",
                "round": 70,
                "walker": "test",
            },
            {
                "ts": 1.0,
                "node_id": "fn_render",
                "kind": "function",
                "path": "Applications/beta.py",
                "name": "render_beta",
                "lineno": 10,
                "lineno_end": 15,
                "parent_id": "file_b",
                "docstring_head": "Render the beta surface.",
                "complexity": 3,
                "mtime": 1.0,
                "content_hash": "hash-b",
                "round": 70,
                "walker": "test",
            },
        ],
    )
    _append_jsonl(
        state_dir / graph.EDGES_LEDGER_FILENAME,
        [
            {
                "ts": 1.0,
                "edge_id": "import_alpha",
                "kind": "import",
                "from_id": "file_b",
                "to_path": "System.alpha",
                "to_name": "",
                "lineno": 2,
                "round": 70,
                "walker": "test",
            },
            {
                "ts": 1.0,
                "edge_id": "call_collect",
                "kind": "call",
                "from_id": "fn_render",
                "to_path": "",
                "to_name": "collect_signal",
                "lineno": 12,
                "round": 70,
                "walker": "test",
            },
        ],
    )


def test_find_by_substring_searches_name_path_and_docstring(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _seed_graph(state)

    hits = query.find_by_substring("signal", state_dir=state)

    labels = [hit["label"] for hit in hits]
    assert "System/alpha.py:collect_signal" in labels
    assert hits[0]["score"] >= hits[-1]["score"]
    assert "match_fields" in hits[0]


def test_find_by_substring_kind_filter(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _seed_graph(state)

    hits = query.find_by_substring("alpha", state_dir=state, kinds=("file",))

    assert hits
    assert {hit["kind"] for hit in hits} == {"file"}


def test_find_dependents_of_module_path(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _seed_graph(state)

    result = query.find_dependents_of("System/alpha.py", state_dir=state)

    assert result["count"] == 1
    assert result["dependents"][0]["path"] == "Applications/beta.py"
    assert result["edges"][0]["kind"] == "import"


def test_find_dependents_of_called_function(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _seed_graph(state)

    result = query.find_dependents_of("collect_signal", state_dir=state)

    assert result["count"] == 1
    assert result["dependents"][0]["name"] == "render_beta"
    assert result["edges"][0]["kind"] == "call"


def test_graph_query_prompt_block_reports_empty_state(tmp_path: Path) -> None:
    block = query.graph_query_prompt_block(state_dir=tmp_path / ".sifta_state")

    assert "no recent graph ledger rows" in block


def test_graph_query_prompt_block_reports_counts(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _seed_graph(state)

    block = query.graph_query_prompt_block(state_dir=state)

    assert "nodes=4" in block
    assert "edges=2" in block


def test_code_persona_summary_reports_body_shape(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _seed_graph(state)

    summary = query.code_persona_summary(state_dir=state)

    assert summary["node_count"] == 4
    assert summary["edge_count"] == 2
    assert summary["kind_counts"]["file"] == 2
    assert summary["kind_counts"]["function"] == 2
    assert {"layer": "Applications", "count": 2} in summary["top_layers"]
    assert {"layer": "System", "count": 2} in summary["top_layers"]
    assert summary["most_complex_functions"][0]["name"] == "render_beta"
    assert summary["most_complex_functions"][0]["complexity"] == 3
    assert any(
        row["name"] == "render_beta" and row["degree"] >= 1
        for row in summary["most_connected_nodes"]
    )
    assert any(
        row["target"] == "collect_signal" and row["count"] == 1
        for row in summary["top_call_targets"]
    )
    assert "Graph shows 2 files" in summary["identity_sentence"]


def test_code_persona_prompt_block_reports_receipt_backed_profile(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _seed_graph(state)

    block = query.code_persona_prompt_block(state_dir=state)

    assert "CODE BODY PROFILE" in block
    assert "receipt-backed" in block
    assert "Graph shows 2 files" in block
    assert "Layers:" in block
    assert "High-complexity functions:" in block


def test_code_persona_prompt_block_reports_empty_state(tmp_path: Path) -> None:
    block = query.code_persona_prompt_block(state_dir=tmp_path / ".sifta_state")

    assert "no code graph ledger rows" in block


def test_changed_paths_from_git_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "SIFTA Test"], cwd=repo, check=True)
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")

    changed = query.changed_paths_from_git("WORKTREE", repo_root=repo)

    assert changed == ["a.py"]


def test_find_impact_of_diff_maps_changed_file_to_nodes_and_dependents(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _seed_graph(state)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "SIFTA Test"], cwd=repo, check=True)
    (repo / "System").mkdir()
    (repo / "System" / "alpha.py").write_text("def collect_signal(): pass\n", encoding="utf-8")
    subprocess.run(["git", "add", "System/alpha.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "System" / "alpha.py").write_text("def collect_signal(): return 2\n", encoding="utf-8")

    impact = query.find_impact_of_diff("WORKTREE", repo_root=repo, state_dir=state)

    assert impact["changed_paths"] == ["System/alpha.py"]
    assert impact["files"][0]["node_count"] == 2
    assert impact["files"][0]["dependent_count"] == 1
    assert impact["files"][0]["dependents"][0]["path"] == "Applications/beta.py"


def test_query_api_does_not_touch_real_ledgers(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _seed_graph(state)
    real_state = Path(".sifta_state")
    watched = [
        real_state / graph.NODES_LEDGER_FILENAME,
        real_state / graph.EDGES_LEDGER_FILENAME,
        real_state / "work_receipts.jsonl",
    ]
    before = {str(path): path.stat().st_size if path.exists() else 0 for path in watched}

    query.find_by_substring("signal", state_dir=state)
    query.find_dependents_of("collect_signal", state_dir=state)
    query.graph_query_prompt_block(state_dir=state)
    query.code_persona_prompt_block(state_dir=state)

    after = {str(path): path.stat().st_size if path.exists() else 0 for path in watched}
    assert after == before
