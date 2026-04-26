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

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPixmap
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

    net_ssid = "Unknown SSID"
    net_ip = "Unknown IP"
    wa_bridge_live = False
    try:
        import subprocess
        # Primary: networksetup (works on most macOS)
        res_ssid = subprocess.run(["networksetup", "-getairportnetwork", "en0"], capture_output=True, text=True, timeout=1)
        if "Current Wi-Fi Network:" in res_ssid.stdout:
            net_ssid = res_ssid.stdout.split(":")[-1].strip()
        # Fallback: system_profiler (macOS Tahoe / newer)
        if net_ssid == "Unknown SSID" or "not associated" in res_ssid.stdout.lower():
            res_ap = subprocess.run(["system_profiler", "SPAirPortDataType"], capture_output=True, text=True, timeout=3)
            lines = res_ap.stdout.splitlines()
            for i, line in enumerate(lines):
                if "Current Network Information:" in line and i + 1 < len(lines):
                    candidate = lines[i + 1].strip().rstrip(":")
                    if candidate:
                        net_ssid = candidate
                    break

        res_ip = subprocess.run(["ipconfig", "getifaddr", "en0"], capture_output=True, text=True, timeout=1)
        if res_ip.stdout.strip():
            net_ip = res_ip.stdout.strip()
    except Exception:
        pass

    # WhatsApp Bridge status — check if node bridge.js is running
    try:
        import subprocess
        res_wa = subprocess.run(["pgrep", "-f", "bridge.js"], capture_output=True, text=True, timeout=1)
        wa_bridge_live = bool(res_wa.stdout.strip())
    except Exception:
        pass

    return {
        "net_ssid": net_ssid,
        "net_ip": net_ip,
        "wa_bridge_live": wa_bridge_live,
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
        
        Alice hunts for cameras like a predator:
        1. Scans camera indices 0-4
        2. Prefers the Mac built-in camera (typically highest native resolution)
        3. Skips cameras that fail to open or return blank frames
        4. Locks onto the first working source autonomously
        """
        import cv2

        self.scan_face_btn.setText("\u23f3 Scanning cameras\u2026")
        self.scan_face_btn.setEnabled(False)
        QApplication.processEvents()

        # Hunt for the best camera
        best_cap = None
        best_idx = -1
        best_w = 0
        candidates = []

        for idx in range(5):
            self.scan_face_btn.setText(f"\u23f3 Probing camera {idx}\u2026")
            QApplication.processEvents()
            try:
                cap = cv2.VideoCapture(idx)
                if not cap.isOpened():
                    continue
                # Read a test frame to verify it actually works
                ret, test_frame = cap.read()
                if not ret or test_frame is None:
                    cap.release()
                    continue
                w = test_frame.shape[1]
                candidates.append((idx, w))
                cap.release()
            except Exception:
                continue

        if not candidates:
            self.scan_face_btn.setText("\u274c No cameras found")
            self.scan_face_btn.setEnabled(True)
            return

        # Prefer the widest resolution (Mac built-in is typically 1920px,
        # iPhone Continuity Camera is often 1280px or lower)
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_idx = candidates[0][0]

        self.scan_face_btn.setText(f"\u23f3 Locked on camera {best_idx} ({candidates[0][1]}px)\u2026")
        QApplication.processEvents()

        cap = None
        try:
            cap = cv2.VideoCapture(best_idx)
            if not cap.isOpened():
                self.scan_face_btn.setText("\u274c Camera lock failed")
                self.scan_face_btn.setEnabled(True)
                return

            # Warm up the sensor
            for _ in range(20):
                cap.read()

            ret, frame = cap.read()
            cap.release()
            cap = None

            if not ret or frame is None:
                self.scan_face_btn.setText("\u274c Capture failed")
                self.scan_face_btn.setEnabled(True)
                return

            # Save the captured photo
            genesis_dir = Path.home() / ".sifta_keys" / "owner_genesis"
            genesis_dir.mkdir(parents=True, exist_ok=True)
            photo_path = genesis_dir / "genesis_photo.jpg"
            cv2.imwrite(str(photo_path), frame)

            # Run the Genesis Ceremony
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
            except Exception as e:
                self.scan_face_btn.setText(f"\u274c Genesis error: {str(e)[:40]}")
        except Exception as e:
            self.scan_face_btn.setText(f"\u274c {str(e)[:50]}")
        finally:
            if cap is not None:
                cap.release()
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
        self.net_ssid = MetricCard("Wi-Fi SSID", "--", "Active Base Station")
        self.net_ip = MetricCard("Local IP", "--", "en0 interface address")
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
                bridge_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Network", "whatsapp_bridge")
                log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".sifta_state", "runtime_logs", "whatsapp_bridge.log")
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                subprocess.Popen(
                    f"cd {bridge_dir} && node bridge.js >> {log_path} 2>&1",
                    shell=True,
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

        # ── Pull LIVE model list from Ollama — zero hardcoded names ──
        all_models = _available_local_ollama_models()

        # Read the corvid organ model dynamically from its own module.
        try:
            from System.swarm_corvid_apprentice import SwarmCorvidApprentice
            import inspect
            sig = inspect.signature(SwarmCorvidApprentice.__init__)
            self._corvid_default = str(sig.parameters["model"].default)
        except Exception:
            self._corvid_default = ""

        # Cortex options = everything except the current corvid model.
        cortex_options = [m for m in all_models if m != self._corvid_default]
        if not cortex_options:
            cortex_options = all_models  # safety: never show empty dropdown

        # Corvid options = everything except the current cortex models.
        # (small models AND big models — the architect decides)
        corvid_options = list(all_models)

        default_model = _select_local_model(get_default_ollama_model(), cortex_options)

        # ── Cortex section ──
        cortex_heading = QLabel("Cortex  ·  Alice's reasoning brain")
        cortex_heading.setStyleSheet("color: rgb(0, 200, 130); font-size: 12px; font-weight: bold;")
        root.addWidget(cortex_heading)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        form.addWidget(QLabel("Alice Cortex Model"), 0, 0)
        self.inf_default_combo = QComboBox()
        self.inf_default_combo.setObjectName("AliceCortexModelCombo")
        self.inf_default_combo.addItems(cortex_options)
        self.inf_default_combo.setCurrentText(default_model)
        self.inf_default_combo.setToolTip("Single canonical cortex model for Alice, Swarm Chat, and OS helpers.")
        form.addWidget(self.inf_default_combo, 0, 1)

        form.addWidget(QLabel("Talk to Alice"), 1, 0)
        alice_follow = QLabel("follows Alice Cortex Model")
        alice_follow.setStyleSheet("color: rgb(0, 200, 130); font-weight: bold;")
        form.addWidget(alice_follow, 1, 1)

        root.addLayout(form)

        # ── Organ section ──
        organ_heading = QLabel("Organs  ·  run simultaneously alongside the cortex")
        organ_heading.setStyleSheet("color: rgb(145, 153, 180); font-size: 12px; font-weight: bold; margin-top: 8px;")
        root.addWidget(organ_heading)

        organ_grid = QGridLayout()
        organ_grid.setHorizontalSpacing(12)
        organ_grid.setVerticalSpacing(6)

        organ_grid.addWidget(QLabel("Corvid Apprentice"), 0, 0)
        self.inf_corvid_combo = QComboBox()
        self.inf_corvid_combo.addItems(corvid_options)
        if self._corvid_default in corvid_options:
            self.inf_corvid_combo.setCurrentText(self._corvid_default)
        self.inf_corvid_combo.setToolTip("Fast classifier organ. Runs in parallel with the cortex.")
        organ_grid.addWidget(self.inf_corvid_combo, 0, 1)

        organ_grid.addWidget(QLabel("Reflex Arc"), 1, 0)
        reflex_lbl = QLabel("Pure Python · no model")
        reflex_lbl.setStyleSheet("color: rgb(0, 200, 130); font-weight: bold;")
        organ_grid.addWidget(reflex_lbl, 1, 1)
        root.addLayout(organ_grid)

        note = QLabel(
            "Cortex models power Alice's reasoning and conversation. "
            "Organ models run in parallel as autonomous background processes."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: rgb(145, 153, 180);")
        root.addWidget(note)

        self.inf_default_combo.currentTextChanged.connect(self._on_inf_default_changed)
        self.inf_corvid_combo.currentTextChanged.connect(self._on_inf_corvid_changed)

        self.inference_default_card = MetricCard("Alice Cortex", "--")
        root.addWidget(self.inference_default_card)

        root.addStretch()
        return page

    def _on_inf_default_changed(self, text: str) -> None:
        if text:
            set_default_ollama_model(text)
            set_app_ollama_model("talk_to_alice", text)

    def _on_inf_corvid_changed(self, text: str) -> None:
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
            self.net_wa.set_metric("Online", "Bridge running on port 3001")
            self.wa_toggle_btn.setText("\ud83d\udd34 Disconnect WhatsApp")
            self.wa_toggle_btn.setStyleSheet(
                "QPushButton { background: rgb(70, 20, 20); color: rgb(255, 120, 120); "
                "border: 1px solid rgb(120, 40, 40); border-radius: 8px; font-size: 14px; font-weight: bold; } "
                "QPushButton:hover { background: rgb(90, 30, 30); }"
            )
        else:
            self.net_wa.set_metric("Offline", "Bridge not running")
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
