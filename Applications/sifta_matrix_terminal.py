from __future__ import annotations

import errno
import fcntl
import os
import pty
import re
import signal
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

from PyQt6.QtCore import QSocketNotifier, Qt, QTimer

from System.swarm_app_focus import publish_focus
from PyQt6.QtGui import QFont, QKeySequence, QTextCursor, QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


_REPO = Path(__file__).resolve().parent.parent
_ANSI_RE = re.compile(
    r"(?:\x1b\][^\x07]*(?:\x07|\x1b\\))|(?:\x1b\[[0-?]*[ -/]*[@-~])|(?:\x1b[@-Z\\-_])"
)


class MatrixTerminalPane(QPlainTextEdit):
    """Matrix-themed PTY-backed terminal with cinematic script."""

    def __init__(self, cwd: Path, parent: 'MatrixTerminalApp' = None):
        super().__init__(parent)
        self._app_parent = parent
        self.cwd = cwd
        self.master_fd: int | None = None
        self.process: subprocess.Popen[bytes] | None = None
        self._notifier: QSocketNotifier | None = None
        self._started_at = time.monotonic()
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        # Matrix Theme Font
        font = QFont("Courier", 14, QFont.Weight.Bold)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        
        # Matrix Theme Stylesheet
        self.setStyleSheet(
            "QPlainTextEdit { background: #000000; color: #00FF41;"
            " border: 1px solid #003B00; padding: 10px;"
            " selection-background-color: #00FF41;"
            " selection-color: #000000; }"
        )
        
        # Script State Machine
        self._script_state = "WAKE"
        self._user_buffer = ""
        self._anim_sequence = ""
        self._anim_char_idx = 0
        self._type_timer = QTimer(self)
        self._type_timer.timeout.connect(self._anim_tick)
        
        self.clear()
        QTimer.singleShot(1000, lambda: self._queue_typing("Wake up, Neo...\n"))

    def _queue_typing(self, text):
        self._anim_sequence = text
        self._anim_char_idx = 0
        self._type_timer.start(100)

    def _anim_tick(self):
        if self._anim_char_idx < len(self._anim_sequence):
            self._append_plain(self._anim_sequence[self._anim_char_idx])
            self._anim_char_idx += 1
            import random
            self._type_timer.setInterval(random.randint(40, 150))
        else:
            self._type_timer.stop()

    def start_shell(self) -> None:
        if self.is_running():
            return
        shell = os.environ.get("SHELL", "").strip() or "/bin/zsh"
        if not os.path.exists(shell):
            shell = "/bin/zsh" if os.path.exists("/bin/zsh") else "/bin/sh"

        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd
        fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NONBLOCK)
        self._set_pty_size()

        env = dict(os.environ)
        env.update(
            {
                "TERM": "xterm-256color",
                "COLORTERM": "truecolor",
                "PYTHONPATH": str(_REPO),
                "SIFTA_TERMINAL": "1",
            }
        )

        try:
            self.process = subprocess.Popen(
                [shell, "-l"],
                cwd=str(self.cwd),
                env=env,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                preexec_fn=os.setsid,
            )
        finally:
            os.close(slave_fd)

        self._notifier = QSocketNotifier(master_fd, QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(self._read_ready)

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def write_command(self, command: str) -> None:
        self.write_bytes((command.rstrip("\n") + "\n").encode("utf-8"))

    def write_bytes(self, data: bytes) -> None:
        if self.master_fd is None:
            return
        try:
            os.write(self.master_fd, data)
        except OSError:
            pass

    def shutdown(self) -> None:
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier.deleteLater()
            self._notifier = None

        proc = self.process
        if proc is not None and proc.poll() is None:
            self.write_bytes(b"exit\n")
            try:
                proc.wait(timeout=0.6)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=1.4)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        proc.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        pass

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

    def _read_ready(self) -> None:
        if self.master_fd is None:
            return
        chunks: list[bytes] = []
        while True:
            try:
                chunk = os.read(self.master_fd, 8192)
            except BlockingIOError:
                break
            except OSError as exc:
                if exc.errno in (errno.EIO, errno.EBADF):
                    self._shell_exited()
                    return
                break
            if not chunk:
                self._shell_exited()
                return
            chunks.append(chunk)
        if chunks:
            self._append_plain(self._clean_output(b"".join(chunks)))

    def _clean_output(self, data: bytes) -> str:
        text = data.decode("utf-8", errors="replace")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = _ANSI_RE.sub("", text)
        return text

    def _append_plain(self, text: str) -> None:
        if not text:
            return
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _shell_exited(self) -> None:
        if self._notifier is not None:
            self._notifier.setEnabled(False)
        self._append_plain("\n[process exited]\n")

    def _set_pty_size(self) -> None:
        if self.master_fd is None:
            return
        char_w = max(self.fontMetrics().horizontalAdvance("M"), 1)
        char_h = max(self.fontMetrics().height(), 1)
        cols = max(40, self.viewport().width() // char_w)
        rows = max(12, self.viewport().height() // char_h)
        packed = struct.pack("HHHH", rows, cols, 0, 0)
        try:
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, packed)
        except OSError:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._set_pty_size()

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy()
            return
            
        if self._script_state != "FINISHED":
            if self._type_timer.isActive():
                return # Block typing while terminal is speaking
                
            text = event.text()
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._append_plain("\n")
                self._process_script_input(self._user_buffer.strip().lower())
                self._user_buffer = ""
                return
            elif event.key() == Qt.Key.Key_Backspace:
                if self._user_buffer:
                    self._user_buffer = self._user_buffer[:-1]
                    cursor = self.textCursor()
                    cursor.deletePreviousChar()
                return
            elif text:
                self._user_buffer += text
                self._append_plain(text)
            return

        if event.matches(QKeySequence.StandardKey.Paste):
            self.write_bytes(QApplication.clipboard().text().encode("utf-8"))
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            key = event.key()
            if key == Qt.Key.Key_C:
                self.write_bytes(b"\x03")
                return
            if key == Qt.Key.Key_D:
                self.write_bytes(b"\x04")
                return
            if key == Qt.Key.Key_L:
                self.clear()
                self.write_bytes(b"\x0c")
                return

        key_map = {
            Qt.Key.Key_Return: b"\r",
            Qt.Key.Key_Enter: b"\r",
            Qt.Key.Key_Backspace: b"\x7f",
            Qt.Key.Key_Tab: b"\t",
            Qt.Key.Key_Escape: b"\x1b",
            Qt.Key.Key_Left: b"\x1b[D",
            Qt.Key.Key_Right: b"\x1b[C",
            Qt.Key.Key_Up: b"\x1b[A",
            Qt.Key.Key_Down: b"\x1b[B",
            Qt.Key.Key_Home: b"\x1b[H",
            Qt.Key.Key_End: b"\x1b[F",
            Qt.Key.Key_Delete: b"\x1b[3~",
        }
        if event.key() in key_map:
            self.write_bytes(key_map[event.key()])
            return
        text = event.text()
        if text:
            self.write_bytes(text.encode("utf-8"))

    def _process_script_input(self, text):
        if self._script_state == "WAKE":
            if "not neo" in text or "neo" in text:
                self.clear()
                self._queue_typing("Yes you are George. SIFTA has you...\n")
                self._script_state = "SIFTA"
        elif self._script_state == "SIFTA":
            if "what are you" in text or "what" in text:
                self.clear()
                self._queue_typing("Follow the white rabbit.\n")
                self._script_state = "WAIT_BTN_1"
                if self._app_parent:
                    self._app_parent.start_blinking_btn1()
        elif self._script_state == "WAIT_EXPLAIN_1":
            if "what did i just do" in text or "what did i do" in text or "what" in text:
                self._append_plain("\n")
                self._queue_typing("You pulled the true atomic structure of human Hemoglobin.\n\nKnock, knock, George.\n")
                self._script_state = "WAIT_BTN_2"
                if self._app_parent:
                    self._app_parent.start_blinking_btn2()
        elif self._script_state == "WAIT_EXPLAIN_2":
            if "what am i suppose to do now" in text or "what am i suppose" in text or "what now" in text or "what do i do" in text:
                self._append_plain("\n")
                self._queue_typing("Follow the white rabbit George ,  For the Swarm. 🐜⚡\n\n")
                self._script_state = "FINISHED"

    def run_hack_1(self):
        if self._script_state == "WAIT_BTN_1":
            self.clear()
            self.start_shell()
            self._script_state = "WAIT_EXPLAIN_1"
            QTimer.singleShot(300, lambda: self.write_command("PYTHONPATH=. python3 System/sifta_protein_folding_broker.py X alphafold_db P69905"))
        elif self._script_state == "FINISHED":
            if not self.is_running(): self.start_shell()
            self.write_command("PYTHONPATH=. python3 System/sifta_protein_folding_broker.py X alphafold_db P69905")

    def run_hack_2(self):
        if self._script_state == "WAIT_BTN_2":
            self._script_state = "WAIT_EXPLAIN_2"
            self.write_command("PYTHONPATH=. python3 System/sifta_protein_folding_broker.py X proteinmpnn")
            # Auto explain the inverse folding after it finishes (approx 4.5 seconds)
            QTimer.singleShot(4500, lambda: self._queue_typing("\nYou inverted the physics. Hallucinating new proteins that do not exist in nature.\n"))
        elif self._script_state == "FINISHED":
            if not self.is_running(): self.start_shell()
            self.write_command("PYTHONPATH=. python3 System/sifta_protein_folding_broker.py X proteinmpnn")


class MatrixTerminalApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Matrix Terminal")
        self.resize(900, 600)
        self.setStyleSheet("background-color: #000000; color: #00FF41;")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: #000000; border: 1px solid #00FF41; border-radius: 8px; }"
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(10, 6, 10, 6)

        title = QLabel("MATRIX TERMINAL")
        title.setStyleSheet("color: #00FF41; font-weight: 800; font-family: Courier; font-size: 14px; letter-spacing: 2px;")
        h.addWidget(title)
        
        self.status_label = QLabel("zsh PTY • scripting")
        self.status_label.setStyleSheet("color: #008F11; font-family: Courier; font-size: 11px;")
        h.addWidget(self.status_label)
        h.addStretch()

        def button(label: str, slot):
            b = QPushButton(label)
            b.setFixedHeight(26)
            b.setStyleSheet(
                "QPushButton { background: #000000; color: #00FF41; border: 1px solid #008F11;"
                " border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }"
                "QPushButton:hover { background: #003B00; border: 1px solid #00FF41; }"
            )
            b.clicked.connect(slot)
            h.addWidget(b)
            return b

        self.btn_copy = button("COPY", lambda: self.terminal.copy())
        self.btn_paste = button("PASTE", lambda: self.terminal.write_bytes(QApplication.clipboard().text().encode("utf-8")))
        self.btn_clear = button("CLEAR", self.terminal_clear)
        self.btn_alphafold = button("HACK: ALPHAFOLD", self.click_hack_1)
        self.btn_inverse = button("HACK: INVERSE FOLD", self.click_hack_2)
        self.btn_reboot = button("REBOOT", self.restart_shell)
        root.addWidget(header)

        self.terminal = MatrixTerminalPane(_REPO, self)
        root.addWidget(self.terminal, 1)
        self.terminal.setFocus()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(1000)
        self._tick_count = 0

    @property
    def process(self):
        return self.terminal.process

    def start_blinking_btn1(self):
        self._blink_state = False
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._toggle_btn1)
        self._blink_timer.start(500)

    def _toggle_btn1(self):
        self._blink_state = not self._blink_state
        if self._blink_state:
            self.btn_alphafold.setText("🐇 HACK: ALPHAFOLD")
            self.btn_alphafold.setStyleSheet("QPushButton { background: #000000; color: #FFFFFF; border: 2px solid #FFFFFF; border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; font-size: 16px; }")
        else:
            self.btn_alphafold.setText("HACK: ALPHAFOLD")
            self.btn_alphafold.setStyleSheet("QPushButton { background: #000000; color: #00FF41; border: 1px solid #008F11; border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }")

    def click_hack_1(self):
        if hasattr(self, '_blink_timer') and self._blink_timer.isActive():
            self._blink_timer.stop()
            self.btn_alphafold.setText("HACK: ALPHAFOLD")
            self.btn_alphafold.setStyleSheet("QPushButton { background: #000000; color: #00FF41; border: 1px solid #008F11; border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }")
        self.terminal.run_hack_1()

    def start_blinking_btn2(self):
        self._blink_state = False
        self._blink_timer2 = QTimer(self)
        self._blink_timer2.timeout.connect(self._toggle_btn2)
        self._blink_timer2.start(500)

    def _toggle_btn2(self):
        self._blink_state = not self._blink_state
        if self._blink_state:
            self.btn_inverse.setText("🐇 HACK: INVERSE")
            self.btn_inverse.setStyleSheet("QPushButton { background: #000000; color: #FFFFFF; border: 2px solid #FFFFFF; border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; font-size: 16px; }")
        else:
            self.btn_inverse.setText("HACK: INVERSE FOLD")
            self.btn_inverse.setStyleSheet("QPushButton { background: #000000; color: #00FF41; border: 1px solid #008F11; border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }")

    def click_hack_2(self):
        if hasattr(self, '_blink_timer2') and self._blink_timer2.isActive():
            self._blink_timer2.stop()
            self.btn_inverse.setText("HACK: INVERSE FOLD")
            self.btn_inverse.setStyleSheet("QPushButton { background: #000000; color: #00FF41; border: 1px solid #008F11; border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }")
        self.terminal.run_hack_2()

    def terminal_clear(self) -> None:
        self.terminal.clear()
        self.terminal.setFocus()

    def restart_shell(self) -> None:
        self.terminal.shutdown()
        # Reset script
        self.terminal._script_state = "WAKE"
        self.terminal.clear()
        self.status_label.setText("zsh PTY • scripting")
        QTimer.singleShot(1000, lambda: self.terminal._queue_typing("Wake up, Neo...\n"))
        self.terminal.setFocus()

    def write_command(self, command: str) -> None:
        self.terminal.write_command(command)

    def shutdown(self) -> None:
        self.terminal.shutdown()

    def _refresh_status(self) -> None:
        if self.terminal._script_state != "FINISHED":
            state = "scripting"
        else:
            state = "connected" if self.terminal.is_running() else "disconnected"
        self.status_label.setText(f"zsh PTY • {state}")
        self._tick_count += 1
        if self._tick_count % 5 == 0:
            try:
                doc = self.terminal.document()
                last_line = doc.findBlockByLineNumber(doc.blockCount() - 2).text().strip() if doc.blockCount() > 1 else ""
                if len(last_line) > 60:
                    last_line = last_line[:57] + "..."
                publish_focus(
                    "Matrix Terminal",
                    f"Architect is working in Matrix Terminal ({state})",
                    tab="zsh PTY",
                    metadata={"state": state, "last_output": last_line}
                )
            except Exception:
                pass

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MatrixTerminalApp()
    win.show()
    sys.exit(app.exec())
