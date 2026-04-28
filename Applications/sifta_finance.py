#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Finance Dashboard
# Robinhood-style view of all Swarm agents: STGM balances,
# energy levels, status. Plus an Install Agent button.
# ─────────────────────────────────────────────────────────────

import sys, json, os, time
from pathlib import Path
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
    QTextEdit, QSizePolicy,
)
from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_app_focus import publish_focus
from PyQt6.QtCore  import Qt, QTimer, QRectF, QSize
from PyQt6.QtGui   import (
    QFont, QColor, QPainter, QBrush, QPen,
    QLinearGradient, QRadialGradient,
)

# Doctor Sigil chrome (canonical Applications/_doctor_sigil_chrome).
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
try:
    from _doctor_sigil_chrome import doctor_sigil_html
    _HAS_SIGIL = True
except Exception:
    _HAS_SIGIL = False

STATE_DIR   = os.path.join(REPO_ROOT, ".sifta_state")
_GIT_BRANCH = os.environ.get("SIFTA_GIT_BRANCH", "feat/sebastian-video-economy")
REPAIR_LOG = os.path.join(REPO_ROOT, "repair_log.jsonl")

# ── Cinematic palette tuned to match the rest of the polished SIFTA OS ──
_FIN_BG_DEEP   = "#06070f"
_FIN_BG_TOP    = "#0d101e"
_FIN_INK       = "#f1f4ff"
_FIN_INK_DIM   = "#8e94ad"
_FIN_INK_SOFT  = "#5a6184"
_FIN_GREEN     = "#2fd16b"   # GREEN_GROW / positive
_FIN_AMBER     = "#ffb53d"   # YELLOW_THROTTLE / warn
_FIN_RED       = "#ff5a6e"   # RED / sybil / overdraw
_FIN_ACCENT    = "#a86bff"   # CG55M signature accent
_FIN_ACCENT2   = "#7aa2f7"
_FIN_CARD      = "rgba(20, 23, 38, 220)"
_FIN_CARD_HI   = "rgba(28, 32, 50, 240)"
_FIN_BORDER    = "rgba(140, 150, 200, 50)"
_FIN_BORDER_HI = "rgba(168, 107, 255, 110)"


# Global QSS for the Finance dashboard. Deliberately scoped via objectName
# selectors so it only paints widgets we explicitly opt-in.
_FINANCE_QSS = f"""
QWidget#FinanceRoot {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {_FIN_BG_TOP},
        stop:1 {_FIN_BG_DEEP});
}}
QTabWidget#FinanceTabs::pane {{
    border: none;
    border-top: 1px solid rgba(168, 107, 255, 35);
    background: transparent;
}}
QTabWidget#FinanceTabs QTabBar::tab {{
    background: transparent;
    color: {_FIN_INK_DIM};
    padding: 12px 22px;
    border: none;
    font-family: 'SF Pro Text', 'Helvetica Neue', system-ui;
    font-size: 13.5px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}
QTabWidget#FinanceTabs QTabBar::tab:selected {{
    color: {_FIN_INK};
    border-bottom: 2px solid {_FIN_ACCENT};
}}
QTabWidget#FinanceTabs QTabBar::tab:hover {{
    color: #d8dcef;
}}
QFrame#FinStatTile {{
    background: {_FIN_CARD};
    border: 1px solid {_FIN_BORDER};
    border-radius: 12px;
}}
QFrame#FinStatTile:hover {{
    background: {_FIN_CARD_HI};
    border-color: {_FIN_BORDER_HI};
}}
QLabel#FinTileLabel {{
    color: {_FIN_INK_DIM};
    font-family: 'SF Pro Text', 'Helvetica Neue', system-ui;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 1.4px;
}}
QLabel#FinTileValue {{
    color: {_FIN_INK};
    font-family: 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', system-ui;
    font-size: 18px;
    font-weight: 600;
    letter-spacing: 0.2px;
}}
QLabel#FinTileSuffix {{
    color: {_FIN_INK_SOFT};
    font-family: 'SF Pro Text', 'Helvetica Neue', system-ui;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 1.2px;
}}
QPushButton#FinPillBtn {{
    background: rgba(28, 32, 50, 230);
    color: {_FIN_INK};
    border: 1px solid {_FIN_BORDER};
    border-radius: 16px;
    padding: 8px 18px;
    font-family: 'SF Pro Text', 'Helvetica Neue', system-ui;
    font-size: 12.5px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
QPushButton#FinPillBtn:hover {{
    background: rgba(40, 46, 70, 240);
    border-color: {_FIN_BORDER_HI};
}}
QPushButton#FinPillBtn:pressed {{
    background: rgba(20, 24, 38, 255);
}}
QPushButton#FinRefresh {{
    background: transparent;
    color: {_FIN_INK_DIM};
    font-size: 18px;
    font-weight: 600;
    border: 1px solid {_FIN_BORDER};
    border-radius: 16px;
}}
QPushButton#FinRefresh:hover {{
    color: {_FIN_INK};
    border-color: {_FIN_BORDER_HI};
    background: rgba(40, 46, 70, 200);
}}
QCheckBox#FinCheck {{
    color: {_FIN_INK_DIM};
    font-family: 'SF Pro Text', 'Helvetica Neue', system-ui;
    font-size: 12.5px;
    spacing: 8px;
}}
QCheckBox#FinCheck::indicator {{
    width: 18px; height: 18px;
    border: 1.5px solid {_FIN_INK_SOFT};
    border-radius: 9px;
    background: rgba(20, 24, 38, 200);
}}
QCheckBox#FinCheck::indicator:checked {{
    background: {_FIN_ACCENT};
    border-color: {_FIN_ACCENT};
}}
QFrame#FinAgentCard {{
    background: rgba(16, 19, 32, 180);
    border: 1px solid rgba(140, 150, 200, 30);
    border-radius: 12px;
}}
QFrame#FinAgentCard:hover {{
    background: rgba(28, 32, 50, 220);
    border-color: rgba(168, 107, 255, 80);
}}
QFrame#FinAgentCard[localNode="true"] {{
    border-left: 3px solid {_FIN_ACCENT};
    background: rgba(22, 26, 44, 200);
}}
QFrame#FinAgentCard[sybil="true"] {{
    border-left: 3px solid {_FIN_RED};
    background: rgba(40, 18, 22, 200);
}}
QFrame#FinAgentCard[stale="true"] {{
    border: 1px dashed rgba(255, 181, 61, 80);
}}
QScrollArea#FinScroll, QScrollArea#FinScroll > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 6px 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(168, 107, 255, 80);
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(168, 107, 255, 160);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0; background: transparent;
}}
QTableWidget#FinMarketTable {{
    background: transparent;
    border: 1px solid {_FIN_BORDER};
    border-radius: 12px;
    gridline-color: rgba(140, 150, 200, 25);
    color: {_FIN_INK};
    selection-background-color: rgba(168, 107, 255, 60);
    outline: 0;
}}
QTableWidget#FinMarketTable QHeaderView::section {{
    background: rgba(20, 23, 38, 220);
    color: {_FIN_INK_DIM};
    padding: 12px 10px;
    border: none;
    border-bottom: 1px solid {_FIN_BORDER};
    font-family: 'SF Pro Text', 'Helvetica Neue', system-ui;
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 0.8px;
}}
QTextEdit#FinWarrenView {{
    background: rgba(12, 14, 26, 220);
    color: {_FIN_INK};
    border: 1px solid {_FIN_BORDER};
    border-radius: 12px;
    padding: 14px 18px;
    selection-background-color: rgba(168, 107, 255, 80);
}}
"""


def _float(value, default=0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if out != out or out in (float("inf"), float("-inf")):
        return float(default)
    return out


def _fmt_stgm(value: float, precision: int = 4) -> str:
    return f"{_float(value):,.{precision}f} STGM"


def _ledger_balance_map() -> dict[str, float]:
    """Return canonical per-agent balances using the cached economy scan."""
    try:
        from System.stgm_economy import scan_economy

        balances = scan_economy().as_dict().get("canonical_wallet_balances") or {}
        if isinstance(balances, dict):
            return {str(k).upper(): _float(v) for k, v in balances.items()}
    except Exception:
        pass
    return {}


def finance_truth_snapshot() -> dict:
    """Live, investor-safe STGM view for Finance and tests.

    Spendable STGM is repair_log.jsonl quorum only. Memory rewards and casino
    rows are surfaced as separate reputation/play-token ledgers so the UI does
    not accidentally present them as money.
    """
    try:
        from System.stgm_economy import scan_economy

        economy = scan_economy().as_dict()
    except Exception as exc:
        economy = {
            "schema": "SIFTA_CANONICAL_STGM_ECONOMY_UNAVAILABLE",
            "canonical_wallet_sum": 0.0,
            "net_stgm": 0.0,
            "spend": 0.0,
            "canonical_minted": 0.0,
            "inference_fee_volume": 0.0,
            "memory_reward_amount": 0.0,
            "casino_player_net_play_tokens": 0.0,
            "warnings": [f"economy_scan_failed:{type(exc).__name__}"],
            "ts": time.time(),
        }

    try:
        from System.swarm_metabolic_homeostasis import MetabolicHomeostat, MetabolicState

        homeostat = MetabolicHomeostat()
        sampled = homeostat.sample_live()
        # Pin the live wallet pressure to the same canonical sum shown in UI.
        state = MetabolicState(
            usd_burn_24h=sampled.usd_burn_24h,
            local_units_24h=sampled.local_units_24h,
            stgm_balance=_float(economy.get("canonical_wallet_sum")),
        )
        metabolic = homeostat.build_ledger_row(state)
    except Exception as exc:
        metabolic = {
            "mode": "UNKNOWN",
            "budget_multiplier": 0.0,
            "pressure": 0.0,
            "stgm_balance": _float(economy.get("canonical_wallet_sum")),
            "recommendation": f"metabolic_scan_failed:{type(exc).__name__}",
            "ts": time.time(),
        }

    return {
        "schema": "SIFTA_FINANCE_TRUTH_SNAPSHOT_V1",
        "wallet_source": "repair_log.jsonl quorum via Kernel.inference_economy.ledger_balance",
        "economy": economy,
        "metabolic": metabolic,
        "canonical_wallet_sum": _float(economy.get("canonical_wallet_sum")),
        "net_supply": _float(economy.get("net_stgm")),
        "spend": _float(economy.get("spend")),
        "minted": _float(economy.get("canonical_minted")),
        "inference_fee_volume": _float(economy.get("inference_fee_volume")),
        "memory_rewards_reputation": _float(economy.get("memory_reward_amount")),
        "casino_play_tokens": _float(economy.get("casino_player_net_play_tokens")),
        "warnings": list(economy.get("warnings") or []),
        "ts": time.time(),
    }


def local_spend_agent_id(serial: str, state_dir: str = STATE_DIR) -> str:
    """Pick the local wallet agent from live node state, not a hardcoded M5/M1 rule."""
    serial = str(serial or "").strip()
    matches: list[str] = []
    try:
        for fp in Path(state_dir).glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            if str(data.get("homeworld_serial") or "").strip() != serial:
                continue
            aid = str(data.get("id") or fp.stem).strip().upper()
            if aid:
                matches.append(aid)
    except Exception:
        matches = []

    preferred = ("ALICE_M5", "M5SIFTA_BODY", "M1SIFTA_BODY", "LOCAL_PREDATOR")
    for aid in preferred:
        if aid in matches:
            return aid
    if matches:
        return sorted(matches)[0]
    return "LOCAL_PREDATOR"


def _git_mesh_commit_push(rel_paths, message):
    """Stage paths, commit, pull --rebase, push — argv only (no shell)."""
    if os.environ.get("SIFTA_FINANCE_ALLOW_GIT_MESH_PUSH", "").strip().lower() not in {"1", "true", "yes", "on"}:
        print(
            "[Finance] Mesh git push skipped. Set SIFTA_FINANCE_ALLOW_GIT_MESH_PUSH=1 "
            "only after explicit Architect GO."
        )
        return
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
    quorum_balances = _ledger_balance_map()
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
            file_bal = _float(data.get("stgm_balance", 0))
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
            quorum_bal = _float(quorum_balances.get(str(agent_id).upper(), 0.0))
            data["stgm_balance"] = quorum_bal
            data["stgm_cache_drift"] = round(file_bal - quorum_bal, 6)
            data["stgm_truth_source"] = "repair_log.jsonl quorum"
            data["state_file_is_cache"] = True

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
            "sybil_quarantined": False,
            "asset_class": "PLAY_TOKEN",
            "display_only": True,
        })
        agents.append({
            "id": "ARCHITECT_CANONICAL_WALLET",
            "stgm_balance": cv.get_real_player_wallet(),
            "stgm_balance_file": cv.get_real_player_wallet(),
            "energy": 100,
            "style": "[REPAIR_LOG ONLY]",
            "homeworld_serial": "ARCHITECT_IDENTITY",
            "sybil_quarantined": False,
            "asset_class": "SUMMARY",
            "display_only": True,
        })
    except Exception as e:
        print(f"Failed to inject Vaults: {e}")

    agents.sort(key=lambda a: float(a.get("stgm_balance") or 0), reverse=True)
    return agents

# ── New visual widgets (CG55M / Opus 4.7 graphics polish) ───────────────

class _HeroBalance(QWidget):
    """Cinematic hero number: huge weight-light balance + small STGM suffix.

    Pure visual layer. `set_value(canonical_wallet_sum)` is the only way
    money flows in — we never read or compute it ourselves.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        # Allocate enough height for an SF-Pro 64pt number with breathing room.
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def set_value(self, value: float) -> None:
        self._value = _float(value)
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        rect = self.rect()
        # The hero sits over the page gradient; we just draw the text.
        # Format: integer part with thousands separators, then a thinner
        # fractional part, then a smaller "STGM" suffix.
        whole = int(self._value)
        frac = abs(self._value) - abs(whole)
        # 4-decimal precision, padded.
        whole_str = f"{whole:,}"
        frac_str = f"{frac:.4f}"[1:]  # ".XXXX"

        # Pick the largest font that still fits within rect.width().
        # We start at 64 and shrink in steps of 2.
        family = "SF Pro Display"
        font_size = 64
        # Pre-render with a bold weight for the integer part so it has
        # visual weight, and a lighter weight for the fractional part
        # so the value reads cleanly.
        while font_size > 24:
            font_whole = QFont(family, font_size, QFont.Weight.Light)
            font_frac = QFont(family, int(font_size * 0.55),
                              QFont.Weight.Light)
            font_suffix = QFont("SF Pro Text", int(font_size * 0.28),
                                QFont.Weight.DemiBold)
            metrics_w = self.fontMetrics()
            p.setFont(font_whole)
            w_whole = p.fontMetrics().horizontalAdvance(whole_str)
            p.setFont(font_frac)
            w_frac = p.fontMetrics().horizontalAdvance(frac_str)
            p.setFont(font_suffix)
            w_suffix = p.fontMetrics().horizontalAdvance("  STGM")
            total = w_whole + w_frac + w_suffix
            if total <= rect.width() - 8:
                break
            font_size -= 2

        # Baseline aligned roughly at 70% of the hero height.
        baseline = int(rect.height() * 0.74)
        x = 0

        # Integer portion: bright ink.
        p.setFont(font_whole)
        p.setPen(QPen(QColor(_FIN_INK)))
        p.drawText(x, baseline, whole_str)
        x += p.fontMetrics().horizontalAdvance(whole_str)

        # Fractional portion: dimmer ink.
        p.setFont(font_frac)
        p.setPen(QPen(QColor(_FIN_INK_DIM)))
        p.drawText(x, baseline, frac_str)
        x += p.fontMetrics().horizontalAdvance(frac_str)

        # Suffix: small accent caps.
        p.setFont(font_suffix)
        p.setPen(QPen(QColor(_FIN_ACCENT)))
        p.drawText(x, baseline, "  STGM")


class _StatTile(QFrame):
    """Frosted stat tile — label, value, suffix. Drop-in QLabel replacement."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FinStatTile")
        self.setMinimumHeight(72)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)

        self._label = QLabel(label.upper())
        self._label.setObjectName("FinTileLabel")
        lay.addWidget(self._label)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._value = QLabel("—")
        self._value.setObjectName("FinTileValue")
        row.addWidget(self._value)

        self._suffix = QLabel("STGM")
        self._suffix.setObjectName("FinTileSuffix")
        # Align with bottom of the value text.
        self._suffix.setAlignment(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
        )
        self._suffix.setContentsMargins(2, 0, 0, 4)
        row.addWidget(self._suffix)
        row.addStretch()
        lay.addLayout(row)

    def set_value(self, value: float, *, suffix: str = "STGM",
                  precision: int = 4, accent: str | None = None) -> None:
        self._value.setText(f"{_float(value):,.{precision}f}")
        self._suffix.setText(suffix)
        if accent:
            self._value.setStyleSheet(
                f"color: {accent}; font-family: 'SF Pro Display', "
                "'SF Pro Text', 'Helvetica Neue', system-ui; "
                "font-size: 18px; font-weight: 600; letter-spacing: 0.2px;"
            )


class _MetabolicPill(QWidget):
    """Glowing metabolic-mode pill with a slim pressure gauge underneath.

    Pure visual. Driven by `set_state(mode, pressure, budget_mult, recommendation)`
    which is computed from the canonical wallet sum upstream.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = "UNKNOWN"
        self._pressure = 0.0
        self._budget_mult = 0.0
        self._recommendation = "—"
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def set_state(self, mode: str, pressure: float,
                  budget_mult: float, recommendation: str) -> None:
        self._mode = str(mode or "UNKNOWN")
        self._pressure = max(0.0, min(1.0, _float(pressure)))
        self._budget_mult = _float(budget_mult)
        self._recommendation = str(recommendation or "—")
        self.update()

    def _accent(self) -> str:
        if self._mode == "GREEN_GROW":
            return _FIN_GREEN
        if self._mode == "YELLOW_THROTTLE":
            return _FIN_AMBER
        if self._mode == "RED_HALT":
            return _FIN_RED
        return _FIN_INK_DIM

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        rect = self.rect()
        accent = self._accent()
        qcol = QColor(accent)

        # Pill background.
        pill_rect = QRectF(0, 4, rect.width(), 36)
        # Subtle radial halo behind the pill for the active accent.
        halo = QRadialGradient(pill_rect.center(), pill_rect.height() * 1.2)
        halo.setColorAt(0.0, QColor(qcol.red(), qcol.green(), qcol.blue(), 60))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(pill_rect, 14, 14)

        # Pill body.
        p.setBrush(QBrush(QColor(20, 23, 38, 220)))
        p.setPen(QPen(QColor(qcol.red(), qcol.green(), qcol.blue(), 140), 1))
        p.drawRoundedRect(pill_rect, 14, 14)

        # Pulse dot.
        dot_x = pill_rect.x() + 18
        dot_y = pill_rect.y() + pill_rect.height() / 2
        # Halo dot.
        p.setBrush(QBrush(QColor(qcol.red(), qcol.green(), qcol.blue(), 70)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(dot_x - 8, dot_y - 8, 16, 16))
        # Core dot.
        p.setBrush(QBrush(qcol))
        p.drawEllipse(QRectF(dot_x - 4, dot_y - 4, 8, 8))

        # Mode label.
        p.setFont(QFont("SF Pro Text", 12, QFont.Weight.Bold))
        p.setPen(QPen(qcol))
        p.drawText(QRectF(dot_x + 14, pill_rect.y(),
                          pill_rect.width() - dot_x - 18, pill_rect.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   self._mode.replace("_", " "))

        # Right side: pressure × budget summary.
        p.setFont(QFont("SF Pro Text", 11, QFont.Weight.DemiBold))
        p.setPen(QPen(QColor(_FIN_INK_DIM)))
        right_text = (f"pressure {self._pressure:.2f}  ·  "
                      f"budget x{self._budget_mult:.2f}")
        p.drawText(QRectF(pill_rect.x(), pill_rect.y(),
                          pill_rect.width() - 16, pill_rect.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                   right_text)

        # Pressure gauge underneath the pill.
        gauge_y = pill_rect.bottom() + 6
        gauge_rect = QRectF(0, gauge_y, rect.width(), 4)
        p.setBrush(QBrush(QColor(28, 32, 50, 220)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(gauge_rect, 2, 2)
        if self._pressure > 0:
            fill_w = gauge_rect.width() * self._pressure
            grad = QLinearGradient(0, 0, gauge_rect.width(), 0)
            grad.setColorAt(0.0, QColor(_FIN_GREEN))
            grad.setColorAt(0.6, QColor(_FIN_AMBER))
            grad.setColorAt(1.0, QColor(_FIN_RED))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(0, gauge_y, fill_w, 4), 2, 2)

        # Recommendation strap (small italic text below the gauge).
        if self._recommendation and self._recommendation != "—":
            rec = self._recommendation
            if len(rec) > 110:
                rec = rec[:108] + "…"
            p.setFont(QFont("SF Pro Text", 10, QFont.Weight.Normal,
                            italic=True))
            p.setPen(QPen(QColor(_FIN_INK_SOFT)))
            p.drawText(QRectF(2, gauge_y + 8, rect.width() - 4, 14),
                       int(Qt.AlignmentFlag.AlignTop |
                           Qt.AlignmentFlag.AlignLeft),
                       rec)


# ─────────────────────────────────────────────────────────────

class AgentCard(QFrame):
    def __init__(self, agent: dict, local_node: bool = False):
        super().__init__()
        self.agent = agent
        self._local_node = bool(local_node)
        self._build(agent)

    def _build(self, a):
        agent_id = str(a.get("id") or a.get("_key", "?")).upper()
        stgm = float(a.get("stgm_balance") or 0)
        file_claim = float(a.get("stgm_balance_file") or 0)
        cache_drift = _float(a.get("stgm_cache_drift"))
        asset_class = str(a.get("asset_class") or "STGM")
        energy = int(a.get("energy") or 0)
        style = str(a.get("style") or "UNKNOWN")
        face = AGENT_FACES.get(agent_id, "[~_~]")
        color = AGENT_COLORS.get(agent_id, DEFAULT_COLOR)

        is_sybil = bool(a.get("sybil_quarantined", False))
        is_play_token = (asset_class == "PLAY_TOKEN")
        is_summary = (asset_class == "SUMMARY")
        is_stale = abs(cache_drift) > 0.0001 and asset_class == "STGM"

        if is_sybil:
            color = _FIN_RED
            face = "[!_!]"
            if stgm > 0:
                style = "GENESIS MISMATCH · QUORUM OK"
            else:
                style = "GENESIS MISMATCH · NO LEDGER CREDITS"

        # ── Card chrome ─────────────────────────────────────────────
        self.setObjectName("FinAgentCard")
        # Dynamic properties drive the QSS variant. We toggle via
        # setProperty + style().polish() so re-styling works after
        # resize/refresh cycles.
        self.setProperty("localNode", "true" if self._local_node else "false")
        self.setProperty("sybil", "true" if is_sybil else "false")
        self.setProperty("stale", "true" if is_stale else "false")
        self.setMinimumHeight(78)
        self.setMaximumHeight(96)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 18, 10)
        lay.setSpacing(14)

        # ── Round avatar with a soft halo behind it ────────────────
        face_frame = QFrame()
        face_frame.setFixedSize(46, 46)
        bg_color = f"{color}33" if not is_sybil else "rgba(255, 90, 110, 60)"
        face_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg_color}; "
            f"border-radius: 23px; border: 1px solid {color}55; }}"
        )
        face_lay = QVBoxLayout(face_frame)
        face_lay.setContentsMargins(0, 0, 0, 0)
        face_lbl = QLabel(face)
        face_lbl.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        face_lbl.setStyleSheet(
            f"color: {color}; border: none; background: transparent;"
        )
        face_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        face_lay.addWidget(face_lbl)
        lay.addWidget(face_frame)

        # ── Info block (name + style line) ─────────────────────────
        info = QVBoxLayout()
        info.setSpacing(2)
        info.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_lbl = QLabel(agent_id.replace("_", " "))
        name_lbl.setFont(QFont("SF Pro Text", 14, QFont.Weight.DemiBold))
        name_lbl.setStyleSheet(
            f"color: {_FIN_RED if is_sybil else _FIN_INK}; "
            "border: none; background: transparent; letter-spacing: 0.2px;"
        )
        name_row.addWidget(name_lbl)
        # Tiny "LOCAL" badge if this is the local-node row.
        if self._local_node:
            local_badge = QLabel("LOCAL")
            local_badge.setFont(QFont("SF Pro Text", 9, QFont.Weight.Bold))
            local_badge.setStyleSheet(
                f"color: {_FIN_ACCENT}; "
                f"background: rgba(168, 107, 255, 50); "
                "border: 1px solid rgba(168, 107, 255, 110); "
                "border-radius: 7px; padding: 1px 6px; "
                "letter-spacing: 1.2px;"
            )
            name_row.addWidget(local_badge)
        # Tiny "PLAY" or "SUMMARY" badge for non-spendable rows.
        if is_play_token or is_summary:
            badge_text = "PLAY" if is_play_token else "SUMMARY"
            badge = QLabel(badge_text)
            badge.setFont(QFont("SF Pro Text", 9, QFont.Weight.Bold))
            badge.setStyleSheet(
                f"color: {_FIN_AMBER}; "
                f"background: rgba(255, 181, 61, 40); "
                "border: 1px solid rgba(255, 181, 61, 100); "
                "border-radius: 7px; padding: 1px 6px; "
                "letter-spacing: 1.2px;"
            )
            name_row.addWidget(badge)
        if is_stale:
            stale_badge = QLabel("CACHE")
            stale_badge.setFont(QFont("SF Pro Text", 9, QFont.Weight.Bold))
            stale_badge.setStyleSheet(
                f"color: {_FIN_AMBER}; "
                "background: rgba(255, 181, 61, 30); "
                "border: 1px dashed rgba(255, 181, 61, 110); "
                "border-radius: 7px; padding: 1px 6px; "
                "letter-spacing: 1.2px;"
            )
            name_row.addWidget(stale_badge)
        name_row.addStretch()
        info.addLayout(name_row)

        style_text = style.replace("[", "").replace("]", "")
        if asset_class != "STGM":
            style_text = f"{style_text} · {asset_class}"
        elif is_stale:
            style_text = f"{style_text} · cache claims {file_claim:,.4f}"
        style_lbl = QLabel(style_text)
        style_lbl.setFont(QFont("SF Pro Text", 11))
        style_lbl.setStyleSheet(
            f"color: {_FIN_AMBER if is_sybil else _FIN_INK_DIM}; "
            "border: none; background: transparent;"
        )
        info.addWidget(style_lbl)
        lay.addLayout(info)
        lay.addStretch()

        # ── STGM and Energy ─────────────────────────────────────────
        right_block = QVBoxLayout()
        right_block.setSpacing(2)
        right_block.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )

        stgm_val = QLabel(_fmt_stgm(stgm, 4))
        stgm_val.setFont(QFont("SF Pro Display", 15, QFont.Weight.Medium))
        stgm_val.setStyleSheet(
            f"color: {_FIN_INK}; border: none; background: transparent; "
            "letter-spacing: 0.1px;"
        )
        stgm_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_block.addWidget(stgm_val)

        if is_sybil:
            warn = QLabel("Sybil Detect")
            warn.setFont(QFont("SF Pro Text", 10, QFont.Weight.Bold))
            warn.setStyleSheet(
                f"color: {_FIN_AMBER}; border: none; background: transparent; "
                "letter-spacing: 0.6px;"
            )
            warn.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_block.addWidget(warn)
        else:
            e_lbl = QLabel(f"{energy}%  PWR")
            e_lbl.setFont(QFont("SF Pro Text", 10, QFont.Weight.DemiBold))
            e_color = (_FIN_GREEN if energy > 50
                       else (_FIN_AMBER if energy > 20 else _FIN_RED))
            e_lbl.setStyleSheet(
                f"color: {e_color}; border: none; background: transparent; "
                "letter-spacing: 0.6px;"
            )
            e_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_block.addWidget(e_lbl)

        lay.addLayout(right_block)

# ─────────────────────────────────────────────────────────────

class InstallAgentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install New Agent")
        self.setMinimumWidth(380)
        self.setStyleSheet(f"""
            QDialog   {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {_FIN_BG_TOP}, stop:1 {_FIN_BG_DEEP});
                color: {_FIN_INK};
                font-family: 'SF Pro Text', 'Helvetica Neue', system-ui;
            }}
            QLabel    {{
                color: {_FIN_INK_DIM}; font-size: 11px; font-weight: 700;
                letter-spacing: 1.2px;
            }}
            QLineEdit {{
                background: rgba(20, 23, 38, 220);
                border: 1px solid {_FIN_BORDER};
                border-radius: 10px; padding: 12px;
                color: {_FIN_INK}; font-size: 14px;
                selection-background-color: rgba(168, 107, 255, 80);
            }}
            QLineEdit:focus {{ border-color: {_FIN_ACCENT}; }}
            QComboBox {{
                background: rgba(20, 23, 38, 220);
                border: 1px solid {_FIN_BORDER};
                border-radius: 10px; padding: 12px;
                color: {_FIN_INK}; font-size: 14px;
            }}
            QComboBox:focus {{ border-color: {_FIN_ACCENT}; }}
            QPushButton {{
                background: {_FIN_ACCENT}; color: #ffffff; border: none;
                border-radius: 22px; padding: 12px 24px;
                font-size: 14px; font-weight: 700; letter-spacing: 0.4px;
            }}
            QPushButton:hover  {{ background: #b97aff; }}
            QPushButton:pressed {{ background: #8a52e3; }}
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
        # Apply the Finance palette QSS on top of whatever the base widget
        # set. Selectors are scoped via objectName so we do not override
        # other apps that share this widget tree.
        self.setObjectName("FinanceRoot")
        self.setStyleSheet(self.styleSheet() + _FINANCE_QSS)

        # ── Doctor Sigil header ─────────────────────────────────────
        if _HAS_SIGIL:
            try:
                sigil = QLabel(doctor_sigil_html(
                    doctors=["C55M", "CG55M", "AG31"],
                    title="Swarm Finance",
                    subtitle="Canonical STGM · repair_log.jsonl quorum",
                ))
                sigil.setTextFormat(Qt.TextFormat.RichText)
                sigil.setWordWrap(True)
                sigil.setStyleSheet(
                    "QLabel { padding: 12px 22px 6px 22px; "
                    "background: transparent; border: none; }"
                )
                layout.addWidget(sigil)
            except Exception:
                pass

        # ── Tabs ────────────────────────────────────────────────────
        self.details_loaded = False
        self._detail_refresh_tick = 0
        self.tabs = QTabWidget()
        self.tabs.setObjectName("FinanceTabs")
        self.tabs.setStyleSheet("QTabWidget::tab-bar { alignment: left; }")
        self.portfolio_tab = QWidget()
        self.market_tab = MarketplaceTab()
        self.warren_tab = QWidget()
        self.tabs.addTab(self.portfolio_tab, "Portfolio")
        self.tabs.addTab(self.market_tab, "Inference Market")
        self.tabs.addTab(self.warren_tab, "Warren Buffett")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._build_warren_tab()
        layout.addWidget(self.tabs)

        self._build_portfolio()
        self.make_timer(5000, self._refresh_all)

    def _on_tab_changed(self, index: int) -> None:
        tab_name = ["Portfolio", "Inference Market", "Warren Buffett"][index] if 0 <= index <= 2 else "Unknown"
        try:
            publish_focus(
                self.APP_NAME,
                f"Viewing Swarm Finance - {tab_name}",
                tab=tab_name
            )
        except Exception:
            pass

    def _build_warren_tab(self):
        wl = QVBoxLayout(self.warren_tab)
        wl.setContentsMargins(18, 18, 18, 18)
        wl.setSpacing(10)

        # Hero header with a subtle "OBSERVE-ONLY" badge.
        hero_row = QHBoxLayout()
        hero_row.setSpacing(10)
        title = QLabel("Warren Buffett")
        title.setFont(QFont("SF Pro Display", 18, QFont.Weight.DemiBold))
        title.setStyleSheet(
            f"color: {_FIN_INK}; border: none; letter-spacing: 0.2px;"
        )
        hero_row.addWidget(title)
        observe_badge = QLabel("OBSERVE-ONLY")
        observe_badge.setFont(QFont("SF Pro Text", 9, QFont.Weight.Bold))
        observe_badge.setStyleSheet(
            f"color: {_FIN_GREEN}; "
            "background: rgba(47, 209, 107, 40); "
            "border: 1px solid rgba(47, 209, 107, 110); "
            "border-radius: 7px; padding: 2px 8px; "
            "letter-spacing: 1.4px;"
        )
        hero_row.addWidget(observe_badge)
        hero_row.addStretch()
        wl.addLayout(hero_row)

        hdr = QLabel(
            "Reads <code>repair_log.jsonl</code>; never mints. Estimates power vs "
            "STGM (optional USD peg via <code>SIFTA_STGM_USD_PEG</code>)."
        )
        hdr.setWordWrap(True)
        hdr.setStyleSheet(
            f"color: {_FIN_INK_DIM}; font-family: 'SF Pro Text', "
            "'Helvetica Neue', system-ui; font-size: 12px; "
            "letter-spacing: 0.2px;"
        )
        wl.addWidget(hdr)

        self.warren_view = QTextEdit()
        self.warren_view.setObjectName("FinWarrenView")
        self.warren_view.setReadOnly(True)
        # Menlo at 12 with a tighter line for accountant feel.
        f = QFont("Menlo", 12)
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.warren_view.setFont(f)
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
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(12)

        # ── Hero balance ────────────────────────────────────────────
        hero_label = QLabel("Spendable canonical wallet sum".upper())
        hero_label.setStyleSheet(
            f"color: {_FIN_INK_SOFT}; "
            "font-family: 'SF Pro Text', 'Helvetica Neue', system-ui; "
            "font-size: 10.5px; font-weight: 700; letter-spacing: 1.6px; "
            "border: none; background: transparent;"
        )
        lay.addWidget(hero_label)
        self.hero_balance = _HeroBalance()
        lay.addWidget(self.hero_balance)

        # ── Metabolic pill (pressure + budget mult) ────────────────
        self.metabolic_pill = _MetabolicPill()
        lay.addWidget(self.metabolic_pill)

        # ── Stat tiles row (Minted / Spent / Net / Memory / Casino) ─
        tile_row = QHBoxLayout()
        tile_row.setSpacing(10)
        self.tile_minted = _StatTile("Minted")
        self.tile_spent = _StatTile("Spent")
        self.tile_net = _StatTile("Net Supply")
        self.tile_memory = _StatTile("Memory Reputation")
        self.tile_play = _StatTile("Casino Play Tokens")
        for t in (
            self.tile_minted, self.tile_spent, self.tile_net,
            self.tile_memory, self.tile_play,
        ):
            tile_row.addWidget(t)
        lay.addLayout(tile_row)

        # ── Truth source line (small, under the tiles) ─────────────
        self.truth_lbl = QLabel()
        self.truth_lbl.setWordWrap(True)
        self.truth_lbl.setStyleSheet(
            f"color: {_FIN_INK_SOFT}; "
            "font-family: 'SF Pro Text', 'Helvetica Neue', system-ui; "
            "font-size: 11px; font-style: italic; "
            "letter-spacing: 0.4px; "
            "border: none; background: transparent;"
        )
        lay.addWidget(self.truth_lbl)

        # ── Sub-header row: vault list label + controls ────────────
        sub_header = QHBoxLayout()
        sub_header.setSpacing(10)
        agents_lbl = QLabel("Vaults · Spendable STGM by hardware")
        agents_lbl.setFont(QFont("SF Pro Text", 13, QFont.Weight.DemiBold))
        agents_lbl.setStyleSheet(
            f"color: {_FIN_INK_DIM}; border: none; background: transparent; "
            "letter-spacing: 0.4px;"
        )
        sub_header.addWidget(agents_lbl)
        sub_header.addStretch()

        self.details_status_lbl = QLabel("Basics loaded first · expanded stream paused")
        self.details_status_lbl.setStyleSheet(
            f"color: {_FIN_INK_SOFT}; border: none; background: transparent;"
        )
        sub_header.addWidget(self.details_status_lbl)

        self.more_data_btn = QPushButton("More Financial Data")
        self.more_data_btn.setObjectName("FinPillBtn")
        self.more_data_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_data_btn.clicked.connect(self._load_more_financial_data)
        sub_header.addWidget(self.more_data_btn)

        self.hide_inactive_cb = QCheckBox("Hide inactive")
        self.hide_inactive_cb.setObjectName("FinCheck")
        self.hide_inactive_cb.setChecked(True)
        self.hide_inactive_cb.stateChanged.connect(self._refresh_all)
        sub_header.addWidget(self.hide_inactive_cb)

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setObjectName("FinRefresh")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setToolTip("Refresh canonical wallet sum from quorum")
        self.refresh_btn.clicked.connect(self._refresh_all)
        sub_header.addWidget(self.refresh_btn)

        install_btn = QPushButton("Install Agent")
        install_btn.setObjectName("FinPillBtn")
        install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        install_btn.clicked.connect(self._install)
        sub_header.addWidget(install_btn)

        lay.addLayout(sub_header)
        lay.addSpacing(2)

        # ── Scroll area for vault + agent cards ────────────────────
        scroll = QScrollArea()
        scroll.setObjectName("FinScroll")
        scroll.setWidgetResizable(True)
        self.card_container = QWidget()
        self.card_container.setStyleSheet("background:transparent;")
        self.card_lay = QVBoxLayout(self.card_container)
        self.card_lay.setSpacing(8)
        self.card_lay.setContentsMargins(0, 0, 4, 0)
        scroll.setWidget(self.card_container)
        lay.addWidget(scroll, 1)

        self._refresh_basics()
        self._show_details_placeholder()

    def _clear_cards(self):
        while self.card_lay.count():
            item = self.card_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_details_placeholder(self):
        self._clear_cards()
        empty = QLabel("Click More Financial Data to load vaults, agents, market, and Warren reports.")
        empty.setStyleSheet(
            f"color: {_FIN_INK_DIM}; font-size: 13px; "
            "padding: 24px; background: transparent; border: none;"
        )
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_lay.addWidget(empty)
        self.card_lay.addStretch()

    def _refresh_basics(self):
        truth = finance_truth_snapshot()
        metabolic = truth["metabolic"]
        total = truth["canonical_wallet_sum"]

        self.hero_balance.set_value(total)
        self.tile_minted.set_value(truth["minted"], precision=4)
        self.tile_spent.set_value(truth["spend"], precision=4,
                                  accent=_FIN_AMBER)
        self.tile_net.set_value(truth["net_supply"], precision=4,
                                accent=_FIN_GREEN)
        self.tile_memory.set_value(truth["memory_rewards_reputation"],
                                   precision=4, suffix="REP")
        self.tile_play.set_value(truth["casino_play_tokens"],
                                 precision=4, suffix="PLAY")

        warns = truth.get("warnings") or []
        warn_str = ""
        if warns:
            warn_str = " · ⚠ " + ", ".join(str(w) for w in warns[:3])
        self.truth_lbl.setText(
            "Source: repair_log.jsonl quorum via cached scan_economy()"
            f"{warn_str}"
        )

        mode = str(metabolic.get("mode", "UNKNOWN"))
        self.metabolic_pill.set_state(
            mode=mode,
            pressure=_float(metabolic.get("pressure")),
            budget_mult=_float(metabolic.get("budget_multiplier")),
            recommendation=str(metabolic.get("recommendation", "")),
        )

    def _load_more_financial_data(self):
        self.details_loaded = True
        self.more_data_btn.setText("Financial Data Loaded")
        self.details_status_lbl.setText("Expanded stream active · throttled")
        self._populate_portfolio()

    def _populate_portfolio(self):
        self._clear_cards()
        self._refresh_basics()

        agents = load_agents()
        hide_inactive = self.hide_inactive_cb.isChecked()
        if hide_inactive:
            agents = [a for a in agents if int(a.get("energy") or 0) > 0
                      or a.get("display_only")]

        if not agents:
            empty = QLabel(
                "All agents inactive. Uncheck 'Hide inactive' to see full history."
            )
            empty.setStyleSheet(
                f"color: {_FIN_INK_DIM}; font-size: 13px; "
                "padding: 24px; background: transparent; border: none;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_lay.addWidget(empty)
        else:
            # Group by Hardware Entity (homeworld_serial). Preserve the
            # sort order from load_agents so the highest-balance vault
            # surfaces first.
            entities: dict[str, list[dict]] = {}
            for a in agents:
                hw = str(a.get("homeworld_serial") or "SWARM_ORPHANS")
                entities.setdefault(hw, []).append(a)

            # Determine local serial to highlight the local node — same
            # subprocess approach Codex left in place.
            try:
                import subprocess
                ioreg = subprocess.run(
                    ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True, text=True, timeout=5,
                )
                local_serial = "UNKNOWN_SERIAL"
                for line in ioreg.stdout.splitlines():
                    if "IOPlatformSerialNumber" in line:
                        local_serial = line.split('"')[-2].strip()
                        break
            except Exception:
                local_serial = "UNKNOWN_SERIAL"

            for hw_serial, swimmers in entities.items():
                if not swimmers:
                    continue

                vault_stgm = sum(
                    float(x.get("stgm_balance") or 0) for x in swimmers
                )
                is_local = (hw_serial == local_serial)
                is_orphans = (hw_serial == "SWARM_ORPHANS")
                display_name = (
                    "Orphans" if hw_serial == "UNKNOWN_SERIAL"
                    else hw_serial
                )

                # Vault header card with a colored dot and a vault total.
                self.card_lay.addWidget(
                    self._make_vault_header(
                        display_name=display_name,
                        is_local=is_local,
                        is_orphans=is_orphans,
                        vault_stgm=vault_stgm,
                        agent_count=len(swimmers),
                    )
                )

                for a in swimmers:
                    self.card_lay.addWidget(
                        AgentCard(a, local_node=is_local)
                    )

                spacer = QWidget()
                spacer.setFixedHeight(8)
                self.card_lay.addWidget(spacer)

        self.card_lay.addStretch()

    def _make_vault_header(self, *, display_name: str, is_local: bool,
                           is_orphans: bool, vault_stgm: float,
                           agent_count: int) -> QFrame:
        """Frosted vault header with a colored dot, label, count, and total."""
        f = QFrame()
        f.setStyleSheet(
            "QFrame { background: transparent; border: none; "
            "border-bottom: 1px solid rgba(140, 150, 200, 30); }"
        )
        row = QHBoxLayout(f)
        row.setContentsMargins(4, 14, 6, 6)
        row.setSpacing(10)

        if is_local:
            dot_color = _FIN_ACCENT
        elif is_orphans:
            dot_color = _FIN_INK_SOFT
        else:
            dot_color = _FIN_ACCENT2

        # Pulse dot.
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {dot_color}; font-size: 14px; "
            "border: none; background: transparent;"
        )
        row.addWidget(dot)

        title = QLabel(display_name)
        title.setFont(QFont("SF Pro Text", 14, QFont.Weight.DemiBold))
        title.setStyleSheet(
            f"color: {_FIN_INK if not is_orphans else _FIN_INK_DIM}; "
            "border: none; background: transparent; letter-spacing: 0.3px;"
        )
        row.addWidget(title)

        if is_local:
            local_badge = QLabel("LOCAL NODE")
            local_badge.setFont(QFont("SF Pro Text", 9, QFont.Weight.Bold))
            local_badge.setStyleSheet(
                f"color: {_FIN_ACCENT}; "
                f"background: rgba(168, 107, 255, 50); "
                "border: 1px solid rgba(168, 107, 255, 110); "
                "border-radius: 7px; padding: 1px 8px; "
                "letter-spacing: 1.4px;"
            )
            row.addWidget(local_badge)

        count_lbl = QLabel(
            f"{agent_count} agent{'s' if agent_count != 1 else ''}"
        )
        count_lbl.setStyleSheet(
            f"color: {_FIN_INK_SOFT}; font-size: 11px; "
            "border: none; background: transparent; letter-spacing: 0.2px;"
        )
        row.addWidget(count_lbl)

        row.addStretch()

        total_lbl = QLabel(_fmt_stgm(vault_stgm, 4))
        total_lbl.setFont(QFont("SF Pro Display", 13, QFont.Weight.Medium))
        total_lbl.setStyleSheet(
            f"color: {_FIN_INK}; border: none; background: transparent; "
            "letter-spacing: 0.2px;"
        )
        row.addWidget(total_lbl)

        return f

    def _refresh_all(self, *_):
        self._detail_refresh_tick += 1
        if not self.details_loaded:
            self._refresh_basics()
            return
        if self._detail_refresh_tick % 3 == 0:
            self._populate_portfolio()
            self.market_tab.load_market()
            self._refresh_warren()
        else:
            self._refresh_basics()

    def _install(self):
        dlg = InstallAgentDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.details_loaded = True
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
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        title_lbl = QLabel("Inference Market")
        title_lbl.setFont(QFont("SF Pro Display", 18, QFont.Weight.DemiBold))
        title_lbl.setStyleSheet(
            f"color: {_FIN_INK}; border: none; background: transparent; "
            "letter-spacing: 0.3px;"
        )
        header.addWidget(title_lbl)

        sub_lbl = QLabel("STGM-priced compute · live mesh listings")
        sub_lbl.setStyleSheet(
            f"color: {_FIN_INK_DIM}; font-size: 11px; "
            "border: none; background: transparent; "
            "letter-spacing: 0.4px; margin-left: 6px;"
        )
        header.addWidget(sub_lbl)
        header.addStretch()

        self.offer_cb = QCheckBox("Offer Compute")
        self.offer_cb.setObjectName("FinCheck")
        self.offer_cb.stateChanged.connect(self._toggle_offer)
        header.addWidget(self.offer_cb)
        lay.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("FinMarketTable")
        self.table.setHorizontalHeaderLabels(
            ["Node", "Power", "Cost", "Models", "Action"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        lay.addWidget(self.table)

        self.load_market()

    def _toggle_offer(self):
        is_offering = self.offer_cb.isChecked()
        listings = self._read_market()
        if is_offering:
            # Query live Ollama for real model list
            offer_models = []
            try:
                import urllib.request as _ur
                _req = _ur.Request("http://127.0.0.1:11434/api/tags")
                with _ur.urlopen(_req, timeout=3) as _resp:
                    _tags = json.loads(_resp.read())
                    offer_models = [m["name"] for m in _tags.get("models", [])]
            except Exception:
                offer_models = ["qwen3.5:2b"]
            listings[self.local_serial] = {
                "timestamp": int(time.time()),
                "stgm_price": 1.0,
                "energy": 100,
                "models": offer_models
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
            price_stgm = _float(data.get("stgm_price"), 1.0)
            is_local = (serial == self.local_serial)

            c_ser = QTableWidgetItem(
                serial + ("  · YOU" if is_local else "")
            )
            c_ser.setForeground(
                QColor(_FIN_ACCENT) if is_local else QColor(_FIN_INK)
            )
            c_ser.setFont(QFont("SF Pro Text", 12, QFont.Weight.DemiBold))

            e_raw = data.get("energy", 100)
            try:
                e_val = int(e_raw)
            except Exception:
                e_val = 100

            c_eng = QTableWidgetItem(
                str(e_raw) + ("%" if isinstance(e_raw, (int, float)) else "")
            )
            if e_val < 30:
                c_eng.setForeground(QColor(_FIN_RED))
            elif e_val < 60:
                c_eng.setForeground(QColor(_FIN_AMBER))
            else:
                c_eng.setForeground(QColor(_FIN_GREEN))
            c_eng.setFont(QFont("SF Pro Text", 12, QFont.Weight.DemiBold))

            c_cst = QTableWidgetItem(_fmt_stgm(price_stgm, 4))
            c_cst.setForeground(QColor(_FIN_INK))
            c_cst.setFont(QFont("SF Pro Display", 12, QFont.Weight.Medium))

            models_text = ", ".join(data.get("models", []))
            c_mod = QTableWidgetItem(models_text)
            c_mod.setForeground(QColor(_FIN_INK_DIM))
            c_mod.setToolTip(models_text)

            self.table.setItem(row, 0, c_ser)
            self.table.setItem(row, 1, c_eng)
            self.table.setItem(row, 2, c_cst)
            self.table.setItem(row, 3, c_mod)

            btn = QPushButton("Purchase")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if is_local:
                btn.setEnabled(False)
                btn.setText("Local")
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; "
                    f"color: {_FIN_INK_SOFT}; border: 1px dashed "
                    "rgba(140, 150, 200, 60); border-radius: 12px; "
                    "padding: 6px 14px; font-weight: 600; margin: 6px; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {_FIN_ACCENT}; "
                    "color: #ffffff; border-radius: 14px; "
                    "font-family: 'SF Pro Text', 'Helvetica Neue', system-ui; "
                    "font-size: 12px; font-weight: 700; "
                    "letter-spacing: 0.4px; margin: 6px; padding: 6px 16px; "
                    "border: 1px solid rgba(255, 255, 255, 30); }}"
                    "QPushButton:hover { background-color: #b97aff; } "
                    "QPushButton:pressed { background-color: #8a52e3; }"
                )
                btn.clicked.connect(
                    (lambda s, p: lambda: self.mine_inference(s, p))(
                        serial, price_stgm
                    )
                )
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
                local_agent = local_spend_agent_id(self.local_serial)
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
