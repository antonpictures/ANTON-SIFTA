#!/usr/bin/env python3
"""
sifta_control_deck.py
=====================
The primary interactive control dashboard for SIFTA.
Allows researchers to execute and monitor specific architectural
and biological subsystem tests without dropping to the terminal.
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QFrame
)
from PyQt6.QtGui import QFont, QColor, QTextCursor, QIcon
from PyQt6.QtCore import QProcess, Qt, pyqtSlot

# --- Aesthetics derived from Colloid Sim ---
BG_COLOR = "#050508"
PANEL_COLOR = "#08080f"
TEXT_COLOR = "#94a3b8"
ACCENT_COLOR = "#c084fc"
SUCCESS_COLOR = "#22c55e"
DANGER_COLOR = "#ef4444"


class SIFTAControlDeck(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA × SwarmRL — Control Deck")
        self.setGeometry(100, 100, 1000, 650)
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG_COLOR}; }}")
        
        self.process = None
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # --- LEFT PANEL: Test Menu ---
        left_panel = QFrame()
        left_panel.setStyleSheet(f"""
            QFrame {{
                background-color: {PANEL_COLOR};
                border: 1px solid #1a1a2e;
                border-radius: 8px;
            }}
        """)
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(280)
        
        title = QLabel("SIFTA CONTROL DECK")
        title.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ACCENT_COLOR}; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)
        
        subtitle = QLabel("Architectural Verification Suite")
        subtitle.setFont(QFont("Menlo", 9))
        subtitle.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(subtitle)
        
        left_layout.addSpacing(20)

        # Buttons
        self.btn_colloid = self.create_button("1. 'Without a Thought'", "Colloid Physics Simulation")
        left_layout.addWidget(self.btn_colloid)
        
        self.btn_lattice = self.create_button("2. Cryptographic Lattice", "SwarmRL Consensus Merge")
        left_layout.addWidget(self.btn_lattice)
        
        self.btn_swimming = self.create_button("3. Proof of Swimming", "Portable Hardware Identity")
        left_layout.addWidget(self.btn_swimming)
        
        self.btn_jellyfish = self.create_button("4. Jellyfish Trigger", "Autonomic Panic Mode")
        left_layout.addWidget(self.btn_jellyfish)

        # Kill Process Button
        left_layout.addStretch()
        self.btn_kill = QPushButton("⏹ HALT EXECUTION")
        self.btn_kill.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        self.btn_kill.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 12px;
            }}
            QPushButton:hover {{ background-color: #dc2626; }}
            QPushButton:disabled {{ background-color: #451a1a; color: #888; }}
        """)
        self.btn_kill.setEnabled(False)
        left_layout.addWidget(self.btn_kill)
        
        main_layout.addWidget(left_panel)

        # --- RIGHT PANEL: Console Output ---
        right_panel = QFrame()
        right_panel.setStyleSheet(f"""
            QFrame {{
                background-color: {PANEL_COLOR};
                border: 1px solid #1a1a2e;
                border-radius: 8px;
            }}
        """)
        right_layout = QVBoxLayout(right_panel)
        
        console_title = QLabel("TERMINAL OUTPUT STREAM")
        console_title.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        console_title.setStyleSheet(f"color: #60a5fa; border: none;")
        right_layout.addWidget(console_title)
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Menlo", 11))
        self.console.setStyleSheet(f"""
            QTextEdit {{
                background-color: #030305;
                color: {TEXT_COLOR};
                border: 1px solid #1a1a2e;
                padding: 10px;
            }}
        """)
        right_layout.addWidget(self.console)
        
        main_layout.addWidget(right_panel)

        # Connect signals
        self.btn_colloid.clicked.connect(self.run_colloid)
        self.btn_lattice.clicked.connect(self.run_lattice)
        self.btn_swimming.clicked.connect(self.run_swimming)
        self.btn_jellyfish.clicked.connect(self.run_jellyfish)
        self.btn_kill.clicked.connect(self.kill_process)

    def create_button(self, primary_text, sub_text):
        btn = QPushButton()
        layout = QVBoxLayout(btn)
        
        l1 = QLabel(primary_text)
        l1.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        l1.setStyleSheet(f"color: #e2e8f0; background: transparent; border: none;")
        
        l2 = QLabel(sub_text)
        l2.setFont(QFont("Menlo", 9))
        l2.setStyleSheet(f"color: #64748b; background: transparent; border: none;")
        
        layout.addWidget(l1)
        layout.addWidget(l2)
        
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #11111a;
                border: 1px solid #1e1e30;
                border-radius: 4px;
                padding: 8px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: #1a1a2e;
                border: 1px solid {ACCENT_COLOR};
            }}
            QPushButton:disabled {{
                background-color: #0a0a0f;
                border: 1px solid #111;
            }}
        """)
        
        # Return the button to be added manually
        return btn

    def set_buttons_enabled(self, enabled):
        self.btn_colloid.setEnabled(enabled)
        self.btn_lattice.setEnabled(enabled)
        self.btn_swimming.setEnabled(enabled)
        self.btn_jellyfish.setEnabled(enabled)
        self.btn_kill.setEnabled(not enabled)

    def print_to_console(self, text, color=TEXT_COLOR):
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertHtml(f'<span style="color: {color};">{text}</span><br>')
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def start_script(self, script_name, description=None):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            return

        self.console.clear()
        if description:
            self.print_to_console(f"=== {description} ===", ACCENT_COLOR)
            self.print_to_console(f"Executing: {script_name}\n", "#475569")

        self.set_buttons_enabled(False)
        
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)
        
        # Ensure we use the virtual environment's python
        python_path = os.path.join(os.getcwd(), ".venv", "bin", "python")
        if not os.path.exists(python_path):
            python_path = "python3" # Fallback if .venv is broken
            
        # Add unbuffered env var
        env = QProcess.systemEnvironment()
        env.append("PYTHONUNBUFFERED=1")
        self.process.setEnvironment(env)

        self.process.start(python_path, [script_name])

    @pyqtSlot()
    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode()
        for line in data.split('\n'):
            if line:
                color = TEXT_COLOR
                if "[+]" in line or "SUCCESS" in line:
                    color = SUCCESS_COLOR
                elif "WARNING" in line or "Contested" in line:
                    color = "#f59e0b"
                elif "[!]" in line or "FAILURE" in line or "SECURITY BREACH" in line:
                    color = DANGER_COLOR
                # HTML escape
                safe_line = line.replace('<', '&lt;').replace('>', '&gt;')
                self.print_to_console(safe_line, color)

    @pyqtSlot()
    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode()
        for line in data.split('\n'):
            if line:
                safe_line = line.replace('<', '&lt;').replace('>', '&gt;')
                self.print_to_console(safe_line, DANGER_COLOR)

    @pyqtSlot()
    def process_finished(self):
        self.print_to_console("\n=== EXECUTION TERMINATED ===", "#475569")
        self.set_buttons_enabled(True)
        self.process = None

    def kill_process(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.print_to_console("Sending INT signal to process...", DANGER_COLOR)
            self.process.terminate()
            # If it doesn't die gracefully, kill it after 1 second
            QProcess.execute("sleep 1")
            self.process.kill()

    # --- Test Launchers ---
    
    def run_colloid(self):
        # We need to spawn the colloid sim in background, and trigger in process
        self.print_to_console("=== Spawning Colloid Simulation Window ===", ACCENT_COLOR)
        self.print_to_console("The renderer will open in a new window. Firing Stigmergic Trigger here...\n", "#475569")
        
        # Spawn detached renderer so it doesn't block the trigger script
        python_path = os.path.join(os.getcwd(), ".venv", "bin", "python")
        QProcess.startDetached(python_path, ["sifta_colloid_sim.py", "--target", "bureau_of_identity/test_target.py"])
        
        # Run the trigger script in our attached console
        self.start_script("trigger_inference.py")
        
    def run_lattice(self):
        self.start_script("test_bridge_consensus.py", "THE CRYPTOGRAPHIC LATTICE")
        
    def run_swimming(self):
        self.start_script("test_proof_of_swimming.py", "PROOF OF SWIMMING")
        
    def run_jellyfish(self):
        self.start_script("test_jellyfish_trigger.py", "JELLYFISH URGENCY TRIGGER")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Force dark mode palette base
    app.setStyle("Fusion")
    
    window = SIFTAControlDeck()
    window.show()
    sys.exit(app.exec())
