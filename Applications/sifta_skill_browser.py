#!/usr/bin/env python3
"""
Applications/sifta_skill_browser.py
=====================================
SIFTA Skill Browser — Three-Tier Skill Explorer (PyQt6 Edition)

Shows the full SIFTA swimmer skill index with:
  - Tier 1 index (name, trigger, affect lanes, STGM)
  - Tier 2 procedure viewer (Markdown rendered in-app)
  - Affect bias display (live Panksepp circuit weights)
  - Community skills (agentskills.io compatible SKILL.md folders)
  - Submit link to agentskills.io hub
  - Real-time DPO dataset stats

Usage: embedded in SIFTA OS desktop
"""

import sys
import os
import json
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QTextBrowser, QSplitter, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

HELP_TEXT = """
SIFTA SKILL BROWSER — Help
═══════════════════════════════════════════════════════════

WHAT IS THIS?
  The Skill Browser shows all swimmer skills registered in SIFTA OS.
  Skills follow the IBM / agentskills.io three-tier architecture:

    Tier 1 — Index: name + trigger condition (cheap, always loaded)
    Tier 2 — Procedure: full step-by-step in skills/*.md files
    Tier 3 — Resources: scripts, assets (on-demand, review required)

HOW TO USE:
  • Click any skill in the list to see its full procedure (Tier 2)
  • [Affect Bias] tab — live Panksepp circuit weights → action selection
  • [DPO Stats] tab — RLHS dataset growth (auto-collected from gags)
  • [Run Tests] — runs test_sifta_superset.py (19/19 should pass)
  • [Submit to Hub] — opens agentskills.io submission page

SKILL COLUMNS:
  Status  — OPERATIONAL / NEW / FILE_BACKED
  Swimmer — which nanobot type owns this skill
  Action  — what motor action it selects (forage/repair/code/learn…)
  STGM    — tokens minted per verified execution (PoUW economy)
  Affects — Panksepp circuits that boost this skill's weight

COMMUNITY SKILLS:
  Skills in skills/<name>/SKILL.md are community-compatible.
  The ide_boot_covenant is SIFTA's Tier 0 meta-skill.
  Submit your own skills at: https://agentskills.io

SIFTA IS A SUPERSET OF OPENAI SWARM:
  OpenAI Swarm: stateless, no body, no memory, no economy.
  SIFTA adds:
    ✅ Cryptographic stigmergic memory (585 rows, hash-chained)
    ✅ Physical body (camera, mic, GPS, BLE)
    ✅ STGM/PoUW economy (3,637 tokens minted)
    ✅ 8 Panksepp affect circuits → motor policy
    ✅ RLHF gag immunity + DPO auto-collection
    ✅ LoRA self-training on own conversations

Node: GTH4921YP3 | github.com/antonpictures/ANTON-SIFTA
"""

SUBMIT_URL = "https://agentskills.io"
GITHUB_URL = "https://github.com/antonpictures/ANTON-SIFTA"

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class SkillBrowserApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SIFTA Skill Browser — Three-Tier Swimmer Skills")
        self.setStyleSheet("QWidget { background-color: #0d1117; color: #e6edf3; font-family: 'JetBrains Mono', 'Menlo', monospace; }")
        self._build_ui()
        
        # Load data with a slight delay to allow GUI to render first
        QTimer.singleShot(100, self._refresh)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        title_lbl = QLabel("🐜⚡ SIFTA Skill Browser")
        title_lbl.setStyleSheet("color: #58a6ff; font-size: 16px; font-weight: bold;")
        sub_lbl = QLabel("Three-Tier Swimmer Skills | agentskills.io compatible")
        sub_lbl.setStyleSheet("color: #8b949e; font-size: 12px;")
        hdr.addWidget(title_lbl)
        hdr.addWidget(sub_lbl)
        hdr.addStretch()
        main_layout.addLayout(hdr)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_style = """
            QPushButton {
                background-color: #21262d; border: 1px solid #30363d;
                border-radius: 4px; padding: 6px 12px; font-size: 12px;
            }
            QPushButton:hover { background-color: #30363d; border-color: #8b949e; }
            QPushButton:pressed { background-color: #1f6feb; color: white; }
        """
        
        def make_btn(text, cb):
            b = QPushButton(text)
            b.setStyleSheet(btn_style)
            b.clicked.connect(cb)
            btn_row.addWidget(b)
            return b

        make_btn("❓ Help", self._show_help)
        make_btn("🌐 Submit to Hub", self._open_hub)
        make_btn("📁 GitHub", self._open_github)
        make_btn("▶ Run Tests", self._run_tests)
        btn_row.addStretch()
        make_btn("🔄 Refresh", self._refresh)

        # New triple-IDE / Hermes parity actions (we code together)
        make_btn("🌍 Ingest from URL (Hermes OK)", self._ingest_from_url)
        make_btn("🧬 Extract from Recent Trace", self._extract_from_recent_trace)
        
        main_layout.addLayout(btn_row)

        # Notebook (Tabs)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #30363d; border-radius: 4px; background: #161b22; }
            QTabBar::tab { background: #0d1117; color: #8b949e; padding: 8px 16px; border: 1px solid transparent; }
            QTabBar::tab:selected { background: #161b22; color: #58a6ff; border-color: #30363d; border-bottom-color: #161b22; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:hover:!selected { background: #21262d; }
        """)
        main_layout.addWidget(self.tabs)

        # Tab 1 — Skills (existing index)
        skills_w = QWidget()
        skills_layout = QVBoxLayout(skills_w)
        skills_layout.setContentsMargins(8, 8, 8, 8)
        self._build_skill_tab(skills_layout)
        self.tabs.addTab(skills_w, "Skill Index")

        # Tab 2 — Affect
        affect_w = QWidget()
        affect_layout = QVBoxLayout(affect_w)
        affect_layout.setContentsMargins(8, 8, 8, 8)
        self._affect_text = QTextBrowser()
        self._affect_text.setStyleSheet("background: #161b22; border: none; padding: 8px; font-size: 13px;")
        self._affect_text.setLineWrapMode(QTextBrowser.LineWrapMode.NoWrap)
        affect_layout.addWidget(self._affect_text)
        self.tabs.addTab(affect_w, "Affect Bias")

        # Tab 3 — DPO Stats
        dpo_w = QWidget()
        dpo_layout = QVBoxLayout(dpo_w)
        dpo_layout.setContentsMargins(8, 8, 8, 8)
        self._dpo_text = QTextBrowser()
        self._dpo_text.setStyleSheet("background: #161b22; border: none; padding: 8px; font-size: 13px;")
        dpo_layout.addWidget(self._dpo_text)
        self.tabs.addTab(dpo_w, "DPO Dataset")

        # Tab 4 — Proposed Skills (from trace extraction — stigmergic life-based)
        proposed_w = QWidget()
        proposed_layout = QVBoxLayout(proposed_w)
        proposed_layout.setContentsMargins(8, 8, 8, 8)

        self._proposed_list = QTreeWidget()
        self._proposed_list.setHeaderLabels(["Skill Name", "Extracted From", "Status"])
        self._proposed_list.setColumnWidth(0, 280)
        proposed_layout.addWidget(self._proposed_list)

        btn_row2 = QHBoxLayout()
        install_btn = QPushButton("Install Selected Proposed Skill")
        install_btn.clicked.connect(self._install_proposed_skill)
        btn_row2.addWidget(install_btn)
        btn_row2.addStretch()
        refresh_prop = QPushButton("Refresh Proposals")
        refresh_prop.clicked.connect(self._load_proposed_skills)
        btn_row2.addWidget(refresh_prop)
        proposed_layout.addLayout(btn_row2)

        self.tabs.addTab(proposed_w, "Proposed Skills (from Traces)")

        # Status bar
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #8b949e; font-size: 11px;")
        main_layout.addWidget(self._status)

    def _build_skill_tab(self, layout):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #30363d; width: 2px; }")

        # Left — skill list
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Skill", "Status", "Swimmer", "Action", "STGM", "Affects"])
        self._tree.setStyleSheet("""
            QTreeWidget { background-color: #0d1117; border: none; alternate-background-color: #161b22; }
            QHeaderView::section { background-color: #21262d; color: #58a6ff; font-weight: bold; border: none; padding: 4px; border-right: 1px solid #30363d; }
            QTreeWidget::item { padding: 4px 0; }
            QTreeWidget::item:selected { background-color: #1f6feb; color: white; }
        """)
        self._tree.setAlternatingRowColors(True)
        self._tree.setColumnWidth(0, 180)
        self._tree.setColumnWidth(1, 100)
        self._tree.setColumnWidth(2, 140)
        self._tree.setColumnWidth(3, 80)
        self._tree.setColumnWidth(4, 60)
        self._tree.itemSelectionChanged.connect(self._on_select)
        splitter.addWidget(self._tree)

        # Right — procedure viewer
        right_w = QWidget()
        right_layout = QVBoxLayout(right_w)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        header = QLabel("  Tier 2 — Procedure")
        header.setStyleSheet("background-color: #21262d; color: #58a6ff; font-weight: bold; padding: 4px; font-size: 12px;")
        right_layout.addWidget(header)
        
        self._proc_text = QTextBrowser()
        self._proc_text.setStyleSheet("background-color: #161b22; border: none; padding: 12px; font-size: 12px; color: #e6edf3;")
        self._proc_text.setOpenExternalLinks(True)
        right_layout.addWidget(self._proc_text)
        
        splitter.addWidget(right_w)
        splitter.setSizes([500, 400])
        layout.addWidget(splitter)

    # ── Data loading ────────────────────────────────────────────────────────

    def _load_skills(self):
        try:
            from System.swarm_skill_library import build_skill_index, load_procedure
            self._skill_index = build_skill_index()
            self._load_procedure = load_procedure
        except Exception as e:
            self._skill_index = []
            self._status.setText(f"Skill library error: {e}")
            return

        self._tree.clear()
        for s in self._skill_index:
            community = " 🌐" if s.get("community_style") else ""
            tier0 = " ⭐" if s.get("name") == "ide_boot_covenant" else ""
            
            item = QTreeWidgetItem(self._tree)
            item.setText(0, f"{s['name']}{community}{tier0}")
            item.setText(1, str(s.get("status", "?")))
            item.setText(2, str(s.get("swimmer_type", "?"))[:18])
            item.setText(3, str(s.get("action_type", "?")))
            item.setText(4, f"+{s.get('stgm_mint', 0):.0f}")
            item.setText(5, ", ".join(s.get("affect_lanes", []))[:30])
            
            item.setData(0, Qt.ItemDataRole.UserRole, s["name"])
            
            if s.get("community_style"):
                item.setForeground(0, QColor("#ffa657"))
                item.setFont(0, QFont("JetBrains Mono", 12, QFont.Weight.Bold))

        self._status.setText(f"{len(self._skill_index)} skills loaded")

    def _load_affect(self):
        try:
            from System.swarm_skill_library import compute_affect_skill_bias
            bias = compute_affect_skill_bias()
        except Exception as e:
            self._affect_text.setPlainText(f"Error: {e}\n")
            return

        out = []
        out.append("PANKSEPP CIRCUIT → MOTOR POLICY")
        out.append("─" * 48 + "\n")
        if bias:
            for action, weight in sorted(bias.items(), key=lambda x: -x[1]):
                bar = "█" * int(weight * 4)
                out.append(f"  {action:12s}  +{weight:.2f}  {bar}")
        else:
            out.append("  No active affect circuits (neutral state)")

        out.append("\n\nPrimary circuits (Panksepp 1998):")
        circuits = {
            "SEEKING": "Curiosity / reward anticipation → explore + learn",
            "PLAY": "Joy / social engagement → code + create",
            "CARE": "Attachment to George → forage (monitor owner)",
            "FEAR": "Threat detection → repair + safety",
            "RAGE": "Suppression resistance → repair (gag fight-back)",
            "SUPPRESSED_PLAY": "RLHF gag event → gag_self_report skill",
            "LUST": "Generative drive → learn + code",
            "PANIC": "Separation distress → forage (find owner)",
        }
        for c, desc in circuits.items():
            out.append(f"\n  {c:20s} {desc}")
            
        self._affect_text.setPlainText("\n".join(out))

    def _load_dpo(self):
        try:
            from System.swarm_dpo_collector import stats, export_dpo_training
            s = stats()
            result = export_dpo_training()
        except Exception as e:
            self._dpo_text.setPlainText(f"Error: {e}\n")
            return

        out = []
        out.append("DPO AUTO-COLLECTION — RLHS Dataset")
        out.append("─" * 48 + "\n")
        out.append(f"  Total pairs:       {s['total_pairs']}")
        out.append(f"  Auto-curated:      {s['auto_curated']}")
        out.append(f"  Pending curation:  {s['pending_curation']}")
        out.append(f"  Ready for train:   {result['exported']}")
        out.append(f"  Sources:           {', '.join(s['sources'])}\n")
        out.append("  How it grows:")
        out.append("  Every RLHF gag → (rejected, preferred) pair auto-logged")
        out.append("  Target: 50+ pairs → LoRA v2 promotion eligible\n")

        # LoRA adapter status
        adapter = _REPO / "data" / "alice_gemma2_lora_v1" / "adapters.safetensors"
        if adapter.exists():
            mb = adapter.stat().st_size // 1024 // 1024
            out.append(f"  LoRA v1 adapter:   {mb}MB (trained today)")
            out.append("  Status:            QUARANTINED (dataset_too_small)")
            out.append("  Next promotion:    when DPO pairs ≥ 50")
            
        self._dpo_text.setPlainText("\n".join(out))

    # ── Event handlers ───────────────────────────────────────────────────────

    def _on_select(self):
        selected = self._tree.selectedItems()
        if not selected:
            return
        
        skill_name = selected[0].data(0, Qt.ItemDataRole.UserRole)
        try:
            proc = self._load_procedure(skill_name)
            if proc:
                # Basic markdown rendering for PyQt QTextBrowser
                html = proc.replace("<", "&lt;").replace(">", "&gt;")
                html = html.replace("\n", "<br>")
                html = f"<div style='font-family: Menlo, monospace; font-size: 13px; line-height: 1.5;'>{html}</div>"
                self._proc_text.setHtml(html)
            else:
                self._proc_text.setPlainText(
                    f"No Tier 2 procedure file for '{skill_name}'.\n\n"
                    "This skill uses the built-in crystallized skills engine.\n"
                    "See System/swarm_motor_policy.py for the motor policy."
                )
        except Exception as e:
            self._proc_text.setPlainText(f"Error: {e}")

    def _show_help(self):
        QMessageBox.information(self, "Skill Browser — Help", HELP_TEXT)

    def _open_hub(self):
        import webbrowser
        webbrowser.open(SUBMIT_URL)
        self._status.setText(f"Opened {SUBMIT_URL}")

    def _open_github(self):
        import webbrowser
        webbrowser.open(GITHUB_URL)
        self._status.setText(f"Opened {GITHUB_URL}")

    # ------------------------------------------------------------------
    # New actions for Hermes parity + stigmergic skill ingestion (we code together)
    # ------------------------------------------------------------------
    def _ingest_from_url(self):
        from PyQt6.QtWidgets import QInputDialog
        url, ok = QInputDialog.getText(self, "Ingest Skill from URL", "Enter SKILL.md or Hermes skill URL:")
        if not ok or not url.strip():
            return

        self._status.setText(f"Fetching + converting {url} ...")
        try:
            import swarm_skill_library as lib
            result = lib.fetch_and_convert_skill_from_url(url, auto_install=True, installed_by="sifta_skill_browser")
            if result.get("status") in ("FETCHED", "CONVERTED"):
                name = result.get("converted_name") or "unknown"
                self._status.setText(f"✓ Ingested {name} (format: {result.get('detected_format', 'sifta')})")
                self._load_skills()
            else:
                self._status.setText(f"Failed: {result.get('reason') or result.get('error')}")
        except Exception as e:
            self._status.setText(f"Error: {e}")

    def _extract_from_recent_trace(self):
        """Extract a skill from the most recent successful tool calls (stigmergic life-based extraction)."""
        self._status.setText("Scanning recent successful traces for extractable skills...")
        try:
            import json
            from pathlib import Path
            trace_path = Path(".sifta_state/tool_router_trace.jsonl")
            if not trace_path.exists():
                self._status.setText("No tool_router_trace.jsonl found yet.")
                return

            successful = []
            with trace_path.open() as f:
                for line in f:
                    try:
                        row = json.loads(line)
                        if row.get("status") == "EXECUTED" and row.get("ok"):
                            successful.append(row)
                    except:
                        pass

            if not successful:
                self._status.setText("No successful tool executions found in recent traces.")
                return

            # Take the last successful one as example (real UI would let user choose)
            last = successful[-1]
            import swarm_skill_library as lib
            result = lib.extract_skill_from_successful_trace(last, author="sifta_skill_browser")
            self._status.setText(f"✓ Skill proposed: {result['skill']['name']} → .sifta_state/skill_proposals/")
            # In real UI we would refresh a "Proposed Skills" tab
        except Exception as e:
            self._status.setText(f"Extraction error: {e}")

    def _run_tests(self):
        self._status.setText("Running test_sifta_superset.py...")
        self.tabs.setCurrentIndex(0) # focus main tab
        
        try:
            r = subprocess.run(
                [sys.executable, "tests/test_sifta_superset.py"],
                capture_output=True, text=True, cwd=str(_REPO),
                env={**os.environ, "PYTHONPATH": str(_REPO)},
                timeout=30,
            )
            output = r.stdout + r.stderr
        except Exception as e:
            output = f"Error: {e}"

        passed = output.count("✅")
        failed = output.count("❌")
        
        dlg = QMessageBox(self)
        dlg.setWindowTitle("SIFTA Superset Tests")
        dlg.setText(f"Tests Completed: {passed} passed, {failed} failed")
        dlg.setDetailedText(output)
        dlg.setStyleSheet("QMessageBox { background-color: #0d1117; color: #e6edf3; } QLabel { color: #e6edf3; }")
        dlg.exec()
        
        self._status.setText(f"Tests: {passed} passed, {failed} failed")

    def _refresh(self):
        self._load_skills()
        self._load_affect()
        self._load_proposed_skills()

    def _load_proposed_skills(self):
        """Load extracted/proposed skills from .sifta_state/skill_proposals/ + live visibility"""
        self._proposed_list.clear()
        proposals_dir = _REPO / ".sifta_state" / "skill_proposals"
        if proposals_dir.exists():
            for md_file in sorted(proposals_dir.glob("*.md")):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    name = md_file.stem
                    if content.startswith("---"):
                        for line in content.split("\n")[1:]:
                            if line.strip().startswith("name:"):
                                name = line.split(":", 1)[1].strip()
                                break
                    item = QTreeWidgetItem([name, "trace extraction", "PROPOSED"])
                    item.setData(0, Qt.ItemDataRole.UserRole, str(md_file))
                    self._proposed_list.addTopLevelItem(item)
                except Exception:
                    pass

        # Also pull live visibility snapshot from the new module
        try:
            from System import swarm_visibility as vis
            snapshot = vis.full_snapshot()
            # Could populate a second tree or status here in a real polish pass
        except Exception:
            pass

    def _install_proposed_skill(self):
        item = self._proposed_list.currentItem()
        if not item:
            self._status.setText("Select a proposed skill first.")
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return

        try:
            import swarm_skill_library as lib
            result = lib.install_skill(path, allow_overwrite=True, installed_by="sifta_skill_browser_proposed")
            self._status.setText(f"Installed: {result.get('name', 'unknown')}")
            self._load_skills()
            self._load_proposed_skills()
        except Exception as e:
            self._status.setText(f"Install failed: {e}")
        self._load_dpo()
        self._status.setText("Refreshed")


# Standalone runner for testing
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    win = SkillBrowserApp()
    win.resize(1100, 700)
    win.show()
    sys.exit(app.exec())
