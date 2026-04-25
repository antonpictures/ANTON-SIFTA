import sys
import os
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QLineEdit, QHBoxLayout, QLabel
from PyQt6.QtCore import QProcess, QProcessEnvironment, Qt
from PyQt6.QtGui import QFont, QTextCursor

class SiftaTerminalApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA Terminal")
        self.resize(740, 500)
        self.setStyleSheet("background-color: #0c0c11; color: #9ece6a; font-family: monospace;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("border: 1px solid #3b4261; padding: 5px; background-color: #0a0a0f;")
        font = QFont("Menlo", 13)
        self.chat_display.setFont(font)
        layout.addWidget(self.chat_display)
        
        input_layout = QHBoxLayout()
        prompt_label = QLabel("user@sifta-os $")
        prompt_label.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 14px;")
        input_layout.addWidget(prompt_label)

        self.input_line = QLineEdit()
        self.input_line.setStyleSheet("border: none; background: transparent; color: #c0caf5; font-size: 14px;")
        self.input_line.returnPressed.connect(self._send_command)
        input_layout.addWidget(self.input_line)

        layout.addLayout(input_layout)

        self.process = QProcess()
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", os.getcwd())
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        
        # Start bash shell
        self.process.start("bash", ["-i"])
        self.chat_display.append("> SIFTA OS Terminal session started")
        self.input_line.setFocus()

    def _send_command(self):
        cmd = self.input_line.text()
        if not cmd:
            return
        
        self.chat_display.append(f"<span style='color: #7aa2f7;'>user@sifta-os $</span> {cmd}")
        self.process.write((cmd + "\\n").encode('utf-8'))
        self.input_line.clear()

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace").strip()
        if text:
            self.chat_display.append(text)
            self._scroll_to_bottom()

    def handle_stderr(self):
        data = self.process.readAllStandardError()
        text = bytes(data).decode("utf-8", errors="replace").strip()
        if text:
            self.chat_display.append("<span style='color: #f7768e;'>" + text + "</span>")
            self._scroll_to_bottom()
            
    def _scroll_to_bottom(self):
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
            self.process.waitForFinished(1000)
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SiftaTerminalApp()
    win.show()
    sys.exit(app.exec())
