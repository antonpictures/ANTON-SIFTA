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
from PyQt6.QtGui import QFont
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

try:
    from System.swarm_gemini_brain import (
        is_gemini_model as _is_gemini_model,
        available_gemini_models as _available_gemini_models,
    )
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False
    def _is_gemini_model(_n: str) -> bool: return False        # type: ignore
    def _available_gemini_models() -> list[str]: return []     # type: ignore

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
    try:
        from System.owner_genesis import is_genesis_complete
        genesis_ok = is_genesis_complete()
    except Exception:
        genesis_ok = False

    try:
        from System.swarm_kernel_identity import owner_silicon, current_agent_digest
        hw_serial = owner_silicon()
        digest = current_agent_digest()[:8]
    except Exception:
        hw_serial = "UNKNOWN"
        digest = "N/A"

    return {
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
        "alice_brain_model": resolve_ollama_model(app_context="talk_to_alice"),
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
        self.id_genesis = MetricCard("Owner Genesis", "--")
        self.id_serial = MetricCard("Silicon Hardware", "--")
        self.id_digest = MetricCard("Electric Field Digest", "--")
        root.addWidget(self.id_genesis)
        root.addWidget(self.id_serial)
        root.addWidget(self.id_digest)
        root.addStretch()
        return page

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
        self.net_relay = MetricCard("Mesh Relay", "N/A", "WebSocket cross-node proxy")
        self.net_nerve = MetricCard("Nerve Channel", "UDP Broadcast", "Fast autonomic reflex bus")
        root.addWidget(self.net_relay)
        root.addWidget(self.net_nerve)
        root.addStretch()
        return page

    def _inference_page(self) -> QWidget:
        page, root = self._page("Inference")
        
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        options = []
        options.append(DEFAULT_OLLAMA_MODEL)
        for m in STIGMERGIC_TEST_MODEL_PRESETS:
            if m not in options:
                options.append(m)
        if _GEMINI_AVAILABLE:
            for m in _available_gemini_models():
                if m not in options:
                    options.append(m)

        form.addWidget(QLabel("Default Local Model"), 0, 0)
        self.inf_default_combo = QComboBox()
        self.inf_default_combo.addItems(options)
        self.inf_default_combo.setCurrentText(get_default_ollama_model())
        self.inf_default_combo.setToolTip("Used by Swarm Chat and OS helpers. Model plumbing belongs here.")
        form.addWidget(self.inf_default_combo, 0, 1)

        form.addWidget(QLabel("Alice Brain Model"), 1, 0)
        self.inf_alice_combo = QComboBox()
        self.inf_alice_combo.addItems(options)
        self.inf_alice_combo.setCurrentText(resolve_ollama_model(app_context="talk_to_alice"))
        self.inf_alice_combo.setToolTip("Used by Talk to Alice. The cockpit stays clean.")
        form.addWidget(self.inf_alice_combo, 1, 1)

        root.addLayout(form)

        note = QLabel(
            "Centralized inference routing: select the models for background OS functions "
            "and Alice's primary talk module."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: rgb(145, 153, 180);")
        root.addWidget(note)
        
        self.inf_default_combo.currentTextChanged.connect(self._on_inf_default_changed)
        self.inf_alice_combo.currentTextChanged.connect(self._on_inf_alice_changed)

        self.inference_default_card = MetricCard("Default Model", "--")
        self.inference_alice_card = MetricCard("Alice Brain", "--")
        root.addWidget(self.inference_default_card)
        root.addWidget(self.inference_alice_card)

        root.addStretch()
        return page

    def _on_inf_default_changed(self, text: str) -> None:
        if text:
            set_default_ollama_model(text)

    def _on_inf_alice_changed(self, text: str) -> None:
        if text:
            set_app_ollama_model("talk_to_alice", text)

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
        self.id_genesis.set_metric("Completed" if snap["genesis_ok"] else "Pending", "Initial provisioning state")
        self.id_serial.set_metric(snap["hw_serial"], "Tied to specific Apple Metal")
        self.id_digest.set_metric(snap["digest"], "Dynamic Electric Field signature")

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
            "Swarm Chat and OS helpers use this by default",
        )
        self.inference_alice_card.set_metric(
            snap["alice_brain_model"],
            "Talk to Alice reads this on launch",
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
