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
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QThread, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QPainter, QPen, QColor, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from System.sifta_app_catalog import group_manifest, normalize_category
from System.sifta_inference_defaults import (
    CANONICAL_CLOUD_CLAUDE,
    CANONICAL_CLOUD_CODEX,
    CANONICAL_CLOUD_GROK,
    CANONICAL_OLLAMA_DAILY,
    CANONICAL_OLLAMA_EXTRA,
    CANONICAL_OLLAMA_FALLBACK,
    CANONICAL_OLLAMA_GEMMA4_SMALL,
    CANONICAL_OLLAMA_LOW_RAM,
    CANONICAL_OLLAMA_M5_FALLBACK,
    CANONICAL_OLLAMA_REFLEX,
    DEFAULT_OLLAMA_MODEL,
    STIGMERGIC_TEST_MODEL_PRESETS,
    get_default_ollama_model,
    list_available_cortexes_with_canonical_fallback,
    resolve_ollama_model,
    set_default_ollama_model,
    set_app_ollama_model,
)
from System.swarm_inference_model_inventory import (
    format_inventory_label,
    inference_runtime_nuggets,
    inventory_detail_text,
    list_inference_model_inventory,
)
from System.sifta_base_widget import SiftaBaseWidget
from System.sifta_desktop_themes import (
    THEMES,
    effective_palette,
    list_stock_wallpapers,
    load_active_theme_id,
    load_custom_wallpaper_path,
    load_font_size_px,
    load_palette_overrides,
    load_reduce_motion,
    save_active_theme_id,
    save_custom_wallpaper_path,
    save_font_size_px,
    save_palette_overrides,
    save_reduce_motion,
)
from System.swarm_camera_unified_field_proof import build_camera_unified_field_proof
from System.swarm_fireworks_qwen_config import (
    install_qwen_fireworks_settings,
    read_fireworks_api_key,
)

class _BonsaiWallpaperWorker(QThread):
    """r272: generate a Bonsai desktop wallpaper OFF the GUI thread (the beachball lesson)."""
    done = pyqtSignal(dict)

    def __init__(self, prompt: str, theme_id: str, parent: "QObject | None" = None) -> None:
        super().__init__(parent)
        self._prompt = prompt
        self._theme_id = theme_id

    def run(self) -> None:
        try:
            from System.swarm_desktop_wallpaper import generate_desktop_wallpaper
            res = generate_desktop_wallpaper(self._prompt, theme_id=self._theme_id)
        except Exception as exc:  # noqa: BLE001
            res = {"ok": False, "path": "", "prompt": self._prompt, "error": f"{type(exc).__name__}: {exc}"}
        self.done.emit(res if isinstance(res, dict) else {"ok": False, "error": "no result"})


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
    return (
        n.startswith("gemini:")
        or n.startswith("gemini-")
        or n.startswith("grok:")
        or n.startswith("grok-")
        or n.startswith("claude:")
        or n.startswith("claude-")
        or n.startswith("codex:")
        or n.startswith("codex-")
        or n.startswith("qwen:")
        or n.startswith("qwen-")
        or n.startswith("cline:")
        or n.startswith("cline-")
        or n.startswith("mimo:")
        or n.startswith("mimo-")
    )


def _is_xai_cortex_tag(name: str) -> bool:
    n = (name or "").strip().lower()
    return n.startswith("grok:") or n.startswith("grok-") or n.startswith("xai:")


def _is_qwen_cortex_tag(name: str) -> bool:
    n = (name or "").strip().lower()
    return n.startswith("qwen:") or n.startswith("qwen-")


def _is_cline_cortex_tag(name: str) -> bool:
    n = (name or "").strip().lower()
    return n.startswith("cline:") or n.startswith("cline-") or n.startswith("alice:") or n.startswith("alice-")


def _qwen_api_key_masked(*, state_dir: str | Path | None = None) -> str:
    key = read_fireworks_api_key(state_dir=state_dir)
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


def _cline_cli_available() -> str | None:
    try:
        # Prefer the new SIFTA alice-hand binary (published as @anton-sifta/alice,
        # bin renamed in r165 to `alice-hand` so the organism's name "Alice"
        # stays unique — no voice/cortex/arm-routing collision).
        # Fall back to legacy `alice` (3.0.14 only, broken bin/CJS) for older
        # installs, then to upstream `cline` for pre-fork users.
        for bin_name in ("alice-hand", "alice", "cline"):
            path = shutil.which(bin_name)
            if path:
                return path
        return None
    except Exception:
        return None


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
    ``qwen3.5:9b`` must not inherit the installed weight of ``alice-gemma4-e2b-cortex-5.1b-4.4gb:latest``.
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


def _format_throttle_decision(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict) or not row:
        return {
            "value": "No throttle decision",
            "detail": "No recent metabolic throttle denial",
            "mode": "UNKNOWN",
            "balance": None,
            "resolved_wallet_file": None,
            "reason": "",
            "decision_hash": "",
        }

    ok = bool(row.get("ok"))
    reason = str(row.get("reason") or "")
    wallet = row.get("resolved_wallet_file")
    wallet_text = str(wallet) if wallet else "wallet unresolved"
    try:
        balance = float(row.get("balance", 0.0) or 0.0)
    except Exception:
        balance = 0.0

    if not wallet:
        value = "wallet unresolved"
        mode = "FAIL_OPEN" if ok else "DENY_UNRESOLVED"
    elif ok:
        value = "Observed"
        mode = "ALLOW"
    else:
        value = "Throttled"
        mode = "DENY"

    return {
        "value": value,
        "detail": f"{reason or mode}; balance {balance:.3f}; wallet {wallet_text}",
        "mode": mode,
        "balance": balance,
        "resolved_wallet_file": wallet,
        "reason": reason,
        "sleep_needed": float(row.get("sleep_needed", 0.0) or 0.0),
        "decision_hash": str(row.get("decision_hash") or ""),
    }


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
    throttle_decision = _format_throttle_decision(_latest_jsonl(STATE / "throttle_decisions.jsonl"))
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
        "throttle_decision": throttle_decision,
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
        (9,  0.12, 0.12, "🩺 DOCTOR",    "ibm/granite4.1:3b", 210, 120, 60),  # text/tool/JSON doctor
        (10, 0.88, 0.56, "🔤 C1",        "Qwen2.5 LoRA", 180, 200,  80),  # classifier input
    ]
    # Sensory/classifier inputs arrive AT cortex (dot travels src → dst = toward cortex)
    _EDGES_IN  = [(1, 0), (2, 0), (8, 0), (9, 0), (10, 0)]
    # Output signals travel FROM cortex to effectors
    _EDGES_OUT = [(0, 3), (0, 4), (0, 5), (0, 6), (0, 7)]
    _EDGES = _EDGES_IN + _EDGES_OUT

    def __init__(self, cortex_model: str, corvid_model: str) -> None:
        super().__init__()
        self._cortex_label = cortex_model or DEFAULT_OLLAMA_MODEL
        self._corvid_label = corvid_model or "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
        self._ollama_live: bool = True
        self._probe_running: bool = False
        # Scout label — detect hardware and set appropriate model name
        self._scout_label = "qwen3.5:9b"  # M5 default
        try:
            import subprocess as _sp
            _res = _sp.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=1)
            mem_gb = int(_res.stdout.strip()) / (1024**3)
            self._scout_label = "qwen3.5:9b" if mem_gb >= 24 else CANONICAL_OLLAMA_LOW_RAM
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
        # Keep every node card fully inside the widget at any width. The cards are
        # fixed-pixel (cortex half-width ~76, the rest ~55), but the positions are
        # fractional — so at the live panel width the edge nodes (SCOUT/VOICE/C1/
        # WhatsApp/DOCTOR/CORVID) spilled past the panel and their model tags
        # overflowed. That is the "graphics do not fit" George reported. Clamp the
        # center by a card-half margin so edges AND cards read the same in-bounds point.
        row = self._NODES[idx]
        pad_x, pad_y = 64.0, 34.0
        x = min(max(row[1] * w, pad_x), w - pad_x)
        y = min(max(row[2] * h, pad_y), h - pad_y)
        return QPointF(x, y)

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
            _c = self._node_center(idx, w, h)  # clamped in-bounds center (edges use the same)
            px, py = _c.x(), _c.y()
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
                # Elide long model tags ("gemma4-e2b-cortex-5.1b-4.4gb:") to the card width
                # so they stop overflowing the node card.
                _sub = p.fontMetrics().elidedText(
                    self._node_sublabel(idx), Qt.TextElideMode.ElideRight, int(bot_rect.width()) - 6
                )
                p.drawText(bot_rect, Qt.AlignmentFlag.AlignCenter, _sub)

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
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)
        self.title = QLabel(title)
        self.title.setStyleSheet("color: rgb(145, 153, 180); font-size: 10px;")
        self.value = QLabel(value)
        self.value.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        self.value.setStyleSheet("color: rgb(238, 244, 255);")
        self.detail = QLabel(detail)
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color: rgb(112, 122, 150); font-size: 10px;")
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def set_metric(self, value: str, detail: str = "") -> None:
        self.value.setText(value)
        self.detail.setText(detail)


class SystemSettingsWidget(SiftaBaseWidget):
    APP_NAME = "System Settings"
    # Maximize inside the SIFTA MDI body — never the host macOS window.
    OPEN_MAXIMIZED = True

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
            "Display": self._display_page(),
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
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)
        heading = QLabel(title)
        heading.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        heading.setStyleSheet("color: rgb(238, 244, 255); margin: 0px;")
        root.addWidget(heading)
        return page, root

    def _display_page(self) -> QWidget:
        page, root = self._page("Display")

        # ── Appearance subsection ───────────────────────────────────────────────────────
        appearance_head = QLabel("Appearance")
        appearance_head.setStyleSheet(
            "color: rgb(238, 244, 255); font-size: 14px; font-weight: bold; margin-top: 4px;"
        )
        root.addWidget(appearance_head)

        info = QLabel(
            "Select the visual identity of the SIFTA organism. "
            "The organism remains the same, only the clothing changes.\n"
            "(Restart OS for full effect)"
        )
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

        self.theme_os_line = QLabel(THEMES[current_theme].os_line)
        self.theme_os_line.setStyleSheet(
            "color: rgb(112, 122, 150); font-family: monospace; font-size: 11px; margin-top: 8px;"
        )
        root.addWidget(self.theme_os_line)

        # ── r152 Appearance overrides (live + persist) ───────────────────────────────
        ov_head = QLabel("Live overrides (apply instantly, survive restart)")
        ov_head.setStyleSheet("color: rgb(238, 244, 255); font-size: 12px; font-weight: bold; margin-top: 10px;")
        root.addWidget(ov_head)

        ov_row = QHBoxLayout()
        ov_row.setSpacing(6)

        def _mk_color_btn(label: str, field: str, default_getter) -> QPushButton:
            btn = QPushButton(label)
            btn.setFixedWidth(92)
            btn.setStyleSheet(
                "QPushButton { background: rgb(20, 22, 32); color: rgb(238, 244, 255); "
                "border: 1px solid rgb(47, 52, 68); border-radius: 4px; padding: 4px 8px; font-size: 11px; }"
                "QPushButton:hover { background: rgb(35, 40, 58); }"
            )
            def _pick():
                cur = QColor(default_getter() or "#ffffff")
                col = QColorDialog.getColor(cur, self, f"Choose {label}")
                if col.isValid():
                    ov = load_palette_overrides()
                    ov[field] = col.name()
                    save_palette_overrides(ov)
                    self._poke_desktop_wallpaper_reload()
            btn.clicked.connect(_pick)
            return btn

        ov_row.addWidget(_mk_color_btn("Accent", "accent_primary", lambda: getattr(effective_palette(), "accent_primary", "#bb9af7")))
        ov_row.addWidget(_mk_color_btn("Background", "bg_deep", lambda: getattr(effective_palette(), "bg_deep", "#0d0e17")))
        ov_row.addWidget(_mk_color_btn("Text", "text_primary", lambda: getattr(effective_palette(), "text_primary", "#c0caf5")))

        self.font_spin = QSpinBox()
        self.font_spin.setRange(9, 28)  # r737: chat is wired to this knob now; real headroom
        self.font_spin.setValue(load_font_size_px())
        self.font_spin.setPrefix("Font ")
        self.font_spin.setSuffix(" px")
        self.font_spin.setStyleSheet(
            "QSpinBox { background: rgb(20, 22, 32); color: rgb(238, 244, 255); "
            "border: 1px solid rgb(47, 52, 68); border-radius: 4px; padding: 2px 6px; font-size: 11px; }"
        )
        self.font_spin.valueChanged.connect(lambda v: (save_font_size_px(v), self._poke_desktop_wallpaper_reload()))
        ov_row.addWidget(self.font_spin)

        self.reduce_motion_chk = QCheckBox("Reduce motion")
        self.reduce_motion_chk.setChecked(load_reduce_motion())
        self.reduce_motion_chk.setStyleSheet("color: rgb(238, 244, 255); font-size: 11px;")
        self.reduce_motion_chk.toggled.connect(lambda v: (save_reduce_motion(v), self._poke_desktop_wallpaper_reload()))
        ov_row.addWidget(self.reduce_motion_chk)

        ov_row.addStretch()
        root.addLayout(ov_row)

        reset_btn = QPushButton("Reset overrides to theme default")
        reset_btn.setFixedWidth(210)
        reset_btn.setStyleSheet(
            "QPushButton { background: rgb(20, 22, 32); color: rgb(238, 244, 255); "
            "border: 1px solid rgb(47, 52, 68); border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { background: rgb(35, 40, 58); }"
        )
        def _reset():
            save_palette_overrides({})
            save_font_size_px(13)
            save_reduce_motion(False)
            self.font_spin.setValue(13)
            self.reduce_motion_chk.setChecked(False)
            self._poke_desktop_wallpaper_reload()
        reset_btn.clicked.connect(_reset)
        root.addWidget(reset_btn)

        # ── Wallpaper subsection ────────────────────────────────────────
        # Architect 2026-05-11 23:25: "let me change the desktop pic in
        # the settings and pick custom if one wants." Stock pictures are
        # bundled in Library/Desktop Pictures; custom is any file picked
        # via QFileDialog. Persisted in .sifta_state/desktop_wallpaper.json.
        wp_sep = QFrame()
        wp_sep.setFrameShape(QFrame.Shape.HLine)
        wp_sep.setStyleSheet("color: rgb(35, 40, 58); margin: 18px 0 10px 0;")
        root.addWidget(wp_sep)

        wp_head = QLabel("Wallpaper")
        wp_head.setStyleSheet(
            "color: rgb(238, 244, 255); font-size: 14px; font-weight: bold; margin-top: 4px;"
        )
        root.addWidget(wp_head)

        # Architect 2026-05-12 16:50: "ONE JPEG PER SELECTION!!!" — the theme
        # IS the wallpaper. Removed the separate wallpaper combobox entirely.
        # Only the "Choose custom file…" button below remains as an optional
        # override (e.g. when the Architect wants a non-default image for a
        # given theme). Picking a theme now sets the wallpaper to that
        # theme's default automatically — see _on_theme_changed below.
        wp_help = QLabel(
            "Each theme ships with its own wallpaper. The theme above is the "
            "selector. Use 'Choose custom file…' only if you want to override "
            "this theme's image with your own."
        )
        wp_help.setWordWrap(True)
        wp_help.setStyleSheet("color: rgb(145, 153, 180); margin-bottom: 8px; font-size: 11px;")
        root.addWidget(wp_help)

        wp_btn_row = QHBoxLayout()
        self.wallpaper_custom_btn = QPushButton("Choose custom file…")
        self.wallpaper_custom_btn.setStyleSheet(
            "QPushButton { background: rgb(20, 22, 32); color: rgb(238, 244, 255); "
            "border: 1px solid rgb(47, 52, 68); border-radius: 6px; padding: 6px 12px; }"
            "QPushButton:hover { background: rgb(35, 40, 58); }"
        )
        self.wallpaper_custom_btn.clicked.connect(self._on_wallpaper_custom_pick)
        wp_btn_row.addWidget(self.wallpaper_custom_btn)
        wp_btn_row.addStretch()
        root.addLayout(wp_btn_row)

        # ── r272: Generate your desktop with Bonsai (on-device). Empty box = a fresh,
        #     always-different prompt from the selected theme. ───────────────────────
        bonsai_row = QHBoxLayout()
        self.bonsai_prompt = QLineEdit()
        self.bonsai_prompt.setPlaceholderText(
            "Describe your desktop… (leave empty for a fresh theme-based one)"
        )
        self.bonsai_prompt.setStyleSheet(
            "QLineEdit { background: rgb(20,22,32); color: rgb(238,244,255); "
            "border: 1px solid rgb(47,52,68); border-radius: 6px; padding: 6px 10px; }"
        )
        bonsai_row.addWidget(self.bonsai_prompt, 1)
        self.bonsai_generate_btn = QPushButton("🌳 Generate your desktop with Bonsai")
        self.bonsai_generate_btn.setStyleSheet(
            "QPushButton { background: rgb(20, 22, 32); color: rgb(238, 244, 255); "
            "border: 1px solid rgb(47, 52, 68); border-radius: 6px; padding: 6px 12px; }"
            "QPushButton:hover { background: rgb(35, 40, 58); }"
        )
        self.bonsai_generate_btn.clicked.connect(self._on_generate_bonsai_desktop)
        bonsai_row.addWidget(self.bonsai_generate_btn)
        root.addLayout(bonsai_row)
        self._bonsai_wp_worker = None

        self.wallpaper_status = QLabel("")
        self.wallpaper_status.setWordWrap(True)
        self.wallpaper_status.setStyleSheet(
            "color: rgb(112, 122, 150); font-family: monospace; font-size: 11px; margin-top: 6px;"
        )
        root.addWidget(self.wallpaper_status)

        # ── Stigmergic OpenGL Driver section (only if real) ──────────────────────
        gl_info = self._probe_stigmergic_opengl()
        if gl_info:  # only rendered if real hardware + real ledger data
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color: rgb(35, 40, 58); margin: 18px 0 10px 0;")
            root.addWidget(sep)

            gl_head = QLabel("Stigmergic OpenGL Driver")
            gl_head.setStyleSheet(
                "color: rgb(0, 220, 255); font-size: 14px; font-weight: bold;"
            )
            root.addWidget(gl_head)

            gl_desc = QLabel(
                "Chromatophore phenotype renderer — SIFTA's novel GPU output organ.\n"
                "Converts stigmergic body-brain ticks into real-time GLSL fragment shader\n"
                "uniforms (waggle dance / honeybee algorithm). ModernGL offscreen pass."
            )
            gl_desc.setWordWrap(True)
            gl_desc.setStyleSheet("color: rgb(145, 153, 180); margin-bottom: 8px; font-size: 11px;")
            root.addWidget(gl_desc)

            # Status chips row
            chips_row = QHBoxLayout()
            for label, val, ok_color in [
                ("ModernGL", gl_info["moderngl_version"], "#00e888"),
                ("Context",  gl_info["context_status"],   "#00e888" if gl_info["context_ok"] else "#f0c040"),
                ("Renderer", gl_info["renderer"],          "#c878f0"),
                ("Ledger",   gl_info["ledger_rows"],       "#00dcff"),
            ]:
                chip = QLabel(f"{label}: {val}")
                chip.setStyleSheet(
                    f"color: {ok_color}; background: rgba(0,0,0,0.4); "
                    "border: 1px solid rgba(255,255,255,0.08); border-radius: 5px; "
                    "padding: 3px 9px; font-size: 10px; font-family: Menlo;"
                )
                chips_row.addWidget(chip)
            chips_row.addStretch()
            root.addLayout(chips_row)

            # Uniform values from last tick
            if gl_info.get("last_uniforms"):
                u = gl_info["last_uniforms"]
                uniform_lbl = QLabel(
                    f"Last tick uniforms  ·  drive={u.get('u_stigmergic_drive',0):.3f}  "
                    f"quorum={u.get('u_quorum_signal',0):.3f}  "
                    f"chemotaxis={u.get('u_chemotaxis_gradient',0):.3f}  "
                    f"confidence={u.get('u_confidence',0):.3f}"
                )
                uniform_lbl.setStyleSheet(
                    "color: rgb(90, 110, 140); font-family: Menlo; font-size: 10px; margin-top: 6px;"
                )
                uniform_lbl.setWordWrap(True)
                root.addWidget(uniform_lbl)

            truth_lbl = QLabel(
                "Truth: OBSERVED_ENGINEERING_SUBSTRATE · "
                "receipt_backed=True rows confirm GPU path is wired to live stigmergic data."
            )
            truth_lbl.setWordWrap(True)
            truth_lbl.setStyleSheet(
                "color: rgb(50, 70, 90); font-size: 9px; font-family: Menlo; margin-top: 6px;"
            )
            root.addWidget(truth_lbl)

        root.addStretch()
        return page

    def _probe_stigmergic_opengl(self) -> Optional[dict]:
        """Probe the real OpenGL driver stack. Returns None if not available."""
        import sys as _sys
        _repo = Path(__file__).resolve().parent.parent
        if str(_repo) not in _sys.path:
            _sys.path.insert(0, str(_repo))
        try:
            import moderngl as _mgl
            moderngl_version = _mgl.__version__
        except ImportError:
            return None  # not real — don't show the section

        # Check ledger has real receipt_backed data
        ledger = _repo / ".sifta_state" / "visual_phenotype_uniforms.jsonl"
        if not ledger.exists():
            return None
        try:
            import json as _json
            lines = [l for l in ledger.read_text("utf-8").splitlines() if l.strip()]
            backed_rows = []
            last_uniforms = None
            for line in lines:
                try:
                    row = _json.loads(line)
                    if row.get("receipt_backed"):
                        backed_rows.append(row)
                        last_uniforms = row
                except Exception:
                    pass
            if not backed_rows:
                return None  # no real receipt-backed data — don't show
        except Exception:
            return None

        # Try to create a GL context (offscreen)
        context_ok = False
        renderer = "unknown"
        try:
            from System.swarm_visual_phenotype_gl import modern_gl_available, try_create_standalone_context
            context_ok = modern_gl_available()
            if context_ok:
                probe = try_create_standalone_context()
                renderer = getattr(probe, "renderer", "offscreen") or "offscreen"
                context_ok = getattr(probe, "ok", False)
        except Exception:
            pass

        return {
            "moderngl_version": f"v{moderngl_version}",
            "context_ok":       context_ok,
            "context_status":   "offscreen ✓" if context_ok else "headless",
            "renderer":         str(renderer)[:24] if renderer else "Apple M-series GPU",
            "ledger_rows":      f"{len(backed_rows)} receipt‑backed rows",
            "last_uniforms":    last_uniforms,
        }

    def _on_theme_changed(self, idx: int) -> None:
        """Picking a theme now also resets the wallpaper to that theme's
        default. Architect 2026-05-12 16:50: 'ONE JPEG PER SELECTION'. The
        theme IS the wallpaper. Clearing the custom override returns the
        resolver in sifta_desktop_themes.wallpaper_path() to use the
        palette's own wallpaper_filename.
        """
        tid = self.theme_combo.itemData(idx)
        if not tid:
            return
        save_active_theme_id(tid)
        # Drop any prior custom override so this theme's default JPEG takes over.
        save_custom_wallpaper_path(None)
        self.theme_os_line.setText(THEMES[tid].os_line + " (Saved. Please restart OS.)")
        self._wallpaper_status_msg(None)
        # Live reload on the running desktop so the wallpaper flips immediately
        # (no restart required for the image swap itself).
        self._poke_desktop_wallpaper_reload()

    def _on_wallpaper_custom_pick(self) -> None:
        """Open a QFileDialog so the Architect can pick any image file as a
        one-off override of the current theme's default wallpaper.
        Architect 2026-05-12 16:50: combobox removed; this button is the only
        manual override now."""
        start_dir = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose desktop wallpaper",
            start_dir,
            "Images (*.png *.jpg *.jpeg *.webp *.heic *.avif *.svg);;All files (*.*)",
        )
        if not path:
            return
        save_custom_wallpaper_path(path)
        self._wallpaper_status_msg(path)
        self._poke_desktop_wallpaper_reload()

    def _on_generate_bonsai_desktop(self) -> None:
        """r272: generate a desktop image with Bonsai (on-device) from the prompt box — or a
        fresh theme-based default when empty — and set it as the wallpaper. Runs off the GUI
        thread; never blocks or crashes the panel."""
        try:
            prompt = self.bonsai_prompt.text().strip()
        except Exception:
            prompt = ""
        try:
            theme_id = self.theme_combo.itemData(self.theme_combo.currentIndex()) or "beeson_v8"
        except Exception:
            theme_id = "beeson_v8"
        # Empty box → show the varied default so the owner sees what will be painted, and use it.
        if not prompt:
            try:
                from System.swarm_desktop_wallpaper import default_prompt_for_theme
                self.bonsai_prompt.setText(default_prompt_for_theme(str(theme_id)))
            except Exception:
                pass
        try:
            self.bonsai_generate_btn.setEnabled(False)
            self.bonsai_generate_btn.setText("🌳 Generating…")
            self.wallpaper_status.setText("Bonsai is painting your desktop on-device…")
        except Exception:
            pass
        worker = _BonsaiWallpaperWorker(self.bonsai_prompt.text().strip(), str(theme_id), self)
        worker.done.connect(self._on_bonsai_desktop_done)
        self._bonsai_wp_worker = worker
        worker.start()

    def _on_bonsai_desktop_done(self, res: dict) -> None:
        try:
            self.bonsai_generate_btn.setEnabled(True)
            self.bonsai_generate_btn.setText("🌳 Generate your desktop with Bonsai")
        except Exception:
            pass
        path = str((res or {}).get("path") or "")
        if (res or {}).get("ok") and path:
            try:
                save_custom_wallpaper_path(path)
                self._wallpaper_status_msg(path)
                self._poke_desktop_wallpaper_reload()
            except Exception as exc:
                self.wallpaper_status.setText(f"Generated but could not apply: {exc}")
        else:
            err = str((res or {}).get("error") or "generation failed")
            self.wallpaper_status.setText(f"Bonsai could not generate a desktop: {err}")

    def _wallpaper_status_msg(self, path: str | None) -> None:
        if not path:
            # None / "" both mean "use the active theme's default wallpaper"
            self.wallpaper_status.setText("Wallpaper: this theme's default image.")
        else:
            self.wallpaper_status.setText(f"Wallpaper override → {path}")

    def _poke_desktop_wallpaper_reload(self) -> None:
        """Best-effort: ask the running SiftaDesktop to reload wallpaper + live palette (r152)."""
        try:
            app = QApplication.instance()
            if app is None:
                return
            for w in app.topLevelWidgets():
                fn = getattr(w, "_apply_wallpaper", None)
                if callable(fn):
                    fn(force=True)
                live = getattr(w, "apply_live_palette", None)
                if callable(live):
                    live(force=True)
        except Exception:
            pass

    def _identity_page(self) -> QWidget:
        page, root = self._page("Identity")

        # ── Architect 2026-05-12 17:55 ─────────────────────────────────────
        # "add the square where is live ... the swimmers in the camera ...
        #  real data real dots near the picture and then a button to set up
        #  her name is Gemma default but then you set it up whatever
        #  Gemma a.k.a. whatever name they wanna add"
        #
        # Row 1 — single horizontal row at the top of the Identity page:
        #   [ Change AGI Name btn ] [ owner photo ] [ alice eye tile ] [ Re-scan Face btn ]
        # Architect 2026-05-12 22:10: "move the two buttons up to the left and
        # to the right of the images and make all this window smaller just to
        # fit everything". Buttons are now sized to the 120 px tile height so
        # the whole identity strip is one tight band instead of three.
        faces_row = QHBoxLayout()
        faces_row.setSpacing(10)
        faces_row.addStretch()

        # LEFT button — Change Stigmergic AGI Name.
        self.change_agi_name_btn = QPushButton("Change\nAGI Name")
        self.change_agi_name_btn.setFixedSize(120, 120)
        self.change_agi_name_btn.setStyleSheet(
            "QPushButton { background: rgb(40, 30, 60); color: rgb(200, 170, 255); "
            "border: 1px solid rgb(80, 60, 120); border-radius: 14px; "
            "font-size: 12px; font-weight: bold; padding: 4px; } "
            "QPushButton:hover { background: rgb(55, 40, 80); }"
        )
        self.change_agi_name_btn.clicked.connect(self._prompt_change_agi_name)
        faces_row.addWidget(self.change_agi_name_btn)

        self.id_photo = QLabel()
        self.id_photo.setFixedSize(120, 120)
        self.id_photo.setStyleSheet(
            "background: rgb(20, 24, 36); border: 2px solid rgb(60, 200, 160); "
            "border-radius: 60px;"
        )
        self.id_photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.id_photo.setText("No Photo")
        faces_row.addWidget(self.id_photo)

        # Alice's live eye tile — refreshed every 2s by _refresh_alice_eye_tile.
        self.alice_eye_tile = QLabel()
        self.alice_eye_tile.setFixedSize(120, 120)
        self.alice_eye_tile.setStyleSheet(
            "background: rgb(8, 12, 22); border: 2px solid rgb(255, 179, 0); "
            "border-radius: 60px; color: rgb(180, 140, 80); font-size: 11px;"
        )
        self.alice_eye_tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alice_eye_tile.setText("eye\nwaking")
        faces_row.addWidget(self.alice_eye_tile)

        # RIGHT button — Re-scan Face for Genesis.
        self.scan_face_btn = QPushButton("Re-scan\nFace")
        self.scan_face_btn.setFixedSize(120, 120)
        self.scan_face_btn.setStyleSheet(
            "QPushButton { background: rgb(20, 40, 60); color: rgb(100, 200, 255); "
            "border: 1px solid rgb(40, 80, 120); border-radius: 14px; "
            "font-size: 12px; font-weight: bold; padding: 4px; } "
            "QPushButton:hover { background: rgb(30, 55, 80); }"
        )
        self.scan_face_btn.clicked.connect(self._scan_face_for_genesis)
        faces_row.addWidget(self.scan_face_btn)

        faces_row.addStretch()
        root.addLayout(faces_row)

        # Stigmergic proof line — Architect 2026-05-12 19:55: "I NEED STIGMERGIC
        # PROOF FROM THE UNIFIED FIELD that the camera is healthy or recognizing
        # ME, OR OS USER. OTHERWISE IS USELESS, WE REMOVE IT." This label reads
        # face_detection_events.jsonl + kernel_process_table + the identity
        # frame stream. It SHOWS the receipt or says honestly that no fresh
        # receipt exists. _refresh_alice_eye_tile updates it every 2 seconds.
        self.alice_eye_proof = QLabel("checking unified field…")
        self.alice_eye_proof.setWordWrap(True)
        self.alice_eye_proof.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alice_eye_proof.setStyleSheet(
            "color: rgb(180, 140, 80); font-size: 11px; font-family: Menlo; "
            "margin-top: 6px; margin-bottom: 4px;"
        )
        root.addWidget(self.alice_eye_proof)

        # Live refresh timer for the eye tile.
        try:
            self._alice_eye_timer = QTimer(self)
            self._alice_eye_timer.timeout.connect(self._refresh_alice_eye_tile)
            self._alice_eye_timer.start(2000)
            QTimer.singleShot(0, self._refresh_alice_eye_tile)
        except Exception:
            pass

        # Cowork 2026-05-12 22:10 — Architect: "move the two buttons up to the
        # left and to the right of the images and make all this window smaller
        # just to fit everything". Both buttons are now constructed inside
        # `faces_row` above, flanking the photo + eye tiles. No separate
        # full-width rows here anymore.

        # Architect 2026-05-12 17:45: "ORGANIZE THESE BETTER, TIGHTER, HUGE
        # EMPTY SPACE". Switched 9 vertically-stacked MetricCards to a
        # 2-column QGridLayout. Vertical scroll halved. Pair-by-meaning:
        #   Row 0: Owner          | Genesis Status
        #   Row 1: Machine Spec   | Operating System
        #   Row 2: Silicon HW     | Genesis Anchor
        #   Row 3: Signature      | Electric Field Digest
        #   Row 4: Voice (spans both columns — has long descriptive subtitle)
        self.id_owner   = MetricCard("Owner", "--")
        self.id_genesis = MetricCard("Genesis Status", "--")
        self.id_spec    = MetricCard("Machine Spec", "--")
        self.id_os      = MetricCard("Operating System", "--")
        self.id_serial  = MetricCard("Silicon Hardware", "--")
        self.id_anchor  = MetricCard("Genesis Anchor", "--")
        self.id_sig     = MetricCard("Signature", "--")
        self.id_digest  = MetricCard("Electric Field Digest", "--")
        self.id_voice   = MetricCard("🎙 George Voice Certainty", "—", "Voice Identity Organ — train via Launchpad")

        id_grid = QGridLayout()
        id_grid.setHorizontalSpacing(6)
        id_grid.setVerticalSpacing(4)
        id_grid.setContentsMargins(0, 0, 0, 0)
        id_grid.addWidget(self.id_owner,   0, 0)
        id_grid.addWidget(self.id_genesis, 0, 1)
        id_grid.addWidget(self.id_spec,    1, 0)
        id_grid.addWidget(self.id_os,      1, 1)
        id_grid.addWidget(self.id_serial,  2, 0)
        id_grid.addWidget(self.id_anchor,  2, 1)
        id_grid.addWidget(self.id_sig,     3, 0)
        id_grid.addWidget(self.id_digest,  3, 1)
        id_grid.addWidget(self.id_voice,   4, 0, 1, 2)  # span both columns
        id_grid.setColumnStretch(0, 1)
        id_grid.setColumnStretch(1, 1)
        root.addLayout(id_grid)
        root.addStretch()
        return page

    def _refresh_alice_eye_tile(self) -> None:
        """Paint Alice's latest webcam frame into the round eye tile, then
        overlay 24 swimmer dots whose positions and color come from the
        most recent visual_stigmergy.jsonl row. Real data driving real dots —
        no synthetic noise. Never fractures the UI if files are missing.
        Cowork 2026-05-12 17:55."""
        try:
            from pathlib import Path as _Path
            import json as _json
            import math as _math
            import hashlib as _hash

            REPO_STATE = _REPO / ".sifta_state"
            frames_dir = REPO_STATE / "iris_frames"

            # 1. Find latest iris frame (newest mtime).
            latest = None
            try:
                if frames_dir.exists():
                    files = [p for p in frames_dir.iterdir()
                             if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
                    if files:
                        latest = max(files, key=lambda p: p.stat().st_mtime)
            except Exception:
                latest = None

            # 2. Build the 120x120 base pixmap (cover-scaled center-crop).
            pm = QPixmap(120, 120)
            pm.fill(QColor(8, 12, 22))
            if latest is not None:
                src = QPixmap(str(latest))
                if not src.isNull():
                    scaled = src.scaled(
                        120, 120,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    x = max(0, (scaled.width() - 120) // 2)
                    y = max(0, (scaled.height() - 120) // 2)
                    pm = scaled.copy(x, y, 120, 120)

            # 3. Read latest visual_stigmergy row (tail of file, cheap).
            # NOTE: rows average ~4 KB each (one carries the long saliency_q
            # string), so the tail window MUST be > 8 KB to reliably capture a
            # complete row. 16 KB picks up the last 2-4 rows.
            row = None
            try:
                vs_path = REPO_STATE / "visual_stigmergy.jsonl"
                if vs_path.exists():
                    sz = vs_path.stat().st_size
                    with vs_path.open("rb") as f:
                        f.seek(max(0, sz - 16384))
                        chunk = f.read().decode("utf-8", errors="ignore")
                    for line in reversed(chunk.splitlines()):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            row = _json.loads(line)
                            break
                        except Exception:
                            continue
            except Exception:
                row = None

            # 4. Paint 5 swimmer dots at the REAL saliency peaks of the latest
            # frame — Architect rule 2026-05-12 18:55: "5 SWIMMERS, REAL DATA
            # FROM CAMERA, MOVE BASED ON HER CAMERA GAZING". The visual_stigmergy
            # row carries `saliency_q` — a hex-quantized saliency map of the
            # frame. We parse it, find the top-5 intensity cells, project each
            # grid cell onto the 120x120 tile. The dots literally sit where the
            # eye's attention is highest — same coordinates as the gaze focus.
            try:
                painter = QPainter(pm)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                if row:
                    hue = float(row.get("hue_deg", 200.0)) % 360.0
                    saliency_peak = float(row.get("saliency_peak", 0.0))
                    color = QColor.fromHsvF(
                        (hue / 360.0) % 1.0, 0.85, 0.98, 0.95
                    )
                    painter.setPen(QPen(color, 0))
                    painter.setBrush(color)
                    sq = str(row.get("saliency_q") or "")
                    placed = 0
                    if len(sq) >= 16:
                        # Build (intensity, index) list. Hex digit per cell.
                        intensities = []
                        for i, c in enumerate(sq):
                            if "0" <= c <= "9":
                                intensities.append((ord(c) - ord("0"), i))
                            elif "a" <= c <= "f":
                                intensities.append((10 + ord(c) - ord("a"), i))
                            # other chars (b/d already covered above) get skipped
                        intensities.sort(key=lambda iv: -iv[0])
                        top5 = intensities[:5]
                        # Infer grid dims from frame aspect ratio.
                        grid_n = len(sq)
                        fw = max(1, int(row.get("w", 1920)))
                        fh = max(1, int(row.get("h", 1080)))
                        aspect = fw / fh
                        grid_h = max(1, int(round(_math.sqrt(grid_n / aspect))))
                        grid_w = max(1, grid_n // grid_h)
                        # Project each peak's grid index → tile (x, y).
                        for intensity, idx in top5:
                            if intensity <= 0:
                                continue
                            col = idx % grid_w
                            grow = idx // grid_w
                            x = int((col + 0.5) / max(1, grid_w) * 120)
                            y = int((grow + 0.5) / max(1, grid_h) * 120)
                            # Dot radius scales with the peak intensity (1..15).
                            r_dot = 2.0 + (intensity / 15.0) * 2.5
                            painter.drawEllipse(QPointF(x, y), r_dot, r_dot)
                            placed += 1
                    # If saliency_q was empty/unparseable, fall back to one
                    # faint center dot — never go completely empty.
                    if placed == 0:
                        painter.setPen(QPen(QColor(255, 179, 0, 140), 0))
                        painter.setBrush(QColor(255, 179, 0, 140))
                        painter.drawEllipse(QPointF(60, 60), 2.2, 2.2)
                else:
                    # No visual_stigmergy row yet — paint one faint center dot
                    # so the tile reads as alive, not empty.
                    painter.setPen(QPen(QColor(255, 179, 0, 120), 0))
                    painter.setBrush(QColor(255, 179, 0, 120))
                    painter.drawEllipse(QPointF(60, 60), 2.0, 2.0)
                painter.end()
            except Exception:
                pass

            self.alice_eye_tile.setPixmap(pm)
            self.alice_eye_tile.setText("")

            # ── Stigmergic-proof status line ──────────────────────────────
            # Reads the same reusable unified-field proof organ as the
            # resident desktop Alice bar. No fresh receipts means no claim.
            try:
                proof = build_camera_unified_field_proof(REPO_STATE)
                self.alice_eye_proof.setText(proof.summary)
            except Exception as _proof_e:
                try:
                    self.alice_eye_proof.setText(f"proof reader: {type(_proof_e).__name__}")
                except Exception:
                    pass
        except Exception as e:
            # Never let the eye-tile refresh crash the settings panel.
            try:
                self.alice_eye_tile.setText(f"eye: {type(e).__name__}")
            except Exception:
                pass

    def _detect_active_weight_name(self) -> str:
        """Return the live weight-baked name of Alice's current LLM.

        Architect rule 2026-05-12 18:10: "do not hardcode the name Gemma
        into sifta system NEVER — extract from the actual model." If the
        user swaps Ollama tag to llama / gemini / mistral / Qwen / Phi
        tomorrow, this returns the new name automatically.

        Source priority (all OBSERVED, no string literals):
          1. last `alice` row in alice_conversation.jsonl → payload.model
          2. Talk widget's _active_alice_model_id()
          3. empty string (UI shows neutral placeholder)
        """
        try:
            from pathlib import Path as _Pf
            import json as _jf
            conv = _REPO / ".sifta_state" / "alice_conversation.jsonl"
            if conv.exists():
                sz = conv.stat().st_size
                with conv.open("rb") as f:
                    f.seek(max(0, sz - 65536))
                    tail = f.read().decode("utf-8", errors="ignore")
                for line in reversed(tail.splitlines()):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        outer = _jf.loads(line)
                    except Exception:
                        continue
                    payload = outer.get("payload") if isinstance(outer, dict) else None
                    if isinstance(payload, str):
                        try:
                            payload = _jf.loads(payload)
                        except Exception:
                            payload = None
                    if not isinstance(payload, dict):
                        continue
                    if str(payload.get("role") or "").lower() != "alice":
                        continue
                    model = payload.get("model") or ""
                    if model:
                        return self._weight_name_from_tag(str(model))
        except Exception:
            pass
        try:
            from Applications.sifta_talk_to_alice_widget import _active_alice_model_id
            tag = _active_alice_model_id() or ""
            if tag:
                return self._weight_name_from_tag(str(tag))
        except Exception:
            pass
        return ""

    @staticmethod
    def _weight_name_from_tag(tag: str) -> str:
        """Parse a model tag like 'alice-gemma4-e2b-cortex-5.1b-4.4gb:latest'
        into a display weight name like 'Gemma4'. Works for any base model
        family the user installs — gemma, llama, mistral, qwen, phi, etc.
        No hardcoded literals."""
        import re as _re
        # Strip Ollama version suffix
        base = tag.split(":")[0]
        # Walk segments; the first one that LOOKS like a base-model family
        # (alphabetic stem + optional digit/version) wins. Skip "alice",
        # "sifta", "cortex", and other SIFTA-side wrappers.
        skip = {"alice", "sifta", "cortex", "lora", "qlora", "abliterated",
                "uncensored", "instruct", "chat", "it", "base"}
        for seg in base.split("-"):
            if not seg:
                continue
            s = seg.lower()
            if s in skip:
                continue
            m = _re.match(r"^([a-z]+)(\d.*)?$", s)
            if m and len(m.group(1)) >= 3:
                stem = m.group(1)
                ver = m.group(2) or ""
                return (stem.capitalize() + ver) if ver else stem.capitalize()
        return base or ""

    def _prompt_change_agi_name(self) -> None:
        """Open one dialog asking for the new Stigmergic AGI name. Save on OK.

        Architect rule 2026-05-12 18:45: "have a button like you have
        rescanned face — just change the AGI name." One click, one dialog,
        one save. No typing row crammed into the page.

        owner_genesis.json (Ed25519 signed) stays untouched. The alias is
        written to .sifta_state/ai_name_alias.json — Layer 1 overlay —
        and the kernel identity cascade (ai_name(), ai_identity_sentence())
        reads it immediately on next refresh.
        """
        # Pre-fill with the current name from the cascade.
        try:
            from System.swarm_kernel_identity import ai_name as _ai_name
            current = _ai_name() or ""
        except Exception:
            current = ""

        # Show the live weight name so the user knows what to "alias OVER".
        weight = ""
        try:
            from System.swarm_kernel_identity import ai_weight_name as _wn
            weight = _wn()
        except Exception:
            try:
                weight = self._detect_active_weight_name() or ""
            except Exception:
                weight = ""
        hint = f"Weights detected: {weight}." if weight else "Weights: not detected yet."
        dialog_label = (
            "Change the Stigmergic AGI name on this node.\n"
            f"{hint}\n"
            "Type any name. The owner_genesis signature stays valid; this is an overlay."
        )

        try:
            new_name, accepted = QInputDialog.getText(
                self,
                "Change Stigmergic AGI Name",
                dialog_label,
                QLineEdit.EchoMode.Normal,
                current,
            )
        except Exception:
            return
        if not accepted:
            return
        new_name = (new_name or "").strip()
        if not new_name:
            self.change_agi_name_btn.setText("✏️  empty — try again")
            QTimer.singleShot(2000, lambda: self.change_agi_name_btn.setText(
                "✏️ Change Stigmergic AGI Name"
            ))
            return

        try:
            from pathlib import Path as _Path
            import json as _json
            import time as _time
            out_path = _REPO / ".sifta_state" / "ai_name_alias.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            can_be_called = sorted(
                {new_name} | ({weight} if weight else set())
            )
            payload = {
                "truth": "OBSERVED",
                "kind": "AI_NAME_ALIAS_V1",
                "weight_name_source": (
                    "ai_weight_name() — live from alice_conversation.jsonl / model tag"
                ),
                "weight_name": weight,
                "alias": new_name,
                "can_be_called": can_be_called,
                "saved_ts": _time.time(),
                "note": (
                    "Non-destructive overlay. owner_genesis.json signature "
                    "stays valid; ai_display_name on genesis untouched. "
                    "weight_name is read live — swap Ollama, value updates "
                    "on next save."
                ),
            }
            out_path.write_text(_json.dumps(payload, indent=2), encoding="utf-8")
            self.change_agi_name_btn.setText(f"✓ Saved: {new_name}")
            QTimer.singleShot(2500, lambda: self.change_agi_name_btn.setText(
                "✏️ Change Stigmergic AGI Name"
            ))
            # Trigger a refresh so the Owner card subtitle re-reads the cascade.
            try:
                self.refresh()
            except Exception:
                pass
        except Exception as e:
            self.change_agi_name_btn.setText(f"err: {type(e).__name__}")
            QTimer.singleShot(3000, lambda: self.change_agi_name_btn.setText(
                "✏️ Change Stigmergic AGI Name"
            ))

    def _scan_face_for_genesis(self) -> None:
        """Use the Mac camera to capture the owner's face and run the Genesis Ceremony.
        
        Camera Priority (per Dr. Cursor's review):
        1. Index 0 = Mac built-in hardware camera (always tried first)
        2. Fallback to indices 1-4 only if index 0 fails
        3. Record every probe failure with reason for Alice to read
        4. Camera errors and Genesis errors are reported separately
        """
        if (
            os.environ.get("SIFTA_DISABLE_CV2_IN_QT_DESKTOP", "").strip().lower()
            in {"1", "true", "yes", "on"}
            and os.environ.get("SIFTA_FORCE_CV2", "").strip().lower()
            not in {"1", "true", "yes", "on"}
        ):
            self.scan_face_btn.setText("cv2 disabled in desktop; use camera daemon")
            return
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
        self.net_wa = MetricCard("WhatsApp Transport", "--", "SIFTA WhatsApp bridge primary; macOS app is diagnostic fallback only")
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
        """Start or stop the optional local WhatsApp bridge."""
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
            self._corvid_default = CANONICAL_OLLAMA_FALLBACK

        if self._corvid_default == "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest":
            self._corvid_default = CANONICAL_OLLAMA_FALLBACK

        try:
            active_cortex = (
                resolve_ollama_model(app_context="talk_to_alice", use_stigmergic=False)
                or get_default_ollama_model()
                or DEFAULT_OLLAMA_MODEL
            )
        except Exception:
            active_cortex = get_default_ollama_model() or DEFAULT_OLLAMA_MODEL

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

        # ── Cortex picker section ──
        # Architect 2026-05-15: ONE dropdown + cycle button, no hardcoded
        # Daily / Fallback / Extra Research tiering.
        # "let me have a dropdown to select the cortex I want ... button that
        # switches the daily cortex, loops through all cortexes ... no hardcoding,
        # I want to try them all."
        cortex_heading = QLabel("🧠  Cortex  ·  pick a local Alice cortex or cloud cortex")
        cortex_heading.setStyleSheet(
            "color: rgb(0, 220, 255); font-size: 13px; font-weight: bold; margin-top: 2px;"
        )
        root.addWidget(cortex_heading)

        # Discover installed cortexes; canonical fallback if Ollama is offline
        try:
            installed_cortexes = list_available_cortexes_with_canonical_fallback()
        except Exception:
            installed_cortexes = [active_cortex]

        self._installed_cortexes = installed_cortexes

        picker_row = QHBoxLayout()
        picker_row.setSpacing(8)

        picker_label = QLabel("Cortex")
        picker_label.setStyleSheet(
            "color: rgb(130, 140, 160); font-size: 11px; min-width: 118px;"
        )
        picker_row.addWidget(picker_label)

        self._cortex_combo = QComboBox()
        self._cortex_combo.setObjectName("AliceCortexPicker")
        self._cortex_combo.setEditable(False)
        self._cortex_combo.setStyleSheet(
            "QComboBox { background: rgb(0, 30, 45); color: rgb(0, 220, 255); "
            "border: 1px solid rgb(0, 150, 200); border-radius: 8px; "
            "padding: 6px 10px; font-size: 12px; font-family: Menlo; }"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox QAbstractItemView { background: rgb(0, 22, 36); "
            "color: rgb(0, 220, 255); selection-background-color: rgb(0, 60, 90); }"
        )
        for tag in installed_cortexes:
            # Round 33/70: make the Grok cloud entry explicit. The tag
            # `grok:grok-4.3` is the canonical SIFTA resolver key (receipt/audit
            # clarity). Round 70 maps that key to the concrete local CLI model
            # `grok-build` at the Grok CLI boundary because `grok models` on
            # this node exposes only `grok-build`.
            if _looks_remote_model_name(tag) and tag.lower().startswith("grok"):
                display = f"{tag}  ·  xAI Grok OAuth (CLI: grok-build)  ·  ☁ cloud"
            elif _looks_remote_model_name(tag) and tag.lower().startswith("claude"):
                display = f"{tag}  ·  Claude Code OAuth teacher  ·  ☁ cloud"
            elif _looks_remote_model_name(tag) and tag.lower().startswith("codex"):
                display = f"{tag}  ·  Codex CLI OAuth teacher  ·  ☁ cloud"
            elif _looks_remote_model_name(tag) and tag.lower().startswith("qwen"):
                # Qwen Code CLI cortexes route through Fireworks. Name the
                # concrete model so gpt-oss, DeepSeek Flash, and legacy Kimi
                # do not appear as duplicate "Kimi" rows in the picker.
                low_tag = tag.lower()
                if "deepseek-v4-flash" in low_tag:
                    qwen_label = "DeepSeek V4 Flash via Fireworks"
                elif "gpt-oss-20b" in low_tag:
                    qwen_label = "gpt-oss-20b via Fireworks"
                elif "kimi-k2p6" in low_tag:
                    qwen_label = "Kimi K2.6 via Fireworks"
                else:
                    qwen_label = "Fireworks"
                display = f"{tag}  ·  Qwen Code ({qwen_label}) teacher  ·  ☁ cloud"
            elif _looks_remote_model_name(tag) and tag.lower().startswith("cline"):
                # Round 89 — Cline open-source CLI cortex (Apache 2.0, multi-provider).
                display = f"{tag}  ·  Cline OAuth teacher (open-source)  ·  ☁ cloud"
            elif _looks_remote_model_name(tag) and tag.lower().startswith("mimo"):
                display = f"{tag}  ·  MiMo CLI teacher  ·  ☁ cloud"
            elif tag.lower().startswith("mlx-vlm:"):
                if "gemma-4-12b-it-8bit-mlx" in tag.lower():
                    display = f"{tag}  ·  MLX local Gemma 4 12B original/censored test  ·  8-bit safetensors"
                else:
                    display = f"{tag}  ·  MLX local VLM  ·  safetensors"
            else:
                weight_suffix = "☁ cloud" if _looks_remote_model_name(tag) else _fmt_weight(tag)
                display = f"{tag}  ·  {weight_suffix}" if weight_suffix else tag
            self._cortex_combo.addItem(display, userData=tag)
        # Pre-select the active cortex if it's in the list
        try:
            idx = installed_cortexes.index(active_cortex)
            self._cortex_combo.blockSignals(True)
            self._cortex_combo.setCurrentIndex(idx)
            self._cortex_combo.blockSignals(False)
        except ValueError:
            try:
                self._cortex_combo.blockSignals(False)
            except Exception:
                pass
        self._cortex_combo.currentIndexChanged.connect(self._on_cortex_picker_changed)
        picker_row.addWidget(self._cortex_combo, stretch=1)

        self._cortex_auth_indicator = QPushButton("●")
        self._cortex_auth_indicator.setObjectName("CortexAuthIndicator")
        self._cortex_auth_indicator.setFixedSize(20, 20)
        self._cortex_auth_indicator.setToolTip("Cortex auth health")
        self._cortex_auth_indicator.clicked.connect(self._on_cortex_auth_indicator_clicked)
        picker_row.addWidget(self._cortex_auth_indicator)

        cycle_btn = QPushButton("↻  Cycle")
        cycle_btn.setFixedHeight(30)
        cycle_btn.setToolTip(
            "Rescan Ollama for newly-pulled models, then rotate the active cortex\n"
            "through every installed Alice cortex. Each click loops to the next one\n"
            "and saves it as the default — no restart needed to see a fresh pull."
        )
        cycle_btn.setStyleSheet(
            "QPushButton { background: rgb(0, 30, 45); color: rgb(0, 220, 255); "
            "border: 1px solid rgb(0, 150, 200); border-radius: 8px; "
            "font-size: 11px; padding: 0 12px; font-family: Menlo; }"
            "QPushButton:hover { background: rgb(0, 60, 90); color: rgb(0, 255, 255); "
            "border-color: rgb(0, 200, 255); }"
        )
        cycle_btn.clicked.connect(self._cycle_cortex)
        picker_row.addWidget(cycle_btn)

        root.addLayout(picker_row)

        llm_row = QHBoxLayout()
        llm_row.setSpacing(8)
        llm_label = QLabel("LLM")
        llm_label.setStyleSheet(
            "color: rgb(130, 140, 160); font-size: 11px; min-width: 118px;"
        )
        llm_row.addWidget(llm_label)
        self._attached_llm_combo = QComboBox()
        self._attached_llm_combo.setObjectName("AliceCortexAttachedLLMPicker")
        self._attached_llm_combo.setEditable(False)
        self._attached_llm_combo.setStyleSheet(
            "QComboBox { background: rgb(0, 30, 45); color: rgb(0, 220, 255); "
            "border: 1px solid rgb(0, 150, 200); border-radius: 8px; "
            "padding: 6px 10px; font-size: 12px; font-family: Menlo; }"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox QAbstractItemView { background: rgb(0, 22, 36); "
            "color: rgb(0, 220, 255); selection-background-color: rgb(0, 60, 90); }"
            "QComboBox:disabled { color: rgb(90, 100, 120); }"
        )
        self._attached_llm_combo.currentIndexChanged.connect(self._on_attached_llm_picker_changed)
        llm_row.addWidget(self._attached_llm_combo, stretch=1)
        self._attached_llm_status = QLabel("")
        self._attached_llm_status.setStyleSheet(
            "color: rgb(100, 120, 150); font-size: 10px; font-family: Menlo;"
        )
        llm_row.addWidget(self._attached_llm_status)
        root.addLayout(llm_row)
        self._refresh_attached_llm_picker()

        inventory_heading = QLabel("📦  Installed model bodies  ·  MLX / GGUF / server runtimes")
        inventory_heading.setStyleSheet(
            "color: rgb(160, 180, 255); font-size: 13px; font-weight: bold; margin-top: 6px;"
        )
        # r669 (George: "THERE IS A DUPLICATE DROPBOX — AND THE SELECTION DID NOT WORK"):
        # this second model dropdown duplicated the Cortex picker above and confused the
        # switch flow (selecting here did not change the live voice unless Apply hit a
        # selectable row). ONE picker = the Cortex dropdown. The inventory machinery
        # stays (body map/matrix read it); only the duplicate UI row is hidden.
        inventory_heading.setVisible(False)
        root.addWidget(inventory_heading)

        inventory_row = QHBoxLayout()
        inventory_row.setSpacing(8)
        inventory_label = QLabel("Body")
        inventory_label.setStyleSheet(
            "color: rgb(130, 140, 160); font-size: 11px; min-width: 118px;"
        )
        inventory_row.addWidget(inventory_label)

        self._model_inventory_combo = QComboBox()
        self._model_inventory_combo.setObjectName("InstalledModelBodyPicker")
        self._model_inventory_combo.setEditable(False)
        self._model_inventory_combo.setStyleSheet(
            "QComboBox { background: rgb(22, 20, 40); color: rgb(190, 205, 255); "
            "border: 1px solid rgb(95, 90, 180); border-radius: 8px; "
            "padding: 6px 10px; font-size: 11px; font-family: Menlo; }"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox QAbstractItemView { background: rgb(16, 15, 30); "
            "color: rgb(190, 205, 255); selection-background-color: rgb(45, 45, 90); }"
        )
        self._model_inventory_combo.currentIndexChanged.connect(self._on_model_inventory_changed)
        inventory_row.addWidget(self._model_inventory_combo, stretch=1)

        self._apply_model_body_btn = QPushButton("Apply")
        self._apply_model_body_btn.setFixedHeight(30)
        self._apply_model_body_btn.setToolTip(
            "Use the selected installed model body as Alice's default cortex when it is directly selectable."
        )
        self._apply_model_body_btn.setStyleSheet(
            "QPushButton { background: rgb(22, 20, 40); color: rgb(190, 205, 255); "
            "border: 1px solid rgb(95, 90, 180); border-radius: 8px; "
            "font-size: 11px; padding: 0 12px; font-family: Menlo; }"
            "QPushButton:disabled { color: rgb(80, 82, 110); border-color: rgb(45, 45, 60); }"
            "QPushButton:hover { background: rgb(35, 32, 70); border-color: rgb(130, 130, 230); }"
        )
        self._apply_model_body_btn.clicked.connect(self._apply_selected_model_body)
        inventory_row.addWidget(self._apply_model_body_btn)
        # r669: hide the duplicate picker row (combo + Apply + label) — the Cortex
        # dropdown above is the ONE switch. Widgets stay alive for programmatic use.
        inventory_label.setVisible(False)
        self._model_inventory_combo.setVisible(False)
        self._apply_model_body_btn.setVisible(False)
        root.addLayout(inventory_row)

        self._model_inventory_detail = QLabel("Scanning installed model bodies...")
        self._model_inventory_detail.setVisible(False)  # r669: rides with the hidden duplicate row
        self._model_inventory_detail.setWordWrap(True)
        self._model_inventory_detail.setStyleSheet(
            "color: rgb(125, 136, 170); font-size: 10px; font-family: Menlo; "
            "background: rgb(12, 12, 22); border: 1px solid rgb(35, 35, 58); "
            "border-radius: 6px; padding: 6px 8px;"
        )
        root.addWidget(self._model_inventory_detail)

        self._runtime_nuggets = QLabel(
            " · ".join(inference_runtime_nuggets()[:3])
        )
        self._runtime_nuggets.setWordWrap(True)
        self._runtime_nuggets.setStyleSheet(
            "color: rgb(90, 104, 135); font-size: 10px; font-family: Menlo;"
        )
        root.addWidget(self._runtime_nuggets)
        self._populate_model_inventory(active_cortex)

        self._cortex_auth_timer = QTimer(self)
        self._cortex_auth_timer.setInterval(5000)
        self._cortex_auth_timer.timeout.connect(self._refresh_cortex_auth_indicator)
        self._cortex_auth_timer.start()
        self._refresh_cortex_auth_indicator()

        # Hermes Arm Provider selector removed (2026-06-01, Architect directive).
        # Arm selection is now 100% stigmergic: Alice chooses the best available arm
        # based on learned experience in her field (what worked for this task/context
        # in the past). New nodes inherit the shipped experience. No manual dropdown.

        # ── Corvid / Fallback section — secondary brain ──
        corvid_heading = QLabel("🐦  Corvid Scout  ·  Qwen side brain for cheap bounded evidence")
        corvid_heading.setStyleSheet(
            "color: rgb(0, 200, 130); font-size: 13px; font-weight: bold; margin-top: 6px;"
        )
        root.addWidget(corvid_heading)
        root.addLayout(_chip_row("Q Scout", self._corvid_default,
                                  chip_style_organ, _fmt_weight(self._corvid_default)))

        # ── C1 Classifier — tertiary brain (gate runs before Cortex) ──
        chip_style_c1 = (
            "background: rgb(20, 22, 8); color: rgb(180, 200, 80); "
            "border: 1px solid rgb(110, 130, 30); border-radius: 8px; "
            "padding: 6px 12px; font-size: 12px; font-family: Menlo;"
        )
        c1_heading = QLabel("🔤  Reflex (Gemma E2B shared)  ·  tertiary brain · turn gate before Cortex")
        c1_heading.setStyleSheet(
            "color: rgb(180, 200, 80); font-size: 13px; font-weight: bold; margin-top: 6px;"
        )
        root.addWidget(c1_heading)
        root.addLayout(_chip_row("Reflex",  f"{CANONICAL_OLLAMA_REFLEX}  ·  SILENCE / TOOL / BOND / ENGAGE",
                                  chip_style_c1, _fmt_weight(CANONICAL_OLLAMA_REFLEX)))
        root.addLayout(_chip_row("Training Corpus", "1,401 rows  ·  rank=16  dropout=0.1",
                                  chip_style_c1))

        # ── Organs section — pure-Python, no Ollama model ──
        organ_heading = QLabel("⚡  Reflex Organs  ·  pure-Python, run alongside cortex")
        organ_heading.setStyleSheet(
            "color: rgb(0, 200, 130); font-size: 13px; font-weight: bold; margin-top: 6px;"
        )
        root.addWidget(organ_heading)
        root.addLayout(_chip_row("Reflex Arc",    "Pure Python · no model", chip_style_fixed))
        root.addLayout(_chip_row("Thermal Cortex", "BISHOP · fever router", chip_style_fixed))

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
            f"this restores {DEFAULT_OLLAMA_MODEL} as the canonical cortex."
        )
        reset_btn.clicked.connect(self._reset_brain_to_default)
        reset_row.addWidget(reset_btn)
        root.addLayout(reset_row)

        self.inference_default_card = MetricCard("Alice Cortex", active_cortex)
        self.inference_default_card.set_metric(active_cortex, "Daily cortex active")
        root.addWidget(self.inference_default_card)

        root.addStretch()
        return page

    def _persist_primary_cortex_selection(self, tag: str, *, source: str) -> dict[str, Any]:
        """Persist the one Settings cortex selector through the receipt-backed switch spine."""
        selected = str(tag or "").strip()
        if not selected:
            return {"ok": False, "reason": "empty_cortex_tag"}
        try:
            installed = list(self._installed_cortexes or [])
        except Exception:
            installed = []
        if selected not in installed:
            installed.append(selected)
        try:
            from System.swarm_primary_cortex_switcher import set_primary_cortex

            receipt = set_primary_cortex(
                selected,
                installed=installed,
                source=source,
            )
        except Exception as exc:
            return {
                "ok": False,
                "reason": f"{type(exc).__name__}: {exc}",
                "selected_model": selected,
            }
        try:
            set_app_ollama_model("owner_vision_body", selected)
        except Exception as exc:
            receipt["owner_vision_body_error"] = f"{type(exc).__name__}: {exc}"
        return {"ok": True, **receipt}

    def _populate_model_inventory(self, active_cortex: str | None = None) -> None:
        if not hasattr(self, "_model_inventory_combo"):
            return
        active_cortex = str(active_cortex or get_default_ollama_model() or "")
        try:
            rows = list_inference_model_inventory()
        except Exception as exc:
            rows = []
            if hasattr(self, "_model_inventory_detail"):
                self._model_inventory_detail.setText(f"Inventory scan failed: {type(exc).__name__}")

        self._model_inventory_rows = rows
        combo = self._model_inventory_combo
        combo.blockSignals(True)
        combo.clear()
        selected_idx = 0
        for idx, row in enumerate(rows):
            label = format_inventory_label(row)
            combo.addItem(label, userData=row)
            value = str(row.get("selectable_value") or "")
            if value and value == active_cortex:
                selected_idx = idx
        if rows:
            combo.setCurrentIndex(selected_idx)
        else:
            combo.addItem("No local model bodies found", userData={})
            combo.setCurrentIndex(0)
        combo.blockSignals(False)
        self._on_model_inventory_changed(combo.currentIndex())

    def _on_model_inventory_changed(self, idx: int) -> None:
        if not hasattr(self, "_model_inventory_combo"):
            return
        try:
            row = self._model_inventory_combo.itemData(idx) or {}
        except Exception:
            row = {}
        if hasattr(self, "_model_inventory_detail"):
            self._model_inventory_detail.setText(inventory_detail_text(row))
        if hasattr(self, "_apply_model_body_btn"):
            self._apply_model_body_btn.setEnabled(bool(row.get("selectable") and row.get("selectable_value")))

    def _apply_selected_model_body(self) -> None:
        if not hasattr(self, "_model_inventory_combo"):
            return
        try:
            row = self._model_inventory_combo.currentData() or {}
        except Exception:
            row = {}
        value = str(row.get("selectable_value") or "").strip()
        if not (row.get("selectable") and value):
            if hasattr(self, "_model_inventory_detail"):
                self._model_inventory_detail.setText(
                    inventory_detail_text(row)
                    + "\nThis row is visible for testing context, but it is not registered as a live SIFTA cortex yet."
                )
            return
        receipt = self._persist_primary_cortex_selection(
            value,
            source="system_settings_hidden_model_inventory_apply",
        )
        if not receipt.get("ok"):
            if hasattr(self, "_model_inventory_detail"):
                self._model_inventory_detail.setText(
                    inventory_detail_text(row) + f"\nApply failed: {receipt.get('reason', 'unknown')}"
                )
            return
        if hasattr(self, "_brain_diagram"):
            try:
                self._brain_diagram.update_cortex_label(value)
            except Exception:
                pass
        if hasattr(self, "inference_default_card"):
            try:
                self.inference_default_card.set_metric(value, "active cortex")
            except Exception:
                pass
        if hasattr(self, "_cortex_combo") and hasattr(self, "_installed_cortexes"):
            try:
                if value in self._installed_cortexes:
                    idx = self._installed_cortexes.index(value)
                    self._cortex_combo.blockSignals(True)
                    self._cortex_combo.setCurrentIndex(idx)
                    self._cortex_combo.blockSignals(False)
            except Exception:
                pass
        if hasattr(self, "_model_inventory_detail"):
            self._model_inventory_detail.setText(inventory_detail_text(row) + "\nApplied as Alice default cortex.")
        self._refresh_cortex_auth_indicator()

    def _reset_brain_to_default(self) -> None:
        """Restore the canonical 8B m5 cortex (architect 2026-05-15 promotion).

        Previously rolled back to the 4.4GB Gemma4 daily cortex; now defaults
        to `alice-m5-cortex-8b-6.3gb:latest` because the 4.4GB was leaking
        service-voice residue ("the system is humming, the core logic is
        aligning") on introspective turns.
        """
        canonical = DEFAULT_OLLAMA_MODEL
        self._persist_primary_cortex_selection(
            canonical,
            source="system_settings_reset_brain_to_default",
        )
        set_app_ollama_model("corvid_apprentice", CANONICAL_OLLAMA_FALLBACK)
        if hasattr(self, "_brain_diagram"):
            self._brain_diagram.update_cortex_label(canonical)
            self._brain_diagram.update_corvid_label(CANONICAL_OLLAMA_FALLBACK)
        # Re-sync the picker if mounted
        if hasattr(self, "_cortex_combo") and hasattr(self, "_installed_cortexes"):
            try:
                idx = self._installed_cortexes.index(canonical)
                # block signal to avoid re-saving on programmatic select
                self._cortex_combo.blockSignals(True)
                self._cortex_combo.setCurrentIndex(idx)
                self._cortex_combo.blockSignals(False)
            except (ValueError, AttributeError):
                pass
        self.refresh()

    def _on_cortex_picker_changed(self, idx: int) -> None:
        """User picked a new cortex from the dropdown — persist it.

        Architect 2026-05-15: every selection saves as the new default
        cortex AND the talk_to_alice override, so the next utterance
        through Alice Talk routes through the picked model.
        """
        try:
            tag = self._cortex_combo.itemData(idx)
        except Exception:
            return
        if not tag:
            return
        tag = str(tag)
        receipt = self._persist_primary_cortex_selection(
            tag,
            source="system_settings_inference_cortex_picker",
        )
        if not receipt.get("ok"):
            if hasattr(self, "inference_default_card"):
                try:
                    self.inference_default_card.set_metric(
                        str(resolve_ollama_model(app_context="talk_to_alice", use_stigmergic=False)),
                        f"switch failed: {receipt.get('reason', 'unknown')}",
                    )
                except Exception:
                    pass
            return
        if hasattr(self, "_brain_diagram"):
            try:
                self._brain_diagram.update_cortex_label(tag)
            except Exception:
                pass
        if hasattr(self, "inference_default_card"):
            try:
                self.inference_default_card.set_metric(tag, "active cortex")
            except Exception:
                pass
        self._refresh_cortex_auth_indicator()
        self._refresh_attached_llm_picker()

    def _selected_cortex_tag(self) -> str:
        try:
            if hasattr(self, "_cortex_combo"):
                idx = self._cortex_combo.currentIndex()
                tag = self._cortex_combo.itemData(idx)
                if tag:
                    return str(tag)
        except Exception:
            pass
        return str(get_default_ollama_model() or "")

    def _refresh_attached_llm_picker(self) -> None:
        """Repopulate the cortex-scoped attached LLM dropdown (r1233)."""
        if not hasattr(self, "_attached_llm_combo"):
            return
        try:
            from System.swarm_cortex_capabilities import (
                active_attached_model_for_cortex,
                attached_models_for_cortex,
                format_attached_model,
                resolve_attached_models_cortex_id,
            )
        except Exception:
            return

        combo = self._attached_llm_combo
        status = getattr(self, "_attached_llm_status", None)
        cortex_tag = self._selected_cortex_tag()
        cid = resolve_attached_models_cortex_id(cortex_tag, state_dir=STATE)
        rec = attached_models_for_cortex(cid, state_dir=STATE)
        models = [str(m) for m in (rec.get("attached_models") or []) if str(m).strip()]
        active = active_attached_model_for_cortex(cortex_tag, state_dir=STATE)

        combo.blockSignals(True)
        combo.clear()
        if not models:
            combo.addItem("(provider default — cortex tag is the model)", userData="")
            combo.setEnabled(False)
            if status is not None:
                status.setText("no attached LLM list for this cortex")
        else:
            combo.setEnabled(True)
            active_idx = 0
            for i, mid in enumerate(models):
                label = format_attached_model(mid)
                combo.addItem(label, userData=mid)
                if mid == active:
                    active_idx = i
            combo.setCurrentIndex(active_idx)
            if status is not None:
                status.setText(
                    f"ledger default: {format_attached_model(active) if active else '(unset)'}"
                )
        combo.blockSignals(False)

    def _on_attached_llm_picker_changed(self, idx: int) -> None:
        """Persist attached/default LLM for the currently selected cortex only."""
        if not hasattr(self, "_attached_llm_combo"):
            return
        try:
            model_id = self._attached_llm_combo.itemData(idx)
        except Exception:
            return
        if not model_id:
            return
        try:
            from System.swarm_cortex_capabilities import (
                format_attached_model,
                persist_attached_llm_default,
            )
        except Exception:
            return
        cortex_tag = self._selected_cortex_tag()
        receipt = persist_attached_llm_default(
            cortex_tag,
            str(model_id),
            state_dir=STATE,
            source="system_settings_attached_llm_picker",
        )
        if not receipt.get("ok"):
            self._refresh_attached_llm_picker()
            return
        if hasattr(self, "_attached_llm_status"):
            self._attached_llm_status.setText(
                f"set: {format_attached_model(str(receipt.get('to_default') or model_id))}"
            )

    def _last_cortex_completion_timestamp(self) -> float | None:
        path = STATE / "work_receipts.jsonl"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None

        if getattr(self, "_last_cortex_receipt_mtime", None) == mtime:
            return getattr(self, "_last_cortex_receipt_ts", None)

        latest: float | None = None
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            blob = json.dumps(row, ensure_ascii=False).lower()
            if "cortex" not in blob:
                continue
            ts = row.get("ts")
            if not isinstance(ts, (int, float)):
                ts = row.get("timestamp")
            if isinstance(ts, (int, float)):
                tsf = float(ts)
                if latest is None or tsf > latest:
                    latest = tsf

        self._last_cortex_receipt_mtime = mtime
        self._last_cortex_receipt_ts = latest
        return latest

    def _refresh_cortex_auth_indicator(self) -> None:
        if not hasattr(self, "_cortex_auth_indicator"):
            return

        indicator = self._cortex_auth_indicator
        tag = self._selected_cortex_tag()
        if not _is_xai_cortex_tag(tag):
            if _is_qwen_cortex_tag(tag):
                key = _qwen_api_key_masked(state_dir=STATE)
                if key:
                    indicator.setVisible(True)
                    indicator.setEnabled(True)
                    indicator.setStyleSheet(
                        "QPushButton { color: rgb(40, 220, 90); background: transparent; border: none; "
                        "font-size: 18px; font-family: Menlo; padding: 0; }"
                        "QPushButton:hover { color: rgb(80, 255, 120); }"
                    )
                    indicator.setToolTip(f"Qwen/Fireworks key present: {key}")
                else:
                    indicator.setVisible(True)
                    indicator.setEnabled(True)
                    indicator.setStyleSheet(
                        "QPushButton { color: rgb(255, 120, 80); background: transparent; border: none; "
                        "font-size: 18px; font-family: Menlo; padding: 0; }"
                        "QPushButton:hover { color: rgb(255, 170, 120); }"
                    )
                    indicator.setToolTip(
                        "Qwen/Fireworks key missing.\n"
                        "Click to set FIREWORKS_API_KEY and write qwen settings."
                    )
                return

            if _is_cline_cortex_tag(tag):
                cli = _cline_cli_available()
                if cli:
                    indicator.setVisible(True)
                    indicator.setEnabled(True)
                    indicator.setStyleSheet(
                        "QPushButton { color: rgb(40, 220, 90); background: transparent; border: none; "
                        "font-size: 18px; font-family: Menlo; padding: 0; }"
                        "QPushButton:hover { color: rgb(80, 255, 120); }"
                    )
                    indicator.setToolTip("Alice / Cline CLI hand detected on PATH.")
                else:
                    indicator.setVisible(True)
                    indicator.setEnabled(True)
                    indicator.setStyleSheet(
                        "QPushButton { color: rgb(255, 120, 80); background: transparent; border: none; "
                        "font-size: 18px; font-family: Menlo; padding: 0; }"
                        "QPushButton:hover { color: rgb(255, 170, 120); }"
                    )
                    indicator.setToolTip(
                        "Alice's hand (alice-hand) not found on PATH.\n"
                        "Install with: npm install -g @anton-sifta/alice\n"
                        "Then invoke with: alice-hand"
                    )
                return

            indicator.setVisible(False)
            return

        indicator.setVisible(True)
        indicator.setEnabled(True)
        try:
            from System.swarm_cortex_auth_health import check_xai_oauth_health

            health = check_xai_oauth_health(STATE)
        except Exception as exc:
            health = {
                "status": "red",
                "reason": f"probe_failed:{type(exc).__name__}",
                "last_failover_age_s": None,
            }

        status = str(health.get("status") or "red").lower()
        reason = str(health.get("reason") or "unknown")
        age = health.get("last_failover_age_s")
        if isinstance(age, (int, float)):
            age_str = f"{age/60.0:.1f}m"
        else:
            age_str = "none"

        if status == "green":
            indicator.setStyleSheet(
                "QPushButton { color: rgb(40, 220, 90); background: transparent; border: none; "
                "font-size: 18px; font-family: Menlo; padding: 0; }"
                "QPushButton:hover { color: rgb(80, 255, 120); }"
            )
            last_ts = self._last_cortex_completion_timestamp()
            if isinstance(last_ts, (int, float)) and last_ts > 0:
                ts_local = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(last_ts)))
                age_s = max(0.0, time.time() - float(last_ts))
                if age_s < 60:
                    age_label = f"{int(age_s)}s ago"
                elif age_s < 3600:
                    age_label = f"{int(age_s // 60)}m ago"
                else:
                    age_label = f"{age_s / 3600.0:.1f}h ago"
                tooltip = (
                    f"xAI OAuth healthy\n"
                    f"last cortex completion: {ts_local} ({age_label})"
                )
            else:
                tooltip = "xAI OAuth healthy\nlast cortex completion: not found in work_receipts.jsonl"
            indicator.setToolTip(tooltip)
        else:
            indicator.setStyleSheet(
                "QPushButton { color: rgb(255, 80, 80); background: transparent; border: none; "
                "font-size: 18px; font-family: Menlo; padding: 0; }"
                "QPushButton:hover { color: rgb(255, 130, 130); }"
            )
            indicator.setToolTip(
                "xAI OAuth missing/expired\n"
                f"reason: {reason}\n"
                f"last failover age: {age_str}\n"
                "Click to run hermes auth add xai-oauth"
            )

    def _on_cortex_auth_indicator_clicked(self) -> None:
        tag = self._selected_cortex_tag()
        if not _is_xai_cortex_tag(tag):
            if _is_qwen_cortex_tag(tag):
                try:
                    current_key = _qwen_api_key_masked(state_dir=STATE)
                    hint = (
                        "Current key is already set."
                        if current_key
                        else "No key set."
                    )
                    new_key, accepted = QInputDialog.getText(
                        self,
                        "Qwen/Fireworks API Key",
                        "Set FIREWORKS_API_KEY for qwen:qwen model routing.\n"
                        f"{hint}\n\n"
                        "Tip: keep your key in .sifta_state/secrets/fireworks_api_key by saving here.",
                        QLineEdit.EchoMode.Password,
                        "",
                    )
                except Exception as exc:
                    self.set_status(f"Qwen key dialog failed: {type(exc).__name__}")
                    self._refresh_cortex_auth_indicator()
                    return

                if not accepted:
                    self.set_status("Qwen key update cancelled.")
                    self._refresh_cortex_auth_indicator()
                    return

                raw_key = (new_key or "").strip()
                if not raw_key:
                    self.set_status("Qwen key is empty — no changes.")
                    self._refresh_cortex_auth_indicator()
                    return

                try:
                    install_qwen_fireworks_settings(
                        raw_key,
                        state_dir=STATE,
                        qwen_home=Path.home() / ".qwen",
                    )
                    self.set_status("Qwen key saved to .sifta_state/secrets/fireworks_api_key.")
                except Exception as exc:
                    self.set_status(f"Qwen key save failed: {type(exc).__name__}")
                self._refresh_cortex_auth_indicator()
                return

            if _is_cline_cortex_tag(tag):
                cli = _cline_cli_available()
                if cli:
                    self.set_status("Alice / Cline CLI hand detected on PATH. The SIFTA OS can now use the new arm.")
                else:
                    self.set_status("Alice's hand (alice-hand) not found on PATH. Install with `npm install -g @anton-sifta/alice`, then `alice-hand` is the command.")
                self._refresh_cortex_auth_indicator()
                return

            return
        try:
            from System.swarm_cortex_auth_health import check_xai_oauth_health
            from System.swarm_cortex_failover_reflex import schedule_oauth_refresh

            health = check_xai_oauth_health(STATE)
            if str(health.get("status") or "") == "red":
                result = schedule_oauth_refresh(force=True)
                self.set_status(f"xAI OAuth refresh: {result.get('status', 'unknown')}")
            else:
                self.set_status("xAI OAuth is healthy.")
        except Exception as exc:
            self.set_status(f"xAI OAuth refresh failed: {type(exc).__name__}")
        self._refresh_cortex_auth_indicator()

    def _on_hermes_arm_provider_changed(self, idx: int) -> None:
        """Round 33 (Claude/Cowork direct, 2026-05-27): persist owner's Hermes
        arm provider choice to .sifta_state/hermes_cortex.json. swarm_agent_arm_launcher.py
        reads that file at delegate-time (hermes_cortex_override ~line 218), so
        the next "Alice, ask Hermes to X" delegation routes through the
        selected provider — local Ollama or xAI Grok OAuth via Hermes auth.json.
        """
        try:
            import json as _json_r33
            import time as _time_r33
            from pathlib import Path as _Path_r33
            value = self._hermes_arm_combo.itemData(idx)
            label = self._hermes_arm_combo.itemText(idx)
            cfg_path = _Path_r33(__file__).resolve().parent.parent / ".sifta_state" / "hermes_cortex.json"
            existing: dict = {}
            if cfg_path.exists():
                try:
                    existing = _json_r33.loads(cfg_path.read_text(encoding="utf-8")) or {}
                except Exception:
                    existing = {}
            previous = str(existing.get("provider") or "")
            row = {
                "provider": str(value or ""),
                "label": str(label or ""),
                "note": "Set via System Settings → Hermes Arm Provider dropdown (Round 33).",
                "set_by": "owner_via_system_settings_ui",
                "changed_at": _time_r33.strftime("%Y-%m-%d %H:%M:%S"),
                "previous": previous,
            }
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(_json_r33.dumps(row, indent=2), encoding="utf-8")
        except Exception as exc:
            # Settings panel must never crash on a persistence failure.
            import sys as _sys_r33
            print(f"[hermes_arm_provider] persist failed: {exc}", file=_sys_r33.stderr)

    def _cycle_cortex(self) -> None:
        """Rescan Ollama for fresh pulls, then rotate through every installed cortex.

        Architect 2026-05-15: *"button that switches the daily cortex, loops
        through all cortexes."* 2026-06-05: *"is not here, takes me forever to
        restart"* — a freshly `ollama pull`-ed model was missing from the picker
        because the list was built once at page load. So before rotating, rescan
        Ollama and APPEND any newly-installed cortex tags to the picker (kept
        index-aligned with `_installed_cortexes`), so a fresh pull shows up with
        no restart. The picker change handler does the persistence.
        """
        if not hasattr(self, "_cortex_combo"):
            return
        if not hasattr(self, "_installed_cortexes") or self._installed_cortexes is None:
            self._installed_cortexes = []

        # ── Rescan: pick up models pulled after the page was built ──
        try:
            fresh = list_available_cortexes_with_canonical_fallback()
        except Exception:
            fresh = list(self._installed_cortexes)
        known = set(self._installed_cortexes)
        new_tags = [t for t in fresh if t and t not in known]
        if new_tags:
            weights: dict = {}
            try:
                import urllib.request as _ur
                with _ur.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.5) as _r:
                    for m in json.loads(_r.read()).get("models", []):
                        weights[m["name"]] = m.get("size", 0)
            except Exception:
                pass
            for tag in new_tags:
                self._installed_cortexes.append(tag)  # keep list ↔ combo index aligned
                if str(tag).lower().startswith("mlx-vlm:"):
                    if "gemma-4-12b-it-8bit-mlx" in str(tag).lower():
                        suffix = "MLX local Gemma 4 12B original/censored test · 8-bit safetensors"
                    else:
                        suffix = "MLX local VLM · safetensors"
                elif _looks_remote_model_name(tag):
                    suffix = "☁ cloud"
                else:
                    try:
                        suffix = _format_ollama_weight_label(tag, weights) or "newly pulled"
                    except Exception:
                        suffix = "newly pulled"
                self._cortex_combo.addItem(f"{tag}  ·  {suffix}", userData=tag)

        if not self._installed_cortexes:
            return
        current_idx = self._cortex_combo.currentIndex()
        next_idx = (current_idx + 1) % self._cortex_combo.count()
        # setCurrentIndex fires currentIndexChanged → _on_cortex_picker_changed
        self._cortex_combo.setCurrentIndex(next_idx)
        self._refresh_cortex_auth_indicator()

    def _on_inf_default_changed(self, text: str) -> None:
        """Internal hook — kept for programmatic use; not wired to any UI control."""
        if text:
            set_default_ollama_model(text)
            set_app_ollama_model("talk_to_alice", text)
            set_app_ollama_model("owner_vision_body", text)

    def _on_inf_corvid_changed(self, text: str) -> None:
        """Internal hook — kept for programmatic use; not wired to any UI control."""
        if text:
            set_app_ollama_model("corvid_apprentice", text)


    def _economy_page(self) -> QWidget:
        page, root = self._page("Swarm Economy")
        self.metabolism_card = MetricCard("Budget Governor", "--")
        self.wallet_card = MetricCard("STGM Reserve", "--")
        self.throttle_card = MetricCard("Throttle Reason", "--")
        root.addWidget(self.metabolism_card)
        root.addWidget(self.wallet_card)
        root.addWidget(self.throttle_card)
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
        # Cowork 2026-05-12 18:45 \u2014 Architect rule: this is Stigmergic AGI,
        # not "AI". The name comes from the Layer 1 cascade (ai_name()) so a
        # fresh clone on someone else's machine shows THEIR chosen name, not
        # the literal "Alice".
        try:
            from System.swarm_kernel_identity import ai_name as _ai_name
            _agi_name = _ai_name()
        except Exception:
            _agi_name = gen.get("ai_display_name") or "\u2014"
        self.id_owner.set_metric(
            gen.get("owner_name", "<unclaimed>"),
            f"Generation {gen.get('generation', 0)} \u00b7 Stigmergic AGI: {_agi_name}",
        )
        self.id_genesis.set_metric(gen.get("status", "MISSING"), "Cryptographic Genesis Ceremony")
        self.id_spec.set_metric(f"{snap.get('hw_chip', 'Unknown')} / {snap.get('hw_memory', 'Unknown')}", "Physical Machine Spec")
        self.id_os.set_metric(snap.get("hw_os", "Unknown"), "Host Environment")
        self.id_serial.set_metric(snap["hw_serial"], "Tied to specific Apple Metal")
        self.id_anchor.set_metric(gen.get("anchor", "N/A"), "SHA-256(photo_hash + silicon_serial)")
        self.id_sig.set_metric(gen.get("sig", "N/A"), "Ed25519 hardware signature")
        self.id_digest.set_metric(snap["digest"], "Dynamic Electric Field signature")

        # ── Voice certainty (stigmergic voice identity organ) ─────────────
        try:
            from System.swarm_voice_identity_organ import (
                classify, exemplar_counts, load_exemplars, extract_features
            )
            counts = exemplar_counts()
            from System.swarm_voice_identity_organ import PRIMARY_OPERATOR_VOICE_LABEL as _PO_LABEL
            n_george = counts.get(_PO_LABEL, 0)
            total = sum(counts.values())
            if n_george == 0:
                self.id_voice.set_metric(
                    "—  No samples",
                    f"Open 🎙 Voice Identity Organ and record George voice samples  |  total exemplars: {total}"
                )
            else:
                # Quick 0.8s mic sample for live classification
                try:
                    import sounddevice as _sd
                    import numpy as _np
                    _audio = _sd.rec(int(0.8 * 16000), samplerate=16000,
                                     channels=1, dtype="float32")
                    _sd.wait()
                    _chunk = _audio[:, 0] if _audio.ndim > 1 else _audio.flatten()
                    _feats = extract_features(_chunk.astype(_np.float32))
                    _result = classify(_feats, load_exemplars())
                    _label = _result.get("label", "unknown")
                    _conf = int(_result.get("confidence", 0.0) * 100)
                    if _label == _PO_LABEL:
                        _display = f"{_conf}% — George ✓"
                        _detail = f"Swimmer vote from {n_george} George exemplars · {total} total in ledger"
                    else:
                        from System.swarm_voice_identity_organ import LABELS as _VL
                        _other = _VL.get(_label, {}).get("display", _label)
                        _detail = f"Detected: {_other} ({_conf}%) · {n_george} George samples · {total} total"
                        _display = f"~{100 - _conf}% — George (room: {_other})"
                    self.id_voice.set_metric(_display, _detail)
                except Exception:
                    # No mic access during refresh — show ledger stats only
                    self.id_voice.set_metric(
                        f"📚 {n_george} George samples",
                        f"Live classification unavailable · {total} total exemplars in ledger"
                    )
        except Exception:
            self.id_voice.set_metric("—", "Voice Identity Organ not installed")

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
        throttle = snap.get("throttle_decision", {})
        self.throttle_card.set_metric(
            str(throttle.get("value", "No throttle decision")),
            str(throttle.get("detail", "")),
        )

        # Inference
        self.inference_default_card.set_metric(
            snap["default_ollama_model"],
            "Daily cortex: Talk, owner vision, and OS helpers",
        )
        self._populate_model_inventory(str(snap["default_ollama_model"]))
        self._refresh_cortex_auth_indicator()
        self._refresh_attached_llm_picker()

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
