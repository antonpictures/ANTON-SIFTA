#!/usr/bin/env python3
"""Qt viewer for Alice's code knowledge graph.

Round 74 (2026-05-27). This app renders the existing code graph ledgers:

- System.swarm_code_knowledge_graph writes node/edge receipts.
- System.swarm_code_knowledge_graph_query summarizes the body profile.
- System.swarm_code_knowledge_graph_layout computes deterministic positions.

The viewer does not invent graph math. It consumes the layout organ and draws
the positions into a QGraphicsScene.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Mapping

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from System import swarm_code_knowledge_graph as graph
from System import swarm_code_knowledge_graph_layout as layout_engine
from System import swarm_code_knowledge_graph_query as graph_query
from System.sifta_base_widget import SiftaBaseWidget

try:
    from System.swarm_app_focus import publish_focus
except Exception:  # pragma: no cover - optional focus bus
    def publish_focus(*_args, **_kwargs) -> None:
        return None


APP_NAME = "Code Knowledge Graph"
DEFAULT_STATE_DIR = _REPO / ".sifta_state"
VIEWER_MAX_NODES = 450
VIEWER_MAX_EDGES = 1500
VIEWER_SOURCE_NODE_LIMIT = 60000


def _norm(value: object) -> str:
    return str(value or "").strip()


def _case(value: object) -> str:
    return _norm(value).casefold()


def _node_label(row: Mapping[str, object], *, limit: int = 42) -> str:
    name = _norm(row.get("name"))
    path = _norm(row.get("path"))
    if name:
        text = name
    else:
        text = Path(path).name or path
    if len(text) > limit:
        return text[: max(1, limit - 1)] + "..."
    return text


def _latest_nodes_by_id(rows: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in rows:
        node_id = _norm(row.get("node_id"))
        if not node_id:
            continue
        prior = latest.get(node_id)
        if prior is None or float(row.get("ts") or 0.0) >= float(prior.get("ts") or 0.0):
            latest[node_id] = dict(row)
    return latest


def _sample_nodes_for_view(rows: list[dict], *, max_nodes: int = VIEWER_MAX_NODES) -> list[dict]:
    """Return a balanced layer sample so the viewer shows the whole body."""
    latest = _latest_nodes_by_id(rows)
    if len(latest) <= max_nodes:
        return list(latest.values())

    groups: dict[str, list[dict]] = {}
    for row in latest.values():
        layer = layout_engine.layer_of(_norm(row.get("path")))
        groups.setdefault(layer, []).append(row)
    for group in groups.values():
        group.sort(
            key=lambda row: (
                _case(row.get("path")),
                int(row.get("lineno") or 0),
                _case(row.get("name")),
            )
        )

    sampled: list[dict] = []
    layer_names = sorted(groups)
    cursor = 0
    while len(sampled) < max_nodes and any(groups.values()):
        layer = layer_names[cursor % len(layer_names)]
        if groups[layer]:
            sampled.append(groups[layer].pop(0))
        cursor += 1
    return sampled


def _path_to_module(path: str) -> str:
    text = _norm(path).replace("\\", "/")
    if text.endswith(".py"):
        text = text[:-3]
    if text.endswith("/__init__"):
        text = text[: -len("/__init__")]
    return text.replace("/", ".").casefold()


class CodeGraphView(QGraphicsView):
    """Canvas with stable antialiasing and wheel zoom."""

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(QColor(7, 9, 18)))

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class CodeKnowledgeGraphWidget(SiftaBaseWidget):
    """MDI app that renders Alice's code graph ledgers."""

    APP_NAME = APP_NAME
    APP_LOCAL_CHAT_DISABLED = True

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        state_dir: Path | str = DEFAULT_STATE_DIR,
        auto_refresh: bool = True,
    ) -> None:
        self._state_dir = Path(state_dir)
        self._auto_refresh = auto_refresh
        self._nodes_by_id: dict[str, dict] = {}
        self._raw_edges: list[dict] = []
        self._layout_result: layout_engine.LayoutResult | None = None
        self._node_items: dict[str, QGraphicsEllipseItem] = {}
        super().__init__(parent)
        publish_focus(self.APP_NAME, "Viewing Alice code knowledge graph")

    def build_ui(self, root: QVBoxLayout) -> None:
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Find node, path, docstring")
        self.search.textChanged.connect(self._render_scene)
        controls.addWidget(QLabel("Search"))
        controls.addWidget(self.search, 2)

        self.layer_filter = QComboBox()
        self.layer_filter.addItem("All layers")
        self.layer_filter.currentIndexChanged.connect(self._render_scene)
        controls.addWidget(QLabel("Layer"))
        controls.addWidget(self.layer_filter, 0)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_graph)
        controls.addWidget(refresh)

        fit = QPushButton("Fit")
        fit.clicked.connect(self.fit_graph)
        controls.addWidget(fit)
        root.addLayout(controls)

        self.summary = QLabel("Loading graph ledgers...")
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary.setStyleSheet(
            "QLabel { color: rgb(190, 205, 230); background: rgb(12, 15, 28); "
            "border: 1px solid rgb(34, 42, 64); border-radius: 4px; padding: 6px; }"
        )
        root.addWidget(self.summary)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.scene = QGraphicsScene(self)
        self.view = CodeGraphView(self.scene)
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter.addWidget(self.view)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(6, 0, 0, 0)
        side_layout.setSpacing(6)
        self.profile = QTextBrowser()
        self.profile.setOpenExternalLinks(False)
        self.profile.setStyleSheet(
            "QTextBrowser { background: rgb(10, 12, 22); color: rgb(220, 226, 242); "
            "border: 1px solid rgb(34, 42, 64); border-radius: 4px; padding: 8px; "
            "font-family: Menlo; font-size: 11px; }"
        )
        side_layout.addWidget(self.profile, 1)

        self.details = QTextBrowser()
        self.details.setStyleSheet(
            "QTextBrowser { background: rgb(8, 10, 18); color: rgb(210, 220, 238); "
            "border: 1px solid rgb(34, 42, 64); border-radius: 4px; padding: 8px; "
            "font-family: Menlo; font-size: 11px; }"
        )
        side_layout.addWidget(self.details, 1)
        splitter.addWidget(side)
        splitter.setSizes([900, 330])
        root.addWidget(splitter, 1)

        self.scene.selectionChanged.connect(self._on_selection_changed)
        self.refresh_graph()
        if self._auto_refresh:
            self.make_timer(15000, self.refresh_graph)

    def refresh_graph(self) -> None:
        """Reload ledgers, recompute layout positions, and redraw."""
        source_rows = graph.load_recent_nodes(self._state_dir, max_n=VIEWER_SOURCE_NODE_LIMIT)
        rows = _sample_nodes_for_view(source_rows, max_nodes=VIEWER_MAX_NODES)
        edges = graph.load_recent_edges(self._state_dir, max_n=VIEWER_MAX_EDGES)
        self._nodes_by_id = _latest_nodes_by_id(rows)
        self._raw_edges = list(edges)
        iterations = 25 if len(self._nodes_by_id) > 250 else 55
        self._layout_result = layout_engine.compute_layout(
            rows,
            edges,
            width=1700.0,
            height=1100.0,
            iterations=iterations,
            seed=74,
        )
        self._refresh_layer_filter()
        self.profile.setPlainText(graph_query.code_persona_prompt_block(state_dir=self._state_dir))
        self.summary.setText(layout_engine.layout_summary_block(self._layout_result))
        self._render_scene()
        QTimer.singleShot(0, self.fit_graph)

    def _refresh_layer_filter(self) -> None:
        current = self.layer_filter.currentText()
        layers = sorted(set((self._layout_result.layers if self._layout_result else {}).values()))
        self.layer_filter.blockSignals(True)
        self.layer_filter.clear()
        self.layer_filter.addItem("All layers")
        for layer_name in layers:
            self.layer_filter.addItem(layer_name)
        index = self.layer_filter.findText(current)
        self.layer_filter.setCurrentIndex(index if index >= 0 else 0)
        self.layer_filter.blockSignals(False)

    def _resolve_edge_pairs(self) -> list[tuple[str, str, str]]:
        positions = (self._layout_result.positions if self._layout_result else {})
        name_to_id: dict[str, str] = {}
        path_to_id: dict[str, str] = {}
        for node_id, row in self._nodes_by_id.items():
            name = _case(row.get("name"))
            path = _case(row.get("path"))
            if name:
                name_to_id.setdefault(name, node_id)
            if path and not _norm(row.get("name")):
                path_to_id.setdefault(path, node_id)
                path_to_id.setdefault(_path_to_module(path), node_id)

        pairs: list[tuple[str, str, str]] = []
        for edge in self._raw_edges:
            src = _norm(edge.get("from_id"))
            if src not in positions:
                continue
            dst = _norm(edge.get("to_id"))
            if dst and dst in positions:
                pairs.append((src, dst, _norm(edge.get("kind"))))
                continue
            name = _case(edge.get("to_name"))
            if name and name in name_to_id:
                pairs.append((src, name_to_id[name], _norm(edge.get("kind"))))
                continue
            path = _case(edge.get("to_path"))
            if path and path in path_to_id:
                pairs.append((src, path_to_id[path], _norm(edge.get("kind"))))
        return pairs

    def _visible_node_ids(self) -> set[str]:
        if not self._layout_result:
            return set()
        layer_filter = self.layer_filter.currentText()
        needle = _case(self.search.text())
        visible: set[str] = set()
        for node_id, row in self._nodes_by_id.items():
            if node_id not in self._layout_result.positions:
                continue
            layer = self._layout_result.layers.get(node_id, "Other")
            if layer_filter and layer_filter != "All layers" and layer != layer_filter:
                continue
            haystack = " ".join(
                [
                    _case(row.get("path")),
                    _case(row.get("name")),
                    _case(row.get("docstring_head")),
                    _case(row.get("kind")),
                ]
            )
            if needle and needle not in haystack:
                continue
            visible.add(node_id)
        return visible

    def _render_scene(self) -> None:
        self.scene.clear()
        self._node_items = {}
        result = self._layout_result
        if result is None or result.node_count == 0:
            text = self.scene.addText("No code graph rows yet. Run the walker to populate code_graph_nodes/edges.", QFont("Menlo", 14))
            text.setDefaultTextColor(QColor(180, 190, 210))
            self.scene.setSceneRect(QRectF(0, 0, 900, 540))
            return

        visible = self._visible_node_ids()
        if not visible:
            text = self.scene.addText("No nodes match the current filter.", QFont("Menlo", 14))
            text.setDefaultTextColor(QColor(180, 190, 210))
            self.scene.setSceneRect(QRectF(0, 0, 900, 540))
            return

        edge_pen = QPen(QColor(115, 128, 156, 95), 1.0)
        call_pen = QPen(QColor(125, 211, 252, 110), 1.2)
        define_pen = QPen(QColor(148, 163, 184, 80), 0.8)
        for src, dst, kind in self._resolve_edge_pairs():
            if src not in visible or dst not in visible:
                continue
            sx, sy = result.positions[src]
            dx, dy = result.positions[dst]
            item = QGraphicsLineItem(float(sx), float(sy), float(dx), float(dy))
            item.setPen(call_pen if kind == "call" else define_pen if kind == "defines" else edge_pen)
            item.setZValue(0)
            self.scene.addItem(item)

        for node_id in sorted(visible):
            row = self._nodes_by_id.get(node_id, {})
            x, y = result.positions[node_id]
            kind = _norm(row.get("kind"))
            layer = result.layers.get(node_id, "Other")
            color = QColor(result.layer_colors.get(layer, "#d4d4d8"))
            radius = 8.0 if kind == "file" else 7.0 if kind == "class" else 5.5
            if kind == "file":
                radius += 2.0
            item = QGraphicsEllipseItem(float(x - radius), float(y - radius), radius * 2, radius * 2)
            item.setBrush(QBrush(color))
            item.setPen(QPen(QColor(8, 12, 20), 1.2))
            item.setZValue(5)
            item.setData(0, node_id)
            item.setToolTip(f"{kind or 'node'} {row.get('path', '')}:{row.get('name', '')}")
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.scene.addItem(item)
            self._node_items[node_id] = item

            if kind in {"file", "class"} or radius >= 7.5:
                label = QGraphicsTextItem(_node_label(row))
                label.setDefaultTextColor(QColor(218, 226, 242))
                label.setFont(QFont("Menlo", 8))
                label.setPos(float(x + radius + 3.0), float(y - 9.0))
                label.setZValue(6)
                self.scene.addItem(label)

        min_x, min_y, max_x, max_y = result.bounding_box
        self.scene.setSceneRect(QRectF(float(min_x - 80), float(min_y - 80), float(max_x - min_x + 160), float(max_y - min_y + 160)))
        self.details.setPlainText(f"{len(visible)} visible nodes. Select a node for receipt-backed metadata.")

    def _on_selection_changed(self) -> None:
        selected = self.scene.selectedItems()
        if not selected:
            return
        node_id = _norm(selected[0].data(0))
        row = self._nodes_by_id.get(node_id)
        if not row:
            return
        lines = [
            f"node_id: {node_id}",
            f"kind: {_norm(row.get('kind'))}",
            f"path: {_norm(row.get('path'))}",
            f"name: {_norm(row.get('name')) or '(file)'}",
            f"line: {int(row.get('lineno') or 0)}-{int(row.get('lineno_end') or 0)}",
            f"complexity: {int(row.get('complexity') or 0)}",
            f"parent_id: {_norm(row.get('parent_id')) or '(root)'}",
            f"content_hash: {_norm(row.get('content_hash'))}",
            f"docstring: {_norm(row.get('docstring_head')) or '(none)'}",
        ]
        self.details.setPlainText("\n".join(lines))

    def fit_graph(self) -> None:
        rect = self.scene.itemsBoundingRect()
        if rect.isNull():
            return
        self.view.fitInView(rect.adjusted(-30, -30, 30, 30), Qt.AspectRatioMode.KeepAspectRatio)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = CodeKnowledgeGraphWidget()
    win.resize(1240, 820)
    win.show()
    sys.exit(app.exec())
