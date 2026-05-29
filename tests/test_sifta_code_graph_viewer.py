from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover - PyQt availability differs by runner
    QApplication = None

from System import swarm_code_knowledge_graph as graph


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


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
                "docstring_head": "Alpha organ.",
                "complexity": 1,
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
                "docstring_head": "Collects owner signal.",
                "complexity": 2,
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
                "docstring_head": "Beta app.",
                "complexity": 0,
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
        ],
    )


@pytest.fixture(scope="module")
def qapp():
    if QApplication is None:
        pytest.skip("PyQt6 unavailable")
    app = QApplication.instance() or QApplication([])
    yield app


def test_manifest_registers_code_graph_viewer() -> None:
    manifest = json.loads(Path("Applications/apps_manifest.json").read_text(encoding="utf-8"))

    entry = manifest["Code Knowledge Graph"]

    assert entry["entry_point"] == "Applications/sifta_code_graph_viewer.py"
    assert entry["widget_class"] == "CodeKnowledgeGraphWidget"
    assert entry["category"] == "Developer"


def test_viewer_renders_seeded_graph(qapp, tmp_path: Path) -> None:
    from Applications.sifta_code_graph_viewer import CodeKnowledgeGraphWidget

    state = tmp_path / ".sifta_state"
    _seed_graph(state)
    widget = CodeKnowledgeGraphWidget(state_dir=state, auto_refresh=False)

    assert widget._layout_result is not None
    assert widget._layout_result.node_count == 3
    assert widget._layout_result.edge_count == 1
    assert "3 nodes" in widget.summary.text()
    assert widget.scene.items()
    assert widget.layer_filter.findText("System") >= 0
    assert widget.layer_filter.findText("Applications") >= 0


def test_viewer_search_filters_visible_nodes(qapp, tmp_path: Path) -> None:
    from Applications.sifta_code_graph_viewer import CodeKnowledgeGraphWidget

    state = tmp_path / ".sifta_state"
    _seed_graph(state)
    widget = CodeKnowledgeGraphWidget(state_dir=state, auto_refresh=False)

    widget.search.setText("collect_signal")
    visible = widget._visible_node_ids()

    assert visible == {"fn_collect"}


def test_viewer_sampling_balances_layers(qapp) -> None:
    from Applications.sifta_code_graph_viewer import _sample_nodes_for_view

    rows = []
    for i in range(20):
        rows.append(
            {
                "ts": float(i),
                "node_id": f"sys_{i}",
                "kind": "file",
                "path": f"System/sys_{i}.py",
                "name": "",
                "lineno": 0,
            }
        )
    for i in range(20):
        rows.append(
            {
                "ts": float(i),
                "node_id": f"app_{i}",
                "kind": "file",
                "path": f"Applications/app_{i}.py",
                "name": "",
                "lineno": 0,
            }
        )

    sample = _sample_nodes_for_view(rows, max_nodes=10)

    paths = [row["path"] for row in sample]
    assert any(path.startswith("System/") for path in paths)
    assert any(path.startswith("Applications/") for path in paths)
    assert len(sample) == 10


def test_viewer_empty_state_is_stable(qapp, tmp_path: Path) -> None:
    from Applications.sifta_code_graph_viewer import CodeKnowledgeGraphWidget

    widget = CodeKnowledgeGraphWidget(state_dir=tmp_path / ".sifta_state", auto_refresh=False)

    assert widget._layout_result is not None
    assert widget._layout_result.node_count == 0
    assert "no nodes positioned" in widget.summary.text()
    assert widget.scene.items()
