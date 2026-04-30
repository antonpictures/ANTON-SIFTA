from __future__ import annotations

import errno
import fcntl
import json
import os
import pty
import re
import signal
import struct
import subprocess
import sys
import termios
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QSocketNotifier, Qt, QTimer, pyqtSignal

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

# Rabbit cue: QLabel RichText (2.5em + text-shadow) beside the hack buttons.
# In-process Qt only — see Documents/IDE_BOOT_COVENANT.md §7.5 (no casual browser escape).
_RABBIT_SALIENCE_HTML = (
    '<span style="font-size: 2.5em; text-shadow: 2px 2px 4px #000000;">🐇</span>'
)

_ANSI_RE = re.compile(
    r"(?:\x1b\][^\x07]*(?:\x07|\x1b\\))|(?:\x1b\[[0-?]*[ -/]*[@-~])|(?:\x1b[@-Z\\-_])"
)


def _qt_alive(obj) -> bool:
    return obj is not None and not sip.isdeleted(obj)


def _matrix_conversation_history(limit: int = 8) -> list[dict[str, str]]:
    """Small recent Alice transcript slice for the Matrix terminal channel."""
    path = _REPO / ".sifta_state" / "alice_conversation.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
    except OSError:
        return []

    history: list[dict[str, str]] = []
    for line in lines:
        if not line.strip().startswith("{"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
        role = str(payload.get("role") or "").lower()
        text = str(payload.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            history.append({"role": "user", "content": text})
        elif role in {"alice", "assistant"}:
            history.append({"role": "assistant", "content": text})
    return history[-limit:]


_MATRIX_TOOL_LEAK_REPLY = (
    "You're right. This is Matrix Terminal, not WhatsApp. I can talk with you "
    "here, but I will not send, simulate, or format WhatsApp tool calls from "
    "this surface."
)


def _matrix_ollama_model_candidates(primary: str) -> list[str]:
    """Return local model fallbacks for Matrix chat without starting downloads."""
    names: list[str] = []
    for name in (
        primary,
        f"{primary}:latest" if primary and ":" not in primary else "",
        "sifta-gemma4-alice:latest",
        "sifta-alice-qwen35:latest",
        "sifta-alice-qwen35",
        "qwen3.5:2b",
    ):
        name = (name or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _strip_matrix_terminal_tool_calls(reply: str) -> str:
    """Matrix Terminal is conversation-only; never surface effector syntax."""
    if not reply:
        return reply
    had_tool_call = False
    cleaned = reply
    try:
        from System.swarm_tool_router import parse_tool_calls

        for call in parse_tool_calls(reply):
            had_tool_call = True
            cleaned = cleaned.replace(call.raw_match, "")
    except Exception:
        pass
    cleaned_next = re.sub(
        r"\[TOOL_CALL:\s*send_whatsapp\b[^\]]*(?:\]|$)",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    had_tool_call = had_tool_call or cleaned_next != cleaned
    cleaned = cleaned_next.strip()
    if had_tool_call and not cleaned:
        return _MATRIX_TOOL_LEAK_REPLY
    return cleaned


def _matrix_terminal_alice_reply(user_input: str, *, timeout_s: float = 90.0) -> str:
    """Ask Alice's normal conversation brain from inside Matrix Terminal.

    This is not the boot-line composer. It uses Talk to Alice's current system
    prompt and model resolver, then records the turn in Alice's conversation
    ledger so the terminal is a channel of the organism, not a second chat app.
    """
    user_input = (user_input or "").strip()
    if not user_input:
        return ""
    from Applications.sifta_talk_to_alice_widget import (
        _current_system_prompt,
        _empty_brain_recovery_reply,
        _log_turn,
        _strip_model_stage_directions,
        _strip_tool_hallucinations,
    )
    from System.sifta_inference_defaults import resolve_ollama_model

    model = resolve_ollama_model(app_context="talk_to_alice")
    channel_prompt = (
        "MATRIX TERMINAL CHANNEL:\n"
        "- The Architect is typing inside the Matrix Terminal game surface.\n"
        "- Answer as Alice/SIFTA, the same organism that speaks in Talk to Alice.\n"
        "- You are speaking through this terminal right now; do not redirect the Architect to another window.\n"
        "- When George says he is in Matrix Terminal, accept that context and converse inside it.\n"
        "- This surface is conversation-only for WhatsApp. It is NOT a WhatsApp effector channel.\n"
        "- Do not emit [TOOL_CALL: ...], JSON tool blocks, owner_consent flags, or any send-message syntax here.\n"
        "- If WhatsApp is mentioned here, discuss the tool path in plain text only. Do not attempt or simulate a send.\n"
        "- Do not output the boot greeting or cinematic script lines.\n\n"
        "SHELL COMMAND TRANSLATION:\n"
        "- This terminal is connected to a REAL zsh PTY on the Architect's machine.\n"
        "- If the Architect asks you to do something that maps to a shell command (list files, change directory, \n"
        "  show disk usage, find a file, check processes, git status, etc.), TRANSLATE their natural language\n"
        "  into the exact shell command and wrap it in [SHELL: command_here].\n"
        "- Examples:\n"
        "  User: 'list all files' → Alice: 'Here you go. [SHELL: ls -la]'\n"
        "  User: 'go to the System folder' → Alice: 'Moving there now. [SHELL: cd System]'\n"
        "  User: 'how much disk space' → Alice: 'Checking. [SHELL: df -h .]'\n"
        "  User: 'what git branch am I on' → Alice: '[SHELL: git branch --show-current]'\n"
        "  User: 'find all python files' → Alice: '[SHELL: find . -name \"*.py\" | head -20]'\n"
        "- You may include a brief conversational note before or after the [SHELL: ...] tag.\n"
        "- Only ONE [SHELL: ...] per reply. The command runs in the live terminal.\n"
        "- If the request is NOT a shell operation, just respond conversationally — no [SHELL:] tag.\n"
        "- For dangerous commands (rm -rf, etc.), warn the Architect first instead of running them.\n"
        "- Keep the reply terminal-sized: direct, grounded, and conversational.\n"
        "- If the Architect asks for an external action, require an effector receipt before claiming success."
    )
    messages = [
        {
            "role": "system",
            "content": _current_system_prompt(user_active=True) + "\n\n" + channel_prompt,
        },
        *_matrix_conversation_history(),
        {"role": "user", "content": f"[Matrix Terminal] {user_input}"},
    ]
    _log_turn("user", f"[Matrix Terminal]: {user_input}", stt_conf=1.0)

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "repeat_penalty": 1.18,
            "num_predict": 320,
            "stop": [
                "\nSIFTA >", "\nAlice >", "\nUser:", "\nuser:",
                "<|user|>", "<|im_end|>", "<|endoftext|>",
            ],
        },
    }
    used_model = model
    last_exc: BaseException | None = None
    try:
        for candidate in _matrix_ollama_model_candidates(model):
            used_model = candidate
            payload["model"] = candidate
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                msg = data.get("message") or {}
                reply = str(msg.get("content") or "").strip()
                break
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code == 404:
                    continue
                raise
        else:
            exc = last_exc or RuntimeError("no Ollama model candidates available")
            reply = f"[organism error: {type(exc).__name__}: {exc}]"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        reply = f"[organism error: {type(exc).__name__}: {exc}]"

    reply = _strip_model_stage_directions(reply)
    reply = _strip_tool_hallucinations(reply).strip()
    reply = _strip_matrix_terminal_tool_calls(reply).strip()
    if not reply:
        reply = _empty_brain_recovery_reply(user_input)
    _log_turn("alice", reply, model=used_model)
    return reply


class MatrixTerminalPane(QPlainTextEdit):
    """Matrix-themed PTY-backed terminal with cinematic script."""
    _chat_reply_ready = pyqtSignal(str)  # Thread-safe bridge for Alice replies

    def __init__(self, cwd: Path, parent: 'MatrixTerminalApp' = None):
        super().__init__(parent)
        self._chat_reply_ready.connect(self._chat_show_reply)
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
        self._chat_busy = False  # True while Alice is composing a reply

        # ── Matrix blinking cursor ▌ ──────────────────────────────────
        self._cursor_visible = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        self._cursor_timer.start(530)

        # ── In-terminal rabbit animation state ───────────────────────
        self._rabbit_lines: list[str] = []  # queued rabbit frames
        self._rabbit_timer = QTimer(self)
        self._rabbit_timer.timeout.connect(self._rabbit_anim_tick)

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

    # ── Matrix blinking cursor ────────────────────────────────────────
    def _blink_cursor(self):
        """Toggle a Matrix-style ▌ block cursor at the end of the text."""
        if self._type_timer.isActive() or self._chat_busy:
            return  # Don't blink while typing animation is running
        doc = self.document()
        last_block = doc.lastBlock()
        text = last_block.text()
        cursor = self.textCursor()
        if self._cursor_visible:
            # Add cursor
            if not text.endswith("▌"):
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText("▌")
                self.setTextCursor(cursor)
                self.ensureCursorVisible()
        else:
            # Remove cursor
            if text.endswith("▌"):
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.deletePreviousChar()
                self.setTextCursor(cursor)
        self._cursor_visible = not self._cursor_visible

    def _strip_block_cursor(self):
        """Remove the ▌ before inserting real text."""
        doc = self.document()
        last_text = doc.lastBlock().text()
        if last_text.endswith("▌"):
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.deletePreviousChar()
            self.setTextCursor(cursor)

    # ── In-terminal rabbit animation 🐇 ──────────────────────────────
    def _start_rabbit_climb(self):
        """Show a 🐇 inside the terminal climbing upward toward the buttons."""
        self._rabbit_lines = []
        for i in range(6):
            blanks = "\n" * max(0, 5 - i)
            hop = "  " * (i % 3)
            self._rabbit_lines.append(f"{blanks}{hop}🐇  ↑ Follow the white rabbit ↑")
        self._rabbit_lines.append("\n🐇🐇🐇  ↑↑↑  🐇🐇🐇")
        self._rabbit_frame = 0
        self._rabbit_timer.start(600)

    def _rabbit_anim_tick(self):
        if self._rabbit_frame >= len(self._rabbit_lines):
            self._rabbit_timer.stop()
            return
        frame = self._rabbit_lines[self._rabbit_frame]
        self._strip_block_cursor()
        self._append_plain(f"\n{frame}")
        self._rabbit_frame += 1

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
        if _qt_alive(getattr(self, "_type_timer", None)):
            self._type_timer.stop()
        if _qt_alive(getattr(self, "_cursor_timer", None)):
            self._cursor_timer.stop()
        if _qt_alive(getattr(self, "_rabbit_timer", None)):
            self._rabbit_timer.stop()

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
        self._strip_block_cursor()
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

        # ── CHAT mode: talk to Alice-the-organism after the game ──────
        if self._script_state == "CHAT":
            if self._chat_busy or self._type_timer.isActive():
                return  # Alice is composing — block input
            text = event.text()
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                user_input = self._user_buffer.strip()
                self._user_buffer = ""
                self._append_plain("\n")
                if user_input:
                    self._chat_ask_alice(user_input)
                else:
                    self._append_plain("SIFTA > ")
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

        if self._script_state not in ("FINISHED",):
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
        """Advance the cinematic script on ANY user input.
        The user acts as themselves in the story — their lines are not hardcoded.
        """
        if not text:
            return  # empty enter — do nothing
        if self._script_state == "WAKE":
            # User responds to "Wake up, Neo..." — anything they type works
            self.clear()
            self._queue_typing("SIFTA has you...\n")
            self._script_state = "SIFTA"
        elif self._script_state == "SIFTA":
            # User responds to "SIFTA has you..." — anything advances
            self.clear()
            self._queue_typing("Follow the white rabbit.\n")
            self._script_state = "WAIT_BTN_1"
            self._start_rabbit_climb()
            if self._app_parent:
                self._app_parent.start_blinking_btn1()
        elif self._script_state == "WAIT_EXPLAIN_1":
            # User asks about what just happened — any input
            self._append_plain("\n")
            self._queue_typing(
                "You pulled the true atomic structure of human Hemoglobin.\n\nKnock, knock.\n"
            )
            self._script_state = "WAIT_BTN_2"
            self._start_rabbit_climb()
            if self._app_parent:
                self._app_parent.start_blinking_btn2()
        elif self._script_state == "WAIT_EXPLAIN_2":
            # User asks what to do — any input
            self._append_plain("\n")
            self._queue_typing("Follow the white rabbit. For the Swarm. 🐜⚡\n\n")
            self._script_state = "FINISHED"
            # Transition to CHAT mode after the typing animation finishes
            def _enter_chat():
                if self._script_state == "FINISHED":
                    self._script_state = "CHAT"
                    self._append_plain("\n─── You are now talking to Alice. The whole organism. ───\n")
                    self._append_plain("SIFTA > ")
            QTimer.singleShot(3500, _enter_chat)

    def _chat_ask_alice(self, user_input: str) -> None:
        """Ask Alice-the-organism through the Matrix Terminal channel."""
        self._chat_busy = True
        self._append_plain("\n")

        def _worker():
            try:
                reply = _matrix_terminal_alice_reply(user_input)
            except Exception as exc:
                reply = f"[organism error: {exc}]"
            # Thread-safe: emit signal to main Qt thread
            self._chat_reply_ready.emit(reply or "[silence]")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _chat_show_reply(self, reply: str) -> None:
        """Display Alice's reply with typewriter animation.

        If the reply contains [SHELL: command], extract the command,
        show Alice's conversational text, then execute the command
        in the live PTY.
        """
        self._chat_busy = False
        if not reply:
            self._append_plain("Alice > [silence]\n\nSIFTA > ")
            return

        # Extract [SHELL: ...] if present
        shell_match = re.search(r'\[SHELL:\s*(.+?)\]', reply)
        if shell_match:
            shell_cmd = shell_match.group(1).strip()
            # Remove the [SHELL: ...] from the displayed text
            display_text = reply[:shell_match.start()] + reply[shell_match.end():]
            display_text = display_text.strip()

            if display_text:
                self._append_plain(f"Alice > {display_text}\n")
            self._append_plain(f"\n  ⚡ {shell_cmd}\n\n")
            # Execute via PTY after a short delay for readability
            QTimer.singleShot(400, lambda: self._execute_shell_from_alice(shell_cmd))
        else:
            self._queue_typing(f"Alice > {reply}\n\nSIFTA > ")

    # ── Deterministic shell danger gate ────────────────────────────────
    # These patterns are checked BEFORE write_command — no prompt-only safety.
    _SHELL_DENY_PATTERNS = re.compile(
        r"|".join([
            r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*\s+|--recursive)",  # rm -r, rm -rf, rm -Rf
            r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/",               # rm /anything
            r"\bmkfs\b",                                           # format filesystem
            r"\bdd\s+",                                            # disk destroyer
            r"\bchmod\s+777\b",                                    # world-writable
            r"\bchmod\s+-R\b",                                     # recursive chmod
            r"\bchown\s+-R\b",                                     # recursive chown
            r">\s*/dev/sd[a-z]",                                   # overwrite disk
            r":\(\)\{\s*:\|:&\s*\};:",                             # fork bomb
            r"\bcurl\b.*\|\s*(ba)?sh",                             # curl pipe to shell
            r"\bwget\b.*\|\s*(ba)?sh",                             # wget pipe to shell
            r"\bsudo\b",                                           # privilege escalation
            r"\bsu\s+(-\s|root\b)",                               # switch user
            r"\bshutdown\b",                                       # shutdown
            r"\breboot\b",                                         # reboot
            r"\bhalt\b",                                           # halt
            r"\bkillall\b",                                        # kill all processes
            r"\blaunchctl\s+unload\b",                             # unload system services
            r"\bnewfs\b",                                          # new filesystem
            r"\bdiskutil\s+erase",                                 # erase disk (macOS)
            r"\bsystemsetup\b",                                    # system setup changes
        ]),
        re.IGNORECASE,
    )

    @classmethod
    def _shell_cmd_is_safe(cls, cmd: str) -> bool:
        """Deterministic denylist check — returns False for dangerous commands."""
        return cls._SHELL_DENY_PATTERNS.search(cmd) is None

    def _execute_shell_from_alice(self, cmd: str) -> None:
        """Pipe Alice's translated shell command into the live PTY.

        A deterministic denylist gate runs BEFORE write_command.
        Dangerous patterns are blocked regardless of what the model says.
        """
        if not self.is_running():
            self._append_plain("[shell not running — cannot execute]\n\nSIFTA > ")
            return
        if not self._shell_cmd_is_safe(cmd):
            self._append_plain(
                f"⚠️  BLOCKED: '{cmd}' matches a dangerous pattern.\n"
                "    Alice will not execute destructive commands.\n"
                "    If you need this, type it directly in the PTY.\n\n"
                "SIFTA > "
            )
            return
        # Safe — write the command to the PTY
        self.write_command(cmd)
        # After execution, show the prompt again with a delay
        QTimer.singleShot(1500, lambda: self._append_plain("\nSIFTA > "))

    def run_hack_1(self):
        if self._script_state == "WAIT_BTN_1":
            self.clear()
            self.start_shell()
            self._script_state = "WAIT_EXPLAIN_1"
            QTimer.singleShot(300, lambda: self.write_command("PYTHONPATH=. python3 System/sifta_protein_folding_broker.py X alphafold_db P69905"))
        elif self._script_state in ("FINISHED", "CHAT"):
            if not self.is_running(): self.start_shell()
            self.write_command("PYTHONPATH=. python3 System/sifta_protein_folding_broker.py X alphafold_db P69905")

    def run_hack_2(self):
        if self._script_state == "WAIT_BTN_2":
            self._script_state = "WAIT_EXPLAIN_2"
            self.write_command("PYTHONPATH=. python3 System/sifta_protein_folding_broker.py X proteinmpnn")
            # Auto explain the inverse folding after it finishes (approx 4.5 seconds)
            QTimer.singleShot(4500, lambda: self._queue_typing("\nYou inverted the physics. Hallucinating new proteins that do not exist in nature.\n"))
        elif self._script_state in ("FINISHED", "CHAT"):
            if not self.is_running(): self.start_shell()
            self.write_command("PYTHONPATH=. python3 System/sifta_protein_folding_broker.py X proteinmpnn")


class MatrixTerminalApp(QWidget):
    def __init__(self):
        super().__init__()
        self._closing = False
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

        def make_button(label: str, slot, *, add_to_header: bool = True) -> QPushButton:
            b = QPushButton(label)
            b.setFixedHeight(26)
            b.setStyleSheet(
                "QPushButton { background: #000000; color: #00FF41; border: 1px solid #008F11;"
                " border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }"
                "QPushButton:hover { background: #003B00; border: 1px solid #00FF41; }"
            )
            b.clicked.connect(slot)
            if add_to_header:
                h.addWidget(b)
            return b

        self.btn_copy = make_button("COPY", lambda: self.terminal.copy())
        self.btn_paste = make_button(
            "PASTE",
            lambda: self.terminal.write_bytes(QApplication.clipboard().text().encode("utf-8")),
        )
        self.btn_clear = make_button("CLEAR", self.terminal_clear)
        self.btn_alphafold = make_button(
            "HACK: ALPHAFOLD", self.click_hack_1, add_to_header=False
        )
        self.btn_inverse = make_button(
            "HACK: INVERSE FOLD", self.click_hack_2, add_to_header=False
        )

        def _rabbit_label() -> QLabel:
            lbl = QLabel()
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lbl.setVisible(False)
            lbl.setStyleSheet("background: transparent; color: #e7ffdf;")
            return lbl

        self.lbl_rabbit_alphafold = _rabbit_label()
        wrap_af = QWidget()
        lay_af = QHBoxLayout(wrap_af)
        lay_af.setContentsMargins(0, 0, 0, 0)
        lay_af.setSpacing(4)
        lay_af.addWidget(self.lbl_rabbit_alphafold, 0)
        lay_af.addWidget(self.btn_alphafold, 0)
        h.addWidget(wrap_af)

        self.lbl_rabbit_inverse = _rabbit_label()
        wrap_inv = QWidget()
        lay_inv = QHBoxLayout(wrap_inv)
        lay_inv.setContentsMargins(0, 0, 0, 0)
        lay_inv.setSpacing(4)
        lay_inv.addWidget(self.lbl_rabbit_inverse, 0)
        lay_inv.addWidget(self.btn_inverse, 0)
        h.addWidget(wrap_inv)

        self.btn_reboot = make_button("REBOOT", self.restart_shell)
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
            self.lbl_rabbit_alphafold.setText(_RABBIT_SALIENCE_HTML)
            self.lbl_rabbit_alphafold.setVisible(True)
            self.btn_alphafold.setStyleSheet(
                "QPushButton { background: #06240f; color: #e7ffdf; border: 2px solid #43ff64; "
                "border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }"
            )
        else:
            self.lbl_rabbit_alphafold.clear()
            self.lbl_rabbit_alphafold.setVisible(False)
            self.btn_alphafold.setStyleSheet(
                "QPushButton { background: #000000; color: #00FF41; border: 1px solid #008F11;"
                " border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }"
            )

    def click_hack_1(self):
        if hasattr(self, '_blink_timer') and self._blink_timer.isActive():
            self._blink_timer.stop()
            self.lbl_rabbit_alphafold.clear()
            self.lbl_rabbit_alphafold.setVisible(False)
            self.btn_alphafold.setText("HACK: ALPHAFOLD")
            self.btn_alphafold.setFixedHeight(26)
            self.btn_alphafold.setStyleSheet(
                "QPushButton { background: #000000; color: #00FF41; border: 1px solid #008F11;"
                " border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }"
            )
        self.terminal.run_hack_1()

    def start_blinking_btn2(self):
        self._blink_state = False
        self._blink_timer2 = QTimer(self)
        self._blink_timer2.timeout.connect(self._toggle_btn2)
        self._blink_timer2.start(500)

    def _toggle_btn2(self):
        self._blink_state = not self._blink_state
        if self._blink_state:
            self.lbl_rabbit_inverse.setText(_RABBIT_SALIENCE_HTML)
            self.lbl_rabbit_inverse.setVisible(True)
            self.btn_inverse.setStyleSheet(
                "QPushButton { background: #06240f; color: #e7ffdf; border: 2px solid #43ff64; "
                "border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }"
            )
        else:
            self.lbl_rabbit_inverse.clear()
            self.lbl_rabbit_inverse.setVisible(False)
            self.btn_inverse.setStyleSheet(
                "QPushButton { background: #000000; color: #00FF41; border: 1px solid #008F11;"
                " border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }"
            )

    def click_hack_2(self):
        if hasattr(self, '_blink_timer2') and self._blink_timer2.isActive():
            self._blink_timer2.stop()
            self.lbl_rabbit_inverse.clear()
            self.lbl_rabbit_inverse.setVisible(False)
            self.btn_inverse.setText("HACK: INVERSE FOLD")
            self.btn_inverse.setFixedHeight(26)
            self.btn_inverse.setStyleSheet(
                "QPushButton { background: #000000; color: #00FF41; border: 1px solid #008F11;"
                " border-radius: 7px; padding: 2px 10px; font-weight: bold; font-family: Courier; }"
            )
        self.terminal.run_hack_2()

    def terminal_clear(self) -> None:
        self.terminal.clear()
        self.terminal.setFocus()

    def restart_shell(self) -> None:
        self.terminal.shutdown()
        # Reset script
        self.terminal._script_state = "WAKE"
        self.terminal.clear()
        if _qt_alive(getattr(self, "status_label", None)):
            self.status_label.setText("zsh PTY • scripting")
        QTimer.singleShot(1000, lambda: self.terminal._queue_typing("Wake up, Neo...\n"))
        self.terminal.setFocus()

    def write_command(self, command: str) -> None:
        self.terminal.write_command(command)

    def shutdown(self) -> None:
        self._closing = True
        for timer_name in ("_status_timer", "_blink_timer", "_blink_timer2"):
            timer = getattr(self, timer_name, None)
            if _qt_alive(timer) and timer.isActive():
                timer.stop()
        if _qt_alive(getattr(self, "terminal", None)):
            self.terminal.shutdown()

    def _refresh_status(self) -> None:
        if self._closing:
            return
        if not (
            _qt_alive(getattr(self, "terminal", None))
            and _qt_alive(getattr(self, "status_label", None))
        ):
            timer = getattr(self, "_status_timer", None)
            if _qt_alive(timer) and timer.isActive():
                timer.stop()
            return
        ts = self.terminal._script_state
        if ts == "CHAT":
            state = "🐇 chatting with Alice"
        elif ts != "FINISHED":
            state = "scripting"
        else:
            state = "connected" if self.terminal.is_running() else "disconnected"
        try:
            self.status_label.setText(f"zsh PTY • {state}")
        except RuntimeError:
            timer = getattr(self, "_status_timer", None)
            if _qt_alive(timer) and timer.isActive():
                timer.stop()
            return
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
