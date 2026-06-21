#!/usr/bin/env python3
"""
Applications/sifta_hermes_parity_widget.py
═══════════════════════════════════════════════════════════════════════
StigAuth: SIFTA_HERMES_PARITY_V1

Pure-Python conversion of the pywebview "white window" (`System/sifta_app.py`
+ `System/sifta_app_ui.html`) into a single PyQt6 MDI widget that lives
inside `sifta_os_desktop.py`.

Per IDE_BOOT_COVENANT.md:
  §7.5 Python-first surface — no HTML/JS hop. Same process, same gaze.
  §7.6 Alice IS the OS — this widget does NOT spawn a second LLM chat.
       Owner natural-language input is published as app_focus so Alice's
       resident Talk widget hears it; this widget invokes tools directly
       (keyword fast path) and surfaces every receipt, but never owns a
       brain conversation thread.
  §7.6.2 One window per app — class-level `_live_instance` singleton.
  §4.5 Visible work is first-person to Alice and George; no detached
       narration. The widget's chat log is just literal action receipts.

What this widget gives George:
  - Status bar (chain head · STGM balance · tools count · owner chip).
  - Tools row — every entry in `swarm_tool_router.TOOL_REGISTRY` as a
    clickable pill. Click a tool to drop a starter command into the
    Talk input ("tool_name "). Hit Enter to invoke.
  - Talk input (keyword fast-path only — `run`, `read`, `list`,
    `search`, `fetch`, `write`, plus `?TOOL` for spec, `list` for
    tool index, `help` for vocab). Anything else publishes focus and
    nudges George to use the OS Talk widget (§7.6 item 2).
  - Receipts column — live tail of every known organ trace.
  - Skills card — pull from URL / marketplace, extract from trace,
    library status — same surface George has elsewhere, here as a
    convenient receipted panel.
  - Verify all chains button — calls each organ's verify_chain() and
    reports.

What this widget intentionally does NOT do:
  - No HTML, no JS, no pywebview.
  - No second LLM brain. The Talk input falls through to "publish focus
    and ask Alice in her main Talk widget" for non-keyword text.
  - No new conversation ledger. Everything routes through the existing
    receipted boundaries (tool router, STGM, skill library).

Truth label: ``SIFTA_HERMES_PARITY_V1``.
Doctor: CW47 (Cowork), signed in at trace_id
        075a30c6-3d72-4c3e-81d3-3c6990326ab2 (2026-05-16T13:03:52Z).
"""
from __future__ import annotations

"""SIFTA Hermes Parity Widget — stigmergic organ for Alice body."""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_SYS = _REPO / "System"
if _SYS.exists() and str(_SYS) not in sys.path:
    sys.path.insert(0, str(_SYS))

# ── Soft-import everything; the widget loads even when an organ is missing.
try:
    import swarm_tool_router as _router  # type: ignore
except Exception:  # pragma: no cover
    _router = None  # type: ignore

try:
    import swarm_stgm_billing as _stgm  # type: ignore
except Exception:  # pragma: no cover
    _stgm = None  # type: ignore

try:
    import swarm_skill_library as _skill_lib  # type: ignore
except Exception:  # pragma: no cover
    try:
        from System import swarm_skill_library as _skill_lib  # type: ignore
    except Exception:
        _skill_lib = None  # type: ignore

# Unified Capability Registry — tools + skills as one field for Alice + UI.
try:
    import swarm_capability_registry as _capabilities  # type: ignore
except Exception:  # pragma: no cover
    try:
        from System import swarm_capability_registry as _capabilities  # type: ignore
    except Exception:
        _capabilities = None  # type: ignore

try:
    from System.swarm_app_focus import publish_focus as _publish_focus  # type: ignore
except Exception:  # pragma: no cover
    _publish_focus = None  # type: ignore

TRUTH_LABEL = "SIFTA_HERMES_PARITY_V1"
_STATE = _REPO / ".sifta_state"

# ── SIFTA / Tokyo Night palette — matches Organism Doctor + Talk widget.
# Dark gradient root, soft purple accents, lavender text. The widget
# inherits BeeSon's visual identity instead of inventing a new theme.
_HERMES_QSS = """
QWidget#HermesParityRoot {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0d101e, stop:1 #06070f);
    color: #f1f4ff;
}
QLabel { color: #f1f4ff; }
QLabel#HermesStatusChip {
    color: #f1f4ff;
    background: rgba(168, 107, 255, 35);
    border: 1px solid rgba(168, 107, 255, 90);
    border-radius: 10px;
    padding: 3px 10px;
    font-family: 'Menlo';
    font-size: 11px;
    letter-spacing: 0.2px;
}
QLabel#HermesSectionTitle {
    color: #8e94ad;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.4px;
    padding: 2px 0 4px 0;
}
QFrame#HermesSection {
    background: rgba(20, 23, 38, 220);
    border: 1px solid rgba(140, 150, 200, 50);
    border-radius: 12px;
}
QTextEdit#HermesChatLog, QListWidget#HermesReceipts, QListWidget#HermesSkillStatus {
    background: rgba(13, 16, 30, 200);
    color: #f1f4ff;
    border: 1px solid rgba(140, 150, 200, 35);
    border-radius: 8px;
    padding: 4px;
    font-family: 'Menlo';
    font-size: 11px;
    selection-background-color: rgba(168, 107, 255, 80);
}
QListWidget#HermesReceipts::item:alternate {
    background: rgba(22, 26, 44, 200);
}
QLineEdit {
    background: rgba(13, 16, 30, 200);
    color: #f1f4ff;
    border: 1px solid rgba(140, 150, 200, 60);
    border-radius: 6px;
    padding: 6px 8px;
    font-family: 'Menlo';
    font-size: 11px;
    selection-background-color: rgba(168, 107, 255, 80);
}
QLineEdit:focus {
    border: 1px solid #a86bff;
}
QPushButton {
    background: rgba(168, 107, 255, 50);
    color: #f1f4ff;
    border: 1px solid #a86bff;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.3px;
}
QPushButton:hover {
    background: #a86bff;
    color: #06070f;
}
QPushButton:disabled {
    background: rgba(168, 107, 255, 20);
    color: rgba(241, 244, 255, 80);
    border: 1px solid rgba(168, 107, 255, 50);
}
QPushButton#HermesToolPill, QPushButton#HermesCapPillTool,
QPushButton#HermesCapPillHybrid, QPushButton#HermesCapPillSkill,
QPushButton#HermesCapPillSkillLearned {
    background: rgba(20, 23, 38, 220);
    color: #c0c5e0;
    border: 1px solid rgba(140, 150, 200, 55);
    border-radius: 11px;
    padding: 3px 9px;
    font-family: 'Menlo';
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.2px;
    text-align: left;
}
QPushButton#HermesToolPill:hover, QPushButton#HermesCapPillTool:hover {
    background: rgba(168, 107, 255, 70);
    color: #f1f4ff;
    border: 1px solid #a86bff;
}
/* Hybrids = habit using a hand — teal accent (executable + teachable). */
QPushButton#HermesCapPillHybrid {
    color: #73daca;
    border: 1px solid rgba(115, 218, 202, 70);
    background: rgba(20, 38, 36, 220);
}
QPushButton#HermesCapPillHybrid:hover {
    background: #73daca;
    color: #06070f;
    border: 1px solid #73daca;
}
/* Pure skills — soft violet, no execution path yet, composition only. */
QPushButton#HermesCapPillSkill {
    color: #bb9af7;
    border: 1px solid rgba(187, 154, 247, 70);
    background: rgba(28, 22, 44, 220);
}
QPushButton#HermesCapPillSkill:hover {
    background: #bb9af7;
    color: #06070f;
    border: 1px solid #bb9af7;
}
/* Learned-from-trace skills — gold accent, Alice's own memory promoted. */
QPushButton#HermesCapPillSkillLearned {
    color: #e0af68;
    border: 1px solid rgba(224, 175, 104, 70);
    background: rgba(36, 28, 16, 220);
}
QPushButton#HermesCapPillSkillLearned:hover {
    background: #e0af68;
    color: #06070f;
    border: 1px solid #e0af68;
}
QSplitter::handle {
    background: rgba(140, 150, 200, 30);
}
QScrollArea {
    background: transparent;
    border: 0;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: rgba(13, 16, 30, 200);
    width: 8px;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle {
    background: rgba(140, 150, 200, 80);
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::add-line, QScrollBar::sub-line { background: none; height: 0; width: 0; }
"""

# All organ traces the receipts feed tails. Adding a new organ here makes
# its rows visible immediately — no other code change required.
_TRACE_FILES = (
    "tool_router_trace.jsonl",
    "terminal_organ.jsonl",
    "file_organ.jsonl",
    "web_organ.jsonl",
    "tab_consciousness.jsonl",
    "stgm_ledger.jsonl",
    "swarm_doctors_bus.jsonl",
    "ide_stigmergic_trace.jsonl",
    "skill_ingest.jsonl",
)

_OWNER_FILE_CANDIDATES = (
    _STATE / "owner_genesis.json",
    _REPO / "owner_genesis.json",
)

# ── Receipt-feed helpers (mirrored from sifta_app.py — same logic, no HTML).


def _summarise(row: Dict[str, Any]) -> str:
    t = str(row.get("type") or row.get("kind") or "")
    if "RESULT" in t:
        cmd = row.get("command") or row.get("path") or row.get("url") or row.get("query") or ""
        bits: List[str] = [str(cmd)[:48] if cmd else (row.get("op") or t)]
        if row.get("exit_code") is not None:
            bits.append(f"exit={row['exit_code']}")
        if row.get("wrote_ok") is not None:
            bits.append(f"wrote_ok={row['wrote_ok']}")
        if row.get("size_bytes") is not None:
            bits.append(f"{row['size_bytes']}B")
        return " · ".join(b for b in bits if b)
    if "INTENT" in t:
        return "intent: " + str(row.get("command") or row.get("path") or row.get("url") or row.get("op") or "")[:60]
    if "REFUSED" in t:
        return "REFUSED: " + str(row.get("refused_for") or row.get("reason") or "")
    if "DEBIT" in t:
        return f"-{float(row.get('amount', 0)):.4f} STGM ({row.get('organ', '')})"
    if "CREDIT" in t:
        return f"+{float(row.get('amount', 0)):.4f} STGM ({row.get('organ', '')})"
    if "REGISTRATION" in t or row.get("action") == "LLM_REGISTRATION":
        return f"sign-in: {row.get('doctor', '?')} ({row.get('model', '?')})"
    if row.get("action") == "OWNER_GENESIS":
        return f"OWNER GENESIS: {row.get('owner_name', '?')}"
    if t.startswith("TOOL_CALL"):
        return f"{t.lower()} → {row.get('tool', '?')}"
    return str(row.get("subject") or row.get("payload") or row.get("reason") or t or "—")[:120]


def _organ_of(filename: str) -> str:
    return filename.replace(".jsonl", "").replace("_", " ")


def _recent_receipts(since_ts: float = 0.0, limit: int = 200) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not _STATE.exists():
        return rows
    for fname in _TRACE_FILES:
        p = _STATE / fname
        if not p.exists():
            continue
        organ = _organ_of(fname)
        try:
            with p.open(encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    ts = float(r.get("ts", 0) or 0)
                    if ts > since_ts:
                        rows.append({
                            "ts": ts,
                            "ts_iso": time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "",
                            "organ": organ,
                            "type": str(r.get("type") or r.get("kind") or "?"),
                            "summary": _summarise(r),
                            "hash": (str(r.get("hash") or ""))[:12],
                            "refused": "REFUSED" in str(r.get("type", "")),
                        })
        except Exception:
            continue
    rows.sort(key=lambda r: r["ts"])
    return rows[-limit:]


# ── Router adapter (same boundary as sifta_app.py — same TOOL_REGISTRY,
#    same ParsedToolCall, same execute_tool_call; just no HTML in front).
_CALLER_PID = "sifta_hermes_parity_widget"


def _router_registry() -> Dict[str, Any]:
    if _router is None:
        return {}
    reg = getattr(_router, "TOOL_REGISTRY", None) or getattr(_router, "REGISTRY", None)
    try:
        return dict(reg or {})
    except Exception:
        return {}


def _capabilities_for_alice() -> str:
    """Unified view for Alice's prompt and for the UI capabilities list."""
    try:
        from System.swarm_tool_router import capabilities_for_alice_prompt
        return capabilities_for_alice_prompt()
    except Exception:
        # Fallback to old surface if the new one isn't available yet
        try:
            from System.swarm_tool_router import tools_for_alice_prompt
            return tools_for_alice_prompt()
        except Exception:
            return "Capabilities temporarily unavailable."


def _stgm_balance() -> Optional[float]:
    if _stgm is not None:
        fn = getattr(_stgm, "balance", None)
        if callable(fn):
            try:
                return float(fn())
            except Exception:
                pass
    try:
        from stgm_economy import scan_economy  # type: ignore

        return float(scan_economy().canonical_wallet_sum)
    except Exception:
        return None


def _router_trace_head() -> Optional[str]:
    if _router is not None:
        cur = getattr(_router, "_current_head", None)
        if callable(cur):
            try:
                return str(cur())
            except Exception:
                pass
    p = _STATE / "tool_router_trace.jsonl"
    if not p.exists():
        return None
    try:
        with p.open(encoding="utf-8", errors="ignore") as f:
            last = ""
            for line in f:
                if line.strip():
                    last = line.strip()
        if last:
            import hashlib

            return hashlib.sha256(last.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return None
    return None


def _ensure_pid(tool_name: str) -> Optional[str]:
    try:
        from swarm_kernel_process_table import (  # type: ignore
            OrganProcess,
            get_kernel_process_table,
        )

        table = get_kernel_process_table(state_root=_STATE)
        table.ensure_registered(
            OrganProcess(
                pid=_CALLER_PID,
                organ_id="Applications/sifta_hermes_parity_widget.py",
                ring=2,
                health=1.0,
                stgm_balance=0.0,
                current_job=f"qt_tool:{tool_name}",
                last_receipt_id="",
                failure_count=0,
                last_heartbeat_ts=time.time(),
                location="sifta_hermes_parity_qt_surface",
                bodies_present=["sifta_hermes_parity_widget", "alice_tool_router"],
                metadata={
                    "source": "Applications/sifta_hermes_parity_widget.py",
                    "kernel_role": "owner_present_qt_tool_adapter",
                },
            ),
            receipt_id=f"hermes_parity_register:{tool_name}",
        )
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def _execute_tool(name: str, args: Optional[Dict[str, Any]], reason: str) -> Dict[str, Any]:
    if _router is None:
        return {"error": "router not loaded"}
    name = str(name or "").strip()
    registry = _router_registry()
    if name not in registry:
        return {"error": "unknown_tool", "name": name}
    params = {str(k): "" if v is None else str(v) for k, v in dict(args or {}).items()}
    if not str(params.get("cost_justification", "")).strip():
        params["cost_justification"] = (
            f"Hermes-parity Qt surface {reason} → {name}; owner-present UI action."
        )
    execute = getattr(_router, "execute_tool_call", None)
    parsed = getattr(_router, "ParsedToolCall", None)
    if callable(execute) and parsed is not None:
        err = _ensure_pid(name)
        if err:
            return {"error": "kernel_registration_failed", "detail": err, "name": name}
        call = parsed(tool_name=name, params=params, raw_match=f"hermes_parity:{reason}:{name}")
        try:
            result = execute(call, owner_present=True, autonomous=False, caller_pid=_CALLER_PID)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}", "name": name}
        # Normalize dataclass / object → dict
        if hasattr(result, "__dict__"):
            try:
                return {**{k: v for k, v in vars(result).items() if not k.startswith("_")}}
            except Exception:
                return {"result": str(result), "name": name}
        return {"result": result, "name": name}
    legacy = getattr(_router, "call_tool", None)
    if callable(legacy):
        try:
            return legacy(name, params, reason=reason)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}", "name": name}
    return {"error": "router execute API unavailable", "name": name}


def _owner_state() -> Dict[str, Any]:
    for c in _OWNER_FILE_CANDIDATES:
        if c.exists():
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
                data["signed_in"] = True
                data["source"] = str(c)
                return data
            except Exception as e:
                return {"signed_in": False, "error": f"{c}: {e}"}
    return {"signed_in": False, "error": "no owner_genesis found"}


def _verify_all() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for label, mod in (("router", _router), ("stgm", _stgm), ("skill_lib", _skill_lib)):
        if mod is None:
            continue
        verify = getattr(mod, "verify_chain", None)
        if callable(verify):
            try:
                out[label] = verify()
            except Exception as e:
                out[label] = {"error": f"{type(e).__name__}: {e}"}
    for mod_name in (
        "swarm_terminal_organ",
        "swarm_file_organ",
        "swarm_web_organ",
        "swarm_tab_consciousness",
        "swarm_doctor_mailbox",
        "swarm_unified_log",
        "swarm_ledger_repair",
    ):
        try:
            import importlib

            m = importlib.import_module(mod_name)
            fn = getattr(m, "verify_chain", None)
            if callable(fn):
                out[mod_name] = fn()
        except Exception as e:
            out[mod_name] = {"error": f"{type(e).__name__}: {e}"}
    return out


# ── Qt widget proper. Singleton per §7.6.2.

_KEYWORD_VERBS = {"run", "read", "list", "search", "fetch", "write", "help", "exec", "ls", "cat", "find", "get"}


class SiftaHermesParityWidget(QWidget):
    """Same physics as the old white pywebview window — now in Qt, MDI-embedded.

    Singleton class — only one instance ever exists per BeeSon boot
    (§7.6.2). Re-opening from the launcher raises the existing window.
    """

    _live_instance: "Optional[SiftaHermesParityWidget]" = None
    _initialized_instance_ids: set = set()

    def __new__(cls, *args, **kwargs):  # noqa: D401
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()  # raises RuntimeError if C++ destroyed
                try:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                except Exception:
                    pass
                return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        # §7.6.2 sip-safe guard: never probe instance attrs before super().__init__.
        # `getattr(self, "_xxx", False)` on a fresh PyQt6 instance routes through
        # the C++ wrapper and raises "super-class __init__() never called".
        # Use a CLASS-level id() set instead — class-attribute access is sip-safe.
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))

        self._last_seen_ts: float = 0.0
        self._refresh_in_flight: bool = False

        self.setObjectName("HermesParityRoot")
        self.setWindowTitle("Hermes Parity — receipted tool surface")
        self.setMinimumSize(960, 640)
        self.setStyleSheet(_HERMES_QSS)

        try:
            self._build_ui()
        except Exception as e:
            # Defensive: keep the widget alive even if UI build hits something
            # surprising on a fresh boot. Surface the cause in a centered label
            # so the Architect sees what broke without a launcher crash dialog.
            from PyQt6.QtWidgets import QVBoxLayout, QLabel
            fail_layout = QVBoxLayout(self)
            err_label = QLabel(f"UI build failed: {type(e).__name__}: {e}")
            err_label.setStyleSheet("color:#b42318;padding:24px;font-family:'Menlo';")
            err_label.setWordWrap(True)
            fail_layout.addWidget(err_label)
            return
        self._refresh_status()
        self._refresh_tools_row()
        self._refresh_receipts(initial=True)
        self._refresh_skills_status()

        # Slow heartbeat. Hardcoded 4s here is honest: George's §4.5 fan-drop
        # work removed *unnecessary* timers; a user-facing receipts feed has
        # to refresh on a perceivable cadence. This timer pauses when the
        # widget is hidden so the launcher tab does not pay for it.
        self._tick = QTimer(self)
        self._tick.setInterval(4000)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start()

        # Publish focus so Alice's resident Talk widget sees this surface
        # open. §7.6 item 2: apps surface state via app_focus, never their
        # own LLM thread.
        self._publish_focus("opened", {"truth_label": TRUTH_LABEL})

    # ─────────────────────────── UI build ───────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 8)
        outer.setSpacing(8)

        outer.addLayout(self._build_status_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_talk_column())
        splitter.addWidget(self._build_receipts_column())
        splitter.addWidget(self._build_skills_column())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 3)
        outer.addWidget(splitter, 1)

        outer.addLayout(self._build_footer())

    def _section(self, title: str) -> QFrame:
        f = QFrame(self)
        f.setObjectName("HermesSection")
        f.setFrameShape(QFrame.Shape.NoFrame)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)
        h = QLabel(title)
        h.setObjectName("HermesSectionTitle")
        lay.addWidget(h)
        return f

    def _build_status_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self._lbl_chain = QLabel("chain head: —")
        self._lbl_stgm = QLabel("STGM: —")
        self._lbl_tools = QLabel("tools: —")
        self._lbl_owner = QLabel("owner: —")
        for w in (self._lbl_chain, self._lbl_stgm, self._lbl_tools, self._lbl_owner):
            w.setObjectName("HermesStatusChip")
            row.addWidget(w)
        row.addStretch(1)
        return row

    def _build_talk_column(self) -> QWidget:
        f = self._section("TALK · keyword fast-path")
        lay: QVBoxLayout = f.layout()  # type: ignore

        self._chat_log = QTextEdit(f)
        self._chat_log.setObjectName("HermesChatLog")
        self._chat_log.setReadOnly(True)
        lay.addWidget(self._chat_log, 1)

        # Tools row (scrollable so 26+ tools never crowd the column).
        scroll = QScrollArea(f)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(110)
        self._tools_inner = QWidget()
        self._tools_grid = QGridLayout(self._tools_inner)
        self._tools_grid.setContentsMargins(2, 2, 2, 2)
        self._tools_grid.setSpacing(5)
        scroll.setWidget(self._tools_inner)
        lay.addWidget(scroll)

        # Talk input row.
        inrow = QHBoxLayout()
        self._chat_input = QLineEdit(f)
        self._chat_input.setPlaceholderText("try: list · ?run_terminal · help · or click a tool above")
        self._chat_input.returnPressed.connect(self._send_chat)
        inrow.addWidget(self._chat_input, 1)
        btn = QPushButton("Send", f)
        btn.clicked.connect(self._send_chat)
        inrow.addWidget(btn)
        lay.addLayout(inrow)

        return f

    def _build_receipts_column(self) -> QWidget:
        f = self._section("RECEIPTS · live tail")
        lay: QVBoxLayout = f.layout()  # type: ignore
        self._receipts = QListWidget(f)
        self._receipts.setObjectName("HermesReceipts")
        self._receipts.setAlternatingRowColors(True)
        lay.addWidget(self._receipts, 1)
        self._lbl_recpt_count = QLabel("0 rows")
        self._lbl_recpt_count.setStyleSheet("color:#565f89;font-size:10px;padding-top:2px;")
        lay.addWidget(self._lbl_recpt_count)
        return f

    def _build_skills_column(self) -> QWidget:
        f = self._section("SKILLS · pull · extract · status")
        lay: QVBoxLayout = f.layout()  # type: ignore

        # Pull section
        self._skill_src = QLineEdit(f)
        self._skill_src.setPlaceholderText("https://… /SKILL.md  ·  or local path")
        lay.addWidget(self._skill_src)
        self._skill_marketplace = QLineEdit(f)
        self._skill_marketplace.setPlaceholderText("marketplace JSON path or URL (optional)")
        lay.addWidget(self._skill_marketplace)
        self._skill_id = QLineEdit(f)
        self._skill_id.setPlaceholderText("skill id (optional, for marketplace pull)")
        lay.addWidget(self._skill_id)
        self._skill_life = QLineEdit(f)
        self._skill_life.setPlaceholderText("life context (why Alice needs this skill now)")
        lay.addWidget(self._skill_life)
        pull_btn = QPushButton("Pull skill", f)
        pull_btn.clicked.connect(self._do_pull_skill)
        lay.addWidget(pull_btn)

        # Spacer
        lay.addSpacing(8)

        # Extract from trace
        self._extract_trace_file = QLineEdit(f)
        self._extract_trace_file.setPlaceholderText("trace file (default tool_router_trace.jsonl)")
        lay.addWidget(self._extract_trace_file)
        self._extract_trace_id = QLineEdit(f)
        self._extract_trace_id.setPlaceholderText("trace id (blank = latest successful)")
        lay.addWidget(self._extract_trace_id)
        self._extract_name = QLineEdit(f)
        self._extract_name.setPlaceholderText("new skill name")
        lay.addWidget(self._extract_name)
        ex_btn = QPushButton("Extract from trace", f)
        ex_btn.clicked.connect(self._do_extract_skill)
        lay.addWidget(ex_btn)

        lay.addSpacing(8)

        self._skills_status = QListWidget(f)
        self._skills_status.setObjectName("HermesSkillStatus")
        self._skills_status.setFixedHeight(140)
        lay.addWidget(self._skills_status)

        return f

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self._lbl_truth = QLabel("🐜  " + TRUTH_LABEL + " · doctor=CW47")
        self._lbl_truth.setStyleSheet(
            "color:#565f89;font-family:'Menlo';font-size:10px;letter-spacing:0.5px;"
        )
        row.addWidget(self._lbl_truth)
        row.addStretch(1)
        verify = QPushButton("Verify all chains")
        verify.clicked.connect(self._do_verify)
        row.addWidget(verify)
        return row

    # ─────────────────────────── Refresh / tick ───────────────────────────

    def _on_tick(self) -> None:
        if not self.isVisible():
            return  # pause work when hidden — §4.5 (no idle fan)
        if self._refresh_in_flight:
            return
        self._refresh_in_flight = True
        try:
            self._refresh_status()
            self._refresh_receipts()
        finally:
            self._refresh_in_flight = False

    def _refresh_status(self) -> None:
        head = _router_trace_head() or "—"
        self._lbl_chain.setText(f"chain head: {head[:12]}…")
        bal = _stgm_balance()
        self._lbl_stgm.setText("STGM: —" if bal is None else f"STGM: {bal:.3f}")
        self._lbl_tools.setText(f"tools: {len(_router_registry())}")
        owner = _owner_state()
        if owner.get("signed_in"):
            self._lbl_owner.setText(f"owner: {owner.get('owner_name', '?')}")
        else:
            self._lbl_owner.setText("owner: (no genesis)")

    def _refresh_tools_row(self) -> None:
        # Clear existing pills.
        while self._tools_grid.count():
            item = self._tools_grid.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.deleteLater()

        # Unified Capability Field — tools + skills as one tagged row, sorted
        # hybrids → pure tools → learned skills → pure skills. Tags drive both
        # the visible label and the QObject name (which the QSS colors).
        capabilities = self._capability_list()
        col_count = 4
        for i, cap in enumerate(capabilities):
            tag, object_name = self._capability_pill_style(cap)
            btn = QPushButton(f"{tag} {cap['name']}")
            btn.setObjectName(object_name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tip = cap.get("description") or cap.get("when_to_use") or ""
            confidence = float(cap.get("confidence", 0.0) or 0.0)
            cost = float(cap.get("cost_stgm", 0.0) or 0.0)
            backing = cap.get("backing") or {}
            btn.setToolTip(
                f"{tag} {cap['name']}\n"
                f"{tip}\n"
                f"cost~{cost:.3f} STGM · conf={confidence:.2f}\n"
                f"backing: tool={backing.get('tool')}  skill={backing.get('skill')}"
            )
            btn.clicked.connect(lambda _checked=False, c=cap: self._on_capability_pill(c))
            r, c = divmod(i, col_count)
            self._tools_grid.addWidget(btn, r, c)

    # ─────────── Capability-row helpers (unified field) ───────────

    def _capability_list(self) -> List[Dict[str, Any]]:
        """Unified capability list as plain dicts.

        Order: hybrids first, then pure tools, then learned skills, then
        pure skills. Falls back to bare TOOL_REGISTRY names when the
        capability registry is not importable.
        """
        if _capabilities is None:
            return [
                {
                    "name": n,
                    "description": "",
                    "when_to_use": "",
                    "confidence": 1.0,
                    "cost_stgm": 0.02,
                    "can_execute": True,
                    "can_teach_compose": False,
                    "learned_from_trace": False,
                    "backing": {"tool": n, "skill": None},
                }
                for n in sorted(_router_registry().keys())
            ]
        try:
            caps = _capabilities.build_capability_index()
        except Exception:
            caps = []

        def _bucket(c) -> int:
            if c.is_hybrid():
                return 0
            if c.can_execute and not c.can_teach_compose:
                return 1
            if c.learned_from_trace:
                return 2
            return 3

        caps = sorted(caps, key=lambda c: (_bucket(c), c.name))
        return [c.to_alice_dict() for c in caps]

    def _capability_pill_style(self, cap: Dict[str, Any]) -> tuple:
        if cap.get("can_execute") and cap.get("can_teach_compose"):
            return ("[hybrid]", "HermesCapPillHybrid")
        if cap.get("can_execute"):
            return ("[tool]", "HermesCapPillTool")
        if cap.get("learned_from_trace"):
            return ("[skill·learned]", "HermesCapPillSkillLearned")
        return ("[skill]", "HermesCapPillSkill")

    def _on_capability_pill(self, cap: Dict[str, Any]) -> None:
        """Click handler. Behavior depends on capability kind.

        * [tool] / [hybrid] — drop tool name into the input so George can
          edit params; hybrids also append a hint that there's a skill
          procedure available via swarm_skill_library.load_procedure().
        * [skill] / [skill·learned] — pure habit, no execution path here.
          Show the procedure body inline in the chat log if we can read
          it. If we cannot, prompt George to invoke Alice via the OS
          Talk widget — she owns composition (§7.6).
        """
        name = cap.get("name", "")
        if not name:
            return
        if cap.get("can_execute"):
            self._chat_input.setText(name + " ")
            self._chat_input.setFocus()
            if cap.get("can_teach_compose"):
                self._append_chat(
                    "hint",
                    f"{name} is a hybrid — execute via the tool, or read its "
                    f"procedure with swarm_skill_library.load_procedure('{name}').",
                )
            return
        body = self._load_skill_procedure(name)
        if body:
            self._append_chat("skill", f"{name} (procedure preview, {len(body)} chars):")
            preview = (
                body if len(body) <= 800
                else body[:800] + "\n…[truncated; full procedure via swarm_skill_library.load_procedure]"
            )
            self._append_chat("skill", preview)
            return
        self._append_chat(
            "skill",
            f"{name} is a pure skill — no procedure file readable. Ask Alice in "
            f"the main Talk widget to compose with this skill (§7.6).",
        )

    def _load_skill_procedure(self, name: str) -> Optional[str]:
        if _skill_lib is None:
            return None
        loader = getattr(_skill_lib, "load_procedure", None)
        if not callable(loader):
            return None
        try:
            return loader(name)
        except Exception:
            return None

    def _refresh_receipts(self, initial: bool = False) -> None:
        rows = _recent_receipts(since_ts=self._last_seen_ts if not initial else 0.0, limit=200 if initial else 80)
        if initial:
            self._receipts.clear()
        for r in rows:
            ts_iso = r.get("ts_iso", "")
            organ = r.get("organ", "")
            summary = r.get("summary", "")
            h = r.get("hash", "")
            refused = r.get("refused")
            line = f"{ts_iso:>8}  {organ:<22}  {summary}  {('#'+h) if h else ''}"
            item = QListWidgetItem(line)
            if refused:
                item.setForeground(QColor("#f7768e"))
            else:
                # Subtle color hint by organ type so the feed reads at a glance.
                organ_color = {
                    "tool router trace": "#a86bff",
                    "terminal organ": "#73daca",
                    "file organ": "#7dcfff",
                    "web organ": "#bb9af7",
                    "stgm ledger": "#e0af68",
                    "ide stigmergic trace": "#f1f4ff",
                    "skill ingest": "#9ece6a",
                }.get(organ, "#c0c5e0")
                item.setForeground(QColor(organ_color))
            self._receipts.addItem(item)
            if r["ts"] > self._last_seen_ts:
                self._last_seen_ts = r["ts"]
        self._receipts.scrollToBottom()
        self._lbl_recpt_count.setText(f"{self._receipts.count()} rows")

    def _refresh_skills_status(self) -> None:
        self._skills_status.clear()
        if _skill_lib is None:
            self._skills_status.addItem(QListWidgetItem("(swarm_skill_library not importable)"))
            return
        try:
            idx = _skill_lib.build_skill_index()
        except Exception as e:
            self._skills_status.addItem(QListWidgetItem(f"index error: {type(e).__name__}: {e}"))
            return
        self._skills_status.addItem(QListWidgetItem(f"{len(idx)} skills in library"))
        for row in idx[:80]:
            name = row.get("name", "?")
            community = row.get("community_style", "")
            self._skills_status.addItem(QListWidgetItem(f"· {name}  [{community}]"))

    # ─────────────────────────── Talk actions ───────────────────────────

    def _append_chat(self, label: str, body: str, error: bool = False) -> None:
        # Tokyo Night palette: bad=#f7768e, ok=#f1f4ff; "you"=purple, others=lavender muted.
        color = "#f7768e" if error else "#f1f4ff"
        lbl_color = "#a86bff" if label == "you" else "#8e94ad"
        safe = str(body).replace("<", "&lt;").replace(">", "&gt;")
        self._chat_log.append(
            f'<span style="color:{lbl_color};font-size:9px;letter-spacing:0.8px;'
            f'text-transform:uppercase">{label}</span> '
            f'<span style="color:{color}">{safe}</span>'
        )

    def _on_tool_pill(self, name: str) -> None:
        # Drop tool name into the input so George can edit params before invoking.
        self._chat_input.setText(name + " ")
        self._chat_input.setFocus()

    def _send_chat(self) -> None:
        text = self._chat_input.text().strip()
        if not text:
            return
        self._chat_input.clear()
        self._append_chat("you", text)

        result = self._dispatch(text)

        # Publish tool-call focus so Alice sees what just ran from here.
        if isinstance(result, dict):
            tool_name = result.get("tool_name") or result.get("name")
            if tool_name and not result.get("error"):
                self._publish_focus("tool_call", {
                    "tool_name": tool_name,
                    "reason": "owner_chat",
                    "input_text": text,
                })

        if isinstance(result, dict) and result.get("error"):
            self._append_chat("err", str(result.get("error")), error=True)
        elif isinstance(result, dict) and result.get("help"):
            for line in result["help"]:
                self._append_chat("help", line)
        elif isinstance(result, dict):
            short = result.get("type") or result.get("status") or "ok"
            h = (result.get("hash") or "")[:8]
            tail = f" #{h}" if h else ""
            self._append_chat("alice", f"{short}{tail}  {str(result)[:200]}")
        else:
            self._append_chat("alice", str(result)[:200])

        # Receipts feed will pick up the new row on the next tick.
        QTimer.singleShot(150, self._refresh_status)
        QTimer.singleShot(300, lambda: self._refresh_receipts(initial=False))

    def _dispatch(self, text: str) -> Dict[str, Any]:
        """Keyword fast-path. Non-keyword input → publish focus + nudge to Talk widget."""
        if _router is None:
            return {"error": "tool router not loaded"}

        parts = text.split(None, 1)
        verb = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if verb == "help":
            return {"help": [
                "run CMD            → run_terminal",
                "read PATH          → read_file",
                "write PATH CONTENT → write_file (atomic)",
                "list [PATH]        → list_dir",
                "search QUERY       → search_web",
                "fetch URL          → fetch_url",
                "?TOOL              → show tool spec",
                "list               → show all registered tools",
                "anything else      → publish focus to Alice (§7.6 item 2)",
            ]}
        if verb == "list" and not rest:
            return {"tools": sorted(_router_registry().keys())}
        if text.startswith("?"):
            name = text[1:].strip()
            spec = _router_registry().get(name)
            if spec is None:
                return {"error": f"unknown tool: {name}"}
            try:
                from dataclasses import asdict, is_dataclass

                return {"spec": asdict(spec)} if is_dataclass(spec) else {"spec": str(spec)}
            except Exception:
                return {"spec": str(spec)}

        if verb in ("run", "exec", "shell", "$"):
            return _execute_tool("run_terminal", {"command": rest}, "chat")
        if verb in ("read", "cat"):
            return _execute_tool("read_file", {"path": rest}, "chat")
        if verb in ("list", "ls"):
            return _execute_tool("list_dir", {"path": rest or "."}, "chat")
        if verb in ("search", "find"):
            return _execute_tool("search_web", {"query": rest}, "chat")
        if verb in ("fetch", "get"):
            return _execute_tool("fetch_url", {"url": rest}, "chat")
        if verb == "write":
            if " " not in rest:
                return {"error": "usage: write PATH CONTENT"}
            path, content = rest.split(" ", 1)
            return _execute_tool("write_file", {"path": path, "content": content}, "chat")

        # Direct tool name match
        if verb in _router_registry():
            args: Dict[str, Any] = {}
            for tok in rest.split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    args[k.strip()] = v
            return _execute_tool(verb, args, "chat")

        # Fallback: publish focus to Alice's Talk widget. §7.6 — this widget
        # owns no LLM brain; Alice's resident Talk widget owns the
        # conversation thread.
        self._publish_focus("nl_query", {"text": text})
        return {
            "type": "FOCUS_PUBLISHED",
            "alice": (
                "Not a keyword. I published this as app_focus for Alice's "
                "Talk widget — switch to her chat and she'll respond there."
            ),
            "focus_payload": {"text": text},
        }

    # ─────────────────────────── Skills actions ───────────────────────────

    def _do_pull_skill(self) -> None:
        if _skill_lib is None:
            self._append_chat("err", "swarm_skill_library not loaded", error=True)
            return
        src = self._skill_src.text().strip()
        market = self._skill_marketplace.text().strip()
        skill_id = self._skill_id.text().strip()
        life = self._skill_life.text().strip() or None
        try:
            if market:
                res = _skill_lib.pull_skill_from_marketplace(
                    market,
                    skill_id=skill_id,
                    life_context=life,
                    installed_by="hermes_parity_widget",
                )
            elif src.startswith(("http://", "https://")):
                res = _skill_lib.pull_skill_from_url(
                    src, life_context=life, installed_by="hermes_parity_widget"
                )
            elif src:
                res = _skill_lib.ingest_skill_source(
                    src, life_context=life, installed_by="hermes_parity_widget"
                )
            else:
                self._append_chat("err", "give a source URL/path or a marketplace JSON", error=True)
                return
        except Exception as e:
            self._append_chat("err", f"pull_skill: {type(e).__name__}: {e}", error=True)
            return
        self._append_chat("skill", f"pull → {str(res)[:200]}")
        self._refresh_skills_status()
        QTimer.singleShot(200, lambda: self._refresh_receipts(initial=False))

    def _do_extract_skill(self) -> None:
        if _skill_lib is None:
            self._append_chat("err", "swarm_skill_library not loaded", error=True)
            return
        try:
            res = _skill_lib.extract_skill_from_trace(
                trace_file=(self._extract_trace_file.text().strip() or "tool_router_trace.jsonl"),
                trace_id=self._extract_trace_id.text().strip(),
                name=self._extract_name.text().strip(),
                installed_by="hermes_parity_widget",
            )
        except Exception as e:
            self._append_chat("err", f"extract_skill: {type(e).__name__}: {e}", error=True)
            return
        self._append_chat("skill", f"extract → {str(res)[:200]}")
        self._refresh_skills_status()
        QTimer.singleShot(200, lambda: self._refresh_receipts(initial=False))

    def _do_verify(self) -> None:
        result = _verify_all()
        ok = sum(1 for v in result.values() if isinstance(v, dict) and v.get("ok"))
        total = len(result)
        self._append_chat("verify", f"{ok}/{total} chains ok")
        for k, v in result.items():
            ok_flag = "ok" if (isinstance(v, dict) and v.get("ok")) else "FAIL"
            self._append_chat("verify", f"  {k}: {ok_flag}")

    # ─────────────────────────── Focus publication ───────────────────────────

    def _publish_focus(self, event: str, payload: Dict[str, Any]) -> None:
        """Publish to .sifta_state/app_focus.jsonl in the format Alice expects.

        Correct signature per System/swarm_app_focus.py:
            publish_focus(app_name: str, detail: str, *, tab="", selection="", metadata=None)

        Alice reads this ledger to know what surface the Architect is on. The
        `detail` string is what she sees in her system prompt context — so we
        spell out what this widget is (it is NOT the "Hermes agent arm" — it
        is the new Hermes-parity tool console, owner-present, receipts-true).
        """
        if _publish_focus is None:
            return

        event_blurbs = {
            "opened": (
                "Architect just opened the SIFTA Hermes-Parity tool console "
                "(Applications/sifta_hermes_parity_widget.py). This is the Qt "
                "conversion of the old pywebview white window — NOT the "
                "Hermes agent-arm subsystem. It surfaces TOOL_REGISTRY (all "
                "27 tools as clickable pills), live receipts across 9 organ "
                "jsonls, skills pull/extract, STGM balance, and chain head. "
                "Owner-present surface; all tool calls flow through "
                "swarm_tool_router.execute_tool_call with caller_pid="
                "'sifta_hermes_parity_widget'. Doctor CW47 (Cowork Opus 4.7) "
                "shipped this 2026-05-16. Talk to me about it normally."
            ),
            "nl_query": (
                f"Architect typed natural language into the Hermes-Parity "
                f"console: {payload.get('text', '')!r}. The console has no "
                "second brain — it routes non-keyword text here via app_focus "
                "so YOU (Alice) answer in the main Talk widget."
            ),
            "closed": (
                "Architect closed the SIFTA Hermes-Parity tool console."
            ),
            "tool_call": (
                f"Architect invoked tool {payload.get('tool_name', '?')!r} "
                f"from the Hermes-Parity console with reason "
                f"{payload.get('reason', '?')!r}."
            ),
        }
        detail = event_blurbs.get(event, f"Hermes-Parity console event: {event}")

        try:
            _publish_focus(
                "SIFTA Hermes Parity",
                detail,
                metadata={
                    "truth_label": TRUTH_LABEL,
                    "doctor": "CW47",
                    "event": event,
                    "widget_class": "SiftaHermesParityWidget",
                    "entry_point": "Applications/sifta_hermes_parity_widget.py",
                    "NOT_THE_HERMES_AGENT_ARM": True,
                    **{k: v for k, v in payload.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))},
                },
            )
        except Exception:
            # Soft-fail — focus is best-effort. The widget still works without it.
            pass

    # ─────────────────────────── Lifecycle ───────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            tick = getattr(self, "_tick", None)
            if tick is not None:
                tick.stop()
        except RuntimeError:
            pass
        try:
            self._publish_focus("closed", {})
        finally:
            if type(self)._live_instance is self:
                type(self)._live_instance = None
            type(self)._initialized_instance_ids.discard(id(self))
            super().closeEvent(event)


# ──────────────────────────── Standalone smoke ────────────────────────────


def main() -> int:  # pragma: no cover
    app = QApplication(sys.argv)
    w = SiftaHermesParityWidget()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
