#!/usr/bin/env python3
"""
sifta_file_manager_widget.py — Norton-style dual-pane file manager for iSwarm OS
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from PyQt6.QtCore import QDir, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFileSystemModel
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class PaneWidget(QFrame):
    def __init__(self, label: str, root_path: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("pane")
        self.model = QFileSystemModel(self)
        self.model.setRootPath(root_path)
        self.model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel(label)
        title.setStyleSheet("font-weight: 700; color: #7aa2f7;")
        layout.addWidget(title)

        self.path_edit = QLineEdit(root_path)
        self.path_edit.returnPressed.connect(self.navigate_to_path)
        layout.addWidget(self.path_edit)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(root_path))
        self.tree.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.doubleClicked.connect(self._on_tree_double)
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        layout.addWidget(self.tree, 1)

        self.list = QListView()
        self.list.setModel(self.model)
        self.list.setRootIndex(self.model.index(root_path))
        self.list.setViewMode(QListView.ViewMode.ListMode)
        self.list.doubleClicked.connect(self._on_list_double)
        layout.addWidget(self.list, 1)

    def current_index(self):
        idx = self.tree.currentIndex()
        if idx.isValid():
            return idx
        idx = self.list.currentIndex()
        if idx.isValid():
            return idx
        return self.model.index(self.path_edit.text())

    def current_path(self) -> str:
        idx = self.current_index()
        if idx.isValid():
            return self.model.filePath(idx)
        return self.path_edit.text()

    def current_dir(self) -> str:
        p = Path(self.current_path())
        if p.is_dir():
            return str(p)
        return str(p.parent)

    def set_dir(self, path: str) -> None:
        idx = self.model.index(path)
        if not idx.isValid():
            return
        self.tree.setRootIndex(idx)
        self.list.setRootIndex(idx)
        self.path_edit.setText(path)

    def navigate_to_path(self) -> None:
        p = self.path_edit.text().strip()
        if os.path.isdir(p):
            self.set_dir(p)
        else:
            QMessageBox.warning(self, "Invalid path", f"Not a directory:\n{p}")

    def _on_tree_double(self, idx) -> None:
        path = self.model.filePath(idx)
        if os.path.isdir(path):
            self.set_dir(path)

    def _on_list_double(self, idx) -> None:
        path = self.model.filePath(idx)
        if os.path.isdir(path):
            self.set_dir(path)


class FileNavigatorWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(
            """
            QWidget { background: #0f111a; color: #c0caf5; }
            QFrame#pane { background: #1a1b26; border: 1px solid #2b3044; border-radius: 10px; }
            QLineEdit { background: #10131f; border: 1px solid #3b4261; border-radius: 6px; padding: 5px; color: #c0caf5; }
            QPushButton {
                background: #7aa2f7; color: #11111b; border: none; border-radius: 7px;
                padding: 6px 10px; font-weight: 700;
            }
            QPushButton:hover { background: #8db5ff; }
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        hdr = QLabel("SIFTA File Navigator — dual-pane commander")
        hdr.setStyleSheet("font-size: 18px; font-weight: 800; color: #bb9af7;")
        root.addWidget(hdr)

        root_path = str(REPO_ROOT)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.left = PaneWidget("LEFT", root_path)
        self.right = PaneWidget("RIGHT", root_path)
        splitter.addWidget(self.left)
        splitter.addWidget(self.right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        ops = QHBoxLayout()
        ops.setSpacing(8)
        self.btn_copy = QPushButton("Copy →")
        self.btn_move = QPushButton("Move →")
        self.btn_rename = QPushButton("Rename")
        self.btn_delete = QPushButton("Delete")
        self.btn_mkdir = QPushButton("New Folder")
        self.btn_refresh = QPushButton("Refresh")
        self.btn_open = QPushButton("Open File")
        self.btn_swap = QPushButton("Swap Panes")
        for b in (
            self.btn_copy,
            self.btn_move,
            self.btn_rename,
            self.btn_delete,
            self.btn_mkdir,
            self.btn_refresh,
            self.btn_open,
            self.btn_swap,
        ):
            ops.addWidget(b)
        ops.addStretch()
        root.addLayout(ops)

        self.status = QLabel("Ready.")
        self.status.setStyleSheet("font-family: monospace; color: #9ece6a;")
        root.addWidget(self.status)

        self.btn_copy.clicked.connect(self.copy_left_to_right)
        self.btn_move.clicked.connect(self.move_left_to_right)
        self.btn_rename.clicked.connect(self.rename_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_mkdir.clicked.connect(self.new_folder)
        self.btn_refresh.clicked.connect(self.refresh_views)
        self.btn_open.clicked.connect(self.open_file)
        self.btn_swap.clicked.connect(self.swap_dirs)

    def _selected_src(self) -> Path:
        return Path(self.left.current_path())

    def _dst_dir(self) -> Path:
        return Path(self.right.current_dir())

    def _set_status(self, text: str, ok: bool = True) -> None:
        self.status.setText(text)
        self.status.setStyleSheet(
            f"font-family: monospace; color: {'#9ece6a' if ok else '#f7768e'};"
        )

    def refresh_views(self) -> None:
        self.left.model.setRootPath(self.left.current_dir())
        self.right.model.setRootPath(self.right.current_dir())
        self.left.set_dir(self.left.current_dir())
        self.right.set_dir(self.right.current_dir())
        self._set_status("Refreshed.")

    def copy_left_to_right(self) -> None:
        src = self._selected_src()
        dst_dir = self._dst_dir()
        try:
            if not src.exists():
                raise FileNotFoundError(src)
            dst = dst_dir / src.name
            if src.is_dir():
                if dst.exists():
                    raise FileExistsError(f"Target exists: {dst}")
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            self.refresh_views()
            self._set_status(f"Copied: {src.name} → {dst_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Copy failed", str(e))
            self._set_status(f"Copy failed: {e}", ok=False)

    def move_left_to_right(self) -> None:
        src = self._selected_src()
        dst_dir = self._dst_dir()
        try:
            if not src.exists():
                raise FileNotFoundError(src)
            dst = dst_dir / src.name
            shutil.move(str(src), str(dst))
            self.refresh_views()
            self._set_status(f"Moved: {src.name} → {dst_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Move failed", str(e))
            self._set_status(f"Move failed: {e}", ok=False)

    def rename_selected(self) -> None:
        src = self._selected_src()
        if not src.exists():
            self._set_status("Nothing selected.", ok=False)
            return
        new_name, _ = QFileDialog.getSaveFileName(
            self, "Rename to...", str(src.parent / src.name)
        )
        if not new_name:
            return
        try:
            src.rename(Path(new_name))
            self.refresh_views()
            self._set_status(f"Renamed: {src.name}")
        except Exception as e:
            QMessageBox.critical(self, "Rename failed", str(e))
            self._set_status(f"Rename failed: {e}", ok=False)

    def delete_selected(self) -> None:
        src = self._selected_src()
        if not src.exists():
            self._set_status("Nothing selected.", ok=False)
            return
        ans = QMessageBox.question(
            self,
            "Confirm delete",
            f"Delete '{src.name}'?\nThis action cannot be undone.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            if src.is_dir():
                shutil.rmtree(src)
            else:
                src.unlink()
            self.refresh_views()
            self._set_status(f"Deleted: {src.name}")
        except Exception as e:
            QMessageBox.critical(self, "Delete failed", str(e))
            self._set_status(f"Delete failed: {e}", ok=False)

    def new_folder(self) -> None:
        base = Path(self.left.current_dir())
        name = "New Folder"
        path = base / name
        i = 2
        while path.exists():
            path = base / f"{name} {i}"
            i += 1
        try:
            path.mkdir(parents=False, exist_ok=False)
            self.refresh_views()
            self._set_status(f"Created: {path.name}")
        except Exception as e:
            QMessageBox.critical(self, "Create folder failed", str(e))
            self._set_status(f"Create failed: {e}", ok=False)

    def open_file(self) -> None:
        src = self._selected_src()
        if src.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(src)))
            self._set_status(f"Opened: {src.name}")
            return
        self._set_status("Select a file to open.", ok=False)

    def swap_dirs(self) -> None:
        l = self.left.current_dir()
        r = self.right.current_dir()
        self.left.set_dir(r)
        self.right.set_dir(l)
        self._set_status("Swapped pane directories.")

