#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Finance Dashboard
# Robinhood-style view of all Swarm agents: STGM balances,
# energy levels, status. Plus an Install Agent button.
# ─────────────────────────────────────────────────────────────

import sys, json, os, time
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
_kernel = os.path.join(REPO_ROOT, "Kernel")
if _kernel not in sys.path:
    sys.path.insert(0, _kernel)
_sys = os.path.join(REPO_ROOT, "System")
if _sys not in sys.path:
    sys.path.insert(0, _sys)
from System.ledger_append import append_ledger_line, append_jsonl_line
from inference_economy import ledger_balance
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QDialog, QLineEdit,
    QComboBox, QMessageBox, QGridLayout, QProgressBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QAbstractItemView,
    QTextEdit,
)
from System.sifta_base_widget import SiftaBaseWidget
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
            quorum_bal = float(ledger_balance(agent_id))
            data["stgm_balance"] = quorum_bal

            # ── SWARM ENFORCEMENT: ERASING GHOST MONEY ─────────────────────────────────
            # If the Swimmer hallucinates ghost funds in their .json file, the Swarm Finance
            # module aggressively slaps them and overwrites their memory with reality.
            if abs(file_bal - quorum_bal) > 0.0001:
                data["stgm_balance"] = quorum_bal
                try:
                    state_file_path = os.path.join(STATE_DIR, fname)
                    with open(state_file_path, "r") as f:
                        file_data = json.load(f)
                    file_data["stgm_balance"] = quorum_bal
                    with open(state_file_path, "w") as f:
                        json.dump(file_data, f, indent=4)
                    print(f"[{agent_id}] Swarm Firewall active: Ghost STGM erased. Reverting memory to {quorum_bal}.")
                except Exception as e:
                    print(f"Failed to enforce reality on {agent_id}: {e}")

            agents.append(data)
        except Exception as e:
            print(f"Skipping {fname} due to error: {e}")
            import traceback
            traceback.print_exc()
            continue
    # Inject legacy casino surface as play-token-only so Finance never presents
    # gambling/game credits as spendable STGM.
    try:
        from System.casino_vault import CasinoVault
        cv = CasinoVault(architect_id="IOAN_M5")
        agents.append({
            "id": "CASINO_PLAY_TOKENS",
            "stgm_balance": 0.0,
            "stgm_balance_file": 0.0,
            "energy": 100,
            "style": f"[PLAY TOKENS ONLY: HOUSE {cv.casino_balance:.2f}]",
            "homeworld_serial": "GAME_TOKEN_LEDGER",
            "sybil_quarantined": False
        })
        agents.append({
            "id": "ARCHITECT_CANONICAL_WALLET",
            "stgm_balance": cv.get_real_player_wallet(),
            "stgm_balance_file": cv.get_real_player_wallet(),
            "energy": 100,
            "style": "[REPAIR_LOG ONLY]",
            "homeworld_serial": "ARCHITECT_IDENTITY",
            "sybil_quarantined": False
        })
    except Exception as e:
        print(f"Failed to inject Vaults: {e}")

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
            color = "#FF453A"
            face = "[!_!]"
            if stgm > 0:
                style = "GENESIS MISMATCH · QUORUM OK"
            else:
                style = "GENESIS MISMATCH · NO LEDGER CREDITS"

        self.setFixedHeight(72)
        self.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
                border-bottom: 1px solid #1c1c1e;
            }
            QFrame:hover { background: #111112; }
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(16)

        # Round Icon
        face_frame = QFrame()
        face_frame.setFixedSize(44, 44)
        bg_color = f"{color}33" if not is_sybil else "#FF453A22"
        face_frame.setStyleSheet(f"background-color: {bg_color}; border-radius: 22px; border: none;")
        face_lay = QVBoxLayout(face_frame)
        face_lay.setContentsMargins(0,0,0,0)
        face_lbl = QLabel(face)
        face_lbl.setFont(QFont("-apple-system", 11, QFont.Weight.Bold))
        face_lbl.setStyleSheet(f"color: {color}; border: none; background: transparent;")
        face_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        face_lay.addWidget(face_lbl)
        lay.addWidget(face_frame)

        # Info block
        info = QVBoxLayout()
        info.setSpacing(1)
        info.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        name_lbl = QLabel(agent_id.replace("_", " "))
        name_lbl.setFont(QFont("-apple-system", 16, QFont.Weight.DemiBold))
        name_lbl.setStyleSheet(f"color: {'#FFFFFF' if not is_sybil else '#FF453A'}; border: none;")
        info.addWidget(name_lbl)

        style_lbl = QLabel(style.replace("[", "").replace("]", ""))
        style_lbl.setFont(QFont("-apple-system", 13))
        style_lbl.setStyleSheet(f"color: {'#8E8E93' if not is_sybil else '#FF9F0A'}; border: none;")
        if is_sybil and abs(file_claim - stgm) > 0.0001 and file_claim > 0:
             style_lbl.setText(f"{style} (Claims {file_claim:,.1f})")
        info.addWidget(style_lbl)

        lay.addLayout(info)
        lay.addStretch()

        # STGM and Energy
        right_block = QVBoxLayout()
        right_block.setSpacing(1)
        right_block.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        stgm_val = QLabel(f"{stgm:,.2f}")
        stgm_val.setFont(QFont("-apple-system", 16, QFont.Weight.Medium))
        stgm_val.setStyleSheet("color: #FFFFFF; border: none;")
        stgm_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_block.addWidget(stgm_val)

        if is_sybil:
            warn = QLabel("Sybil Detect")
            warn.setFont(QFont("-apple-system", 12))
            warn.setStyleSheet("color: #FF9F0A; border: none;")
            warn.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_block.addWidget(warn)
        else:
            e_lbl = QLabel(f"{energy}% PWR")
            e_lbl.setFont(QFont("-apple-system", 12, QFont.Weight.Medium))
            e_color = "#00C805" if energy > 50 else ("#FF9F0A" if energy > 20 else "#FF453A")
            e_lbl.setStyleSheet(f"color: {e_color}; border: none;")
            e_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_block.addWidget(e_lbl)

        lay.addLayout(right_block)

# ─────────────────────────────────────────────────────────────

class InstallAgentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install New Agent")
        self.setMinimumWidth(360)
        self.setStyleSheet("""
            QDialog   { background: #000000; color: #FFFFFF; font-family: '-apple-system'; }
            QLabel    { color: #8E8E93; font-size: 13px; font-weight: 500; }
            QLineEdit { background: #1c1c1e; border: none; border-radius: 8px; padding: 12px; color: #FFFFFF; font-size: 14px; }
            QComboBox { background: #1c1c1e; border: none; border-radius: 8px; padding: 12px; color: #FFFFFF; font-size: 14px; }
            QPushButton { background: #00C805; color: #000000; border: none; border-radius: 20px; padding: 14px 24px; font-size: 15px; font-weight: bold; }
            QPushButton:hover { background: #00DE06; }
            QPushButton:pressed { background: #00A604; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        lay.addWidget(QLabel("Agent ID (e.g. SCOUT_M5)"))
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("AGENT_NAME")
        lay.addWidget(self.id_input)

        lay.addWidget(QLabel("Role"))
        self.role = QComboBox()
        self.role.addItems(["ACTIVE","SCOUT","REPAIR","MEDIC","WATCHER","DETECTIVE"])
        lay.addWidget(self.role)

        # ── NO FREE STGM AT GENESIS ─────────────────────────────
        # Swimmers are born hungry. They earn STGM by observing the
        # Architect, repairing code, routing inference, and performing
        # useful work. No birth presents. No handouts. No breach.
        # ──────────────────────────────────────────────────────────────

        lay.addSpacing(8)
        btn = QPushButton("Install Agent")
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

class FinanceDashboard(SiftaBaseWidget):
    APP_NAME = "Swarm Finance"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # Override the base SIFTA styles with Finance's specialized Robinhood dark theme
        self.setStyleSheet(self.styleSheet() + """
            QTabWidget::pane { border: none; border-top: 1px solid #1c1c1e; }
            QTabBar::tab { background: transparent; color: #8E8E93; padding: 12px 20px; border: none; font-size: 15px; font-weight: 500; }
            QTabBar::tab:selected { color: #FFFFFF; font-weight: bold; border-bottom: 2px solid #00C805; }
            QTabBar::tab:hover { color: #D1D1D6; }
            QTableWidget { background: #000000; border: none; gridline-color: #1c1c1e; color: #FFFFFF; selection-background-color: #1c1c1e; outline: 0; }
            QHeaderView::section { background: #000000; color: #8E8E93; padding: 12px 8px; border: none; border-bottom: 1px solid #1c1c1e; font-size: 13px; font-weight: 500; text-transform: uppercase; }
        """)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::tab-bar { alignment: center; }")
        self.portfolio_tab = QWidget()
        self.market_tab = MarketplaceTab()
        self.warren_tab = QWidget()
        self.tabs.addTab(self.portfolio_tab, "Portfolio")
        self.tabs.addTab(self.market_tab, "Inference Market")
        self.tabs.addTab(self.warren_tab, "Warren Buffett")
        self._build_warren_tab()
        layout.addWidget(self.tabs)

        self._build_portfolio()
        self.make_timer(5000, self._refresh_all)

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
        self.warren_view.setFont(QFont("Menlo", 12))
        self.warren_view.setStyleSheet(
            "QTextEdit { background: transparent; color: #FFFFFF; border: none; padding: 10px; }"
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
        lay.setContentsMargins(16, 24, 16, 16)
        lay.setSpacing(8)
        
        # ── Portfolio total ──────────────────────────────────
        self.portfolio_lbl = QLabel()
        self.portfolio_lbl.setFont(QFont("-apple-system", 56, QFont.Weight.Light))
        self.portfolio_lbl.setStyleSheet("color: #FFFFFF; letter-spacing: -2px; border: none; padding: 0;")
        lay.addWidget(self.portfolio_lbl)

        sub_header = QHBoxLayout()
        agents_lbl = QLabel("Total Swarm Balance (STGM)")
        agents_lbl.setFont(QFont("-apple-system", 15))
        agents_lbl.setStyleSheet("color: #8E8E93; border: none;")
        sub_header.addWidget(agents_lbl)
        sub_header.addStretch()

        from PyQt6.QtWidgets import QCheckBox
        self.hide_inactive_cb = QCheckBox("Hide inactive")
        self.hide_inactive_cb.setChecked(True)
        self.hide_inactive_cb.setStyleSheet(
            "QCheckBox { color: #8E8E93; font-size: 14px; spacing: 8px; }"
            "QCheckBox::indicator { width: 18px; height: 18px; border: 1.5px solid #8E8E93; border-radius: 9px; }"
            "QCheckBox::indicator:checked { background: #00C805; border-color: #00C805; image: none; }"
        )
        self.hide_inactive_cb.stateChanged.connect(self._refresh_all)
        sub_header.addWidget(self.hide_inactive_cb)

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setStyleSheet("QPushButton{background:transparent; color:#8E8E93; font-size:20px; font-weight:bold; border:none;} QPushButton:hover{color:#FFFFFF;}")
        self.refresh_btn.clicked.connect(self._refresh_all)
        sub_header.addWidget(self.refresh_btn)

        install_btn = QPushButton("  Install Agent  ")
        install_btn.setStyleSheet("QPushButton{background:#1c1c1e; color:#FFFFFF; border:none; border-radius:16px; padding:8px 16px; font-size:14px; font-weight:600;} QPushButton:hover{background:#2c2c2e;}")
        install_btn.clicked.connect(self._install)
        sub_header.addWidget(install_btn)
        
        lay.addLayout(sub_header)
        
        lay.addSpacing(24) # Space between balance and list

        # ── Scroll area for cards ────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;} QScrollBar:vertical{width:5px;background:transparent;} QScrollBar::handle:vertical{background:#333333;border-radius:2px;}")
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

        # Exclude the Casino's independent liquidity pool from the Architect's/Swarm's Total Portfolio metric.
        total_portfolio_agents = [a for a in agents if a.get("id") != "CASINO_VAULT"]
        total = sum(float(a.get("stgm_balance") or 0) for a in total_portfolio_agents)
        self.portfolio_lbl.setText(f"${total:,.2f}")

        if not agents:
            empty = QLabel("All agents inactive. Uncheck 'Hide inactive' to see full history.")
            empty.setStyleSheet("color: #8E8E93; font-size: 14px; padding: 24px;")
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
                display_name = hw_serial if hw_serial != "UNKNOWN_SERIAL" else "Orphans"
                vault_header = QLabel(f"{display_name}")
                
                if hw_serial == local_serial:
                    vault_header.setText(f"{display_name} (Local Node)")
                    vault_header.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 18px; margin-top: 24px; margin-bottom: 12px; border-bottom: 1px solid #1c1c1e; padding-bottom: 8px;")
                elif hw_serial == "SWARM_ORPHANS":
                    vault_header.setStyleSheet("color: #8E8E93; font-weight: 600; font-size: 16px; margin-top: 24px; margin-bottom: 12px; border-bottom: 1px solid #1c1c1e; padding-bottom: 8px;")
                else:
                    vault_header.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 18px; margin-top: 24px; margin-bottom: 12px; border-bottom: 1px solid #1c1c1e; padding-bottom: 8px;")
                
                self.card_lay.addWidget(vault_header)

                for a in swimmers:
                    self.card_lay.addWidget(AgentCard(a))
                
                # Small spacer between entities
                spacer = QWidget()
                spacer.setFixedHeight(8)
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
        title_lbl = QLabel("Inference Market")
        title_lbl.setStyleSheet("font-size: 24px; font-weight: 600; color: #FFFFFF; margin-bottom: 12px;")
        header.addWidget(title_lbl)
        header.addStretch()

        self.offer_cb = QCheckBox("Offer Compute")
        self.offer_cb.setStyleSheet(
            "QCheckBox { color: #8E8E93; font-size: 14px; font-weight: 500; spacing: 8px; }"
            "QCheckBox::indicator { width: 18px; height: 18px; border: 1.5px solid #8E8E93; border-radius: 9px; }"
            "QCheckBox::indicator:checked { background: #00C805; border-color: #00C805; image: none; }"
        )
        self.offer_cb.stateChanged.connect(self._toggle_offer)
        header.addWidget(self.offer_cb)
        lay.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Node", "Power", "Cost", "Models", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
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
                "models": ["llama-4-maverick", "gemma4-phc:latest", "llama3:latest"]
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

            btn = QPushButton("Purchase")
            if serial == self.local_serial:
                btn.setEnabled(False)
                btn.setText("Local")
                btn.setStyleSheet("background: transparent; color: #8E8E93; border: none;")
            else:
                btn.setStyleSheet("QPushButton { background-color: #00C805; color: #000000; border-radius: 14px; font-weight: bold; margin: 4px; } QPushButton:hover { background-color: #00DE06; }")
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
