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
from PyQt6.QtGui import QFont, QKeySequence, QTextCursor
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


class TerminalPane(QPlainTextEdit):
    """Small PTY-backed terminal surface for Mermaid OS.

    This is intentionally not a full xterm emulator. It gives SIFTA a real
    pseudo-terminal, real zsh job control, direct typing, Ctrl-C, paste, and a
    clean process lifecycle without pulling in another dependency.
    """

    def __init__(self, cwd: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.cwd = cwd
        self.master_fd: int | None = None
        self.process: subprocess.Popen[bytes] | None = None
        self._notifier: QSocketNotifier | None = None
        self._started_at = time.monotonic()
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setFont(QFont("Menlo", 13))
        self.setStyleSheet(
            "QPlainTextEdit { background: #05050a; color: #c0caf5;"
            " border: 1px solid #3b4261; padding: 8px;"
            " selection-background-color: #7aa2f7;"
            " selection-color: #05050a; }"
        )
        self._append_plain("Mermaid OS Terminal — zsh PTY\n")
        self._append_plain(f"cwd: {self.cwd}\n\n")
        self.start_shell()

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


class SiftaTerminalApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Terminal")
        self.resize(820, 540)
        self.setStyleSheet("background-color: #0c0c11; color: #c0caf5;")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: #11131c; border: 1px solid #2f3548; border-radius: 8px; }"
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(10, 6, 10, 6)

        title = QLabel("Terminal")
        title.setStyleSheet("color: #7aa2f7; font-weight: 700; font-size: 13px;")
        h.addWidget(title)
        self.status_label = QLabel("zsh PTY")
        self.status_label.setStyleSheet("color: #565f89; font-family: Menlo; font-size: 11px;")
        h.addWidget(self.status_label)
        h.addStretch()

        def button(label: str, slot):
            b = QPushButton(label)
            b.setFixedHeight(26)
            b.setStyleSheet(
                "QPushButton { background: #24283b; color: #c0caf5; border: 1px solid #414868;"
                " border-radius: 7px; padding: 2px 10px; font-weight: 600; }"
                "QPushButton:hover { background: #313650; }"
            )
            b.clicked.connect(slot)
            h.addWidget(b)

        button("Copy", lambda: self.terminal.copy())
        button("Paste", lambda: self.terminal.write_bytes(QApplication.clipboard().text().encode("utf-8")))
        button("Clear", self.terminal_clear)
        button("Restart", self.restart_shell)
        root.addWidget(header)

        self.terminal = TerminalPane(_REPO, self)
        root.addWidget(self.terminal, 1)
        self.terminal.setFocus()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(1000)

    @property
    def process(self):
        return self.terminal.process

    def terminal_clear(self) -> None:
        self.terminal.clear()
        self.terminal.setFocus()

    def restart_shell(self) -> None:
        self.terminal.shutdown()
        self.terminal.start_shell()
        self.terminal.setFocus()

    def write_command(self, command: str) -> None:
        self.terminal.write_command(command)

    def shutdown(self) -> None:
        self.terminal.shutdown()

    def _refresh_status(self) -> None:
        state = "running" if self.terminal.is_running() else "stopped"
        self.status_label.setText(f"zsh PTY • {state}")

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SiftaTerminalApp()
    win.show()
    sys.exit(app.exec())
