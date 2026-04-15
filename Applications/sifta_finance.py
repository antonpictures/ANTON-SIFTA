#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Finance Dashboard
# Robinhood-style view of all Swarm agents: STGM balances,
# energy levels, status. Plus an Install Agent button.
# ─────────────────────────────────────────────────────────────

import sys, json, os, time
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
_sys = os.path.join(REPO_ROOT, "System")
if _sys not in sys.path:
    sys.path.insert(0, _sys)
from ledger_append import append_ledger_line, append_jsonl_line
from inference_economy import ledger_balance
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QDialog, QLineEdit,
    QComboBox, QMessageBox, QGridLayout, QProgressBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QAbstractItemView,
    QTextEdit,
)
from PyQt6.QtCore  import Qt, QTimer
from PyQt6.QtGui   import QFont, QColor

STATE_DIR   = os.path.join(REPO_ROOT, ".sifta_state")
_GIT_BRANCH = os.environ.get("SIFTA_GIT_BRANCH", "feat/sebastian-video-economy")


def _git_mesh_commit_push(rel_paths, message):
    """Stage paths, commit, pull --rebase, push — argv only (no shell)."""
    import subprocess
    for p in rel_paths:
        subprocess.run(["git", "-C", REPO_ROOT, "add", p], capture_output=True, timeout=60)
    r = subprocess.run(
        ["git", "-C", REPO_ROOT, "commit", "-m", message],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if r.returncode != 0:
        return
    subprocess.run(
        ["git", "-C", REPO_ROOT, "pull", "origin", _GIT_BRANCH, "--rebase", "-X", "theirs"],
        capture_output=True,
        timeout=120,
    )
    subprocess.run(
        ["git", "-C", REPO_ROOT, "push", "origin", _GIT_BRANCH],
        capture_output=True,
        timeout=120,
    )

AGENT_FACES = {
    "ALICE_M5":   "[_o_]", "M1THER":   "[O_O]", "ANTIALICE": "[o|o]",
    "SEBASTIAN":  "[_o_]", "HERMES":   "[_v_]",  "IMPERIAL":  "[@_@]",
    "REPAIR-DRONE":"[X_X]","M1SIFTA_BODY":"[M1]","M5SIFTA_BODY":"[M5]",
    "GROK_SWARMGPT":"[G_G]","OPENCLAW_QUEEN":"[Q_Q]","M1QUEEN":"[q_q]",
    "CURSOR_IDE": "[C>]", "ANTIGRAVITY_IDE": "[A>]",
}
AGENT_COLORS = {
    "ALICE_M5":"#ff9e64","M1THER":"#7dcfff","ANTIALICE":"#bb9af7",
    "SEBASTIAN":"#9ece6a","HERMES":"#e0af68","M5SIFTA_BODY":"#ff9e64",
    "M1SIFTA_BODY":"#7dcfff","GROK_SWARMGPT":"#73daca","M1QUEEN":"#7dcfff",
    "CURSOR_IDE":"#7aa2f7","ANTIGRAVITY_IDE":"#bb9af7",
}
DEFAULT_COLOR = "#565f89"

# ─────────────────────────────────────────────────────────────

def load_agents():
    # ── GENESIS BLOCK VALIDATION ──
    genesis_registry = {}
    genesis_file = os.path.join(STATE_DIR, "genesis_log.jsonl")
    if os.path.exists(genesis_file):
        try:
            with open(genesis_file, "r") as gf:
                for line in gf:
                    if not line.strip(): continue
                    try:
                        entry = json.loads(line)
                        if entry.get("event") == "GENESIS":
                            genesis_registry[entry.get("agent_id")] = {
                                "seal": entry.get("architect_seal"),
                                "timestamp": entry.get("timestamp"),
                                "starting_stgm": float(entry.get("starting_stgm", 0.0)),
                                "serial": entry.get("hardware_serial")
                            }
                    except: pass
        except Exception as e:
            print(f"Genesis verification error: {e}")

    agents = []
    skip = {"circadian_m1","circadian_m5","identity_stats","intelligence_settings",
            "m1queen_identity_anchor","physical_registry","scheduler_m5",
            "state_bus","territory_manifest","m1queen_memory"}
    for fname in sorted(os.listdir(STATE_DIR)):
        if not fname.endswith(".json"): continue
        key = fname.replace(".json","")
        if key in skip: continue
        try:
            with open(os.path.join(STATE_DIR, fname)) as f:
                data = json.load(f)
            if "energy" not in data and "stgm_balance" not in data: continue
            data["_file"] = fname
            data["_key"]  = key
            if "id" not in data or not data["id"]:
                data["id"] = key

            # SYBIL DEFENSE FLAG (Ed25519 Validation) — does NOT zero quorum STGM.
            agent_id = data["id"]
            file_bal = float(data.get("stgm_balance", 0) or 0)
            data["stgm_balance_file"] = file_bal
            claimed_seal = data.get("architect_seal", "UNSEALED")
            hw_serial = data.get("homeworld_serial", "UNKNOWN")

            # The genesis payload that was signed was: "agent_id:stgm:serial:timestamp"
            is_valid = False
            if agent_id in genesis_registry:
                gen_data = genesis_registry[agent_id]
                seal_signature = gen_data["seal"]
                gen_ts = gen_data["timestamp"]
                gen_stgm = gen_data["starting_stgm"]

                if claimed_seal == seal_signature and data.get("homeworld_serial") == gen_data["serial"]:
                    verify_str = f"{agent_id}:{gen_stgm}:{hw_serial}:{gen_ts}"
                    sys.path.append(REPO_ROOT)
                    try:
                        from System.crypto_keychain import verify_block
                        if verify_block(hw_serial, verify_str, seal_signature):
                            is_valid = True
                    except Exception as e:
                        print(f"Verify failed: {e}")

            data["sybil_quarantined"] = not is_valid
            # Canonical display: repair_log quorum (same as server / spend guards).
            data["stgm_balance"] = float(ledger_balance(agent_id))

            agents.append(data)
        except Exception as e:
            print(f"Skipping {fname} due to error: {e}")
            import traceback
            traceback.print_exc()
            continue
    agents.sort(key=lambda a: float(a.get("stgm_balance") or 0), reverse=True)
    return agents

# ─────────────────────────────────────────────────────────────

class AgentCard(QFrame):
    def __init__(self, agent: dict):
        super().__init__()
        self.agent = agent
        self._build(agent)

    def _build(self, a):
        agent_id = str(a.get("id") or a.get("_key","?")).upper()
        stgm     = float(a.get("stgm_balance") or 0)
        file_claim = float(a.get("stgm_balance_file") or 0)
        energy   = int(a.get("energy") or 0)
        style    = str(a.get("style") or "UNKNOWN")
        face     = AGENT_FACES.get(agent_id, "[~_~]")
        color    = AGENT_COLORS.get(agent_id, DEFAULT_COLOR)

        is_sybil = a.get("sybil_quarantined", False)

        if is_sybil:
            color = "#e0af68"
            face = "[!_!]"
            if stgm > 0:
                style = "[GENESIS SEAL MISMATCH · QUORUM STGM OK]"
            else:
                style = "[GENESIS SEAL MISMATCH — NO LEDGER CREDITS FOR THIS ID]"

        self.setFixedHeight(130)
        self.setStyleSheet(f"""
            QFrame {{
                background: #13141f;
                border: 1px solid {color}44;
                border-left: 3px solid {color};
                border-radius: 8px;
            }}
            QFrame:hover {{ background: #1a1b2e; border-color: {color}88; }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(16)

        # Face
        face_lbl = QLabel(face)
        face_lbl.setFont(QFont("Courier", 16, QFont.Weight.Bold))
        face_lbl.setStyleSheet(f"color: {color}; min-width: 54px;")
        face_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(face_lbl)

        # Info block
        info = QVBoxLayout()
        info.setSpacing(3)

        name_lbl = QLabel(agent_id)
        name_lbl.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {color};")
        info.addWidget(name_lbl)

        style_lbl = QLabel(style)
        style_lbl.setFont(QFont("Inter", 10))
        if is_sybil:
            style_lbl.setStyleSheet("color: #f7768e; font-weight: bold;")
        else:
            style_lbl.setStyleSheet("color: #565f89;")
        info.addWidget(style_lbl)

        # Energy bar
        energy_row = QHBoxLayout()
        if is_sybil:
            warn_txt = "⚠ Genesis / seal check failed — UI shows quorum STGM from repair_log."
            if abs(file_claim - stgm) > 0.0001 and file_claim > 0:
                warn_txt += f" (JSON file claims {file_claim:,.1f})"
            sybil_warn = QLabel(warn_txt)
            sybil_warn.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            sybil_warn.setStyleSheet("color: #e0af68;")
            sybil_warn.setWordWrap(True)
            energy_row.addWidget(sybil_warn)
        else:
            energy_bar = QProgressBar()
            energy_bar.setRange(0, 100)
            energy_bar.setValue(energy)
            energy_bar.setFixedHeight(6)
            energy_bar.setTextVisible(False)
            bar_color = "#9ece6a" if energy > 60 else "#e0af68" if energy > 25 else "#f7768e"
            energy_bar.setStyleSheet(f"""
                QProgressBar {{ background: #1f2335; border-radius: 3px; border: none; }}
                QProgressBar::chunk {{ background: {bar_color}; border-radius: 3px; }}
            """)
            energy_row.addWidget(energy_bar)
            e_lbl = QLabel(f"{energy}%")
            e_lbl.setFont(QFont("Inter", 9))
            e_lbl.setStyleSheet("color: #565f89; min-width:30px;")
            energy_row.addWidget(e_lbl)
        
        info.addLayout(energy_row)
        lay.addLayout(info)

        lay.addStretch()

        # STGM block
        stgm_block = QVBoxLayout()
        stgm_block.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        stgm_val = QLabel(f"{stgm:,.1f}")
        stgm_val.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        stgm_val.setStyleSheet(f"color: {'#9ece6a' if stgm > 0 else '#f7768e'};")
        stgm_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        stgm_block.addWidget(stgm_val)

        stgm_lbl = QLabel("STGM")
        stgm_lbl.setFont(QFont("Inter", 9))
        stgm_lbl.setStyleSheet("color: #565f89;")
        stgm_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        stgm_block.addWidget(stgm_lbl)
        lay.addLayout(stgm_block)

# ─────────────────────────────────────────────────────────────

class InstallAgentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install New Agent")
        self.setMinimumWidth(360)
        self.setStyleSheet("""
            QDialog   { background: #0d0e17; color: #a9b1d6; }
            QLabel    { color: #a9b1d6; font-size: 12px; }
            QLineEdit { background: #1a1b2e; border: 1px solid #2a2b3d;
                        border-radius:4px; padding:6px; color:#a9b1d6; }
            QComboBox { background: #1a1b2e; border: 1px solid #2a2b3d;
                        border-radius:4px; padding:6px; color:#a9b1d6; }
            QPushButton { background:#3d59a1; color:#fff; border:none;
                          border-radius:4px; padding:8px 16px; font-weight:bold; }
            QPushButton:hover { background:#4a6cbf; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20,20,20,20)
        lay.setSpacing(10)

        lay.addWidget(QLabel("Agent ID (e.g. SCOUT_M5):"))
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("AGENT_NAME · try CURSOR_IDE for IDE-bound guest")
        lay.addWidget(self.id_input)

        lay.addWidget(QLabel("Role:"))
        self.role = QComboBox()
        self.role.addItems(["ACTIVE","SCOUT","REPAIR","MEDIC","WATCHER","DETECTIVE"])
        lay.addWidget(self.role)

        # ── NO FREE STGM AT GENESIS ─────────────────────────────
        # Swimmers are born hungry. They earn STGM by observing the
        # Architect, repairing code, routing inference, and performing
        # useful work. No birth presents. No handouts. No breach.
        # ──────────────────────────────────────────────────────────────

        btn = QPushButton("⬇  INSTALL AGENT")
        btn.clicked.connect(self._install)
        lay.addWidget(btn)

    def _install(self):
        agent_id  = self.id_input.text().strip().upper().replace(" ","_")
        role      = self.role.currentText()
        stgm      = 0.0  # SEALED: swimmers earn, never gifted
        if not agent_id:
            QMessageBox.warning(self, "Error", "Agent ID required.")
            return
        fpath = os.path.join(STATE_DIR, f"{agent_id}.json")
        if os.path.exists(fpath):
            QMessageBox.warning(self, "Exists", f"{agent_id} already installed.")
            return

        # Claude Audit Fix 1: Baptism Gate / ARCHITECT_SEAL (safe serial read)
        try:
            _sysd = os.path.join(REPO_ROOT, "System")
            if _sysd not in sys.path:
                sys.path.insert(0, _sysd)
            from silicon_serial import read_apple_serial
            serial = read_apple_serial()
        except Exception:
            serial = "UNKNOWN_SERIAL"

        import hashlib
        import sys
        sys.path.append(REPO_ROOT)
        
        ts = int(time.time())
        seal_payload = f"{agent_id}:{stgm}:{serial}:{ts}"
        
        try:
            from System.crypto_keychain import sign_block
            seal = sign_block(seal_payload)
        except Exception as e:
            print(f"Ed25519 sign error, falling back to SHA256: {e}")
            seal = "SEAL_" + hashlib.sha256(seal_payload.encode()).hexdigest()[:12]

        payload = {
            "id":           agent_id,
            "ascii":        f"<///[~_~]///::ID[{agent_id}]::INSTALLED[{ts}]>",
            "stgm_balance": stgm,
            "style":        role,
            "energy":       100,
            "architect_seal": seal,
            "homeworld_serial": serial
        }
        with open(fpath, "w") as f:
            json.dump(payload, f, indent=2)

        # ── Immutable Genesis Log (STGM always 0.0 — earn only) ───
        genesis_entry = {
            "timestamp": ts,
            "agent_id": agent_id,
            "event": "GENESIS",
            "starting_stgm": 0.0,
            "architect_seal": seal,
            "hardware_serial": serial
        }
        try:
            append_jsonl_line(os.path.join(REPO_ROOT, ".sifta_state", "genesis_log.jsonl"), genesis_entry)
            # ── NO STGM_MINT AT GENESIS ──────────────────────────────
            # The free-mint breach is permanently sealed.
            # Swimmers begin life at 0.0 and earn through useful work.
            # ─────────────────────────────────────────────────────────
        except Exception as e:
            print(f"Log write error: {e}")

        QMessageBox.information(self,"Installed", f"Agent {agent_id} installed.\nSTGM: 0.0 (earn only) | Role: {role}\nSeal: {seal}")
        self.accept()

# ─────────────────────────────────────────────────────────────

class FinanceDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QWidget { background-color: #0d0e17; color: #a9b1d6; font-family: 'Inter'; }
            QTabWidget::pane { border: 1px solid #2a2b3d; border-radius: 4px; }
            QTabBar::tab { background: #1a1b2e; color: #565f89; padding: 10px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
            QTabBar::tab:selected { background: #24253a; color: #7aa2f7; font-weight: bold; }
            QTableWidget { background: #15161e; border: 1px solid #2a2b3d; gridline-color: #1f2335; color: #a9b1d6; }
            QHeaderView::section { background: #1a1b2e; color: #7aa2f7; padding: 4px; border: 1px solid #1f2335; }
        """)
        self._main_lay = QVBoxLayout(self)
        self._main_lay.setContentsMargins(16, 12, 16, 12)
        self._main_lay.setSpacing(10)

        self.tabs = QTabWidget()
        self.portfolio_tab = QWidget()
        self.market_tab = MarketplaceTab()
        self.warren_tab = QWidget()
        self.tabs.addTab(self.portfolio_tab, "💰 Portfolio")
        self.tabs.addTab(self.market_tab, "⚡ Inference Market")
        self.tabs.addTab(self.warren_tab, "📊 Warren Buffett")
        self._build_warren_tab()
        self._main_lay.addWidget(self.tabs)

        self._build_portfolio()
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_all)
        self._timer.start(5000)

    def _build_warren_tab(self):
        wl = QVBoxLayout(self.warren_tab)
        wl.setContentsMargins(10, 10, 10, 10)
        hdr = QLabel(
            "<b>Warren Buffett</b> — OBSERVE-only accountant. Reads <code>repair_log.jsonl</code>; "
            "does not mint. Estimates power vs STGM (optional USD peg via <code>SIFTA_STGM_USD_PEG</code>)."
        )
        hdr.setWordWrap(True)
        hdr.setStyleSheet("color: #565f89; font-size: 11px;")
        wl.addWidget(hdr)
        self.warren_view = QTextEdit()
        self.warren_view.setReadOnly(True)
        self.warren_view.setFont(QFont("Menlo", 10))
        self.warren_view.setStyleSheet(
            "QTextEdit { background: #13141f; color: #a9b1d6; border: 1px solid #2a2b3d; border-radius: 6px; }"
        )
        wl.addWidget(self.warren_view, 1)
        self._refresh_warren()

    def _refresh_warren(self):
        try:
            _sysd = os.path.join(REPO_ROOT, "System")
            if _sysd not in sys.path:
                sys.path.insert(0, _sysd)
            from warren_buffett import ascii_report, profit_report
            self.warren_view.setPlainText(ascii_report() + "\n\n" + json.dumps(profit_report(), indent=2))
        except Exception as e:
            self.warren_view.setPlainText(f"Warren report unavailable: {e}")

    def _build_portfolio(self):
        lay = QVBoxLayout(self.portfolio_tab)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)
        # ── Header ──────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("⚡ SWARM FINANCE")
        title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #7aa2f7;")
        header.addWidget(title)
        header.addStretch()

        from PyQt6.QtWidgets import QCheckBox
        self.hide_inactive_cb = QCheckBox("Hide inactive")
        self.hide_inactive_cb.setChecked(True)
        self.hide_inactive_cb.setStyleSheet(
            "QCheckBox { color: #565f89; font-size: 11px; spacing: 5px; }"
            "QCheckBox::indicator { width:13px; height:13px; border:1px solid #414868;"
            "  border-radius:3px; background:#1a1b2e; }"
            "QCheckBox::indicator:checked { background:#7aa2f7; border-color:#7aa2f7; }"
        )
        self.hide_inactive_cb.stateChanged.connect(self._refresh_all)
        header.addWidget(self.hide_inactive_cb)

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedSize(30, 30)
        self.refresh_btn.setStyleSheet("QPushButton{background:#1a1b2e;border:1px solid #2a2b3d;border-radius:15px;color:#7aa2f7;font-weight:bold;} QPushButton:hover{background:#2a2b3d;}")
        self.refresh_btn.clicked.connect(self._refresh_all)
        header.addWidget(self.refresh_btn)

        install_btn = QPushButton("⬇  Install Agent")
        install_btn.setStyleSheet("QPushButton{background:#1a1b2e;border:1px solid #9ece6a;border-radius:4px;color:#9ece6a;padding:5px 12px;font-weight:bold;} QPushButton:hover{background:#1f2335;}")
        install_btn.clicked.connect(self._install)
        header.addWidget(install_btn)
        lay.addLayout(header)

        # ── Portfolio total ──────────────────────────────────
        self.portfolio_lbl = QLabel()
        self.portfolio_lbl.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        self.portfolio_lbl.setStyleSheet("color: #9ece6a; padding: 4px 0;")
        lay.addWidget(self.portfolio_lbl)

        agents_lbl = QLabel("TOTAL SWARM PORTFOLIO  ·  STGM")
        agents_lbl.setStyleSheet("color: #565f89; font-size: 11px; margin-bottom: 6px;")
        lay.addWidget(agents_lbl)

        # ── Scroll area for cards ────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;} QScrollBar:vertical{width:6px;background:#1a1b2e;} QScrollBar::handle:vertical{background:#414868;border-radius:3px;}")
        self.card_container = QWidget()
        self.card_container.setStyleSheet("background:transparent;")
        self.card_lay = QVBoxLayout(self.card_container)
        self.card_lay.setSpacing(8)
        self.card_lay.setContentsMargins(0,0,0,0)
        scroll.setWidget(self.card_container)
        lay.addWidget(scroll)

        self._populate_portfolio()

    def _populate_portfolio(self):
        while self.card_lay.count():
            item = self.card_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        agents = load_agents()
        hide_inactive = self.hide_inactive_cb.isChecked()
        if hide_inactive:
            agents = [a for a in agents if int(a.get("energy") or 0) > 0]

        total  = sum(float(a.get("stgm_balance") or 0) for a in agents)
        self.portfolio_lbl.setText(f"{total:,.1f}")

        if not agents:
            empty = QLabel("All agents inactive. Uncheck \"Hide inactive\" to see full history.")
            empty.setStyleSheet("color: #565f89; font-size: 12px; padding: 20px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_lay.addWidget(empty)
        else:
            # Group by Hardware Entity (homeworld_serial)
            entities = {}
            for a in agents:
                hw = str(a.get("homeworld_serial") or "SWARM_ORPHANS")
                if hw not in entities:
                    entities[hw] = []
                entities[hw].append(a)

            # Determine local serial to highlight the local node
            try:
                import subprocess
                ioreg = subprocess.run(
                    ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True, text=True, timeout=5
                )
                local_serial = "UNKNOWN_SERIAL"
                for line in ioreg.stdout.splitlines():
                    if "IOPlatformSerialNumber" in line:
                        local_serial = line.split('"')[-2].strip()
                        break
            except:
                local_serial = "UNKNOWN_SERIAL"

            for hw_serial, swimmers in entities.items():
                if not swimmers: continue

                # Hardware Vault Header
                vault_stgm = sum(float(x.get("stgm_balance") or 0) for x in swimmers)
                vault_header = QLabel(f"⬡ ENTITY: {hw_serial}  |  TOTAL VALUE: {vault_stgm:,.1f} STGM")
                if hw_serial == local_serial:
                    vault_header.setText(f"⬡ ENTITY: {hw_serial} (LOCAL)  |  TOTAL VALUE: {vault_stgm:,.1f} STGM")
                    vault_header.setStyleSheet("color: #9ece6a; font-weight: bold; font-size: 13px; margin-top: 10px; margin-bottom: 2px;")
                elif hw_serial == "SWARM_ORPHANS":
                    vault_header.setStyleSheet("color: #565f89; font-weight: bold; font-size: 13px; margin-top: 10px; margin-bottom: 2px;")
                else:
                    vault_header.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 13px; margin-top: 10px; margin-bottom: 2px;")
                
                self.card_lay.addWidget(vault_header)

                for a in swimmers:
                    self.card_lay.addWidget(AgentCard(a))
                
                # Small spacer between entities
                spacer = QWidget()
                spacer.setFixedHeight(10)
                self.card_lay.addWidget(spacer)

        self.card_lay.addStretch()

    def _refresh_all(self):
        self._populate_portfolio()
        self.market_tab.load_market()
        self._refresh_warren()

    def _install(self):
        dlg = InstallAgentDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_all()

# ─────────────────────────────────────────────────────────────

class MarketplaceTab(QWidget):
    def __init__(self):
        super().__init__()
        self.market_file = os.path.join(STATE_DIR, "marketplace_listings.json")
        try:
            _sysd = os.path.join(REPO_ROOT, "System")
            if _sysd not in sys.path:
                sys.path.insert(0, _sysd)
            from silicon_serial import read_apple_serial
            self.local_serial = read_apple_serial()
        except Exception:
            self.local_serial = "UNKNOWN_SERIAL"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>DECENTRALIZED INFERENCE MARKET</b>"))
        header.addStretch()

        self.offer_cb = QCheckBox("Offer My Compute")
        self.offer_cb.setStyleSheet(
            "QCheckBox { color: #9ece6a; font-weight: bold; }"
            "QCheckBox::indicator:checked { background: #9ece6a; }"
        )
        self.offer_cb.stateChanged.connect(self._toggle_offer)
        header.addWidget(self.offer_cb)
        lay.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Node Serial", "Energy", "Cost (STGM)", "Models", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table)

        self.load_market()

    def _toggle_offer(self):
        is_offering = self.offer_cb.isChecked()
        listings = self._read_market()
        if is_offering:
            listings[self.local_serial] = {
                "timestamp": int(time.time()),
                "stgm_price": 1.0,
                "energy": 100,  # Could dynamically read from body state
                "models": ["llama-4-maverick", "qwen3.5:2b", "llama3:latest"]
            }
        else:
            if self.local_serial in listings:
                del listings[self.local_serial]
        
        with open(self.market_file, "w") as f:
            json.dump(listings, f, indent=2)
            
        # NATIVELY PUSH TO THE SWARM GRID SO OTHER NODES SEE IT
        try:
            _git_mesh_commit_push(
                [".sifta_state/marketplace_listings.json"],
                "mesh: marketplace listing updated",
            )
        except Exception:
            pass

        self.load_market()

    def _read_market(self):
        if os.path.exists(self.market_file):
            try:
                with open(self.market_file) as f:
                    return json.load(f)
            except: pass
        return {}

    def load_market(self):
        listings = self._read_market()
        
        # Determine local status
        if self.local_serial in listings:
            self.offer_cb.blockSignals(True)
            self.offer_cb.setChecked(True)
            self.offer_cb.blockSignals(False)
        else:
            self.offer_cb.blockSignals(True)
            self.offer_cb.setChecked(False)
            self.offer_cb.blockSignals(False)

        # Cleanup old listings (older than 1 hour)
        now = int(time.time())
        cleaned = {}
        for k, v in listings.items():
            if now - v.get("timestamp", 0) < 3600:
                cleaned[k] = v
        if len(cleaned) != len(listings):
            with open(self.market_file, "w") as f:
                json.dump(cleaned, f, indent=2)
            listings = cleaned

        self.table.setRowCount(len(listings))
        for row, (serial, data) in enumerate(listings.items()):
            c_ser = QTableWidgetItem(serial + (" (YOU)" if serial == self.local_serial else ""))
            if serial == self.local_serial: c_ser.setForeground(QColor("#9ece6a"))
            
            e_raw = data.get("energy", 100)
            try:
                e_val = int(e_raw)
            except:
                e_val = 100  # Default if string like "M1 Neural Engine..."

            c_eng = QTableWidgetItem(str(e_raw) + ("%" if isinstance(e_raw, (int, float)) else ""))
            if e_val < 30: c_eng.setForeground(QColor("#f7768e"))
            else: c_eng.setForeground(QColor("#7dcfff"))

            c_cst = QTableWidgetItem(f"{data.get('stgm_price', 1.0):.1f}")
            c_mod = QTableWidgetItem(", ".join(data.get("models", [])))
            c_mod.setToolTip(", ".join(data.get("models", [])))

            self.table.setItem(row, 0, c_ser)
            self.table.setItem(row, 1, c_eng)
            self.table.setItem(row, 2, c_cst)
            self.table.setItem(row, 3, c_mod)

            btn = QPushButton("Mine for Me")
            if serial == self.local_serial:
                btn.setEnabled(False)
                btn.setText("Local")
            else:
                btn.setStyleSheet("background-color: #3d59a1; color: white;")
                btn.clicked.connect((lambda s, p: lambda: self.mine_inference(s, p))(serial, data.get('stgm_price', 1.0)))
            self.table.setCellWidget(row, 4, btn)

    def mine_inference(self, target_serial, price):
        reply = QMessageBox.question(self, "Confirm Transaction",
            f"Pay {price} STGM to Node {target_serial} to run your payload?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            # Here it drops STGM_SPEND and writes to the dead drop payload queue.
            try:
                ts = int(time.time())
                import hashlib
                seal_payload = f"{self.local_serial}:{target_serial}:{price}:{ts}"
                # Ed25519 sign — proves this spend was authorized by the genuine hardware
                try:
                    from System.crypto_keychain import sign_block as _sign
                    seal = _sign(seal_payload)
                except Exception:
                    seal = "MARKET_" + hashlib.sha256(seal_payload.encode()).hexdigest()[:12]
                
                # ── UTXO Engine — canonical dual-dialect ledger check ──────────
                local_agent = "M5SIFTA_BODY" if "GTH4921YP3" in self.local_serial else "M1SIFTA_BODY"
                true_balance = ledger_balance(local_agent)

                if true_balance < price:
                    QMessageBox.critical(self, "Insufficient STGM",
                        f"Double-Spend Blocked.\n"
                        f"True UTXO Balance (both dialects): {true_balance}\n"
                        f"Required: {price}")
                    return

                # Debit localhost wallet
                tx_spend = {
                    "timestamp": ts,
                    "agent_id": local_agent,
                    "tx_type": "STGM_SPEND",
                    "amount": float(price),
                    "target_node": target_serial,
                    "reason": "Purchased Inference Compute",
                    "hash": hashlib.sha256(seal_payload.encode()).hexdigest(),
                    "ed25519_sig": seal,
                    "signing_node": self.local_serial,
                }
                append_ledger_line(os.path.join(REPO_ROOT, "repair_log.jsonl"), tx_spend)
                
                # Deduct local balance
                state_file = os.path.join(STATE_DIR, f"{local_agent}.json")
                if os.path.exists(state_file):
                    with open(state_file, "r") as sf:
                        ag = json.load(sf)
                    ag["stgm_balance"] = float(ledger_balance(local_agent))
                    with open(state_file, "w") as sf:
                        json.dump(ag, sf, indent=2)

                # Route to dead drop for multi-node mesh
                drop_payload = {
                    "sender": f"[MARKET_SPEND::{local_agent}::{self.local_serial}]",
                    "target_node": target_serial,
                    "action": "MINE_INFERENCE",
                    "amount": price,
                    "timestamp": ts,
                    "text": f"[{seal}] INFERENCE PURCHASE REQUEST -> Node {target_serial}"
                }
                append_jsonl_line(os.path.join(STATE_DIR, "human_signals.jsonl"), drop_payload)

                # NATIVELY PUSH LEDGER TRANSACTION TO THE SWARM GRID
                try:
                    _git_mesh_commit_push(
                        [".sifta_state/", "repair_log.jsonl"],
                        "mesh: market intelligence purchase tx executed",
                    )
                except Exception:
                    pass

                QMessageBox.information(self, "Success", f"Tx {seal} confirmed.\n{price} STGM spent.\nPayload routed cross-node.")
            except Exception as e:
                QMessageBox.critical(self, "Tx Failed", f"Market error: {e}")

# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("SIFTA Finance")
    w = FinanceDashboard()
    w.resize(700, 600)
    w.show()
    sys.exit(app.exec())
