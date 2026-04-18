#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Intelligence Settings
# Configure local Ollama models, OpenRouter API, and active
# inference engine for all Swarm Voice entities on this node.
# ─────────────────────────────────────────────────────────────

import sys, json, os, urllib.request, urllib.error
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QTabWidget, QFrame,
    QListWidget, QListWidgetItem, QMessageBox, QCheckBox, QTextEdit
)
from PyQt6.QtCore    import Qt, QThread, pyqtSignal
from PyQt6.QtGui     import QFont

REPO_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(REPO_ROOT, ".sifta_state", "intelligence_settings.json")

OPENROUTER_MODELS = [
    "meta-llama/llama-4-maverick",
    "meta-llama/llama-4-scout",
    "meta-llama/llama-3.3-70b-instruct",
    "anthropic/claude-sonnet-4-5",
    "google/gemini-2.5-pro-preview",
    "mistralai/mistral-large",
    "deepseek/deepseek-r1",
    "openai/gpt-4o",
]

# ─────────────────────────────────────────────────────────────

def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "active_engine":     "ollama",
            "ollama_model":      "llama3:latest",
            "openrouter_key":    "",
            "openrouter_model":  "meta-llama/llama-4-maverick",
        }

def save_settings(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────────────────────────

class OllamaFetcher(QThread):
    models_ready = pyqtSignal(list)
    error        = pyqtSignal(str)
    status_ready = pyqtSignal(str)

    def __init__(self, mode="models"):
        super().__init__()
        self.mode = mode

    def run(self):
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
                names = [m["name"] for m in data.get("models", [])]
                if self.mode == "models":
                    self.models_ready.emit(names)
                else:
                    status = "OK:\n" + "\n".join(f"  {n}" for n in names)
                    self.status_ready.emit(status)
        except Exception as e:
            if self.mode == "models":
                self.error.emit(str(e))
            else:
                self.status_ready.emit(f"OFFLINE: {e}")

# ─────────────────────────────────────────────────────────────

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA OS — Intelligence Settings")
        self.setMinimumSize(640, 520)
        self.setStyleSheet("""
            QWidget     { background-color: #0d0e17; color: #a9b1d6; font-family: 'Inter'; font-size: 13px; }
            QTabWidget::pane { border: 1px solid #2a2b3d; border-radius: 6px; }
            QTabBar::tab { background: #1a1b2e; color: #565f89; padding: 8px 20px;
                           border-radius: 4px; margin-right: 2px; }
            QTabBar::tab:selected { background: #24253a; color: #7aa2f7; }
            QComboBox   { background: #1a1b2e; border: 1px solid #2a2b3d; border-radius: 4px;
                          padding: 6px; color: #a9b1d6; }
            QComboBox::drop-down { border: none; }
            QLineEdit   { background: #1a1b2e; border: 1px solid #2a2b3d; border-radius: 4px;
                          padding: 6px; color: #a9b1d6; }
            QPushButton { background: #24253a; border: 1px solid #2a2b3d; border-radius: 4px;
                          padding: 8px 16px; color: #a9b1d6; }
            QPushButton:hover { background: #2a2b3d; color: #7aa2f7; }
            QPushButton#primary { background: #3d59a1; color: #ffffff; border: none; }
            QPushButton#primary:hover { background: #4a6cbf; }
            QListWidget { background: #1a1b2e; border: 1px solid #2a2b3d; border-radius: 4px; padding: 4px; }
            QListWidget::item:selected { background: #3d59a1; color: #ffffff; border-radius: 3px; }
            QLabel#section { color: #7aa2f7; font-size: 12px; font-weight: bold;
                             padding: 8px 0 4px 0; letter-spacing: 1px; }
            QLabel#hint { color: #565f89; font-size: 11px; }
        """)

        self.settings = load_settings()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Title
        title = QLabel("⚡ INTELLIGENCE SETTINGS")
        title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #7aa2f7; margin-bottom: 8px;")
        layout.addWidget(title)

        node_label = QLabel(f"Node: {self._get_node_identity()}")
        node_label.setObjectName("hint")
        layout.addWidget(node_label)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._build_ollama_tab(), "🖥  Local Ollama")
        tabs.addTab(self._build_openrouter_tab(), "🌐  OpenRouter")
        tabs.addTab(self._build_active_tab(), "⚡  Active Engine")
        layout.addWidget(tabs)

        # Save
        save_btn = QPushButton("SAVE SETTINGS")
        save_btn.setObjectName("primary")
        save_btn.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _get_node_identity(self):
        try:
            sys_dir = os.path.join(REPO_ROOT, "System")
            if sys_dir not in sys.path:
                sys.path.insert(0, sys_dir)
            from silicon_serial import read_apple_serial
            serial = read_apple_serial()
            registry = {"GTH4921YP3": "ALICE_M5 — Mac Studio", "C07FL0JAQ6NV": "M1THER — Mac Mini"}
            return f"{registry.get(serial, 'UNKNOWN')} ({serial})"
        except Exception:
            return "UNKNOWN NODE"

    # ── Ollama Tab ────────────────────────────────────────────
    def _build_ollama_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        lbl = QLabel("LOCAL OLLAMA MODELS")
        lbl.setObjectName("section")
        lay.addWidget(lbl)

        hint = QLabel("Models installed on this node's silicon. Inference stays local — no cloud.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.ollama_list = QListWidget()
        self.ollama_list.setMinimumHeight(160)
        lay.addWidget(self.ollama_list)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton("↻  Refresh")
        self.refresh_btn.clicked.connect(self._refresh_ollama)
        row.addWidget(self.refresh_btn)

        # Llama 4 pull button
        llama4_btn = QPushButton("⬇  Pull Llama 4 Maverick (70B)")
        llama4_btn.setStyleSheet("color: #ff9e64; border-color: #ff9e64;")
        llama4_btn.clicked.connect(self._pull_llama4)
        row.addWidget(llama4_btn)
        lay.addLayout(row)

        self.ollama_selected = QComboBox()
        self.ollama_selected.setPlaceholderText("Select active local model...")
        lay.addWidget(self.ollama_selected)

        lay.addStretch()
        self._refresh_ollama()
        return w

    def _refresh_ollama(self):
        self.refresh_btn.setText("Fetching...")
        self.refresh_btn.setEnabled(False)
        self._fetcher = OllamaFetcher(mode="models")   # strong ref
        self._fetcher.models_ready.connect(self._on_ollama_models)
        self._fetcher.error.connect(self._on_ollama_error)
        self._fetcher.start()

    def _on_ollama_models(self, models):
        self.ollama_list.clear()
        self.ollama_selected.clear()
        for m in models:
            self.ollama_list.addItem(m)
            self.ollama_selected.addItem(m)
        current = self.settings.get("ollama_model", "")
        idx = self.ollama_selected.findText(current)
        if idx >= 0:
            self.ollama_selected.setCurrentIndex(idx)
        self.refresh_btn.setText("↻  Refresh")
        self.refresh_btn.setEnabled(True)

    def _on_ollama_error(self, err):
        self.ollama_list.clear()
        self.ollama_list.addItem(f"[ERROR] Ollama not reachable: {err}")
        self.ollama_list.addItem("Run: ollama serve")
        self.refresh_btn.setText("↻  Refresh")
        self.refresh_btn.setEnabled(True)

    def _pull_llama4(self):
        import subprocess
        QMessageBox.information(self, "Pulling Llama 4",
            "Running: ollama pull meta-llama/llama-4-maverick\n\nThis may take a while depending on your connection.\nCheck terminal for progress.")
        subprocess.Popen(["ollama", "pull", "meta-llama/llama-4-maverick"])

    # ── OpenRouter Tab ────────────────────────────────────────
    def _build_openrouter_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        lbl = QLabel("OPENROUTER API")
        lbl.setObjectName("section")
        lay.addWidget(lbl)

        hint = QLabel("OpenRouter gives access to Llama 4, Claude, Gemini, DeepSeek and more via one API key.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        key_lbl = QLabel("API Key:")
        key_lbl.setObjectName("hint")
        lay.addWidget(key_lbl)

        self.or_key = QLineEdit()
        self.or_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.or_key.setPlaceholderText("sk-or-v1-...")
        self.or_key.setText(self.settings.get("openrouter_key", ""))
        lay.addWidget(self.or_key)

        model_lbl = QLabel("Model:")
        model_lbl.setObjectName("hint")
        lay.addWidget(model_lbl)

        self.or_model = QComboBox()
        for m in OPENROUTER_MODELS:
            self.or_model.addItem(m)
        current_or = self.settings.get("openrouter_model", OPENROUTER_MODELS[0])
        idx = self.or_model.findText(current_or)
        if idx >= 0:
            self.or_model.setCurrentIndex(idx)
        lay.addWidget(self.or_model)

        note = QLabel("⚠  OpenRouter sends messages to external servers. Use only for non-sensitive queries.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        note.setStyleSheet("color: #e0af68; font-size: 11px;")
        lay.addWidget(note)

        lay.addStretch()
        return w

    # ── Active Engine Tab ─────────────────────────────────────
    def _build_active_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        lbl = QLabel("ACTIVE INFERENCE ENGINE")
        lbl.setObjectName("section")
        lay.addWidget(lbl)

        hint = QLabel("Choose which engine the Swarm Voice uses when the Architect sends a message.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["ollama  —  Local silicon (sovereign, offline)", "openrouter  —  Cloud models (Llama 4, Claude, etc.)"])
        current_engine = self.settings.get("active_engine", "ollama")
        self.engine_combo.setCurrentIndex(0 if current_engine == "ollama" else 1)
        lay.addWidget(self.engine_combo)

        status_lbl = QLabel("LOCAL MODELS DETECTED:")
        status_lbl.setObjectName("section")
        lay.addWidget(status_lbl)

        self.active_status = QTextEdit()
        self.active_status.setReadOnly(True)
        self.active_status.setMaximumHeight(120)
        self.active_status.setStyleSheet("background: #1a1b2e; border: 1px solid #2a2b3d; border-radius:4px; color: #9ece6a; font-family: monospace; font-size: 11px;")
        self.active_status.setText("Checking Ollama...")
        lay.addWidget(self.active_status)

        self._check_active_status()
        lay.addStretch()
        return w

    def _check_active_status(self):
        """Non-blocking — runs in QThread. Prevents SIGABRT from blocking Qt main thread."""
        self.active_status.setText("Checking Ollama...")
        self._status_fetcher = OllamaFetcher(mode="status")   # strong ref prevents GC
        self._status_fetcher.status_ready.connect(self._on_status_ready)
        self._status_fetcher.start()

    def _on_status_ready(self, status):
        if "OFFLINE" in status:
            self.active_status.setText(f"Ollama OFFLINE\nRun: ollama serve\n{status}")
        else:
            self.active_status.setText(f"Ollama ONLINE\n{status}")


    # ── Save ──────────────────────────────────────────────────
    def _save(self):
        engine = "ollama" if self.engine_combo.currentIndex() == 0 else "openrouter"
        data = {
            "active_engine":    engine,
            "ollama_model":     self.ollama_selected.currentText(),
            "openrouter_key":   self.or_key.text().strip(),
            "openrouter_model": self.or_model.currentText(),
        }
        save_settings(data)
        QMessageBox.information(self, "Saved",
            f"Settings saved.\nActive engine: {engine}\n"
            f"Model: {data['ollama_model'] if engine == 'ollama' else data['openrouter_model']}")

# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("SIFTA Intelligence Settings")
    w = SettingsWindow()
    w.show()
    sys.exit(app.exec())
