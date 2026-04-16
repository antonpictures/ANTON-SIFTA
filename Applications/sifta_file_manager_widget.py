#!/usr/bin/env python3
"""
sifta_file_manager_widget.py — Dual-Pane Finder for iSwarm OS
══════════════════════════════════════════════════════════════
Steve Jobs dual-pane file navigator. Clean. Functional. Beautiful.
Sort by click. Navigate by double-click. Breadcrumb path bar.
Copy, Move, Rename, Delete, New Folder, Preview, Open in System.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QDir, QModelIndex, QSize, Qt, QUrl, QTimer
from PyQt6.QtGui import QDesktopServices, QFileSystemModel, QFont, QIcon, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ── File size formatting ─────────────────────────────────────────────────────

def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


# ── Single Pane ──────────────────────────────────────────────────────────────

class FinderPane(QFrame):
    """One side of the dual-pane navigator. Behaves like macOS Finder list view."""

    def __init__(self, label: str, start_path: str, parent=None):
        super().__init__(parent)
        self.setObjectName("finderPane")
        self._history: list[str] = [start_path]
        self._history_idx = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Navigation Bar ───────────────────────────────────────────
        nav_bar = QFrame()
        nav_bar.setFixedHeight(38)
        nav_bar.setStyleSheet(
            "QFrame { background: #1a1b26; border-bottom: 1px solid #24283b; }"
        )
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(6, 0, 6, 0)
        nav_layout.setSpacing(4)

        nav_btn_style = (
            "QPushButton { background: transparent; color: #7aa2f7; border: none;"
            " font-size: 14px; padding: 4px 8px; border-radius: 4px; }"
            "QPushButton:hover { background: #24283b; }"
            "QPushButton:disabled { color: #414868; }"
        )

        self.btn_back = QPushButton("◀")
        self.btn_back.setFixedSize(28, 28)
        self.btn_back.setStyleSheet(nav_btn_style)
        self.btn_back.setToolTip("Back")
        self.btn_back.clicked.connect(self._go_back)
        nav_layout.addWidget(self.btn_back)

        self.btn_forward = QPushButton("▶")
        self.btn_forward.setFixedSize(28, 28)
        self.btn_forward.setStyleSheet(nav_btn_style)
        self.btn_forward.setToolTip("Forward")
        self.btn_forward.clicked.connect(self._go_forward)
        nav_layout.addWidget(self.btn_forward)

        self.btn_up = QPushButton("▲")
        self.btn_up.setFixedSize(28, 28)
        self.btn_up.setStyleSheet(nav_btn_style)
        self.btn_up.setToolTip("Parent directory")
        self.btn_up.clicked.connect(self._go_up)
        nav_layout.addWidget(self.btn_up)

        self.path_edit = QLineEdit(start_path)
        self.path_edit.setStyleSheet(
            "QLineEdit {"
            "  background: #12131e; border: 1px solid #2b3044; border-radius: 5px;"
            "  padding: 3px 8px; color: #a9b1d6; font-size: 11px;"
            "  selection-background-color: #1e3a5f;"
            "}"
            "QLineEdit:focus { border-color: #7aa2f7; }"
        )
        self.path_edit.returnPressed.connect(self._navigate_to_typed_path)
        nav_layout.addWidget(self.path_edit, 1)

        layout.addWidget(nav_bar)

        # ── File System Model ────────────────────────────────────────
        self.model = QFileSystemModel(self)
        self.model.setRootPath(start_path)
        self.model.setFilter(
            QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.Hidden
        )

        # ── Tree View (Finder-style list) ────────────────────────────
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(start_path))
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(0)  # Flat list, no tree indentation
        self.tree.setRootIsDecorated(False)
        self.tree.setAnimated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setItemsExpandable(False)

        # Show Name, Size, Type, Date Modified
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        self.tree.setStyleSheet(
            "QTreeView {"
            "  background: #0d0e17; border: none; color: #c0caf5;"
            "  font-size: 12px; font-family: 'SF Pro Display', Inter, sans-serif;"
            "}"
            "QTreeView::item { padding: 3px 4px; border: none; }"
            "QTreeView::item:selected {"
            "  background: #1e3a5f; color: #ffffff;"
            "}"
            "QTreeView::item:hover {"
            "  background: #1a1e30;"
            "}"
            "QTreeView::item:alternate { background: #10121c; }"
            "QHeaderView::section {"
            "  background: #15161e; color: #565f89; border: none;"
            "  border-right: 1px solid #1f2335; border-bottom: 1px solid #1f2335;"
            "  padding: 5px 8px; font-size: 10px; font-weight: bold;"
            "  text-transform: uppercase;"
            "}"
        )

        self.tree.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tree, 1)

        # ── Info Bar ─────────────────────────────────────────────────
        self.info_bar = QLabel(f"  {label}")
        self.info_bar.setFixedHeight(24)
        self.info_bar.setStyleSheet(
            "QLabel { background: #15161e; color: #565f89; font-size: 10px;"
            " border-top: 1px solid #1f2335; padding-left: 8px; }"
        )
        layout.addWidget(self.info_bar)

        self._update_nav_buttons()

    # ── Navigation ───────────────────────────────────────────────────

    def current_dir(self) -> str:
        return self._history[self._history_idx]

    def selected_paths(self) -> list[Path]:
        """Return all selected file/dir paths."""
        indexes = self.tree.selectionModel().selectedRows()
        return [Path(self.model.filePath(idx)) for idx in indexes if idx.isValid()]

    def selected_path(self) -> Path | None:
        paths = self.selected_paths()
        return paths[0] if paths else None

    def navigate_to(self, path: str) -> None:
        if not os.path.isdir(path):
            return
        # Trim forward history
        self._history = self._history[: self._history_idx + 1]
        self._history.append(path)
        self._history_idx = len(self._history) - 1
        self._apply_dir(path)

    def _apply_dir(self, path: str) -> None:
        idx = self.model.index(path)
        self.tree.setRootIndex(idx)
        self.path_edit.setText(path)
        self._update_nav_buttons()
        self._update_info()

    def _go_back(self):
        if self._history_idx > 0:
            self._history_idx -= 1
            self._apply_dir(self._history[self._history_idx])

    def _go_forward(self):
        if self._history_idx < len(self._history) - 1:
            self._history_idx += 1
            self._apply_dir(self._history[self._history_idx])

    def _go_up(self):
        parent = str(Path(self.current_dir()).parent)
        if parent != self.current_dir():
            self.navigate_to(parent)

    def _navigate_to_typed_path(self):
        p = self.path_edit.text().strip()
        if os.path.isdir(p):
            self.navigate_to(p)
        elif os.path.isfile(p):
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        else:
            self.info_bar.setText("  ⚠ Invalid path")

    def _on_double_click(self, idx: QModelIndex):
        path = self.model.filePath(idx)
        if os.path.isdir(path):
            self.navigate_to(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _update_nav_buttons(self):
        self.btn_back.setEnabled(self._history_idx > 0)
        self.btn_forward.setEnabled(self._history_idx < len(self._history) - 1)

    def _update_info(self):
        try:
            items = list(Path(self.current_dir()).iterdir())
            dirs = sum(1 for i in items if i.is_dir())
            files = sum(1 for i in items if i.is_file())
            self.info_bar.setText(f"  {dirs} folders, {files} files")
        except PermissionError:
            self.info_bar.setText("  ⚠ Permission denied")
        except Exception:
            self.info_bar.setText("  —")


# ── Main Navigator Widget ───────────────────────────────────────────────────

class FileNavigatorWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet("QWidget { background: #0d0e17; color: #c0caf5; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title Bar ────────────────────────────────────────────────
        title_bar = QFrame()
        title_bar.setFixedHeight(42)
        title_bar.setStyleSheet(
            "QFrame { background: #15161e; border-bottom: 1px solid #1f2335; }"
        )
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 0, 12, 0)

        title_lbl = QLabel("📁 SIFTA File Navigator")
        title_lbl.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #bb9af7;")
        title_layout.addWidget(title_lbl)

        title_layout.addStretch()

        # Quick-nav buttons
        qnav_style = (
            "QPushButton { background: #1a1b26; color: #7aa2f7; border: 1px solid #24283b;"
            " border-radius: 5px; padding: 4px 10px; font-size: 10px; font-weight: bold; }"
            "QPushButton:hover { background: #24283b; border-color: #7aa2f7; }"
        )
        btn_home = QPushButton("🏠 Home")
        btn_home.setStyleSheet(qnav_style)
        btn_home.clicked.connect(lambda: self.left.navigate_to(str(HOME)))
        title_layout.addWidget(btn_home)

        btn_repo = QPushButton("⚙ SIFTA")
        btn_repo.setStyleSheet(qnav_style)
        btn_repo.clicked.connect(lambda: self.left.navigate_to(str(REPO_ROOT)))
        title_layout.addWidget(btn_repo)

        btn_apps = QPushButton("📦 Apps")
        btn_apps.setStyleSheet(qnav_style)
        btn_apps.clicked.connect(
            lambda: self.left.navigate_to(str(REPO_ROOT / "Applications"))
        )
        title_layout.addWidget(btn_apps)

        btn_docs = QPushButton("📝 Docs")
        btn_docs.setStyleSheet(qnav_style)
        btn_docs.clicked.connect(
            lambda: self.left.navigate_to(str(REPO_ROOT / ".sifta_documents"))
        )
        title_layout.addWidget(btn_docs)

        root.addWidget(title_bar)

        # ── Dual Panes ───────────────────────────────────────────────
        self._pane_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._pane_splitter.setStyleSheet(
            "QSplitter::handle { background: #1f2335; width: 2px; }"
        )

        self.left = FinderPane("Left", str(REPO_ROOT))
        self.right = FinderPane("Right", str(HOME))
        self._pane_splitter.addWidget(self.left)
        self._pane_splitter.addWidget(self.right)
        self._pane_splitter.setStretchFactor(0, 1)
        self._pane_splitter.setStretchFactor(1, 1)
        root.addWidget(self._pane_splitter, 1)
        QTimer.singleShot(0, self._balance_pane_splitter)

        # ── Action Bar ───────────────────────────────────────────────
        action_bar = QFrame()
        action_bar.setFixedHeight(44)
        action_bar.setStyleSheet(
            "QFrame { background: #15161e; border-top: 1px solid #1f2335; }"
        )
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(10, 0, 10, 0)
        action_layout.setSpacing(6)

        btn_style = (
            "QPushButton {"
            "  background: #1a1b26; color: #c0caf5; border: 1px solid #2b3044;"
            "  border-radius: 6px; padding: 5px 14px; font-size: 11px; font-weight: bold;"
            "}"
            "QPushButton:hover { background: #24283b; border-color: #7aa2f7; color: #7aa2f7; }"
        )
        btn_danger = (
            "QPushButton {"
            "  background: #1a1b26; color: #f7768e; border: 1px solid #2b3044;"
            "  border-radius: 6px; padding: 5px 14px; font-size: 11px; font-weight: bold;"
            "}"
            "QPushButton:hover { background: #2d1520; border-color: #f7768e; }"
        )

        actions = [
            ("📋 Copy →", btn_style, self._copy),
            ("✂ Move →", btn_style, self._move),
            ("✏️ Rename", btn_style, self._rename),
            ("📁 New Folder", btn_style, self._new_folder),
            ("🔍 Open", btn_style, self._open_file),
            ("🔄 Swap", btn_style, self._swap),
            ("🗑 Delete", btn_danger, self._delete),
        ]

        for label, style, handler in actions:
            btn = QPushButton(label)
            btn.setStyleSheet(style)
            btn.clicked.connect(handler)
            action_layout.addWidget(btn)

        action_layout.addStretch()

        # Status
        self.status = QLabel("Ready")
        self.status.setStyleSheet("color: #565f89; font-size: 10px;")
        action_layout.addWidget(self.status)

        root.addWidget(action_bar)

    def _balance_pane_splitter(self) -> None:
        from System.splitter_utils import balance_horizontal_splitter

        balance_horizontal_splitter(
            self._pane_splitter,
            self,
            left_ratio=0.5,
            min_right=260,
            min_left=260,
        )

    # ── Operations ───────────────────────────────────────────────────

    def _set_status(self, text: str, ok: bool = True):
        color = "#9ece6a" if ok else "#f7768e"
        self.status.setStyleSheet(f"color: {color}; font-size: 10px;")
        self.status.setText(text)

    def _copy(self):
        sources = self.left.selected_paths()
        if not sources:
            self._set_status("Select files to copy", False)
            return
        dst_dir = Path(self.right.current_dir())
        copied = 0
        for src in sources:
            try:
                dst = dst_dir / src.name
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                copied += 1
            except Exception as e:
                self._set_status(f"Copy error: {e}", False)
                return
        self._set_status(f"Copied {copied} item(s) → {dst_dir.name}")

    def _move(self):
        sources = self.left.selected_paths()
        if not sources:
            self._set_status("Select files to move", False)
            return
        dst_dir = Path(self.right.current_dir())
        moved = 0
        for src in sources:
            try:
                shutil.move(str(src), str(dst_dir / src.name))
                moved += 1
            except Exception as e:
                self._set_status(f"Move error: {e}", False)
                return
        self._set_status(f"Moved {moved} item(s) → {dst_dir.name}")

    def _rename(self):
        sel = self.left.selected_path()
        if not sel or not sel.exists():
            self._set_status("Select a file to rename", False)
            return
        new_name, ok = QInputDialog.getText(
            self, "Rename", f"New name for '{sel.name}':", text=sel.name
        )
        if ok and new_name and new_name != sel.name:
            try:
                sel.rename(sel.parent / new_name)
                self._set_status(f"Renamed → {new_name}")
            except Exception as e:
                self._set_status(f"Rename error: {e}", False)

    def _delete(self):
        sources = self.left.selected_paths()
        if not sources:
            self._set_status("Select files to delete", False)
            return
        names = ", ".join(s.name for s in sources[:5])
        if len(sources) > 5:
            names += f" (+{len(sources) - 5} more)"
        ans = QMessageBox.question(
            self, "Confirm Delete",
            f"Permanently delete {len(sources)} item(s)?\n{names}",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        deleted = 0
        for src in sources:
            try:
                if src.is_dir():
                    shutil.rmtree(src)
                else:
                    src.unlink()
                deleted += 1
            except Exception as e:
                self._set_status(f"Delete error: {e}", False)
                return
        self._set_status(f"Deleted {deleted} item(s)")

    def _new_folder(self):
        base = Path(self.left.current_dir())
        name, ok = QInputDialog.getText(
            self, "New Folder", "Folder name:", text="New Folder"
        )
        if ok and name:
            path = base / name
            try:
                path.mkdir(parents=False, exist_ok=False)
                self._set_status(f"Created: {name}")
            except Exception as e:
                self._set_status(f"Create error: {e}", False)

    def _open_file(self):
        sel = self.left.selected_path()
        if sel and sel.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(sel)))
            self._set_status(f"Opened: {sel.name}")
        elif sel and sel.is_dir():
            self.left.navigate_to(str(sel))
        else:
            self._set_status("Select a file to open", False)

    def _swap(self):
        l = self.left.current_dir()
        r = self.right.current_dir()
        self.left.navigate_to(r)
        self.right.navigate_to(l)
        self._set_status("Panes swapped")
