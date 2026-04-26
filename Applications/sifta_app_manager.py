#!/usr/bin/env python3
"""
sifta_app_manager.py — Alice Shell
═══════════════════════════════════════════════════
Alice's voice-and-text command interface for the Swarm OS.
Speak naturally or type. She understands. She talks back.
"""
from __future__ import annotations

import json
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor

from System.sifta_base_widget import SiftaBaseWidget

MANIFEST_PATH = _REPO / "Applications" / "apps_manifest.json"
DISABLED_PATH = _REPO / ".sifta_state" / "disabled_apps.json"


def _load_manifest() -> Dict:
    try:
        return json.loads(MANIFEST_PATH.read_text())
    except Exception:
        return {}


def _save_manifest(data: Dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(data, indent=2) + "\n")


def _load_disabled() -> Dict:
    try:
        return json.loads(DISABLED_PATH.read_text())
    except Exception:
        return {}


def _save_disabled(data: Dict) -> None:
    DISABLED_PATH.parent.mkdir(parents=True, exist_ok=True)
    DISABLED_PATH.write_text(json.dumps(data, indent=2) + "\n")


def _fuzzy_match(query: str, names: List[str]) -> Optional[str]:
    """Find the best-matching app name for a fuzzy query."""
    query_lower = query.lower().strip()
    # Exact substring first
    for name in names:
        if query_lower in name.lower():
            return name
    # Fuzzy ratio
    best, best_score = None, 0.0
    for name in names:
        score = SequenceMatcher(None, query_lower, name.lower()).ratio()
        if score > best_score:
            best, best_score = name, score
    return best if best_score > 0.35 else None


class AppManagerWidget(SiftaBaseWidget):
    """Conversational Install / Uninstall — speak to the OS."""

    APP_NAME = "Alice Shell"

    def build_ui(self, layout: QVBoxLayout) -> None:

        # App list panel
        self.app_list = QPlainTextEdit()
        self.app_list.setReadOnly(True)
        self.app_list.setMaximumHeight(280)
        layout.addWidget(self.app_list)

        # Conversation log
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

        # Input row
        inp_row = QHBoxLayout()
        prompt_lbl = QLabel("iSwarm >")
        prompt_lbl.setStyleSheet("color:rgb(0,255,200); font-size:13px; font-weight:bold;")
        inp_row.addWidget(prompt_lbl)

        self.input = QLineEdit()
        self.input.setPlaceholderText("type a command… (list, info <app>, uninstall <app>, install <app>, help)")
        self.input.returnPressed.connect(self._on_enter)
        inp_row.addWidget(self.input, 1)

        btn_send = QPushButton("Send")
        btn_send.clicked.connect(self._on_enter)
        inp_row.addWidget(btn_send)

        layout.addLayout(inp_row)

        self._refresh_list()
        self._say("Alice Shell online. Speak naturally or type a command — try: list, info <app>, install <app>, uninstall <app>.")

    # ── Commands ───────────────────────────────────────────────

    def _on_enter(self):
        raw = self.input.text().strip()
        self.input.clear()
        if not raw:
            return

        self._say(f"> {raw}", color="#b0b8d0")

        parts = raw.lower().split(None, 1)
        cmd = parts[0] if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("help", "?", "commands"):
            self._cmd_help()
        elif cmd in ("list", "ls", "apps", "all"):
            self._cmd_list(arg)
        elif cmd in ("info", "describe", "show"):
            self._cmd_info(arg)
        elif cmd in ("uninstall", "remove", "delete", "disable"):
            self._cmd_uninstall(arg)
        elif cmd in ("install", "enable", "restore", "reinstall"):
            self._cmd_install(arg)
        elif cmd in ("categories", "cats"):
            self._cmd_categories()
        elif cmd in ("count", "stats", "status"):
            self._cmd_stats()
        else:
            self._say("Unknown command. Type 'help' to see what I understand.")

    def _cmd_help(self):
        self._say(
            "Commands I understand:\n"
            "  list [category]     — show installed apps (optionally filter by category)\n"
            "  info <app>          — details about a specific app\n"
            "  uninstall <app>     — remove an app from the manifest\n"
            "  install <app>       — restore a previously uninstalled app\n"
            "  categories          — show all app categories\n"
            "  stats               — counts & overview\n"
            "  help                — this message\n"
            "\nYou can use natural names: 'uninstall warehouse', 'info territory', 'list simulations'"
        )

    def _cmd_list(self, category_filter: str = ""):
        manifest = _load_manifest()
        if not manifest:
            self._say("Manifest is empty or unreadable.")
            return

        if category_filter:
            filtered = {k: v for k, v in manifest.items()
                        if category_filter.lower() in v.get("category", "").lower()}
            if not filtered:
                self._say(f"No apps found in category matching '{category_filter}'.")
                return
            header = f"Apps in '{category_filter}':"
        else:
            filtered = manifest
            header = f"All installed apps ({len(filtered)}):"

        lines = [header]
        cats: Dict[str, List[str]] = {}
        for name, meta in sorted(filtered.items()):
            cat = meta.get("category", "Other")
            cats.setdefault(cat, []).append(name)
        for cat in sorted(cats):
            lines.append(f"\n  [{cat}]")
            for n in cats[cat]:
                lines.append(f"    • {n}")

        self._say("\n".join(lines))
        self._refresh_list()

    def _cmd_info(self, query: str):
        if not query:
            self._say("Usage: info <app name>")
            return
        manifest = _load_manifest()
        match = _fuzzy_match(query, list(manifest.keys()))
        if not match:
            disabled = _load_disabled()
            match_d = _fuzzy_match(query, list(disabled.keys()))
            if match_d:
                meta = disabled[match_d]
                self._say(
                    f"'{match_d}' [UNINSTALLED]\n"
                    f"  Category:    {meta.get('category', '?')}\n"
                    f"  Entry:       {meta.get('entry_point', '?')}\n"
                    f"  Widget:      {meta.get('widget_class', 'N/A')}\n"
                    f"  Type 'install {match_d.lower()}' to restore it."
                )
                return
            self._say(f"No app matching '{query}' found in manifest or uninstall archive.")
            return

        meta = manifest[match]
        entry = meta.get("entry_point", "?")
        exists = (_REPO / entry).exists() if entry != "?" else False
        self._say(
            f"'{match}'\n"
            f"  Category:    {meta.get('category', '?')}\n"
            f"  Entry:       {entry} {'[EXISTS]' if exists else '[MISSING]'}\n"
            f"  Widget:      {meta.get('widget_class', 'script-only')}\n"
            f"  Window:      {meta.get('window_width', '—')} × {meta.get('window_height', '—')}\n"
            f"  Signature:   {meta.get('signature', 'UNVERIFIED')}"
        )

    def _cmd_uninstall(self, query: str):
        if not query:
            self._say("Usage: uninstall <app name>\nExample: uninstall warehouse")
            return
        manifest = _load_manifest()
        match = _fuzzy_match(query, list(manifest.keys()))
        if not match:
            self._say(f"No installed app matching '{query}'.")
            return

        meta = manifest.pop(match)
        _save_manifest(manifest)

        disabled = _load_disabled()
        disabled[match] = meta
        _save_disabled(disabled)

        self._say(f"Uninstalled '{match}'.\nIt's archived — type 'install {match.lower()}' to bring it back.")
        self._refresh_list()

    def _cmd_install(self, query: str):
        if not query:
            self._say("Usage: install <app name>\nThis restores a previously uninstalled app.")
            return

        disabled = _load_disabled()
        match = _fuzzy_match(query, list(disabled.keys()))
        if match:
            meta = disabled.pop(match)
            _save_disabled(disabled)

            manifest = _load_manifest()
            manifest[match] = meta
            _save_manifest(manifest)

            self._say(f"Restored '{match}' to the manifest. It will appear in the Programs menu on next refresh.")
            self._refresh_list()
            return

        # Check if already installed
        manifest = _load_manifest()
        match2 = _fuzzy_match(query, list(manifest.keys()))
        if match2:
            self._say(f"'{match2}' is already installed.")
            return

        self._say(f"No uninstalled app matching '{query}'. Nothing to restore.")

    def _cmd_categories(self):
        manifest = _load_manifest()
        cats: Dict[str, int] = {}
        for meta in manifest.values():
            c = meta.get("category", "Other")
            cats[c] = cats.get(c, 0) + 1
        lines = ["Categories:"]
        for c in sorted(cats):
            lines.append(f"  {c}: {cats[c]} apps")
        self._say("\n".join(lines))

    def _cmd_stats(self):
        manifest = _load_manifest()
        disabled = _load_disabled()
        cats: Dict[str, int] = {}
        for meta in manifest.values():
            c = meta.get("category", "Other")
            cats[c] = cats.get(c, 0) + 1

        verified = sum(1 for m in manifest.values() if m.get("signature", "") != "UNVERIFIED")
        self._say(
            f"Installed: {len(manifest)} apps across {len(cats)} categories\n"
            f"Uninstalled (archived): {len(disabled)}\n"
            f"Verified signatures: {verified}/{len(manifest)}\n"
            f"Categories: {', '.join(sorted(cats))}"
        )

    # ── UI helpers ─────────────────────────────────────────────

    def _say(self, text: str, color: str = "#00ffc8"):
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log.setTextCursor(cursor)
        self.log.appendPlainText(text)

    def _refresh_list(self):
        manifest = _load_manifest()
        cats: Dict[str, List[str]] = {}
        for name, meta in sorted(manifest.items()):
            c = meta.get("category", "Other")
            cats.setdefault(c, []).append(name)

        lines = [f"╔══ Installed Apps ({len(manifest)}) ══╗"]
        for cat in sorted(cats):
            lines.append(f"\n  ▸ {cat}")
            for n in cats[cat]:
                lines.append(f"      {n}")
        lines.append(f"\n╚═════════════════════════════╝")
        self.app_list.setPlainText("\n".join(lines))


# ── Standalone ──────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AppManagerWidget()
    w.resize(800, 700)
    w.setWindowTitle("Alice Shell — SIFTA OS")
    w.show()
    sys.exit(app.exec())
