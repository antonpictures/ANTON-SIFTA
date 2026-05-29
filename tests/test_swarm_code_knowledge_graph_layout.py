"""Round 72 tests — code knowledge graph force-directed layout.

Verifies:
  - empty input yields empty layout (never raises)
  - layer assignment maps top-level dir buckets, falls back to "Other"
  - deterministic positions: same nodes + seed → same coordinates
  - different seeds produce different coordinates
  - layer anchors are placed on distinct points around the canvas
  - bounding box bounds the actual positions
  - edges actually pull endpoints (with-edge layout differs from no-edge)
  - layout_summary_block reports counts + empty state cleanly
  - compute_layout_from_state reads the Round 70 ledger shape
  - real .sifta_state ledgers are not mutated (pure read)
"""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_code_knowledge_graph as graph
from System import swarm_code_knowledge_graph_layout as layout


# ─── Fixture helpers ───────────────────────────────────────────────────────


def _nodes_basic() -> list[dict]:
    return [
        {
            "ts": 1.0, "node_id": "f_alpha", "kind": "file",
            "path": "System/alpha.py", "name": "",
            "lineno": 0, "lineno_end": 20, "parent_id": "",
            "docstring_head": "alpha", "complexity": 1,
            "mtime": 1.0, "content_hash": "h-a",
            "round": 70, "walker": "test",
        },
        {
            "ts": 1.0, "node_id": "fn_collect", "kind": "function",
            "path": "System/alpha.py", "name": "collect_signal",
            "lineno": 4, "lineno_end": 9, "parent_id": "f_alpha",
            "docstring_head": "collects", "complexity": 1,
            "mtime": 1.0, "content_hash": "h-a",
            "round": 70, "walker": "test",
        },
        {
            "ts": 1.0, "node_id": "f_beta", "kind": "file",
            "path": "Applications/beta.py", "name": "",
            "lineno": 0, "lineno_end": 30, "parent_id": "",
            "docstring_head": "beta", "complexity": 0,
            "mtime": 1.0, "content_hash": "h-b",
            "round": 70, "walker": "test",
        },
        {
            "ts": 1.0, "node_id": "fn_render", "kind": "function",
            "path": "Applications/beta.py", "name": "render_beta",
            "lineno": 10, "lineno_end": 15, "parent_id": "f_beta",
            "docstring_head": "render", "complexity": 3,
            "mtime": 1.0, "content_hash": "h-b",
            "round": 70, "walker": "test",
        },
        {
            "ts": 1.0, "node_id": "f_test", "kind": "file",
            "path": "tests/test_alpha.py", "name": "",
            "lineno": 0, "lineno_end": 25, "parent_id": "",
            "docstring_head": "alpha tests", "complexity": 0,
            "mtime": 1.0, "content_hash": "h-t",
            "round": 70, "walker": "test",
        },
    ]


def _edges_basic() -> list[dict]:
    return [
        {
            "ts": 1.0, "edge_id": "e_imp", "kind": "import",
            "from_id": "f_beta", "to_path": "System.alpha", "to_name": "",
            "lineno": 2, "round": 70, "walker": "test",
        },
        {
            "ts": 1.0, "edge_id": "e_call", "kind": "call",
            "from_id": "fn_render", "to_path": "", "to_name": "collect_signal",
            "lineno": 12, "round": 70, "walker": "test",
        },
    ]


# ─── Empty / degenerate ────────────────────────────────────────────────────


def test_empty_nodes_yields_empty_result():
    result = layout.compute_layout([], [])
    assert result.node_count == 0
    assert result.edge_count == 0
    assert result.positions == {}
    assert result.bounding_box == (0.0, 0.0, 0.0, 0.0)
    # Still returns palette so the viewer has something to bind to
    assert "System" in result.layer_colors


# ─── Layer bucketing ───────────────────────────────────────────────────────


def test_layer_of_buckets_top_level():
    assert layout.layer_of("System/foo.py") == "System"
    assert layout.layer_of("Applications/bar.py") == "Applications"
    assert layout.layer_of("tests/baz.py") == "tests"
    assert layout.layer_of("Utilities/qux.py") == "Utilities"
    assert layout.layer_of("Documents/IDE_BOOT_COVENANT.md") == "Documents"


def test_layer_of_unknown_falls_back_to_other():
    assert layout.layer_of("vendor/external.py") == "Other"
    assert layout.layer_of("") == "Other"


def test_layer_of_is_case_insensitive_fallback():
    # Allow 'system/' (lowercase) to still bucket into 'System'.
    assert layout.layer_of("system/foo.py") == "System"


# ─── Determinism ───────────────────────────────────────────────────────────


def test_layout_is_deterministic_for_same_seed():
    nodes = _nodes_basic()
    edges = _edges_basic()
    a = layout.compute_layout(nodes, edges, seed=70, iterations=40)
    b = layout.compute_layout(nodes, edges, seed=70, iterations=40)
    assert a.positions == b.positions
    assert a.layers == b.layers
    assert a.bounding_box == b.bounding_box


def test_different_seed_changes_initial_positions():
    nodes = _nodes_basic()
    a = layout.compute_layout(nodes, [], seed=70, iterations=0)
    b = layout.compute_layout(nodes, [], seed=4242, iterations=0)
    # At least one node must end up at a different starting point.
    diffs = [a.positions[n] != b.positions[n] for n in a.positions]
    assert any(diffs)


# ─── Node placement / layers ───────────────────────────────────────────────


def test_every_node_gets_a_position_and_layer():
    nodes = _nodes_basic()
    result = layout.compute_layout(nodes, _edges_basic(), iterations=20)
    for row in nodes:
        nid = row["node_id"]
        assert nid in result.positions
        assert nid in result.layers
    assert result.layers["f_alpha"] == "System"
    assert result.layers["f_beta"] == "Applications"
    assert result.layers["f_test"] == "tests"


def test_layer_anchors_are_distinct():
    nodes = _nodes_basic()
    result = layout.compute_layout(nodes, [], iterations=0)
    anchor_pts = list(result.layer_anchors.values())
    assert len(anchor_pts) == len(set(anchor_pts))


def test_layer_colors_include_palette_entries():
    nodes = _nodes_basic()
    result = layout.compute_layout(nodes, [], iterations=0)
    for layer_name, colour in result.layer_colors.items():
        assert colour.startswith("#")
        assert len(colour) == 7


# ─── Bounding box ──────────────────────────────────────────────────────────


def test_bounding_box_bounds_positions():
    nodes = _nodes_basic()
    result = layout.compute_layout(nodes, _edges_basic(), iterations=30)
    min_x, min_y, max_x, max_y = result.bounding_box
    for x, y in result.positions.values():
        assert min_x - 1e-6 <= x <= max_x + 1e-6
        assert min_y - 1e-6 <= y <= max_y + 1e-6


# ─── Edges actually move things ────────────────────────────────────────────


def test_edges_pull_connected_nodes_closer():
    nodes = _nodes_basic()
    iters = 80
    with_edges = layout.compute_layout(nodes, _edges_basic(), seed=70, iterations=iters)
    no_edges = layout.compute_layout(nodes, [], seed=70, iterations=iters)
    # Distance between f_beta (Applications) and f_alpha (System) should be
    # smaller WITH the import edge than without — the spring pulls them.
    def _d(layout_result, a, b):
        ax, ay = layout_result.positions[a]
        bx, by = layout_result.positions[b]
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    assert _d(with_edges, "f_beta", "f_alpha") < _d(no_edges, "f_beta", "f_alpha")


# ─── Summary block ────────────────────────────────────────────────────────


def test_summary_block_empty():
    result = layout.compute_layout([], [])
    assert "no nodes positioned" in layout.layout_summary_block(result)


def test_summary_block_reports_counts():
    nodes = _nodes_basic()
    result = layout.compute_layout(nodes, _edges_basic(), iterations=20)
    text = layout.layout_summary_block(result)
    assert "5 nodes" in text
    assert "2 edges" in text
    assert "System=2" in text or "System=2," in text


# ─── compute_layout_from_state ────────────────────────────────────────────


def _seed_ledger(state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = state_dir / graph.NODES_LEDGER_FILENAME
    edges_path = state_dir / graph.EDGES_LEDGER_FILENAME
    with nodes_path.open("a", encoding="utf-8") as f:
        for row in _nodes_basic():
            f.write(json.dumps(row, sort_keys=True) + "\n")
    with edges_path.open("a", encoding="utf-8") as f:
        for row in _edges_basic():
            f.write(json.dumps(row, sort_keys=True) + "\n")


def test_compute_layout_from_state(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_ledger(state)
    result = layout.compute_layout_from_state(state, iterations=20)
    assert result.node_count == 5
    assert result.edge_count >= 1


def test_latest_row_wins_collapse(tmp_path: Path):
    """Two rows with the same node_id collapse to the latest by ts."""
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    nodes_path = state / graph.NODES_LEDGER_FILENAME
    base = _nodes_basic()[0]
    older = dict(base, ts=1.0, path="System/alpha.py")
    newer = dict(base, ts=9.0, path="Applications/alpha.py")  # moved layer
    with nodes_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(older, sort_keys=True) + "\n")
        f.write(json.dumps(newer, sort_keys=True) + "\n")
    result = layout.compute_layout_from_state(state, iterations=0)
    assert result.layers["f_alpha"] == "Applications"


# ─── Real ledger isolation ─────────────────────────────────────────────────


def test_real_ledgers_untouched(tmp_path: Path):
    """Pure read module — must not mutate any real .sifta_state file."""
    real = Path(".sifta_state")
    watched = [
        real / graph.NODES_LEDGER_FILENAME,
        real / graph.EDGES_LEDGER_FILENAME,
        real / "work_receipts.jsonl",
        real / "ide_stigmergic_trace.jsonl",
        real / "alice_conversation.jsonl",
    ]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watched}

    # Exercise the public surface with a tmp state dir.
    state = tmp_path / ".sifta_state"
    _seed_ledger(state)
    _ = layout.compute_layout(_nodes_basic(), _edges_basic(), iterations=10)
    _ = layout.compute_layout_from_state(state, iterations=10)
    _ = layout.layout_summary_block(
        layout.compute_layout(_nodes_basic(), [], iterations=0)
    )

    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watched}
    for k in before:
        assert before[k] == after[k], f"layout module mutated {k}"
