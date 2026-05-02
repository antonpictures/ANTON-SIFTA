#!/usr/bin/env python3
"""
Applications/sifta_system_settings.py
macOS-style settings surface for SIFTA OS.

Body telemetry belongs in Settings, not as scattered standalone readouts.
This app reads the same ledgers the desktop HUD reads and keeps expensive
diagnostics manual.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QFont, QPixmap, QPainter, QPen, QColor, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from System.sifta_app_catalog import group_manifest, normalize_category
from System.sifta_inference_defaults import (
    DEFAULT_OLLAMA_MODEL,
    STIGMERGIC_TEST_MODEL_PRESETS,
    get_default_ollama_model,
    resolve_ollama_model,
    set_default_ollama_model,
    set_app_ollama_model,
)
from System.sifta_base_widget import SiftaBaseWidget
from System.sifta_desktop_themes import THEMES, load_active_theme_id, save_active_theme_id

STATE = _REPO / ".sifta_state"
MANIFEST = _REPO / "Applications" / "apps_manifest.json"
GAIN_STATE_FILE = STATE / "talk_to_alice_audio_gain.json"
AUDIO_SETTINGS_FILE = STATE / "alice_audio_settings.json"
WHISPER_MODELS = ("tiny.en", "base.en", "small.en")
DEFAULT_WHISPER_MODEL = "tiny.en"
DEFAULT_MIC_GAIN = 2.0
MIN_MIC_GAIN = 0.5
MAX_MIC_GAIN = 8.0
ALICE_VOICE_SHORTLIST = (
    "Ava (Premium)",
    "Zoe (Premium)",
    "Evan (Premium)",
    "Nathan (Premium)",
    "Ava (Enhanced)",
    "Samantha (Enhanced)",
    "Alex",
    "Samantha",
)


def _looks_remote_model_name(name: str) -> bool:
    n = (name or "").strip().lower()
    return n.startswith("gemini:") or n.startswith("gemini-")


def _parse_ollama_tags_payload(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    models = payload.get("models", [])
    if not isinstance(models, list):
        return names
    for item in models:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name and not _looks_remote_model_name(name) and name not in names:
            names.append(name)
    return names


def _parse_ollama_list_output(text: str) -> list[str]:
    names: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("NAME "):
            continue
        name = stripped.split()[0]
        if name and not _looks_remote_model_name(name) and name not in names:
            names.append(name)
    return names


def _format_ollama_weight_label(
    model_name: str,
    model_weights: dict[str, int],
    *,
    missing_label: str = "not installed",
) -> str:
    """Return an exact local model weight label.

    Do not prefix-match model families here. A planned tag such as
    ``qwen3.5:9b`` must not inherit the installed weight of ``qwen3.5:2b``.
    """
    model = (model_name or "").strip()
    if not model:
        return missing_label

    size = model_weights.get(model)
    if size is None and ":" not in model:
        size = model_weights.get(f"{model}:latest")

    if not size:
        return missing_label
    if size >= 1e9:
        return f"⚖ {size / 1e9:.2f} GB"
    return f"⚖ {size / 1e6:.0f} MB"


def _canonical_local_model_name(
    name: str,
    installed: list[str],
    *,
    allow_missing: bool = True,
) -> str:
    model = (name or "").strip()
    if not model:
        return ""
    if _looks_remote_model_name(model):
        return ""
    if model in installed:
        return model
    if ":" not in model:
        latest = f"{model}:latest"
        if latest in installed:
            return latest
    return model if allow_missing else ""


def _select_local_model(preferred: str, installed: list[str]) -> str:
    selected = _canonical_local_model_name(preferred, installed, allow_missing=False)
    if selected:
        return selected
    selected = _canonical_local_model_name(DEFAULT_OLLAMA_MODEL, installed, allow_missing=False)
    if selected:
        return selected
    return installed[0] if installed else (preferred or DEFAULT_OLLAMA_MODEL)


def _available_local_ollama_models() -> list[str]:
    """Return installed local Ollama models only; never mix in cloud API names."""
    options: list[str] = []
    try:
        import urllib.request

        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=4) as resp:
            options.extend(_parse_ollama_tags_payload(json.loads(resp.read())))
    except Exception:
        pass

    if not options:
        try:
            out = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=4)
            options.extend(_parse_ollama_list_output(out.stdout))
        except Exception:
            pass

    if not options:
        saved = (
            get_default_ollama_model(),
            resolve_ollama_model(app_context="talk_to_alice"),
            DEFAULT_OLLAMA_MODEL,
        )
        for model in saved:
            canonical = _canonical_local_model_name(model, options)
            if canonical and canonical not in options:
                options.append(canonical)
        for model in STIGMERGIC_TEST_MODEL_PRESETS:
            canonical = _canonical_local_model_name(model, options)
            if canonical and canonical not in options:
                options.append(canonical)

    return options


def _latest_jsonl(path: Path) -> dict[str, Any]:
    try:
        last = ""
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
        return json.loads(last) if last else {}
    except Exception:
        return {}


def _dir_mb(path: Path) -> float:
    try:
        total = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
        return round(total / (1024 * 1024), 2)
    except Exception:
        return 0.0


def _clamp_gain(value: float) -> float:
    try:
        value = float(value)
    except Exception:
        value = DEFAULT_MIC_GAIN
    if value != value:
        value = DEFAULT_MIC_GAIN
    return max(MIN_MIC_GAIN, min(MAX_MIC_GAIN, value))


def _load_mic_gain() -> float:
    try:
        data = json.loads(GAIN_STATE_FILE.read_text(encoding="utf-8"))
        return _clamp_gain(data.get("mic_gain", DEFAULT_MIC_GAIN))
    except Exception:
        return DEFAULT_MIC_GAIN


def _save_mic_gain(value: float) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    GAIN_STATE_FILE.write_text(
        json.dumps({"mic_gain": _clamp_gain(value), "saved_at": time.time()}, indent=2),
        encoding="utf-8",
    )


def _load_audio_settings() -> dict[str, Any]:
    settings: dict[str, Any] = {
        "whisper_model": DEFAULT_WHISPER_MODEL,
        "voice_name": "",
        "ground_swarm_state": True,
    }
    try:
        data = json.loads(AUDIO_SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            settings.update({k: v for k, v in data.items() if k in settings})
    except Exception:
        pass
    settings["whisper_model"] = str(settings.get("whisper_model") or DEFAULT_WHISPER_MODEL)
    if settings["whisper_model"] not in WHISPER_MODELS:
        settings["whisper_model"] = DEFAULT_WHISPER_MODEL
    settings["voice_name"] = str(settings.get("voice_name") or "")
    settings["ground_swarm_state"] = bool(settings.get("ground_swarm_state", True))
    return settings


def _save_audio_settings(settings: dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    payload = _load_audio_settings()
    payload.update({k: v for k, v in settings.items() if k in payload})
    payload["saved_at"] = time.time()
    AUDIO_SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _curated_voice_rows() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=4).stdout
        locale_re = re.compile(r"\s+([a-z]{2}_[A-Z]{2})\s+#")
        for line in out.splitlines():
            match = locale_re.search(line)
            if not match:
                continue
            name = line[: match.start()].strip()
            locale = match.group(1)
            if name and locale.startswith("en"):
                rows.append((name, locale))
    except Exception:
        pass
    if not rows:
        rows = [("Samantha", "en_US"), ("Alex", "en_US")]

    available = {name: locale for name, locale in rows}
    curated: list[tuple[str, str]] = []
    for name in ALICE_VOICE_SHORTLIST:
        locale = available.get(name)
        if locale:
            curated.append((name, locale))
    return curated


def read_system_settings_snapshot() -> dict[str, Any]:
    health = _latest_jsonl(STATE / "health_scores.jsonl")
    metabolic = _latest_jsonl(STATE / "metabolic_homeostasis.jsonl")
    manifest = {}
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        manifest = {}

    score = int(health.get("score", 0) or 0)
    dimensions = health.get("dimensions", {}) if isinstance(health.get("dimensions"), dict) else {}
    raw = health.get("raw", {}) if isinstance(health.get("raw"), dict) else {}
    economics = raw.get("economic", {}) if isinstance(raw.get("economic"), dict) else {}
    state_mb = _dir_mb(STATE)
    iris_mb = _dir_mb(STATE / "iris_frames")

    # Add identity and network proxies (for now using defaults/placeholders if modules are un-init)
    genesis_data = {"ok": False, "owner_name": "<unclaimed>", "status": "MISSING", "anchor": "N/A", "sig": "N/A", "generation": 0, "photo_present": False, "photo_path": "", "ai_display_name": "Alice"}
    try:
        from System.owner_genesis import verify_genesis, OWNER_DIR
        v = verify_genesis()
        genesis_data["ok"] = v.get("exists", False) and v.get("valid", False) and v.get("status") == "ACTIVE"
        genesis_data["owner_name"] = v.get("owner_name", "<unclaimed>") or "<unclaimed>"
        genesis_data["status"] = v.get("status", "MISSING")
        genesis_data["generation"] = v.get("generation", 0)
        genesis_data["ai_display_name"] = v.get("ai_display_name", "Alice")
        genesis_data["photo_present"] = v.get("photo_present", False)
        # Read anchor and sig from the raw scar
        import json as _json
        _gf = STATE / "owner_genesis.json"
        if _gf.exists():
            _scar = _json.loads(_gf.read_text())
            genesis_data["anchor"] = _scar.get("genesis_anchor", "N/A")[:16] + "…"
            genesis_data["sig"] = _scar.get("sig", "N/A")[:16] + "…"
        # Find photo path
        for ext in [".jpg", ".jpeg", ".png", ".heic", ".webp"]:
            p = OWNER_DIR / f"genesis_photo{ext}"
            if p.exists():
                genesis_data["photo_path"] = str(p)
                break
    except Exception:
        pass
    genesis_ok = genesis_data["ok"]

    try:
        from System.swarm_kernel_identity import owner_silicon
        hw_serial = owner_silicon()
        import hashlib
        digest = hashlib.sha256(hw_serial.encode()).hexdigest()[:8]
    except Exception:
        hw_serial = "UNKNOWN"
        digest = "N/A"

    hw_chip = "Unknown Chip"
    hw_memory = "Unknown Memory"
    hw_os = "Unknown OS"
    try:
        import subprocess
        res = subprocess.run(["system_profiler", "SPHardwareDataType", "SPSoftwareDataType"], capture_output=True, text=True, timeout=2)
        for line in res.stdout.splitlines():
            if "Chip:" in line: hw_chip = line.split(":")[-1].strip()
            if "Memory:" in line: hw_memory = line.split(":")[-1].strip()
            if "System Version:" in line: hw_os = line.split(":")[-1].strip()
    except Exception:
        pass

    # Network — detect active interface, distinguish Wi-Fi vs Ethernet
    net_ssid = "Unknown"
    net_ip = "Unknown IP"
    wa_bridge_live = False
    try:
        import subprocess as _sp
        # Find the interface carrying the default route
        _rt = _sp.run(["route", "get", "default"], capture_output=True, text=True, timeout=2)
        _default_iface = None
        for _ln in _rt.stdout.splitlines():
            if "interface:" in _ln:
                _default_iface = _ln.split(":")[-1].strip()
                break
        # Discover what hardware type that interface is
        _hw_ports = _sp.run(["networksetup", "-listallhardwareports"], capture_output=True, text=True, timeout=2).stdout
        _iface_type = "Unknown"
        _is_wifi = False
        if _default_iface:
            _blocks = _hw_ports.split("Hardware Port:")
            for _blk in _blocks:
                if f"Device: {_default_iface}" in _blk:
                    if "Wi-Fi" in _blk or "AirPort" in _blk:
                        _iface_type = "Wi-Fi"
                        _is_wifi = True
                    elif "Thunderbolt" in _blk:
                        _iface_type = "Thunderbolt"
                    elif "Ethernet" in _blk:
                        _iface_type = "Ethernet"
                    else:
                        _iface_type = _blk.strip().split("\n")[0].strip()
                    break
        # Get the IP
        if _default_iface:
            _ip_r = _sp.run(["ipconfig", "getifaddr", _default_iface], capture_output=True, text=True, timeout=1)
            if _ip_r.stdout.strip():
                net_ip = _ip_r.stdout.strip()
        # SSID only makes sense for Wi-Fi
        if _is_wifi:
            try:
                from System.alice_hardware_body import wifi as _hw_wifi
                _wf = _hw_wifi()
                if _wf.get("associated") and _wf.get("ssid"):
                    net_ssid = _wf["ssid"]
                elif _wf.get("powered_on") is False:
                    net_ssid = "Wi-Fi Off"
                else:
                    net_ssid = "Wi-Fi (SSID hidden by macOS)"
            except Exception:
                net_ssid = "Wi-Fi (SSID hidden by macOS)"
        else:
            net_ssid = f"{_iface_type} ({_default_iface})"
    except Exception:
        pass

    # WhatsApp Bridge status — use the actual local health endpoint, not pgrep.
    wa_bridge_detail = "Bridge not reachable"
    try:
        from System.whatsapp_bridge_autopilot import bridge_health

        _wa = bridge_health(timeout=1.0)
        wa_bridge_live = bool(_wa.get("ok"))
        wa_bridge_detail = str(_wa.get("result") or _wa.get("status") or wa_bridge_detail)
    except Exception as exc:
        wa_bridge_detail = f"Bridge health probe failed: {type(exc).__name__}"
        pass

    return {
        "net_ssid": net_ssid,
        "net_ip": net_ip,
        "wa_bridge_live": wa_bridge_live,
        "wa_bridge_detail": wa_bridge_detail,
        "hw_chip": hw_chip,
        "hw_memory": hw_memory,
        "hw_os": hw_os,
        "genesis": genesis_data,
        "score": score,
        "grade": "HEALTHY" if score >= 80 else "NOMINAL" if score >= 60 else "DEGRADING" if score >= 40 else "CRITICAL",
        "dimensions": dimensions,
        "state_mb": state_mb,
        "iris_mb": iris_mb,
        "net_stgm": float(economics.get("canonical_wallet_sum", economics.get("net_stgm", 0.0)) or 0.0),
        "spend_stgm": float(economics.get("spend", 0.0) or 0.0),
        "metabolic_mode": metabolic.get("mode", "UNKNOWN"),
        "budget_multiplier": float(metabolic.get("budget_multiplier", 0.0) or 0.0),
        "rest_seconds": float(metabolic.get("rest_seconds", 0.0) or 0.0),
        "apps_total": len(manifest),
        "app_groups": {k: len(v) for k, v in group_manifest(manifest).items()},
        "missing_apps": [
            name for name, meta in manifest.items()
            if not (_REPO / str(meta.get("entry_point", ""))).exists()
        ],
        "default_ollama_model": get_default_ollama_model(),
        "alice_brain_model": get_default_ollama_model(),
        "corvid_model": resolve_ollama_model(app_context="corvid_apprentice"),
        "genesis_ok": genesis_ok,
        "hw_serial": hw_serial,
        "digest": digest,
    }


class _BrainDiagramWidget(QWidget):
    """Live-painted brain architecture diagram — lightweight QPainter animation.

    Pulse strategy (zero file I/O on paint tick):
    • _pulse_tick: 80 ms QTimer — advances signal-dot positions along edges
      and computes cortex glow breath. All pure math, no disk/network.
    • _health_tick: 5 s QTimer — probes Ollama /api/tags in a thread;
      result stored in _ollama_live bool. Only one probe in-flight at a time.
    """

    _NODES = [
        # idx, x_frac, y_frac, label, sublabel, r, g, b
        (0,  0.50, 0.44, "🧠 CORTEX",   "",              0,   200, 255),  # primary brain
        (1,  0.50, 0.04, "👁 EYES",      "Iris",          0,   220, 130),  # sensory input
        (2,  0.08, 0.30, "🎙 EARS",      "Whisper STT",   0,   200, 130),  # sensory input
        (3,  0.92, 0.30, "🔊 VOICE",     "macOS TTS",     0,   200, 130),  # output effector
        (4,  0.12, 0.82, "🐦 CORVID",    "",              180, 100, 255),  # output organ
        (5,  0.50, 0.90, "⚡ REFLEX",    "Pure Python",   255, 200,  60),  # output organ
        (6,  0.88, 0.82, "💬 WhatsApp",  "Effector",       37, 211, 102),  # output effector
        (7,  0.50, 0.60, "🧬 MEMORY",    "Hippocampus",  100, 160, 255),  # sub-cortex store
        (8,  0.88, 0.12, "🔭 SCOUT",     "",              255, 180,  40),  # Qwen3.5 multimodal input
        (9,  0.12, 0.12, "🩺 DOCTOR",    "Granite4.1",   210, 120,  60),  # text/tool/JSON doctor
        (10, 0.88, 0.56, "🔤 C1",        "Qwen2.5 LoRA", 180, 200,  80),  # classifier input
    ]
    # Sensory/classifier inputs arrive AT cortex (dot travels src → dst = toward cortex)
    _EDGES_IN  = [(1, 0), (2, 0), (8, 0), (9, 0), (10, 0)]
    # Output signals travel FROM cortex to effectors
    _EDGES_OUT = [(0, 3), (0, 4), (0, 5), (0, 6), (0, 7)]
    _EDGES = _EDGES_IN + _EDGES_OUT

    def __init__(self, cortex_model: str, corvid_model: str) -> None:
        super().__init__()
        self._cortex_label = cortex_model or "sifta-gemma4-alice"
        self._corvid_label = corvid_model or "qwen3.5:2b"
        self._ollama_live: bool = True
        self._probe_running: bool = False
        # Scout label — detect hardware and set appropriate model name
        self._scout_label = "qwen3.5:9b"  # M5 default
        try:
            import subprocess as _sp
            _res = _sp.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=1)
            mem_gb = int(_res.stdout.strip()) / (1024**3)
            self._scout_label = "qwen3.5:9b" if mem_gb >= 24 else "qwen3.5:4b"
        except Exception:
            pass

        # Pulse state
        import math
        self._tick: int = 0
        self._math = math

        # Per-edge dot phases (offset so they don't all fire simultaneously)
        n_edges = len(self._EDGES)
        self._dot_phases = [i / n_edges for i in range(n_edges)]

        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(290)

        # 80 ms paint tick (≈12 fps — smooth but very cheap)
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(80)
        self._pulse_timer.timeout.connect(self._on_pulse)
        self._pulse_timer.start()

        # 5 s health probe
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(5000)
        self._health_timer.timeout.connect(self._probe_ollama)
        self._health_timer.start()
        self._probe_ollama()  # immediate first check

    def _on_pulse(self) -> None:
        self._tick += 1
        speed = 0.018  # dots travel at this fraction of the edge per tick
        self._dot_phases = [(p + speed) % 1.0 for p in self._dot_phases]
        self.update()

    def _probe_ollama(self) -> None:
        """Non-blocking Ollama /api/tags ping — uses a daemon thread, zero UI block."""
        if self._probe_running:
            return
        self._probe_running = True
        import threading
        def _check():
            try:
                import urllib.request
                with urllib.request.urlopen(
                    "http://127.0.0.1:11434/api/tags", timeout=2.0
                ) as r:
                    self._ollama_live = (r.status == 200)
            except Exception:
                self._ollama_live = False
            finally:
                self._probe_running = False
        threading.Thread(target=_check, daemon=True).start()

    def update_cortex_label(self, text: str) -> None:
        self._cortex_label = text or "—"
        self.update()

    def update_corvid_label(self, text: str) -> None:
        self._corvid_label = text or "—"
        self.update()

    # ── helpers ────────────────────────────────────────────────────────────

    def _node_center(self, idx: int, w: int, h: int) -> QPointF:
        row = self._NODES[idx]
        return QPointF(row[1] * w, row[2] * h)

    def _node_color(self, idx: int, alpha: int = 255) -> QColor:
        row = self._NODES[idx]
        return QColor(row[5], row[6], row[7], alpha)

    def _node_label(self, idx: int) -> str:
        if idx == 0:
            return self._NODES[idx][3]
        return self._NODES[idx][3]

    def _node_sublabel(self, idx: int) -> str:
        if idx == 0:
            return self._cortex_label
        if idx == 4:  # CORVID
            return self._corvid_label
        if idx == 8:  # SCOUT
            return self._scout_label
        return self._NODES[idx][4]

    # ── paint ──────────────────────────────────────────────────────────────

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        breath = (math.sin(self._tick * 0.06) + 1.0) / 2.0
        n_in  = len(self._EDGES_IN)

        # ── 1. Draw edges + travelling signal dots ─────────────────────────
        for edge_i, (src_i, dst_i) in enumerate(self._EDGES):
            src = self._node_center(src_i, w, h)
            dst = self._node_center(dst_i, w, h)
            is_input = edge_i < n_in  # sensory/classifier inputs → cortex

            # Pick colour from destination node for outputs, source node for inputs
            colour_node = src_i if is_input else dst_i
            r, g, b = self._NODES[colour_node][5], self._NODES[colour_node][6], self._NODES[colour_node][7]

            # Input edges are slightly brighter / warmer; output edges use dst colour
            glow_a = 28 if is_input else 18
            line_a = 110 if is_input else 80
            p.setPen(QPen(QColor(r, g, b, glow_a), 5.0))
            p.drawLine(src, dst)
            p.setPen(QPen(QColor(r, g, b, line_a), 1.4))
            p.drawLine(src, dst)

            # Travelling dot — lerp along the edge
            t = self._dot_phases[edge_i]
            dot_x = src.x() + (dst.x() - src.x()) * t
            dot_y = src.y() + (dst.y() - src.y()) * t
            dot_alpha = int(180 + 70 * breath)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(r, g, b, dot_alpha))
            p.drawEllipse(QPointF(dot_x, dot_y), 3.5, 3.5)
            p.setBrush(QColor(r, g, b, 40))
            p.drawEllipse(QPointF(dot_x, dot_y), 7.0, 7.0)

        # ── 2. Draw node cards ─────────────────────────────────────────────
        for idx, (_, nx, ny, label, _, r, g, b) in enumerate(self._NODES):
            px, py = nx * w, ny * h
            is_cortex = (idx == 0)
            is_memory = (idx == 7)
            is_input_node = idx in (1, 2, 8, 9, 10)  # sensory/classifier inputs

            card_w = 152 if is_cortex else (105 if is_memory else 110)
            card_h = 58  if is_cortex else (20  if is_memory else 44)
            rect = QRectF(px - card_w / 2, py - card_h / 2, card_w, card_h)

            p.setBrush(QColor(14, 16, 26, 215))

            if is_cortex:
                live_r, live_g, live_b = (0, 220, 255) if self._ollama_live else (255, 80, 60)
                border_alpha = int(140 + 100 * breath)
                p.setPen(QPen(QColor(live_r, live_g, live_b, border_alpha), 2.2))
            elif is_input_node:
                # Input nodes get a slightly warmer border to signal they feed INTO cortex
                p.setPen(QPen(QColor(r, g, b, 150), 1.6))
            else:
                p.setPen(QPen(QColor(r, g, b, 110), 1.4))

            p.drawRoundedRect(rect, 10.0, 10.0)

            # Cortex multi-ring glow
            if is_cortex:
                live_r2, live_g2, live_b2 = (0, 220, 255) if self._ollama_live else (255, 80, 60)
                p.setBrush(QColor(0, 0, 0, 0))
                for gi in range(1, 4):
                    ga = int((30 - gi * 7) * breath)
                    p.setPen(QPen(QColor(live_r2, live_g2, live_b2, max(ga, 0)), 1.0))
                    p.drawRoundedRect(rect.adjusted(-gi*3, -gi*3, gi*3, gi*3), 12.0, 12.0)

            # Input node subtle inner pulse circle
            if is_input_node and not is_memory:
                pulse_r = int(3 + 2 * breath)
                p.setBrush(QColor(r, g, b, int(80 + 80 * breath)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(px - card_w/2 + 10, py), float(pulse_r), float(pulse_r))

            # Text
            p.setPen(QColor(240, 245, 255))
            if is_memory:
                p.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._node_sublabel(idx))
            else:
                p.setFont(QFont("Menlo", 11 if is_cortex else 8, QFont.Weight.Bold))
                top_rect = QRectF(rect.x(), rect.y() + 4, rect.width(), rect.height() * 0.48)
                p.drawText(top_rect, Qt.AlignmentFlag.AlignCenter, label)
                sub_color = QColor(live_r, live_g, live_b, 190) if is_cortex else QColor(r, g, b, 190)
                p.setPen(sub_color)
                p.setFont(QFont("Menlo", 8 if is_cortex else 6))
                bot_rect = QRectF(rect.x(), rect.y() + rect.height() * 0.50, rect.width(), rect.height() * 0.48)
                p.drawText(bot_rect, Qt.AlignmentFlag.AlignCenter, self._node_sublabel(idx))

        # ── 3. Status bar ──────────────────────────────────────────────────
        status_text = "● Ollama online" if self._ollama_live else "● Ollama offline"
        status_color = QColor(0, 200, 130) if self._ollama_live else QColor(255, 80, 60)
        p.setPen(status_color)
        p.setFont(QFont("Menlo", 9))
        p.drawText(QRectF(0, h - 18, w, 16), Qt.AlignmentFlag.AlignRight, status_text)

        p.end()



class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "", detail: str = "") -> None:
        super().__init__()
        self.setObjectName("MetricCard")
        self.setStyleSheet(
            "QFrame#MetricCard { background: rgb(20, 22, 32);"
            " border: 1px solid rgb(47, 52, 68); border-radius: 8px; }"
            "QFrame#MetricCard QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        self.title = QLabel(title)
        self.title.setStyleSheet("color: rgb(145, 153, 180); font-size: 11px;")
        self.value = QLabel(value)
        self.value.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
        self.value.setStyleSheet("color: rgb(238, 244, 255);")
        self.detail = QLabel(detail)
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color: rgb(112, 122, 150); font-size: 11px;")
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def set_metric(self, value: str, detail: str = "") -> None:
        self.value.setText(value)
        self.detail.setText(detail)


class SystemSettingsWidget(SiftaBaseWidget):
    APP_NAME = "System Settings"

    def build_ui(self, layout: QVBoxLayout) -> None:
        shell = QHBoxLayout()
        shell.setSpacing(10)
        layout.addLayout(shell, 1)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(180)
        self.sidebar.setStyleSheet(
            "QListWidget { background: rgb(18, 20, 28); border: 1px solid rgb(44, 49, 64); border-radius: 8px; }"
            "QListWidget::item { padding: 9px 10px; }"
            "QListWidget::item:selected { background: rgb(56, 101, 190); border-radius: 6px; color: white; }"
        )
        shell.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        shell.addWidget(self.stack, 1)

        self._pages = {
            "Identity": self._identity_page(),
            "Appearance": self._appearance_page(),
            "Audio": self._audio_page(),
            "Body": self._body_page(),
            "Network": self._network_page(),
            "Inference": self._inference_page(),
            "Economy": self._economy_page(),
            "Storage": self._privacy_page(),
            "Developer": self._developer_page(),
        }
        for name, page in self._pages.items():
            self.sidebar.addItem(QListWidgetItem(name))
            self.stack.addWidget(page)
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        row = QHBoxLayout()
        row.addStretch()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        layout.addLayout(row)
        self.refresh()
        QTimer.singleShot(0, self._collapse_entity_chat)

    def _collapse_entity_chat(self) -> None:
        if getattr(self, "_gci", None):
            self._splitter.setSizes([max(1, self.width()), 0])

    def _page(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(8, 8, 8, 8)
        heading = QLabel(title)
        heading.setFont(QFont("Menlo", 20, QFont.Weight.Bold))
        heading.setStyleSheet("color: rgb(238, 244, 255);")
        root.addWidget(heading)
        return page, root

    def _appearance_page(self) -> QWidget:
        page, root = self._page("Appearance")
        
        info = QLabel("Select the visual identity of the SIFTA organism. The organism remains the same, only the clothing changes.\n(Restart OS for full effect)")
        info.setWordWrap(True)
        info.setStyleSheet("color: rgb(145, 153, 180); margin-bottom: 12px;")
        root.addWidget(info)

        self.theme_combo = QComboBox()
        self.theme_combo.setStyleSheet(
            "QComboBox { background: rgb(20, 22, 32); color: rgb(238, 244, 255); "
            "border: 1px solid rgb(47, 52, 68); border-radius: 6px; padding: 6px 10px; font-size: 14px; }"
        )
        
        current_theme = load_active_theme_id()
        idx_to_select = 0
        for i, (tid, palette) in enumerate(THEMES.items()):
            self.theme_combo.addItem(palette.display_name, userData=tid)
            if tid == current_theme:
                idx_to_select = i
        self.theme_combo.setCurrentIndex(idx_to_select)
        
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        root.addWidget(self.theme_combo)
        
        # Display OS line for selected
        self.theme_os_line = QLabel(THEMES[current_theme].os_line)
        self.theme_os_line.setStyleSheet("color: rgb(112, 122, 150); font-family: monospace; font-size: 11px; margin-top: 8px;")
        root.addWidget(self.theme_os_line)
        
        root.addStretch()
        return page

    def _on_theme_changed(self, idx: int) -> None:
        tid = self.theme_combo.itemData(idx)
        if tid:
            save_active_theme_id(tid)
            self.theme_os_line.setText(THEMES[tid].os_line + " (Saved. Please restart OS.)")

    def _identity_page(self) -> QWidget:
        page, root = self._page("Identity")

        # Owner photo thumbnail
        self.id_photo = QLabel()
        self.id_photo.setFixedSize(120, 120)
        self.id_photo.setStyleSheet(
            "background: rgb(20, 24, 36); border: 2px solid rgb(60, 200, 160); "
            "border-radius: 60px;"
        )
        self.id_photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.id_photo.setText("No Photo")
        root.addWidget(self.id_photo, alignment=Qt.AlignmentFlag.AlignCenter)

        # Scan Face button — Alice uses the camera to capture the owner's face
        self.scan_face_btn = QPushButton("\ud83d\udcf7 Scan Face for Genesis")
        self.scan_face_btn.setFixedHeight(44)
        self.scan_face_btn.setStyleSheet(
            "QPushButton { background: rgb(20, 40, 60); color: rgb(100, 200, 255); "
            "border: 1px solid rgb(40, 80, 120); border-radius: 8px; font-size: 14px; font-weight: bold; } "
            "QPushButton:hover { background: rgb(30, 55, 80); }"
        )
        self.scan_face_btn.clicked.connect(self._scan_face_for_genesis)
        root.addWidget(self.scan_face_btn)

        self.id_owner = MetricCard("Owner", "--")
        self.id_genesis = MetricCard("Genesis Status", "--")
        self.id_spec = MetricCard("Machine Spec", "--")
        self.id_os = MetricCard("Operating System", "--")
        self.id_serial = MetricCard("Silicon Hardware", "--")
        self.id_anchor = MetricCard("Genesis Anchor", "--")
        self.id_sig = MetricCard("Signature", "--")
        self.id_digest = MetricCard("Electric Field Digest", "--")
        root.addWidget(self.id_owner)
        root.addWidget(self.id_genesis)
        root.addWidget(self.id_spec)
        root.addWidget(self.id_os)
        root.addWidget(self.id_serial)
        root.addWidget(self.id_anchor)
        root.addWidget(self.id_sig)
        root.addWidget(self.id_digest)
        root.addStretch()
        return page

    def _scan_face_for_genesis(self) -> None:
        """Use the Mac camera to capture the owner's face and run the Genesis Ceremony.
        
        Camera Priority (per Dr. Cursor's review):
        1. Index 0 = Mac built-in hardware camera (always tried first)
        2. Fallback to indices 1-4 only if index 0 fails
        3. Record every probe failure with reason for Alice to read
        4. Camera errors and Genesis errors are reported separately
        """
        import cv2

        self.scan_face_btn.setText("\u23f3 Scanning cameras\u2026")
        self.scan_face_btn.setEnabled(False)
        QApplication.processEvents()

        probe_log = []
        locked_idx = -1

        for idx in range(5):
            self.scan_face_btn.setText(f"\u23f3 Probing camera {idx}\u2026")
            QApplication.processEvents()
            entry = {"index": idx, "status": "unknown", "reason": "", "width": 0}
            try:
                cap = cv2.VideoCapture(idx)
                if not cap.isOpened():
                    entry["status"] = "open_failed"
                    entry["reason"] = "Device did not open"
                    probe_log.append(entry)
                    continue
                ret, test_frame = cap.read()
                cap.release()
                if not ret or test_frame is None:
                    entry["status"] = "read_failed"
                    entry["reason"] = "Opened but returned no frame"
                    probe_log.append(entry)
                    continue
                entry["status"] = "ok"
                entry["width"] = int(test_frame.shape[1])
                entry["height"] = int(test_frame.shape[0])
                probe_log.append(entry)
                if locked_idx == -1:
                    locked_idx = idx
            except Exception as exc:
                entry["status"] = "exception"
                entry["reason"] = f"{type(exc).__name__}: {str(exc)[:60]}"
                probe_log.append(entry)

        if locked_idx == -1:
            fail_summary = "; ".join(f"cam{e['index']}:{e['status']}" for e in probe_log)
            self.scan_face_btn.setText(f"\u274c No cameras [{fail_summary}]")
            self.scan_face_btn.setEnabled(True)
            return

        locked_entry = next(e for e in probe_log if e["index"] == locked_idx)
        self.scan_face_btn.setText(f"\u23f3 Locked cam{locked_idx} ({locked_entry['width']}x{locked_entry.get('height', '?')}px)")
        QApplication.processEvents()

        cap = None
        try:
            cap = cv2.VideoCapture(locked_idx)
            if not cap.isOpened():
                self.scan_face_btn.setText(f"\u274c cam{locked_idx} lock failed on re-open")
                self.scan_face_btn.setEnabled(True)
                return
            for _ in range(20):
                cap.read()
            ret, frame = cap.read()
            cap.release()
            cap = None
            if not ret or frame is None:
                self.scan_face_btn.setText(f"\u274c cam{locked_idx} capture returned None")
                self.scan_face_btn.setEnabled(True)
                return
            genesis_dir = Path.home() / ".sifta_keys" / "owner_genesis"
            genesis_dir.mkdir(parents=True, exist_ok=True)
            photo_path = genesis_dir / "genesis_photo.jpg"
            cv2.imwrite(str(photo_path), frame)
            self.scan_face_btn.setText("\u23f3 Running Genesis Ceremony\u2026")
            QApplication.processEvents()
        except Exception as cam_err:
            self.scan_face_btn.setText(f"\u274c Camera: {type(cam_err).__name__}: {str(cam_err)[:35]}")
            self.scan_face_btn.setEnabled(True)
            if cap is not None:
                cap.release()
            return

        try:
            from System.owner_genesis import perform_genesis
            owner_name = ""
            try:
                import subprocess
                res = subprocess.run(["id", "-F"], capture_output=True, text=True, timeout=1)
                if res.stdout.strip():
                    owner_name = res.stdout.strip()
            except Exception:
                pass
            perform_genesis(str(photo_path), owner_name or "Owner")
            self.scan_face_btn.setText("\u2705 Genesis Complete")
            self.scan_face_btn.setStyleSheet(
                "QPushButton { background: rgb(20, 60, 40); color: rgb(100, 255, 150); "
                "border: 1px solid rgb(40, 100, 60); border-radius: 8px; font-size: 14px; font-weight: bold; } "
                "QPushButton:hover { background: rgb(30, 80, 50); }"
            )
            self.refresh()
        except Exception as gen_err:
            self.scan_face_btn.setText(f"\u274c Genesis: {type(gen_err).__name__}: {str(gen_err)[:30]}")
        finally:
            self.scan_face_btn.setEnabled(True)


    def _audio_page(self) -> QWidget:
        page, root = self._page("Audio")
        self.audio_status_card = MetricCard("Alice Audio", "--")
        root.addWidget(self.audio_status_card)

        settings = _load_audio_settings()
        gain = _load_mic_gain()

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        form.addWidget(QLabel("Ear model"), 0, 0)
        self.audio_whisper_combo = QComboBox()
        self.audio_whisper_combo.addItems(WHISPER_MODELS)
        self.audio_whisper_combo.setCurrentText(settings["whisper_model"])
        self.audio_whisper_combo.setToolTip("Speech-to-text model Alice uses after the microphone captures speech.")
        form.addWidget(self.audio_whisper_combo, 0, 1)

        form.addWidget(QLabel("Mic gain"), 1, 0)
        gain_row = QHBoxLayout()
        self.audio_gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.audio_gain_slider.setMinimum(int(MIN_MIC_GAIN * 10))
        self.audio_gain_slider.setMaximum(int(MAX_MIC_GAIN * 10))
        self.audio_gain_slider.setSingleStep(1)
        self.audio_gain_slider.setValue(int(round(gain * 10)))
        self.audio_gain_label = QLabel(f"{gain:.1f}x")
        self.audio_gain_label.setMinimumWidth(44)
        gain_row.addWidget(self.audio_gain_slider, 1)
        gain_row.addWidget(self.audio_gain_label)
        form.addLayout(gain_row, 1, 1)

        form.addWidget(QLabel("Alice voice"), 2, 0)
        self.audio_voice_combo = QComboBox()
        self.audio_voice_combo.addItem("Alice Default  ·  best available", userData="")
        for name, locale in _curated_voice_rows():
            self.audio_voice_combo.addItem(f"{name}  ·  {locale}", userData=name)
        voice_idx = self.audio_voice_combo.findData(settings["voice_name"])
        if voice_idx >= 0:
            self.audio_voice_combo.setCurrentIndex(voice_idx)
        form.addWidget(self.audio_voice_combo, 2, 1)

        form.addWidget(QLabel("Context"), 3, 0)
        self.audio_grounding_check = QCheckBox("Ground Alice in current swarm state")
        self.audio_grounding_check.setChecked(settings["ground_swarm_state"])
        self.audio_grounding_check.setToolTip(
            "Allows Alice to receive the current visual stigmergy and recent semantic state."
        )
        form.addWidget(self.audio_grounding_check, 3, 1)

        root.addLayout(form)

        note = QLabel(
            "These controls live here so Talk to Alice stays a conversation surface, "
            "not a hardware panel."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: rgb(145, 153, 180);")
        root.addWidget(note)

        self.audio_gain_slider.valueChanged.connect(self._on_audio_gain_changed)
        self.audio_whisper_combo.currentTextChanged.connect(self._save_audio_page)
        self.audio_voice_combo.currentIndexChanged.connect(self._save_audio_page)
        self.audio_grounding_check.toggled.connect(self._save_audio_page)

        root.addStretch()
        self._update_audio_status()
        return page

    def _on_audio_gain_changed(self, raw_value: int) -> None:
        gain = _clamp_gain(raw_value / 10.0)
        self.audio_gain_label.setText(f"{gain:.1f}x")
        _save_mic_gain(gain)
        self._update_audio_status()

    def _save_audio_page(self, *_args: Any) -> None:
        voice_name = self.audio_voice_combo.currentData()
        _save_audio_settings(
            {
                "whisper_model": self.audio_whisper_combo.currentText(),
                "voice_name": voice_name if isinstance(voice_name, str) else "",
                "ground_swarm_state": self.audio_grounding_check.isChecked(),
            }
        )
        self._update_audio_status()

    def _update_audio_status(self) -> None:
        if not hasattr(self, "audio_status_card"):
            return
        settings = _load_audio_settings()
        voice = settings["voice_name"] or "Alice Default"
        grounding = "grounded" if settings["ground_swarm_state"] else "ungrounded"
        self.audio_status_card.set_metric(
            f"{settings['whisper_model']} · {_load_mic_gain():.1f}x",
            f"{voice}; {grounding}",
        )

    def _body_page(self) -> QWidget:
        page, root = self._page("Body Status")
        grid = QGridLayout()
        self.card_health = MetricCard("Global Health", "--")
        self.card_mode = MetricCard("Metabolism", "--")
        grid.addWidget(self.card_health, 0, 0)
        grid.addWidget(self.card_mode, 0, 1)
        root.addLayout(grid)

        self.body_grid = QGridLayout()
        self.body_cards: dict[str, MetricCard] = {}
        labels = ["hardware", "memory", "economic", "mutation", "field", "mortality"]
        for i, key in enumerate(labels):
            card = MetricCard(key.title(), "--")
            self.body_cards[key] = card
            self.body_grid.addWidget(card, i // 2, i % 2)
        root.addLayout(self.body_grid)
        root.addStretch()
        return page

    def _network_page(self) -> QWidget:
        page, root = self._page("Network")
        self.net_ssid = MetricCard("Connection", "--", "Default route interface")
        self.net_ip = MetricCard("Local IP", "--", "Default route interface address")
        self.net_wa = MetricCard("WhatsApp Bridge", "--", "Baileys Node.js bridge on port 3001")
        self.net_relay = MetricCard("Mesh Relay", "N/A", "WebSocket cross-node proxy")
        self.net_nerve = MetricCard("Nerve Channel", "UDP Broadcast", "Fast autonomic reflex bus")
        root.addWidget(self.net_ssid)
        root.addWidget(self.net_ip)
        root.addWidget(self.net_wa)

        # WhatsApp Connect / Disconnect toggle button
        self.wa_toggle_btn = QPushButton("⏳ Checking…")
        self.wa_toggle_btn.setFixedHeight(44)
        self.wa_toggle_btn.setStyleSheet(
            "QPushButton { background: rgb(30, 35, 50); color: rgb(200, 210, 230); "
            "border: 1px solid rgb(60, 70, 90); border-radius: 8px; font-size: 14px; font-weight: bold; } "
            "QPushButton:hover { background: rgb(40, 50, 70); }"
        )
        self.wa_toggle_btn.clicked.connect(self._toggle_whatsapp_bridge)
        root.addWidget(self.wa_toggle_btn)

        root.addWidget(self.net_relay)
        root.addWidget(self.net_nerve)
        root.addStretch()
        return page

    def _toggle_whatsapp_bridge(self) -> None:
        """Start or stop the WhatsApp Baileys bridge."""
        import subprocess
        try:
            res = subprocess.run(["pgrep", "-f", "bridge.js"], capture_output=True, text=True, timeout=1)
            is_running = bool(res.stdout.strip())
        except Exception:
            is_running = False

        if is_running:
            # Kill it
            try:
                subprocess.run(["pkill", "-f", "bridge.js"], timeout=3)
                subprocess.run(["pkill", "-f", "scripts/whatsapp_alice_server.py"], timeout=3)
                self.wa_toggle_btn.setText("🔌 Connect WhatsApp")
                self.wa_toggle_btn.setStyleSheet(
                    "QPushButton { background: rgb(20, 60, 40); color: rgb(100, 255, 150); "
                    "border: 1px solid rgb(40, 100, 60); border-radius: 8px; font-size: 14px; font-weight: bold; } "
                    "QPushButton:hover { background: rgb(30, 80, 50); }"
                )
                self.net_wa.set_metric("Offline", "Bridge stopped by user")
            except Exception as e:
                self.net_wa.set_metric("Error", str(e))
        else:
            # Start it
            try:
                import os
                repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                script_path = os.path.join(repo_dir, "scripts", "start_swarm_whatsapp.sh")
                log_path = os.path.join(repo_dir, ".sifta_state", "runtime_logs", "whatsapp_bridge.log")
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as log:
                    subprocess.Popen(
                        ["bash", script_path],
                        cwd=repo_dir,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                self.wa_toggle_btn.setText("🔴 Disconnect WhatsApp")
                self.wa_toggle_btn.setStyleSheet(
                    "QPushButton { background: rgb(70, 20, 20); color: rgb(255, 120, 120); "
                    "border: 1px solid rgb(120, 40, 40); border-radius: 8px; font-size: 14px; font-weight: bold; } "
                    "QPushButton:hover { background: rgb(90, 30, 30); }"
                )
                self.net_wa.set_metric("Starting…", "Bridge launching")
            except Exception as e:
                self.net_wa.set_metric("Error", str(e))

    def _inference_page(self) -> QWidget:
        page, root = self._page("Inference")

        # Resolve active models — no user-editable dropdowns
        try:
            from System.swarm_corvid_apprentice import SwarmCorvidApprentice
            import inspect
            sig = inspect.signature(SwarmCorvidApprentice.__init__)
            self._corvid_default = str(sig.parameters["model"].default)
        except Exception:
            self._corvid_default = "qwen3.5:2b"

        active_cortex = get_default_ollama_model() or "sifta-gemma4-alice"

        # ── Fetch physical weights from Ollama once (no timer, cached) ──
        model_weights: dict[str, int] = {}
        try:
            import urllib.request as _ur
            with _ur.urlopen("http://127.0.0.1:11434/api/tags", timeout=2.0) as _r:
                for m in json.loads(_r.read()).get("models", []):
                    model_weights[m["name"]] = m.get("size", 0)
        except Exception:
            pass

        def _fmt_weight(model_name: str) -> str:
            """Return human-readable weight string for a model name."""
            return f"  {_format_ollama_weight_label(model_name, model_weights)}"

        def _state_dir_weight(subdir: str) -> str:
            """Measure a .sifta_state subdirectory without blocking."""
            from pathlib import Path as _P
            p = _P(".sifta_state") / subdir
            if not p.exists():
                return "⚖ 0 MB"
            try:
                total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                if total >= 1e9:
                    return f"⚖ {total/1e9:.2f} GB"
                return f"⚖ {total/1e6:.1f} MB"
            except Exception:
                return "⚖ ? MB"

        # ── Brain Architecture Diagram (live, animated) ──
        diagram = _BrainDiagramWidget(active_cortex, self._corvid_default)
        diagram.setFixedHeight(290)
        root.addWidget(diagram)
        self._brain_diagram = diagram

        # ── Status chips — READ ONLY ──
        chip_style_cortex = (
            "background: rgb(0, 30, 45); color: rgb(0, 220, 255); "
            "border: 1px solid rgb(0, 150, 200); border-radius: 8px; "
            "padding: 6px 12px; font-size: 12px; font-family: Menlo;"
        )
        chip_style_organ = (
            "background: rgb(10, 28, 18); color: rgb(0, 200, 130); "
            "border: 1px solid rgb(0, 140, 90); border-radius: 8px; "
            "padding: 6px 12px; font-size: 12px; font-family: Menlo;"
        )
        chip_style_fixed = (
            "background: rgb(28, 26, 10); color: rgb(200, 170, 50); "
            "border: 1px solid rgb(140, 110, 0); border-radius: 8px; "
            "padding: 6px 12px; font-size: 12px; font-family: Menlo;"
        )
        chip_style_weights = (
            "background: rgb(20, 10, 30); color: rgb(160, 100, 220); "
            "border: 1px solid rgb(100, 50, 160); border-radius: 8px; "
            "padding: 6px 12px; font-size: 12px; font-family: Menlo;"
        )
        weight_style = (
            "color: rgb(100, 115, 135); font-size: 10px; font-family: Menlo; "
            "padding: 4px 6px; "
        )
        planned_style = (
            "color: rgb(80, 80, 80); font-size: 10px; font-family: Menlo; "
            "padding: 4px 6px; font-style: italic;"
        )

        def _chip_row(label: str, value: str, chip_css: str, weight_str: str = "",
                      planned: bool = False) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label)
            lbl.setStyleSheet("color: rgb(130, 140, 160); font-size: 11px; min-width: 118px;")
            chip = QLabel(value)
            chip.setStyleSheet(chip_css)
            row.addWidget(lbl)
            row.addWidget(chip)
            if weight_str:
                w_lbl = QLabel(weight_str)
                w_lbl.setStyleSheet(planned_style if planned else weight_style)
                row.addWidget(w_lbl)
            row.addStretch()
            return row

        def _scout_weight(model: str) -> tuple[str, bool]:
            """Returns (label, is_planned). Never shows stale prefix data."""
            label = _fmt_weight(model).strip()
            if label and label != "not installed":
                return label, False
            return "PLANNED  ·  ↓ pull to activate", True

        # ── Live summary banner ──
        installed_count = len(model_weights)
        total_bytes = sum(model_weights.values())
        total_gb = total_bytes / 1e9 if total_bytes > 0 else 0
        summary_lbl = QLabel(
            f"{'✅' if installed_count >= 2 else '⚠️'}  Ollama live  ·  "
            f"{installed_count} model{'s' if installed_count != 1 else ''} installed  ·  "
            f"⚖ {total_gb:.1f} GB on disk"
        )
        summary_lbl.setStyleSheet(
            "color: rgb(0, 210, 120); font-size: 11px; font-family: Menlo; "
            "background: rgb(5, 22, 14); border: 1px solid rgb(0, 100, 60); "
            "border-radius: 6px; padding: 4px 10px; margin-bottom: 4px;"
        )
        root.addWidget(summary_lbl)

        # ── Cortex section ──
        cortex_heading = QLabel("🧠  Primary Cortex  ·  Alice's main reasoning brain")
        cortex_heading.setStyleSheet(
            "color: rgb(0, 220, 255); font-size: 13px; font-weight: bold; margin-top: 2px;"
        )
        root.addWidget(cortex_heading)
        root.addLayout(_chip_row("Alice Cortex", active_cortex,
                                  chip_style_cortex, _fmt_weight(active_cortex)))

        # ── Corvid / Fallback section ──
        corvid_heading = QLabel("🐦  Corvid / Fallback  ·  fast reflex + canonical fallback model")
        corvid_heading.setStyleSheet(
            "color: rgb(0, 200, 130); font-size: 13px; font-weight: bold; margin-top: 6px;"
        )
        root.addWidget(corvid_heading)
        root.addLayout(_chip_row("Corvid · Fallback", self._corvid_default + "  ·  2.7 GB installed",
                                  chip_style_organ, _fmt_weight(self._corvid_default)))

        # ── Scout section (PLANNED) ──
        scout_heading = QLabel("🔭  Multimodal Scout  ·  vision receipts feed into Gemma4  [PLANNED]")
        scout_heading.setStyleSheet(
            "color: rgb(100, 100, 100); font-size: 13px; font-weight: bold; margin-top: 6px;"
        )
        root.addWidget(scout_heading)
        chip_style_scout_planned = (
            "background: rgb(20, 18, 5); color: rgb(100, 100, 80); "
            "border: 1px solid rgb(60, 55, 20); border-radius: 8px; "
            "padding: 6px 12px; font-size: 12px; font-family: Menlo;"
        )
        m5_w, m5_p = _scout_weight("qwen3.5:9b")
        mini_w, mini_p = _scout_weight("qwen3.5:4b")
        root.addLayout(_chip_row("M5 Scout",
                                  "qwen3.5:9b  ·  multimodal VLM",
                                  chip_style_scout_planned, m5_w, planned=m5_p))
        root.addLayout(_chip_row("Mac Mini Scout",
                                  "qwen3.5:4b  ·  8 GB safe",
                                  chip_style_scout_planned, mini_w, planned=mini_p))

        # ── Doctor section (PLANNED) ──
        doctor_heading = QLabel("🩺  Doctor Organ  ·  text / tool / JSON  [PLANNED]")
        doctor_heading.setStyleSheet(
            "color: rgb(100, 100, 100); font-size: 13px; font-weight: bold; margin-top: 6px;"
        )
        root.addWidget(doctor_heading)
        chip_style_doctor_planned = (
            "background: rgb(20, 10, 5); color: rgb(100, 80, 60); "
            "border: 1px solid rgb(60, 35, 10); border-radius: 8px; "
            "padding: 6px 12px; font-size: 12px; font-family: Menlo;"
        )
        gran_w, gran_p = _scout_weight("granite4.1")
        root.addLayout(_chip_row("Granite Doctor",
                                  "granite4.1  ·  router / coder / prover",
                                  chip_style_doctor_planned, gran_w, planned=gran_p))

        # ── Organs section ──
        organ_heading = QLabel("⚡  Reflex Organs  ·  pure-Python, run alongside cortex")
        organ_heading.setStyleSheet(
            "color: rgb(0, 200, 130); font-size: 13px; font-weight: bold; margin-top: 6px;"
        )
        root.addWidget(organ_heading)
        root.addLayout(_chip_row("Reflex Arc",    "Pure Python · no model", chip_style_fixed))
        root.addLayout(_chip_row("Thermal Cortex", "BISHOP · fever router", chip_style_fixed))

        # ── C1 Classifier section ──
        c1_heading = QLabel("🔤  C1 Classifier  ·  Qwen2.5 LoRA · SILENCE / TOOL / BOND / ENGAGE")
        c1_heading.setStyleSheet(
            "color: rgb(180, 200, 80); font-size: 13px; font-weight: bold; margin-top: 6px;"
        )
        root.addWidget(c1_heading)
        chip_style_c1 = (
            "background: rgb(20, 22, 8); color: rgb(180, 200, 80); "
            "border: 1px solid rgb(110, 130, 30); border-radius: 8px; "
            "padding: 6px 12px; font-size: 12px; font-family: Menlo;"
        )
        root.addLayout(_chip_row("C1 Classifier",  "sifta-classifier-c1  ·  role=classifier",
                                  chip_style_c1, _fmt_weight("sifta-classifier-c1")))
        root.addLayout(_chip_row("Training Corpus", "1,401 rows  ·  rank=16  dropout=0.1",
                                  chip_style_c1))

        # Reset button
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton("↺  Reset Brain to Default")
        reset_btn.setFixedHeight(32)
        reset_btn.setStyleSheet(
            "QPushButton { background: rgb(20, 22, 32); color: rgb(100, 115, 135); "
            "border: 1px solid rgb(40, 45, 60); border-radius: 8px; font-size: 11px; padding: 0 14px; }"
            "QPushButton:hover { background: rgb(28, 32, 48); color: rgb(0, 200, 255); "
            "border-color: rgb(0, 140, 200); }"
        )
        reset_btn.setToolTip(
            "If the assignments.json was manually edited and broke Alice,\n"
            "this restores sifta-gemma4-alice as the canonical cortex."
        )
        reset_btn.clicked.connect(self._reset_brain_to_default)
        reset_row.addWidget(reset_btn)
        root.addLayout(reset_row)

        self.inference_default_card = MetricCard("Alice Cortex", active_cortex)
        self.inference_default_card.set_metric(active_cortex, f"⚖ {total_gb:.1f} GB total")
        root.addWidget(self.inference_default_card)

        root.addStretch()
    def _reset_brain_to_default(self) -> None:
        """Restore the canonical gemma4 cortex without exposing model names to the user."""
        canonical = "sifta-gemma4-alice"
        set_default_ollama_model(canonical)
        set_app_ollama_model("talk_to_alice", canonical)
        if hasattr(self, "_brain_diagram"):
            self._brain_diagram.update_cortex_label(f"{canonical}:latest")
        self.refresh()

    def _on_inf_default_changed(self, text: str) -> None:
        """Internal hook — kept for programmatic use; not wired to any UI control."""
        if text:
            set_default_ollama_model(text)
            set_app_ollama_model("talk_to_alice", text)

    def _on_inf_corvid_changed(self, text: str) -> None:
        """Internal hook — kept for programmatic use; not wired to any UI control."""
        if text:
            set_app_ollama_model("corvid_apprentice", text)


    def _economy_page(self) -> QWidget:
        page, root = self._page("Swarm Economy")
        self.metabolism_card = MetricCard("Budget Governor", "--")
        self.wallet_card = MetricCard("STGM Reserve", "--")
        root.addWidget(self.metabolism_card)
        root.addWidget(self.wallet_card)
        root.addStretch()
        return page

    def _privacy_page(self) -> QWidget:
        page, root = self._page("Storage")
        self.storage_state_card = MetricCard(".sifta_state", "--")
        self.storage_iris_card = MetricCard("iris_frames", "--")
        root.addWidget(self.storage_state_card)
        root.addWidget(self.storage_iris_card)
        root.addStretch()
        return page

    def _developer_page(self) -> QWidget:
        page, root = self._page("Developer")
        self.card_apps = MetricCard("Applications", "--")
        root.addWidget(self.card_apps)
        self.apps_summary = QLabel()
        self.apps_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.apps_summary.setStyleSheet(
            "background: rgb(12, 14, 22); border: 1px solid rgb(44, 49, 64); border-radius: 8px; padding: 12px;"
        )
        root.addWidget(self.apps_summary, 1)
        return page

    def refresh(self) -> None:
        snap = read_system_settings_snapshot()

        # Identity
        gen = snap.get("genesis", {})
        # Owner photo
        photo_path = gen.get("photo_path", "")
        if photo_path:
            pix = QPixmap(photo_path)
            if not pix.isNull():
                pix = pix.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                self.id_photo.setPixmap(pix)
                self.id_photo.setStyleSheet(
                    "background: rgb(20, 24, 36); border: 2px solid rgb(60, 200, 160); "
                    "border-radius: 60px;"
                )
        else:
            self.id_photo.setText("No Photo")
        # Update scan button text based on genesis state
        if gen.get("ok"):
            self.scan_face_btn.setText("\ud83d\udcf7 Re-scan Face")
            self.scan_face_btn.setStyleSheet(
                "QPushButton { background: rgb(25, 30, 45); color: rgb(120, 140, 170); "
                "border: 1px solid rgb(50, 60, 80); border-radius: 8px; font-size: 13px; } "
                "QPushButton:hover { background: rgb(35, 45, 65); }"
            )
        else:
            self.scan_face_btn.setText("\ud83d\udcf7 Scan Face for Genesis")
            self.scan_face_btn.setStyleSheet(
                "QPushButton { background: rgb(20, 40, 60); color: rgb(100, 200, 255); "
                "border: 1px solid rgb(40, 80, 120); border-radius: 8px; font-size: 14px; font-weight: bold; } "
                "QPushButton:hover { background: rgb(30, 55, 80); }"
            )
        self.id_owner.set_metric(gen.get("owner_name", "<unclaimed>"), f"Generation {gen.get('generation', 0)} \u00b7 AI: {gen.get('ai_display_name', 'Alice')}")
        self.id_genesis.set_metric(gen.get("status", "MISSING"), "Cryptographic Genesis Ceremony")
        self.id_spec.set_metric(f"{snap.get('hw_chip', 'Unknown')} / {snap.get('hw_memory', 'Unknown')}", "Physical Machine Spec")
        self.id_os.set_metric(snap.get("hw_os", "Unknown"), "Host Environment")
        self.id_serial.set_metric(snap["hw_serial"], "Tied to specific Apple Metal")
        self.id_anchor.set_metric(gen.get("anchor", "N/A"), "SHA-256(photo_hash + silicon_serial)")
        self.id_sig.set_metric(gen.get("sig", "N/A"), "Ed25519 hardware signature")
        self.id_digest.set_metric(snap["digest"], "Dynamic Electric Field signature")

        # Network
        self.net_ssid.set_metric(snap.get("net_ssid", "Unknown"), "Active Base Station")
        self.net_ip.set_metric(snap.get("net_ip", "Unknown"), "en0 interface address")
        wa_live = snap.get("wa_bridge_live", False)
        if wa_live:
            self.net_wa.set_metric("Online", snap.get("wa_bridge_detail", "Bridge running on port 3001"))
            self.wa_toggle_btn.setText("\ud83d\udd34 Disconnect WhatsApp")
            self.wa_toggle_btn.setStyleSheet(
                "QPushButton { background: rgb(70, 20, 20); color: rgb(255, 120, 120); "
                "border: 1px solid rgb(120, 40, 40); border-radius: 8px; font-size: 14px; font-weight: bold; } "
                "QPushButton:hover { background: rgb(90, 30, 30); }"
            )
        else:
            self.net_wa.set_metric("Offline", snap.get("wa_bridge_detail", "Bridge not running"))
            self.wa_toggle_btn.setText("\ud83d\udd0c Connect WhatsApp")
            self.wa_toggle_btn.setStyleSheet(
                "QPushButton { background: rgb(20, 60, 40); color: rgb(100, 255, 150); "
                "border: 1px solid rgb(40, 100, 60); border-radius: 8px; font-size: 14px; font-weight: bold; } "
                "QPushButton:hover { background: rgb(30, 80, 50); }"
            )

        # Body
        self._update_audio_status()

        # Body
        self.card_health.set_metric(f"{snap['score']}/100", snap["grade"])
        self.card_mode.set_metric(str(snap["metabolic_mode"]), f"budget x{snap['budget_multiplier']:.2f}")

        for key, card in self.body_cards.items():
            pct = float(snap["dimensions"].get(key, 0.0) or 0.0)
            card.set_metric(f"{int(round(pct * 100))}%", "from latest health score")

        # Economy
        self.metabolism_card.set_metric(
            str(snap["metabolic_mode"]),
            f"budget x{snap['budget_multiplier']:.2f}; rest {snap['rest_seconds']:.0f}s",
        )
        self.wallet_card.set_metric(
            f"{snap['net_stgm']:.3f} STGM",
            f"spend {snap['spend_stgm']:.3f} STGM",
        )

        # Inference
        self.inference_default_card.set_metric(
            snap["default_ollama_model"],
            "Single cortex spend: Alice, Swarm Chat, and OS helpers",
        )

        # Privacy
        self.storage_state_card.set_metric(f"{snap['state_mb']:.1f} MB", "target ceiling is 50 MB")
        self.storage_iris_card.set_metric(f"{snap['iris_mb']:.1f} MB", "raw camera frames should remain near zero")

        # Developer
        self.card_apps.set_metric(str(snap["apps_total"]), "macOS-style catalog")
        groups = "\n".join(f"{name}: {count}" for name, count in snap["app_groups"].items() if count)
        missing = "\n".join(snap["missing_apps"]) or "none"
        self.apps_summary.setText(f"Installed apps: {snap['apps_total']}\n\n{groups}\n\nMissing entry points:\n{missing}")
        self.set_status(f"Refreshed: {snap['grade']}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SystemSettingsWidget()
    w.resize(980, 680)
    w.setWindowTitle("System Settings - SIFTA OS")
    w.show()
    sys.exit(app.exec())
