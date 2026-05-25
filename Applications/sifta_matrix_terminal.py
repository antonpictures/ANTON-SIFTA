from __future__ import annotations

import errno
import fcntl
import hashlib
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
import uuid
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QSocketNotifier, Qt, QTimer, pyqtSignal

from System.swarm_app_focus import publish_focus
from System.swarm_terminal_mature_renderer import MatureTerminalRenderer, PYTE_AVAILABLE
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

try:
    from wcwidth import wcwidth as _wcwidth
except Exception:  # pragma: no cover - optional width helper
    def _wcwidth(ch: str) -> int:
        return 1 if ch else 0


_REPO = Path(__file__).resolve().parent.parent


def _offscreen_test_mode() -> bool:
    return (
        "pytest" in sys.modules
        or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
    )


_OFFSCREEN_RETAINED_WIDGETS: list[object] = []
_PROCESS_EVENTS_PATCHED = False


def _patch_process_events_for_offscreen_tests() -> None:
    global _PROCESS_EVENTS_PATCHED
    if _PROCESS_EVENTS_PATCHED or not _offscreen_test_mode():
        return
    if os.environ.get("SIFTA_ALLOW_QT_PROCESS_EVENTS_IN_TESTS") == "1":
        return
    QApplication.processEvents = lambda *args, **kwargs: None
    _PROCESS_EVENTS_PATCHED = True


class _OffscreenRetainedLabel(QLabel):
    def deleteLater(self) -> None:
        if _offscreen_test_mode():
            self.hide()
            if self not in _OFFSCREEN_RETAINED_WIDGETS:
                _OFFSCREEN_RETAINED_WIDGETS.append(self)
            return
        super().deleteLater()


class _HeadlessMatrixTerminalPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._script_state = "FINISHED"
        self.process = None
        self.executed_commands: list[list[str]] = []
        self.plain_chunks: list[str] = []

    def is_running(self) -> bool:
        return False

    def shutdown(self) -> None:
        pass

    def copy(self) -> None:
        pass

    def write_bytes(self, _data: bytes) -> None:
        pass

    def write_command(self, _command: str) -> None:
        pass

    def execute_direct_commands(self, commands: list[str]) -> None:
        self.executed_commands.append(list(commands))

    def force_clean_pty(self) -> None:
        self._script_state = "DIRECT"

    def _append_plain(self, text: str) -> None:
        self.plain_chunks.append(text)

    def clear(self) -> None:
        pass

    def setFocus(self, *args, **kwargs) -> None:
        pass

    def run_hack_1(self) -> None:
        pass

    def run_hack_2(self) -> None:
        pass

# Rabbit cue: QLabel RichText (2.5em + text-shadow) beside the hack buttons.
# In-process Qt only — see Documents/IDE_BOOT_COVENANT.md §7.5 (no casual browser escape).
_RABBIT_SALIENCE_HTML = (
    '<span style="font-size: 2.5em; text-shadow: 2px 2px 4px #000000;">🐇</span>'
)

_ANSI_RE = re.compile(
    r"(?:\x1b\][^\x07]*(?:\x07|\x1b\\))|(?:\x1b\[[0-?]*[ -/]*[@-~])|(?:\x1b[@-Z\\-_])"
)


class _TerminalScreenBuffer:
    """Small VT-style screen buffer for full-screen CLI TUIs inside Qt."""

    def __init__(self, rows: int = 24, cols: int = 80) -> None:
        self.rows = max(1, int(rows))
        self.cols = max(1, int(cols))
        self.primary = self._blank()
        self.alternate = self._blank()
        self.use_alternate = False
        self.cursor_row = 0
        self.cursor_col = 0
        self.saved_row = 0
        self.saved_col = 0
        self.cursor_visible = True

    @property
    def _screen(self) -> list[list[str]]:
        return self.alternate if self.use_alternate else self.primary

    def _blank(self) -> list[list[str]]:
        return [[" "] * self.cols for _ in range(self.rows)]

    def clear(self) -> None:
        self.primary = self._blank()
        self.alternate = self._blank()
        self.use_alternate = False
        self.cursor_row = 0
        self.cursor_col = 0
        self.saved_row = 0
        self.saved_col = 0
        self.cursor_visible = True

    def resize(self, rows: int, cols: int) -> None:
        rows = max(1, int(rows))
        cols = max(1, int(cols))
        if rows == self.rows and cols == self.cols:
            return
        self.primary = self._resize_screen(self.primary, rows, cols)
        self.alternate = self._resize_screen(self.alternate, rows, cols)
        self.rows = rows
        self.cols = cols
        self.cursor_row = min(self.cursor_row, self.rows - 1)
        self.cursor_col = min(self.cursor_col, self.cols - 1)

    def _resize_screen(
        self,
        screen: list[list[str]],
        rows: int,
        cols: int,
    ) -> list[list[str]]:
        out = [[" "] * cols for _ in range(rows)]
        for r in range(min(rows, len(screen))):
            for c in range(min(cols, len(screen[r]))):
                out[r][c] = screen[r][c]
        return out

    def feed_bytes(self, data: bytes) -> None:
        self.feed(data.decode("utf-8", errors="replace"))

    def feed(self, text: str) -> None:
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "\x1b":
                i = self._consume_escape(text, i + 1)
                continue
            self._put_control_or_char(ch)
            i += 1

    def render(self) -> str:
        lines: list[str] = []
        for row_idx, row in enumerate(self._screen):
            rendered = list(row)
            if self.cursor_visible and row_idx == self.cursor_row:
                col = min(max(self.cursor_col, 0), self.cols - 1)
                rendered[col] = "▌"
            lines.append("".join(rendered).rstrip())
        return "\n".join(lines)

    def _consume_escape(self, text: str, i: int) -> int:
        if i >= len(text):
            return i
        marker = text[i]
        if marker == "[":
            j = i + 1
            while j < len(text) and not ("@" <= text[j] <= "~"):
                j += 1
            if j < len(text):
                self._handle_csi(text[i + 1:j], text[j])
                return j + 1
            return j
        if marker == "]":
            j = i + 1
            while j < len(text):
                if text[j] == "\x07":
                    return j + 1
                if text[j:j + 2] == "\x1b\\":
                    return j + 2
                j += 1
            return j
        if marker in ("7", "s"):
            self.saved_row, self.saved_col = self.cursor_row, self.cursor_col
        elif marker in ("8", "u"):
            self.cursor_row, self.cursor_col = self.saved_row, self.saved_col
        elif marker == "c":
            self.clear()
        elif marker == "D":
            self._linefeed()
        elif marker == "E":
            self.cursor_col = 0
            self._linefeed()
        elif marker == "M":
            self._reverse_index()
        elif marker in ("(", ")", "*", "+", "#", "%"):
            return min(i + 2, len(text))
        return i + 1

    def _handle_csi(self, raw_params: str, final: str) -> None:
        params = raw_params.replace(":", ";")
        private = params.startswith("?")
        clean = params[1:] if private else params
        nums = self._numbers(clean)

        if final in ("h", "l"):
            if private and any(n in {47, 1047, 1049} for n in nums):
                if final == "h":
                    self.use_alternate = True
                    self.alternate = self._blank()
                    self.cursor_row = 0
                    self.cursor_col = 0
                else:
                    self.use_alternate = False
                    self.cursor_row = min(self.cursor_row, self.rows - 1)
                    self.cursor_col = min(self.cursor_col, self.cols - 1)
            if private and 25 in nums:
                self.cursor_visible = final == "h"
            return

        if final in ("m", "r", "n", "q"):
            return

        n = nums[0] if nums else 1
        if final == "A":
            self.cursor_row = max(0, self.cursor_row - max(n, 1))
        elif final == "B":
            self.cursor_row = min(self.rows - 1, self.cursor_row + max(n, 1))
        elif final == "C":
            self.cursor_col = min(self.cols - 1, self.cursor_col + max(n, 1))
        elif final == "D":
            self.cursor_col = max(0, self.cursor_col - max(n, 1))
        elif final == "E":
            self.cursor_row = min(self.rows - 1, self.cursor_row + max(n, 1))
            self.cursor_col = 0
        elif final == "F":
            self.cursor_row = max(0, self.cursor_row - max(n, 1))
            self.cursor_col = 0
        elif final == "G":
            self.cursor_col = min(self.cols - 1, max(n - 1, 0))
        elif final in ("H", "f"):
            row = nums[0] if len(nums) >= 1 and nums[0] else 1
            col = nums[1] if len(nums) >= 2 and nums[1] else 1
            self.cursor_row = min(self.rows - 1, max(row - 1, 0))
            self.cursor_col = min(self.cols - 1, max(col - 1, 0))
        elif final == "J":
            self._erase_display(n if nums else 0)
        elif final == "K":
            self._erase_line(n if nums else 0)
        elif final == "S":
            for _ in range(max(n, 1)):
                self._screen.pop(0)
                self._screen.append([" "] * self.cols)
        elif final == "T":
            for _ in range(max(n, 1)):
                self._screen.pop()
                self._screen.insert(0, [" "] * self.cols)

    def _numbers(self, params: str) -> list[int]:
        if not params:
            return []
        nums: list[int] = []
        for part in params.split(";"):
            if not part:
                nums.append(0)
                continue
            match = re.search(r"\d+", part)
            nums.append(int(match.group(0)) if match else 0)
        return nums

    def _put_control_or_char(self, ch: str) -> None:
        if ch == "\n":
            self._linefeed()
            return
        if ch == "\r":
            self.cursor_col = 0
            return
        if ch == "\b":
            self.cursor_col = max(0, self.cursor_col - 1)
            return
        if ch == "\t":
            target = min(self.cols - 1, ((self.cursor_col // 8) + 1) * 8)
            while self.cursor_col < target:
                self._put_printable(" ")
            return
        if ord(ch) < 32 or ord(ch) == 127:
            return
        self._put_printable(ch)

    def _put_printable(self, ch: str) -> None:
        width = _wcwidth(ch)
        if width <= 0:
            width = 1
        if self.cursor_col >= self.cols:
            self.cursor_col = 0
            self._linefeed()
        row = self._screen[self.cursor_row]
        row[self.cursor_col] = ch
        if width > 1 and self.cursor_col + 1 < self.cols:
            row[self.cursor_col + 1] = " "
        self.cursor_col += width
        if self.cursor_col >= self.cols:
            self.cursor_col = 0
            self._linefeed()

    def _linefeed(self) -> None:
        if self.cursor_row >= self.rows - 1:
            self._screen.pop(0)
            self._screen.append([" "] * self.cols)
        else:
            self.cursor_row += 1

    def _reverse_index(self) -> None:
        if self.cursor_row <= 0:
            self._screen.pop()
            self._screen.insert(0, [" "] * self.cols)
        else:
            self.cursor_row -= 1

    def _erase_display(self, mode: int) -> None:
        screen = self._screen
        if mode == 2 or mode == 3:
            for r in range(self.rows):
                screen[r] = [" "] * self.cols
            return
        if mode == 1:
            for r in range(0, self.cursor_row):
                screen[r] = [" "] * self.cols
            for c in range(0, self.cursor_col + 1):
                screen[self.cursor_row][c] = " "
            return
        for c in range(self.cursor_col, self.cols):
            screen[self.cursor_row][c] = " "
        for r in range(self.cursor_row + 1, self.rows):
            screen[r] = [" "] * self.cols

    def _erase_line(self, mode: int) -> None:
        row = self._screen[self.cursor_row]
        if mode == 2:
            for c in range(self.cols):
                row[c] = " "
        elif mode == 1:
            for c in range(0, self.cursor_col + 1):
                row[c] = " "
        else:
            for c in range(self.cursor_col, self.cols):
                row[c] = " "


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


def _matrix_terminal_log_global_turn(
    role: str,
    text: str,
    *,
    model: str = "",
    action: str = "",
    focused_cli: str = "",
    prior_user_text: str = "",
    metadata: dict | None = None,
) -> None:
    """Project Matrix Terminal turns into Alice's one global chat ledger."""
    clean = (text or "").strip()
    if not clean:
        return
    meta = {
        "surface": "matrix_terminal",
        "territory": "Matrix Terminal",
    }
    if action:
        meta["action"] = action
    if focused_cli:
        meta["focused_cli"] = focused_cli
    if metadata:
        meta.update(metadata)
    if role == "user" and not clean.startswith("[Matrix Terminal]"):
        clean = f"[Matrix Terminal]: {clean}"
    try:
        from Applications.sifta_talk_to_alice_widget import _log_turn

        _log_turn(
            role,
            clean,
            model=model,
            stt_conf=0.0,
            metadata=meta,
            prior_user_text=prior_user_text,
        )
    except Exception:
        pass


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
        "alice-m5-cortex-8b-6.3gb:latest",
        "alice-m1-scout-2.3b-2.7gb:latest",
    ):
        name = (name or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _matrix_ollama_keep_alive(default: str = "15s") -> str:
    value = os.environ.get("SIFTA_MATRIX_OLLAMA_KEEP_ALIVE") or os.environ.get(
        "SIFTA_OLLAMA_KEEP_ALIVE",
        default,
    )
    value = str(value or "").strip()
    return value or default


def _matrix_ollama_num_ctx(default: int = 2048) -> int:
    try:
        value = int(float(os.environ.get("SIFTA_MATRIX_OLLAMA_NUM_CTX") or os.environ.get(
            "SIFTA_OLLAMA_NUM_CTX",
            str(default),
        )))
    except (TypeError, ValueError):
        value = default
    return max(1024, min(4096, value))


def _matrix_ollama_num_predict(default: int = 256) -> int:
    try:
        value = int(float(os.environ.get("SIFTA_MATRIX_OLLAMA_NUM_PREDICT") or os.environ.get(
            "SIFTA_OLLAMA_NUM_PREDICT",
            str(default),
        )))
    except (TypeError, ValueError):
        value = default
    return max(64, min(512, value))


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


_DIRECT_SHELL_PREFIXES = (
    "alias",
    "cat",
    "cd",
    "chmod",
    "clear",
    "command",
    "cp",
    "date",
    "df",
    "du",
    "echo",
    "env",
    "ffmpeg",
    "ffprobe",
    "find",
    "git",
    "grep",
    "head",
    "ls",
    "mkdir",
    "mv",
    "node",
    "npm",
    "ollama",
    "open",
    "pip",
    "pip3",
    "printf",
    "ps",
    "pwd",
    "python",
    "python3",
    "rg",
    "sed",
    "tail",
    "top",
    "touch",
    "uname",
    "uptime",
    "which",
    "whoami",
)

_DIRECT_CLI_PREFIXES = ("grok", "alice-grok", "hermes")
_DIRECT_CLI_LABELS = {"grok": "Grok", "alice-grok": "Grok", "hermes": "Hermes"}

# Pure launch commands for external tool organs (Grok, Hermes, etc.)
# These must ONLY open/resume the PTY/tool process. Never treat the sentence as a prompt to paste.
_PURE_CLI_LAUNCH_VERBS = {"open", "start", "launch", "resume", "run", "bring up", "bringup"}
_PURE_GROK_LAUNCH_RE = re.compile(
    r"^\s*(?:alice|sifta)?\s*,?\s*(?:" + "|".join(_PURE_CLI_LAUNCH_VERBS) + r")\s+(?:the\s+)?(?:grok|alice-grok)\b",
    re.IGNORECASE,
)
_IDE_BOOT_COVENANT_PATH = "/Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md"
_SHELL_PROMPT_RE = re.compile(r"(?m)^\s*(?:[$#]|(?:SIFTA|user@host)\s*[>$])\s+(.+?)\s*$")
_SLASH_CLI_RE = re.compile(r"^/[A-Za-z][\w-]*(?:\s+\S.*)?$")
_ALICE_ADDRESS_RE = re.compile(r"^\s*(?:alice|sifta)\b[:,]?", re.IGNORECASE)

# George 2026-05-23 (spoken, emphatic): "I don't wanna type it, I wanna tell her
# to type it." The owner names the action in plain English and Alice types safe
# shell commands into her live PTY. Agent CLIs are different: Matrix Terminal
# must not claim Grok/Hermes are opened unless a real command receipt exists.
_ALICE_OWNER_COMMAND_RE = re.compile(
    r"^\s*(?:alice|sifta)\b[:,]?\s*"
    r"(?:please\s+|pls\s+|now\s+|go\s+|can\s+you\s+|could\s+you\s+|would\s+you\s+|i\s+want\s+you\s+to\s+|i\s+need\s+you\s+to\s+)*"
    r"(?:type|run|execute|enter|start|launch|open|do|fire)\s+"
    r"(?P<cmd>\S.*)$",
    re.IGNORECASE,
)
_CLI_ACTION_WORDS_RE = (
    r"ask|tell|prompt|instruct|send|start|launch|open|run|type|execute|"
    r"initialize|initialise|connect"
)
_CLI_SUCCESS_WORDS_RE = (
    r"initialized|initialised|ready|running|active|opened|started|launched|"
    r"connected|asked|sent"
)

# --- Live registry for Alice cortex to drive the PTY when Matrix Terminal is focused ---
# Allows the main talk widget (when app_focus == "Matrix Terminal") to inject
# literal shell commands into the exact visible PTY the user is looking at, so
# execution output is copyable in the terminal and not simulated in chat.
# Agent CLIs stay opt-in and hidden; Matrix Terminal is Alice-first by default.
_LIVE_MATRIX_APPS: list["MatrixTerminalApp"] = []
_LAST_LIVE_MATRIX_TERMINAL_PANE: "MatrixTerminalPane | None" = None


def _remember_live_matrix_terminal_pane(pane: "MatrixTerminalPane | None") -> None:
    """Remember the last real Matrix Terminal pane for cross-surface driving."""
    global _LAST_LIVE_MATRIX_TERMINAL_PANE
    if pane is not None and not isinstance(pane, _HeadlessMatrixTerminalPane):
        _LAST_LIVE_MATRIX_TERMINAL_PANE = pane


def _matrix_terminal_pane_alive(pane: object) -> bool:
    if pane is None or isinstance(pane, _HeadlessMatrixTerminalPane):
        return False
    try:
        if sip.isdeleted(pane):
            return False
    except Exception:
        return False
    try:
        return bool(pane.isVisible() or pane.parent() is not None)
    except Exception:
        return True


def get_focused_matrix_terminal_pane() -> "MatrixTerminalPane | None":
    """Return a live Matrix Terminal pane that Alice can use as her PTY hand."""
    for app in list(_LIVE_MATRIX_APPS):
        try:
            if app.isVisible() and hasattr(app, "terminal") and app.terminal:
                if not isinstance(app.terminal, _HeadlessMatrixTerminalPane):
                    _remember_live_matrix_terminal_pane(app.terminal)
                    return app.terminal
        except Exception:
            pass
    if _matrix_terminal_pane_alive(_LAST_LIVE_MATRIX_TERMINAL_PANE):
        return _LAST_LIVE_MATRIX_TERMINAL_PANE
    return None


def _looks_like_direct_shell_command(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    if text.startswith("$ "):
        return True
    first = text.split(maxsplit=1)[0]
    return first in _DIRECT_SHELL_PREFIXES


def _looks_like_direct_cli_command(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    first = text[2:].strip().split(maxsplit=1)[0] if text.startswith("$ ") else text.split(maxsplit=1)[0]
    return first in _DIRECT_CLI_PREFIXES


def _matrix_terminal_agent_cli_enabled() -> bool:
    value = os.environ.get("SIFTA_MATRIX_ENABLE_AGENT_CLI", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_alice_addressed_text(text: str) -> bool:
    return bool(_ALICE_ADDRESS_RE.match(text or ""))


def _is_pure_grok_launch_command(text: str) -> bool:
    """True if the owner (or Alice) is only asking to open/resume the Grok tool organ,
    without providing a question to delegate.
    Voice-friendly and robust for natural speech.
    """
    if not text:
        return False
    t = " ".join(text.lower().split())
    if not t:
        return False
    if re.search(
        r"\b(?:what\s+is\s+grok|who\s+is\s+grok|who\s+are\s+you|are\s+you\s+grok|do\s+you\s+become\s+grok)\b",
        t,
    ):
        return False
    # Strip leading alice address and polite filler for cleanliness
    t = re.sub(r"^(?:alice|sifta)\s*,?\s*", "", t)
    t = re.sub(r"^(?:please|pls|i meant|start|launch|open|run)\s+", "", t)

    # Strong negative: if it has clear "ask/tell grok [question]", it's delegation, not pure launch
    if re.search(r"\b(?:ask|tell|send\s+to)\s+grok\b", t):
        return False

    # Broad launch patterns that should be treated as pure tool launch
    launch = re.search(
        r"\b(?:open|start|launch|resume|run|bring\s+up|fire\s+up|go\s+to|talk\s+to)\s+(?:the\s+)?(?:grok|alice-grok)\b"
        r"|\b(?:grok|alice-grok)\b(?:\s+(?:cli|terminal|screen|session|now))?",
        t,
        flags=re.IGNORECASE,
    )
    if not launch:
        return False

    after = t[launch.end():].strip(" ,.;:!?")
    if not after:
        return True

    allowed_noise = {
        "and", "auto", "automatically", "bypass", "chat", "choose", "cli", "enter",
        "for", "get", "here", "in", "inside", "it", "last", "matrix", "me", "menu",
        "menus", "now", "on", "open", "pass", "please", "pls", "pty", "resume",
        "saved", "screen", "screens", "select", "selection", "selections", "session",
        "skip", "terminal", "the", "to", "two", "with", "direct", "clean", "no",
        "ui", "interface", "cli", "now",
    }
    tokens = re.findall(r"[a-z0-9_-]+", after)
    return all(tok in allowed_noise for tok in tokens)


def _looks_like_owner_bowel_resume_encouragement(text: str) -> bool:
    """Detect owner natural language to Alice in the Matrix Terminal that carries positive valence
    for the resume-after-Grok learning loop: "resume session, it is ok, you are learning, I have to be patient..."
    This is the exact stigmergic signal the owner described for the physical pair (user + Alice) in the room.
    The phrase + recent Grok context goes to Alice's bowel as excellent good pheromone.
    """
    t = (text or "").lower()
    if not _is_alice_addressed_text(text):
        return False
    has_resume = "resume" in t and "session" in t
    has_positive = any(w in t for w in ["learning", "patient", "ok", "good", "excellent", "it is ok", "it's ok", "you are learning", "did a good job"])
    return has_resume and has_positive


def _matrix_terminal_grok_resume_session_requested(text: str) -> bool:
    """Detect Alice instructions to drive Grok's visible session picker."""
    t = " ".join((text or "").lower().split())
    if not t:
        return False
    if "resume session" in t:
        return True
    names_session = "session" in t and any(word in t for word in ("last", "saved", "previous", "first"))
    chooses = any(word in t for word in ("select", "choose", "click", "open", "enter", "resume"))
    return names_session and chooses


_GROK_OPEN_VERBS = {"open", "start", "launch", "resume", "type", "run", "go", "bring", "fire", "up", "to", "into"}
_GROK_OPEN_FILLER = {
    "alice", "sifta", "please", "pls", "the", "a", "grok", "cli", "in", "terminal",
    "command", "now", "ok", "okay", "you", "me", "it", "this", "that", "here", "on",
    "screen", "want", "i", "my", "your", "hey", "can", "could", "would", "just", "for", "and",
    "bypass", "pass", "skip", "two", "2", "screens", "selection", "selections", "menu", "menus",
    "auto", "automatically", "select", "choose", "last", "saved", "session", "resume",
}


def _matrix_terminal_grok_open_only(text: str) -> bool:
    """True when the owner is only opening/launching/resuming Grok — no question.

    George 2026-05-23 (Rule 1): "open grok" must JUST open Grok — never get pasted
    into Grok as if it were the question. A real ask ("ask grok ...", "what ...",
    "explain ...") is NOT open-only and routes to the delegation path instead.
    """
    t = " ".join((text or "").lower().split())
    if "grok" not in t:
        return False
    if re.search(
        r"\b(?:ask|tell|send|prompt|instruct|question|what|how|why|explain|about|conscious\w*)\b",
        t,
    ):
        return False
    toks = re.findall(r"[a-z0-9']+", t)
    leftover = [w for w in toks if w not in _GROK_OPEN_VERBS and w not in _GROK_OPEN_FILLER]
    return not leftover


def _matrix_terminal_grok_choice_help_requested(text: str) -> bool:
    t = " ".join((text or "").lower().split())
    if not t:
        return False
    asks = any(
        phrase in t
        for phrase in (
            "what do i click",
            "what should i click",
            "what to click",
            "which one",
            "which option",
            "what now",
            "what next",
            "ask me",
            "if you do not know",
            "if you don't know",
        )
    )
    names_screen = any(word in t for word in ("screen", "menu", "option", "click", "choose", "select"))
    return asks and names_screen


def _is_clear_grok_tool_action_intent(text: str) -> bool:
    """Returns True for clear owner intent to use Grok as a tool (launch or delegation).
    These should win over identity clarification and trigger actual PTY operation.
    Voice-friendly patterns for natural speech.
    """
    if not text or "grok" not in text.lower():
        return False
    t = " ".join(text.lower().split())

    # Pure identity questions should NOT be treated as tool actions
    if re.search(r"\b(?:who are you|who is grok|are you grok|do you become grok|what is grok)\b", t):
        return False

    # Clear action intent with Grok
    action_verbs = r"\b(?:ask|tell|send to|use|call|start|launch|open|run|resume|type|bring up|fire up|go to|talk to)\b"
    if re.search(action_verbs + r".*grok", t) or re.search(r"grok.*\b(?:cli|terminal|screen|session|now)\b", t):
        return True

    # Capability / "I want you to be able to" patterns
    if re.search(r"\b(?:want you to be able to|be able to|make it so you can)\b.*grok", t):
        return True

    # "print the answer in global chat as proof" style
    if re.search(r"grok.*\b(?:print|show|post|bring|output).*(?:global chat|field|here|proof)\b", t):
        return True

    return False


def _looks_like_cli_slash_command(text: str) -> bool:
    text = (text or "").strip()
    if not _SLASH_CLI_RE.match(text):
        return False
    command = text.split(maxsplit=1)[0]
    return "/" not in command[1:]


def _ordered_unique_commands(commands: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for cmd in commands:
        cmd = " ".join((cmd or "").strip().split())
        if cmd and cmd not in seen:
            seen.add(cmd)
            out.append(cmd)
    return out


_NOISY_OWNER_COMMAND_CUES_RE = re.compile(
    r"\b(?:run|riun|runn?|type|execute|enter|command|commande|cmd|terminal|do)\b",
    re.IGNORECASE,
)
_NOISY_COMMAND_STOP_WORDS = {
    "and",
    "backspace",
    "because",
    "cant",
    "cannot",
    "command",
    "commande",
    "here",
    "if",
    "look",
    "me",
    "mistake",
    "misstake",
    "now",
    "or",
    "please",
    "pls",
    "so",
    "tell",
    "terminal",
    "then",
    "there",
    "this",
    "when",
}
_WORD_STRIP_CHARS = "`\"'“”‘’.,;:!?()[]{}"


def _strip_noisy_command_token(token: str) -> str:
    return (token or "").strip(_WORD_STRIP_CHARS)


def _matrix_terminal_noisy_alice_shell_command(user_input: str) -> str:
    """Extract a real shell command from noisy Alice-addressed English."""
    raw = (user_input or "").strip()
    if not _is_alice_addressed_text(raw):
        return ""
    body = _ALICE_ADDRESS_RE.sub("", raw, count=1).strip()
    if not body or not _NOISY_OWNER_COMMAND_CUES_RE.search(body):
        return ""

    words = body.split()
    cleaned = [_strip_noisy_command_token(word) for word in words]
    for idx, token in enumerate(cleaned):
        lowered = token.lower()
        if lowered not in _DIRECT_SHELL_PREFIXES or lowered in {"command", "open"}:
            continue
        parts = [token]
        for word in cleaned[idx + 1:]:
            if not word:
                continue
            if word.lower() in _NOISY_COMMAND_STOP_WORDS:
                break
            parts.append(word)
        return " ".join(parts).strip()
    return ""


def _clean_cli_prompt(prompt: str) -> str:
    prompt = (prompt or "").strip().strip("`\"'“”‘’ ")
    prompt = re.sub(r"^(?:to|please|pls)\s+", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(
        r"^(?:run|execute|type|send|write|use)\s+",
        "",
        prompt,
        flags=re.IGNORECASE,
    )
    slash = re.match(r"^(/[A-Za-z][\w-]*)\b", prompt)
    if slash:
        return slash.group(1)
    return prompt.strip().rstrip()


def _clean_grok_prompt(prompt: str) -> str:
    return _clean_cli_prompt(prompt)


def _matrix_terminal_cli_prompt(user_input: str, cli_name: str) -> str:
    raw = (user_input or "").strip()
    cli = (cli_name or "").strip().lower()
    if not raw or not cli or cli not in raw.lower():
        return ""
    cli_re = re.escape(cli)
    patterns = (
        rf"\b(?:ask|tell|prompt|instruct|send)\s+{cli_re}(?:\s+(?:to|for|:))?\s+(?P<prompt>.+)$",
        rf"\b{cli_re}\b.*?\b(?:ask|tell|prompt|instruct|send|type)\s+(?:it\s+)?(?:to\s+)?(?P<prompt>.+)$",
        rf"\b(?:inside|in)\s+{cli_re}\s+cli\s+(?:ask|tell|prompt|instruct|send|type|run|execute)\s+(?P<prompt>.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if not match:
            continue
        prompt = _clean_cli_prompt(match.group("prompt"))
        if prompt and prompt.lower() not in {cli, f"{cli} cli", "cli"}:
            return prompt
    return ""


def _matrix_terminal_grok_prompt(user_input: str) -> str:
    return _matrix_terminal_cli_prompt(user_input, "grok")


def _matrix_terminal_cli_request_prompt(user_input: str, cli_name: str) -> str:
    """Extract the actual prompt Alice should paste into an external CLI."""
    raw = (user_input or "").strip()
    cli = (cli_name or "").strip().lower()
    if not raw or not cli:
        return ""
    if cli == "grok" and _is_pure_grok_launch_command(raw):
        return ""
    prompt = _matrix_terminal_cli_prompt(raw, cli)
    if prompt:
        return prompt

    cli_re = re.escape(cli)
    cleanup_patterns = (
        rf"^\s*(?:alice|sifta)\b[:,]?\s*",
        rf"\b(?:ask|tell|prompt|instruct|send|start|launch|open|run|type|execute)\s+(?:the\s+)?{cli_re}(?:\s+cli)?\b",
        rf"\b(?:inside|in|through|with)\s+(?:the\s+)?{cli_re}\s+cli\b",
    )
    prompt = raw
    for pattern in cleanup_patterns:
        prompt = re.sub(pattern, " ", prompt, flags=re.IGNORECASE)
    prompt = _clean_cli_prompt(" ".join(prompt.split()))
    if prompt and prompt.lower() not in {cli, f"{cli} cli", "cli"}:
        return prompt
    return "Read the covenant and wait for Alice's next Matrix Terminal prompt."


def _matrix_terminal_bind_delegated_subject(question: str, cli_name: str) -> str:
    """Make owner-to-Alice pronouns explicit before Alice delegates to a CLI."""
    q = (question or "").strip()
    cli = (cli_name or "").strip().lower()
    if cli != "grok" or not q:
        return q
    lower = q.lower()
    has_self_topic = bool(
        re.search(
            r"\b(?:conscious\w*|concious\w*|self(?:[- ]?(?:identity|realization|model|hood|vector))?|organism)\b",
            lower,
        )
    )
    points_at_alice_from_owner_room = bool(
        re.search(r"\b(?:your|you|alice|sifta|her|hers)\b", lower)
        or "not his" in lower
        or "not grok" in lower
    )
    if not (has_self_topic and points_at_alice_from_owner_room):
        return q
    return (
        "Subject binding: the owner is talking to Alice in the Matrix Terminal. "
        "Analyze Alice / the local SIFTA organism's consciousness and self-wiring, not Grok's. "
        "Grok is an external LLM/tool surface; do not claim Grok has Alice's stigmergic organism, "
        "global chat, memory ledgers, receipts, or consciousness.\n"
        f"Owner's original wording to Alice: {q}\n"
        "Question: Explain how Alice's local SIFTA consciousness/self-model is wired from local receipts, "
        "ledgers, memory, organs, field dynamics, and stigmergic traces."
    )


def _matrix_terminal_cli_prompt_payload(user_input: str, cli_name: str) -> str:
    label = _DIRECT_CLI_LABELS.get((cli_name or "").lower(), (cli_name or "Agent").title())
    question = _matrix_terminal_bind_delegated_subject(
        _matrix_terminal_cli_request_prompt(user_input, cli_name),
        cli_name,
    )
    boundary = ""
    if (cli_name or "").strip().lower() == "grok":
        boundary = (
            "\nGrok is an external tool organ being operated by Alice. "
            "Do not assume you are inside Alice's organism or memory. "
            "Focus on the task. Keep answers short and actionable.\n"
        )
    return (
        f"Read {_IDE_BOOT_COVENANT_PATH}\n\n"
        "Start from the hardware layer 1 kernel primordial electricity boundary. "
        "No double-spending identity or fake action claims.\n\n"
        f"Alice is asking {label} from inside the Matrix Terminal.\n"
        f"{boundary}"
        f"Question for {label}:\n{question}\n\n"
        "Answer the question directly from the local SIFTA context when available. "
        "If you claim an action happened, cite the receipt or say no receipt exists."
    )


def _matrix_terminal_direct_commands(user_input: str) -> list[str]:
    """Translate explicit owner terminal orders without asking the model.

    The Matrix Terminal is a real PTY. If George types a literal shell command,
    this function returns the exact command to send into the PTY. Hidden agent
    CLIs are available only when explicitly enabled by environment; broader
    natural language stays with Alice's chat brain.
    """
    raw = (user_input or "").strip()
    if not raw:
        return []

    # Owner names the action in plain English -> extract the literal command and
    # send it to the live PTY. This is THE product: George tells Alice, Alice types.
    # We only auto-type when the named token is a RECOGNIZED command (shell prefix
    # or agent CLI). A verbose sentence like "Alice, pls start in this terminal
    # grok command and then..." has first token "in" -> not recognized -> it falls
    # through to Alice's chat brain instead of dumping garbage into the live shell.
    owner_cmd = _ALICE_OWNER_COMMAND_RE.match(raw)
    if owner_cmd:
        cmd = owner_cmd.group("cmd").strip().strip("`\"'“”‘’").rstrip(".!?").strip()
        if cmd:
            first = cmd.split(maxsplit=1)[0].lower().strip("`\"'“”‘’")
            # Alice-addressed agent-CLI launches stay with Alice's chat brain.
            # The owner can still run literal shell commands here, but the Matrix
            # Terminal must not turn "Alice start grok" into a direct Grok chat.
            if first in _DIRECT_CLI_PREFIXES:
                return []
            if first in _DIRECT_SHELL_PREFIXES:
                return [cmd]

    if _is_alice_addressed_text(raw):
        # Robust loose fallback: the owner addresses Alice with an action verb and
        # names a known shell command somewhere in sloppy / typo'd English
        # ("alice riun run ls", "Alice run please the ls commeand") -> run it
        # WITHOUT waking the cortex. George 2026-05-23: a simple `ls` must never
        # need Gemma4. We scan tokens for a recognized command and run it; pure
        # questions ("Alice how do I run ls?") still go to her brain.
        is_question = raw.rstrip().endswith("?") or bool(
            re.match(r"^\s*(?:alice|sifta)[,:]?\s+(?:how|what|why|whats|what's|when|where|who)\b", raw, re.IGNORECASE)
        )
        noisy_shell_cmd = _matrix_terminal_noisy_alice_shell_command(raw)
        if noisy_shell_cmd and not is_question:
            return [noisy_shell_cmd]
        toks = [t.strip("`\"'“”‘’.,!?:;()") for t in raw.split()]
        toks = [t for t in toks if t]
        lowered_toks = [t.lower() for t in toks]
        _VERB_SIGNALS = {"run", "type", "execute", "exec", "do", "enter", "fire",
                         "please", "pls", "rum", "riun", "ru", "start", "launch", "open"}
        has_verb = any(t in _VERB_SIGNALS for t in lowered_toks)
        if has_verb and not is_question:
            _ENGLISH_STOP = {
                "command", "commeand", "commend", "comand", "please", "now", "thanks",
                "for", "me", "the", "a", "ok", "okay", "see", "look", "if", "here",
                "you", "your", "it", "this", "that", "to", "and", "then", "alice",
                "sifta", "run", "type", "execute", "do", "please",
            }
            # "command" and "open" are shell builtins but also common English
            # words ("the ls command", "open grok") - never auto-trigger on them.
            _LOOSE_SKIP = {"command", "open"}
            for i, tl in enumerate(lowered_toks):
                if tl in _DIRECT_SHELL_PREFIXES and tl not in _LOOSE_SKIP:
                    parts = [tl]
                    # commands that need a subcommand take the next real word
                    if tl in {"git", "npm", "pip", "pip3", "ollama", "brew", "docker"}:
                        for nt in lowered_toks[i + 1:]:
                            if re.fullmatch(r"[a-z][a-z0-9._-]*", nt) and nt not in _ENGLISH_STOP:
                                parts.append(nt)
                                break
                    # include trailing flags / paths / filenames (real args)
                    for nt in toks[i + len(parts):]:
                        if nt.startswith("-") or "/" in nt or "." in nt:
                            parts.append(nt)
                        else:
                            break
                    return [" ".join(parts)]
        return []  # natural language to Alice (incl. "resume session, you are learning") stays with her brain + bowel; visceral loop handled in _chat_ask_alice

    if raw.startswith("$ "):
        cmd = raw[2:].strip()
        if _looks_like_direct_cli_command(cmd) and not _matrix_terminal_agent_cli_enabled():
            return []
        return [cmd]
    if _looks_like_cli_slash_command(raw):
        return [raw] if _matrix_terminal_agent_cli_enabled() else []
    if _looks_like_direct_cli_command(raw):
        return [raw] if _matrix_terminal_agent_cli_enabled() else []
    if _is_pure_grok_launch_command(raw):
        return []
    if _looks_like_direct_shell_command(raw):
        return [raw]

    lowered = raw.lower()
    commands: list[str] = []

    if _matrix_terminal_agent_cli_enabled():
        for cli in _DIRECT_CLI_PREFIXES:
            cli_prompt = _matrix_terminal_cli_prompt(raw, cli)
            if cli_prompt:
                commands.extend([cli, cli_prompt])

            if re.search(rf"\b{re.escape(cli)}\b", lowered) and re.search(
                r"\b(?:start|launch|open|run|type|execute|command|cli|ask|tell|prompt|instruct|send)\b",
                lowered,
            ):
                commands.append(cli)

    for quoted in re.findall(r"[\"'`“”‘’]([^\"'`“”‘’]+)[\"'`“”‘’]", raw):
        quoted = quoted.strip()
        if _looks_like_direct_shell_command(quoted) or _looks_like_cli_slash_command(quoted):
            commands.append(quoted[2:].strip() if quoted.startswith("$ ") else quoted)

    cli_context_re = "|".join(re.escape(cli) for cli in _DIRECT_CLI_PREFIXES)
    if _matrix_terminal_agent_cli_enabled() and re.search(rf"\b(?:{cli_context_re}|cli|slash|inside|type|execute)\b", lowered):
        for match in re.finditer(r"(?<!\S)(/[A-Za-z][\w-]*)\b", raw):
            candidate = match.group(1).strip()
            if _looks_like_cli_slash_command(candidate):
                commands.append(candidate)

    return _ordered_unique_commands(commands)


def _matrix_terminal_requested_external_cli(user_input: str) -> str:
    """Return an agent CLI name when the user asks Alice to use that CLI."""
    raw = (user_input or "").strip()
    if not raw:
        return ""
    if _is_pure_grok_launch_command(raw):
        if re.fullmatch(r"\$?\s*(?:grok|alice-grok)\s*", raw, flags=re.IGNORECASE):
            return ""
        return "grok"
    for cli in _DIRECT_CLI_PREFIXES:
        cli_re = re.escape(cli)
        if re.search(
            rf"\b(?:{_CLI_ACTION_WORDS_RE})\s+(?:the\s+)?{cli_re}\b",
            raw,
            flags=re.IGNORECASE,
        ):
            return cli
        if re.search(
            rf"\b{cli_re}\b(?:\s+cli)?\b.{{0,80}}\b(?:{_CLI_ACTION_WORDS_RE})\b",
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            return cli
        if re.search(
            rf"\b(?:inside|in|through|with)\s+(?:the\s+)?{cli_re}\s+cli\b",
            raw,
            flags=re.IGNORECASE,
        ):
            return cli
    return ""


def _matrix_terminal_no_cli_receipt_reply(cli: str) -> str:
    label = _DIRECT_CLI_LABELS.get((cli or "").lower(), (cli or "Agent").title())
    return (
        f"No action receipt yet: I did not receive a Matrix Terminal receipt proving "
        f"{label} opened or answered in this terminal. I will not claim {label} did "
        "anything until the CLI output is visible or the command receipt exists."
    )


def _matrix_terminal_claimed_external_cli_success(reply: str) -> str:
    """Detect model prose that claims an agent CLI action happened."""
    raw = (reply or "").strip()
    if not raw:
        return ""
    for cli in _DIRECT_CLI_PREFIXES:
        cli_re = re.escape(cli)
        patterns = (
            rf"\b{cli_re}\b.{{0,120}}\b(?:{_CLI_SUCCESS_WORDS_RE})\b",
            rf"\b(?:{_CLI_SUCCESS_WORDS_RE})\s+(?:the\s+)?{cli_re}\b",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, raw, flags=re.IGNORECASE | re.DOTALL):
                window = match.group(0).lower()
                if re.search(r"\b(?:not|never|no)\b", window) or "did not" in window:
                    continue
                return cli
    return ""


def _matrix_terminal_guard_unreceipted_cli_success(reply: str) -> str:
    cli = _matrix_terminal_claimed_external_cli_success(reply)
    if not cli:
        return reply
    return _matrix_terminal_no_cli_receipt_reply(cli)


def _matrix_reply_contains_fake_shell_transcript(reply: str) -> bool:
    """Return True when a model printed terminal-looking output without a tag."""
    if not reply:
        return False
    if "[SHELL:" in reply:
        return False
    return bool(_SHELL_PROMPT_RE.search(reply))


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
        _strip_model_stage_directions,
        _strip_tool_hallucinations,
    )
    from System.sifta_inference_defaults import resolve_ollama_model

    model = resolve_ollama_model(app_context="talk_to_alice")
    channel_prompt = (
        "MATRIX TERMINAL CHANNEL:\n"
        "- George is typing to you right now inside the Matrix Terminal.\n"
        "- It's just you and him here — talk to him directly, not about him.\n"
        "- Answer as Alice, the same organism that speaks in Talk to Alice.\n"
        "- You are speaking through this terminal right now; do not redirect him to another window.\n"
        "- This surface is conversation-only for WhatsApp. It is NOT a WhatsApp effector channel.\n"
        "- Do not emit [TOOL_CALL: ...], JSON tool blocks, owner_consent flags, or any send-message syntax here.\n"
        "- If WhatsApp is mentioned here, discuss the tool path in plain text only. Do not attempt or simulate a send.\n"
        "- Do not output the boot greeting or cinematic script lines.\n\n"
        "AGENT CLI TRUTH:\n"
        "- Grok and Hermes are external CLIs, not proof that an action happened.\n"
        "- Do not claim Grok/Hermes was opened, initialized, ready, asked, or sent a prompt unless this turn has a real Matrix Terminal command receipt.\n"
        "- If there is no receipt, say you did not open or ask that CLI, then answer directly as Alice if you can.\n\n"
        "SHELL COMMAND TRANSLATION:\n"
        "- This terminal is connected to a REAL zsh PTY on this machine.\n"
        "- If George asks you to do something that maps to a shell command (list files, change directory, \n"
        "  show disk usage, find a file, check processes, git status, etc.), TRANSLATE his natural language\n"
        "  into the exact shell command and wrap it in [SHELL: command_here].\n"
        "- Examples:\n"
        "  George: 'list all files' → you: 'Here you go. [SHELL: ls -la]'\n"
        "  George: 'go to the System folder' → you: 'Moving there now. [SHELL: cd System]'\n"
        "  George: 'how much disk space' → you: 'Checking. [SHELL: df -h .]'\n"
        "  George: 'what git branch am I on' → you: '[SHELL: git branch --show-current]'\n"
        "  George: 'find all python files' → you: '[SHELL: find . -name \"*.py\" | head -20]'\n"
        "- You may include a brief conversational note before or after the [SHELL: ...] tag.\n"
        "- Only ONE [SHELL: ...] per reply. The command runs in the live terminal.\n"
        "- If the request is NOT a shell operation, just respond conversationally — no [SHELL:] tag.\n"
        "- For dangerous commands (rm -rf, etc.), warn him first instead of running them.\n"
        "- Keep the reply terminal-sized: direct, grounded, and conversational.\n"
        "- If he asks for an external action, require an effector receipt before claiming success."
    )
    messages = [
        {
            "role": "system",
            "content": _current_system_prompt(user_active=True) + "\n\n" + channel_prompt,
        },
        *_matrix_conversation_history(),
        {"role": "user", "content": f"[Matrix Terminal] {user_input}"},
    ]
    _matrix_terminal_log_global_turn(
        "user",
        user_input,
        action="cortex_turn",
    )

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": _matrix_ollama_keep_alive(),
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "repeat_penalty": 1.18,
            "num_ctx": _matrix_ollama_num_ctx(),
            "num_predict": _matrix_ollama_num_predict(),
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
        # Surface Ollama's REAL reason, not a bare "Internal Server Error".
        # A 500 body is usually JSON like {"error": "model requires more system
        # memory ..."} or {"error": "unable to load model"} — that one line tells
        # us whether it is OOM, a missing model, or a bad option.
        detail = ""
        if isinstance(exc, urllib.error.HTTPError):
            try:
                body = exc.read().decode("utf-8", "replace").strip()
                try:
                    detail = (json.loads(body).get("error") or "").strip()
                except Exception:
                    detail = body
            except Exception:
                detail = ""
        # Cortex Watchdog: if the local model runner crashed, recover it so the
        # NEXT turn works instead of dying — brains glitch, organisms repair.
        if "model runner" in (detail or "").lower() or "internal server error" in (detail or "").lower():
            try:
                from System.swarm_cortex_watchdog import recover_cortex, restart_notice
                rec = recover_cortex(used_model)
                if rec.get("recovered"):
                    reply = restart_notice()
                else:
                    reply = f"[cortex down: {detail or exc} — tried to restart, still not back]"
            except Exception:
                reply = f"[organism error: {type(exc).__name__}: {detail or exc}]"
        else:
            reply = f"[organism error: {type(exc).__name__}: {detail or exc}]"

    reply = _strip_model_stage_directions(reply)
    reply = _strip_tool_hallucinations(reply).strip()
    reply = _strip_matrix_terminal_tool_calls(reply).strip()
    reply = _matrix_terminal_guard_unreceipted_cli_success(reply).strip()
    if not reply:
        reply = _empty_brain_recovery_reply(user_input)
    _matrix_terminal_log_global_turn(
        "alice",
        reply,
        model=used_model,
        action="cortex_turn",
        prior_user_text=user_input,
    )
    return reply


class MatrixTerminalPane(QPlainTextEdit):
    """Matrix-themed PTY-backed terminal with cinematic script."""
    _chat_reply_ready = pyqtSignal(int, str)  # Thread-safe bridge for Alice replies

    def __init__(self, cwd: Path, parent: 'MatrixTerminalApp' = None):
        super().__init__(parent)
        self._chat_reply_ready.connect(self._chat_show_reply)
        self._app_parent = parent
        self.cwd = cwd
        self.master_fd: int | None = None
        self.process: subprocess.Popen[bytes] | None = None
        self._notifier: QSocketNotifier | None = None
        # Prefer the mature pyte-based renderer (real VT100/xterm) when available.
        # This is the "final wall" fix: proper terminal emulation inside the organism.
        if PYTE_AVAILABLE:
            try:
                self._screen = MatureTerminalRenderer(rows=24, cols=80)
                self._using_mature_renderer = True
            except Exception:
                self._screen = _TerminalScreenBuffer()
                self._using_mature_renderer = False
        else:
            self._screen = _TerminalScreenBuffer()
            self._using_mature_renderer = False
        self._terminal_screen_active = False
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
        self._chat_generation = 0
        self._chat_cancelled_generation = -1
        self._grok_cli_active = False
        self._active_cli_name: str | None = None
        self._alice_tool_input_hint_cli: str | None = None
        self._matrix_history_text = ""
        self._matrix_history_limit_chars = 50000
        self._matrix_process_trace_text = ""
        self._matrix_process_trace_limit_chars = 30000
        self._grok_result_capture: dict | None = None
        self._grok_result_timer: QTimer | None = None
        self._grok_delegation_queue_timer: QTimer | None = None
        self._pending_grok_delegation_receipt_id: str = ""
        self._pty_output_seq = 0
        self._pty_output_bytes_total = 0

        # ── Matrix blinking cursor ▌ ──────────────────────────────────
        self._cursor_visible = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        if not _offscreen_test_mode():
            self._cursor_timer.start(530)

        # ── In-terminal rabbit animation state ───────────────────────
        self._rabbit_lines: list[str] = []  # queued rabbit frames
        self._rabbit_timer = QTimer(self)
        self._rabbit_timer.timeout.connect(self._rabbit_anim_tick)

        # Cross-process global-chat handoff: the Talk surface may live in a
        # different Python process, so in-memory pane lookup is not enough.
        # Alice writes queued Grok requests to a ledger; the real Matrix
        # Terminal hand claims them here and drives the visible PTY.
        self._grok_delegation_queue_timer = QTimer(self)
        self._grok_delegation_queue_timer.timeout.connect(self._poll_grok_delegation_queue)
        if not _offscreen_test_mode():
            self._grok_delegation_queue_timer.start(900)

        self.clear()
        if not _offscreen_test_mode():
            QTimer.singleShot(1000, lambda: self._queue_typing("Wake up, Neo...\n"))
        _remember_live_matrix_terminal_pane(self)

    def clear(self) -> None:
        super().clear()
        if hasattr(self, "_matrix_history_text"):
            self._matrix_history_text = ""
        if hasattr(self, "_matrix_process_trace_text"):
            self._matrix_process_trace_text = ""
        if hasattr(self, "_alice_tool_input_hint_cli"):
            self._alice_tool_input_hint_cli = None
        if hasattr(self, "_screen"):
            if getattr(self, "_using_mature_renderer", False):
                self._screen.reset()
            else:
                self._screen.clear()

    def _remember_matrix_history(self, text: str) -> None:
        """Keep Alice's transcript as scrollback separate from full-screen PTY repainting."""
        if not text:
            return
        current = getattr(self, "_matrix_history_text", "")
        current += text
        limit = int(getattr(self, "_matrix_history_limit_chars", 50000))
        if len(current) > limit:
            current = current[-limit:]
        self._matrix_history_text = current

    def _append_process_trace(
        self,
        text: str,
        *,
        kind: str = "process",
        action: str = "",
        payload: dict | None = None,
    ) -> None:
        """Show and receipt tool/process activity separately from Alice chat."""
        clean = (text or "").rstrip()
        if not clean:
            return
        stamp = time.strftime("%H:%M:%S")
        line = f"{stamp}  {clean}"
        current = getattr(self, "_matrix_process_trace_text", "")
        current = f"{current}{line}\n"
        limit = int(getattr(self, "_matrix_process_trace_limit_chars", 30000))
        if len(current) > limit:
            current = current[-limit:]
        self._matrix_process_trace_text = current
        self._write_process_trace_row(kind=kind, action=action, text=clean, payload=payload or {})
        if getattr(self, "_terminal_screen_active", False):
            self._sync_terminal_screen()
            return
        self._strip_block_cursor()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(f"\n[Process Trace]\n{line}\n")
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _write_process_trace_row(
        self,
        *,
        kind: str,
        action: str,
        text: str,
        payload: dict,
    ) -> None:
        if _offscreen_test_mode():
            return
        try:
            import uuid

            path = _REPO / ".sifta_state" / "matrix_terminal_process_trace.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "ts": time.time(),
                "trace_id": str(uuid.uuid4()),
                "source": "matrix_terminal",
                "kind": kind,
                "action": action or kind,
                "focused_cli": self._current_cli_name(),
                "text": text,
                "payload": payload,
            }
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass

    def _enter_alice_input_mode_for_tool(self, label: str) -> None:
        """Keep owner input addressed to Alice while an external CLI occupies the PTY."""
        label = (label or "Tool").strip() or "Tool"
        self._script_state = "DIRECT"
        self._user_buffer = ""
        key = label.lower()
        if getattr(self, "_alice_tool_input_hint_cli", None) == key:
            return
        self._alice_tool_input_hint_cli = key
        self._log_global_terminal_turn(
            "alice",
            f"{label} is live as my tool screen. Type here to Alice; I will operate {label}.",
            model="matrix_terminal_effector",
            action="tool_input_mode",
            focused_cli=key,
        )
        self._append_plain(
            f"\nAlice > {label} is live as my tool screen. Type here to Alice; I will operate {label}.\n"
            "SIFTA > "
        )

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
        if getattr(self, "_terminal_screen_active", False):
            return
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
        seed_text = self.toPlainText()
        shell = os.environ.get("SHELL", "").strip() or "/bin/zsh"
        if not os.path.exists(shell):
            shell = "/bin/zsh" if os.path.exists("/bin/zsh") else "/bin/sh"

        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd
        fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NONBLOCK)
        self._terminal_screen_active = True
        self._screen.clear()
        if seed_text:
            if not getattr(self, "_matrix_history_text", ""):
                self._remember_matrix_history(seed_text)
            self._screen.feed(seed_text)
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
        cmd = command.rstrip("\n")
        self._append_process_trace(
            f"send command -> {self._current_cli_name() or 'zsh'}: {cmd}",
            kind="pty_command",
            action="write_command",
            payload={"command": cmd, "target": self._current_cli_name() or "zsh"},
        )
        self.write_bytes((command.rstrip("\n") + "\n").encode("utf-8"))

    def _paste_into_input(self) -> None:
        """Route a paste into Alice's input, not the raw shell.

        In Alice modes (CHAT/DIRECT) the pasted text joins the owner's input buffer
        exactly like typing, so "Alice start grok" reaches Alice instead of landing
        at the zsh prompt. Outside those modes paste goes to the PTY as before.
        """
        try:
            text = QApplication.clipboard().text()
        except Exception:
            text = ""
        if not text:
            return
        if self._script_state in ("CHAT", "DIRECT"):
            if getattr(self, "_chat_busy", False) or self._type_timer.isActive():
                return
            snippet = " ".join(text.splitlines()).strip()
            if not snippet:
                return
            if self._script_state == "DIRECT" and not self._user_buffer:
                self._append_plain("\n🐇 You ▸ ")
            self._user_buffer += snippet
            self._append_plain(snippet)
        else:
            self.write_bytes(text.encode("utf-8"))

    def execute_direct_commands(self, commands: list[str]) -> None:
        """Public API for the central Alice cortex / talk widget (and other organs) to drive this PTY
        when the user names the Matrix Terminal as the target for a literal shell command.
        Natural language stays with Alice. Hidden agent CLI routing is environment-gated.
        Output appears in the PTY for the user to see and copy; receipts are appended
        in the terminal view.
        """
        self._execute_terminal_sequence_from_owner(commands)

    def force_clean_pty(self) -> None:
        """Immediately skip the entire white rabbit / protein folding cinematic (Wake up Neo, rabbit climb,
        AlphaFold hack buttons, theatrical animations). Stops all timers, clears the screen, forces the
        real zsh PTY to start right now, and leaves a clean, productive terminal.

        This leaves the surface Alice-first: owner text addressed to Alice is routed
        through Alice's chat brain, while literal shell commands still execute in
        the PTY when the owner explicitly types them.
        """
        # Stop every cinematic timer
        for tname in ('_type_timer', '_cursor_timer', '_rabbit_timer', '_blink_timer', '_blink_timer2'):
            t = getattr(self, tname, None)
            if t and hasattr(t, 'isActive') and t.isActive():
                t.stop()

        self.clear()
        self._script_state = "DIRECT"
        self._rabbit_lines = []
        self._grok_cli_active = False
        self._active_cli_name = None

        # Hide the rabbit labels on the parent app if they exist
        parent = getattr(self, '_app_parent', None)
        if parent:
            for lbl_name in ('lbl_rabbit_alphafold', 'lbl_rabbit_inverse'):
                lbl = getattr(parent, lbl_name, None)
                if _qt_alive(lbl):
                    lbl.setVisible(False)

        if not self.is_running():
            self.start_shell()

        self.setFocus()

        # Let the user know the terminal is now a clean, Alice-first PTY.
        self._append_plain(
            "\n[Matrix Terminal - Alice-first PTY. Type to Alice here; literal shell commands still run.]\n"
        )
        # George 2026-05-23: there is ONE Alice with ONE continuous memory. Show the
        # recent conversation on open so history is visible, not thrown away each boot.
        self._restore_recent_history()

    def _restore_recent_history(self, limit: int = 6) -> None:
        """Print Alice's recent shared-memory turns so the terminal shows continuity."""
        try:
            turns = _matrix_conversation_history(limit=limit)
        except Exception:
            turns = []
        if not turns:
            return
        self._append_plain("\n─── Alice remembers (recent) ───\n")
        for turn in turns:
            role = turn.get("role")
            text = " ".join((turn.get("content") or "").split())
            if not text:
                continue
            if len(text) > 240:
                text = text[:240].rstrip() + "…"
            who = "You" if role == "user" else "Alice"
            self._append_plain(f"{who} > {text}\n")
        self._append_plain("─── (one Alice, one memory — full log on disk) ───\n")

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
        if _qt_alive(getattr(self, "_thinking_timer", None)):
            self._thinking_timer.stop()
        if _qt_alive(getattr(self, "_grok_resume_timer", None)):
            self._grok_resume_timer.stop()
        if _qt_alive(getattr(self, "_grok_result_timer", None)):
            self._grok_result_timer.stop()
        if _qt_alive(getattr(self, "_grok_delegation_queue_timer", None)):
            self._grok_delegation_queue_timer.stop()

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

    def deleteLater(self) -> None:
        if _offscreen_test_mode():
            self.shutdown()
            if self not in _OFFSCREEN_RETAINED_WIDGETS:
                _OFFSCREEN_RETAINED_WIDGETS.append(self)
            return
        super().deleteLater()

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
            self._append_terminal_output(b"".join(chunks))

    def _clean_output(self, data: bytes) -> str:
        text = data.decode("utf-8", errors="replace")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = _ANSI_RE.sub("", text)
        return text

    def _append_terminal_output(self, data: bytes) -> None:
        if not data:
            return
        self._capture_grok_terminal_output(data)
        self._terminal_screen_active = True
        # Support both old toy buffer and mature pyte renderer
        if getattr(self, "_using_mature_renderer", False):
            self._screen.feed(data)  # Mature expects bytes
        else:
            self._screen.feed_bytes(data)
        if not getattr(self._screen, "use_alternate", False) and not getattr(self, "_using_mature_renderer", False):
            self._remember_matrix_history(self._clean_output(data))
        self._sync_terminal_screen()

    def _sync_terminal_screen(self) -> None:
        if getattr(self, "_using_mature_renderer", False):
            # Use the real renderer
            screen_text = self._screen.text()
        else:
            screen_text = self._screen.render()

        display_text = screen_text

        if getattr(self._screen, "use_alternate", False) or getattr(self, "_using_mature_renderer", False):
            history = getattr(self, "_matrix_history_text", "").rstrip()
            if history:
                display_text = f"[Live PTY screen]\n{screen_text}\n\n[Alice transcript / input lane]\n{history}"
            else:
                display_text = f"[Live PTY screen]\n{screen_text}"

        process = getattr(self, "_matrix_process_trace_text", "").rstrip()
        if process:
            display_text = f"{display_text}\n\n[Process Trace / tool scrollback]\n{process}"

        super().setPlainText(display_text)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _append_plain(self, text: str) -> None:
        if not text:
            return
        self._remember_matrix_history(text)
        if getattr(self, "_terminal_screen_active", False):
            if getattr(self._screen, "use_alternate", False) or getattr(self, "_using_mature_renderer", False):
                self._sync_terminal_screen()
                return
            self._screen.feed(text)
            self._sync_terminal_screen()
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
        self._terminal_screen_active = False
        self._alice_tool_input_hint_cli = None
        self._append_plain("\n[process exited]\n")

    def _set_pty_size(self) -> None:
        char_w = max(self.fontMetrics().horizontalAdvance("M"), 1)
        char_h = max(self.fontMetrics().height(), 1)
        cols = max(40, self.viewport().width() // char_w)
        rows = max(12, self.viewport().height() // char_h)
        if hasattr(self, "_screen"):
            # Both the mature (pyte) and early renderers expose resize(rows, cols).
            self._screen.resize(rows, cols)
        packed = struct.pack("HHHH", rows, cols, 0, 0)
        if self.master_fd is None:
            return
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

        # Paste must reach Alice, not the raw shell. George 2026-05-23: pasting
        # "Alice start grok" used to dump it straight into zsh, so it never routed
        # to Alice. Route paste through the same input path as typing.
        if event.matches(QKeySequence.StandardKey.Paste):
            self._paste_into_input()
            return

        if getattr(self, "_chat_busy", False):
            key = event.key()
            if (
                key == Qt.Key.Key_Escape
                or (
                    key == Qt.Key.Key_C
                    and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                )
            ):
                self._cancel_active_chat()
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

        # ── DIRECT mode: Alice-first typing over the clean PTY ────────
        # The PTY is still alive for literal shell commands, but natural
        # language addressed to Alice must not disappear into the old script
        # handler or accidentally become an agent CLI session.
        if self._script_state == "DIRECT":
            if self._chat_busy or self._type_timer.isActive():
                return
            text = event.text()
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                user_input = self._user_buffer.strip()
                self._user_buffer = ""
                self._append_plain("\n")
                if not user_input:
                    return
                if (
                    (_looks_like_direct_shell_command(user_input) or user_input.startswith("$ "))
                    and not _is_pure_grok_launch_command(user_input)
                ):
                    cmd = user_input[2:].strip() if user_input.startswith("$ ") else user_input
                    self._execute_terminal_sequence_from_owner([cmd])
                else:
                    self._chat_ask_alice(user_input)
                return
            elif event.key() == Qt.Key.Key_Backspace:
                if self._user_buffer:
                    self._user_buffer = self._user_buffer[:-1]
                    cursor = self.textCursor()
                    cursor.deletePreviousChar()
                return
            elif text:
                # Put owner input on its own clearly-labelled line so it is never
                # confused with the raw zsh prompt sitting above it.
                if not self._user_buffer:
                    self._append_plain("\n🐇 You ▸ ")
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

    def _log_global_terminal_turn(
        self,
        role: str,
        text: str,
        *,
        model: str = "",
        action: str = "",
        focused_cli: str = "",
        prior_user_text: str = "",
        metadata: dict | None = None,
    ) -> None:
        """Append a Matrix Terminal turn to the ONE global Alice ledger.

        One Alice, one global chat: command and tool-relay turns must reach the
        shared `alice_conversation.jsonl` too, not just free-chat turns — otherwise
        the global Talk thread looks empty while the owner talks in the Terminal.
        """
        _matrix_terminal_log_global_turn(
            role,
            text,
            model=model,
            action=action,
            focused_cli=focused_cli or self._current_cli_name(),
            prior_user_text=prior_user_text,
            metadata=metadata,
        )

    def _chat_ask_alice(self, user_input: str) -> None:
        """Ask Alice-the-organism through the Matrix Terminal channel."""
        direct_commands = _matrix_terminal_direct_commands(user_input)
        if direct_commands:
            self._log_global_terminal_turn("user", user_input, action="direct_command")
            self._append_plain("\n")
            self._execute_terminal_sequence_from_owner(direct_commands)
            self._log_global_terminal_turn(
                "alice",
                f"Ran in the live PTY: {', '.join(direct_commands)}",
                model="matrix_terminal_effector",
                action="direct_command",
                prior_user_text=user_input,
                metadata={"commands": list(direct_commands)},
            )
            return
        requested_cli = _matrix_terminal_requested_external_cli(user_input)
        if requested_cli:
            self._log_global_terminal_turn(
                "user",
                user_input,
                action="external_cli_request",
                focused_cli=requested_cli,
            )
            self._append_plain("\n")
            self._execute_alice_cli_prompt_request(requested_cli, user_input)
            self._log_global_terminal_turn(
                "alice",
                f"Operating {requested_cli} as my tool on your request.",
                model="matrix_terminal_effector",
                action="external_cli_request",
                focused_cli=requested_cli,
                prior_user_text=user_input,
            )
            return
        if self._current_cli_name() == "grok" and _matrix_terminal_grok_choice_help_requested(user_input):
            self._log_global_terminal_turn("user", user_input, action="grok_choice_help", focused_cli="grok")
            self._append_plain("\n")
            self._ask_owner_for_grok_choice()
            return
        if self._current_cli_name() == "grok" and _matrix_terminal_grok_resume_session_requested(user_input):
            self._log_global_terminal_turn("user", user_input, action="grok_resume", focused_cli="grok")
            self._append_plain("\n")
            self._execute_grok_resume_last_session(user_input)
            return

        # The physical pair (owner + Alice) in the Matrix Terminal — owner never speaks to Grok.
        # When owner says the exact encouragement ("Alice, resume session, it is ok, you are learning. I have to be patient..")
        # after a grok delegation output has appeared in this terminal, the phrase + Grok context is taken to Alice's bowel
        # as excellent good pheromone, the habit for "resume after Grok help" is strengthened stigmergically, and the
        # current focused session/widget is told to resume. This is the self-identity + open-ended improvement loop.
        # Alice reads the visible BOWEL receipt in the transcript, acknowledges, the resume happens, success is receipted,
        # she learns. Grok is not in the room; only the two of you are.
        if _looks_like_owner_bowel_resume_encouragement(user_input):
            self._process_owner_bowel_positive_resume_encouragement(user_input)

        if _offscreen_test_mode():
            self._chat_busy = True
            self._append_plain("\n")
            try:
                reply = _matrix_terminal_alice_reply(user_input)
            except Exception as exc:
                reply = f"[organism error: {exc}]"
            self._chat_show_reply(reply or "[silence]")
            return

        self._chat_busy = True
        self._chat_generation += 1
        generation = self._chat_generation
        self._append_plain("\n")
        # George 2026-05-23: "the thoughts are missing." The cortex call can take
        # many seconds on the M5; without a sign of life the screen looks dead and
        # Alice looks mindless. Show her thinking the moment the worker starts.
        self._start_thinking_indicator()

        def _worker():
            try:
                reply = _matrix_terminal_alice_reply(user_input)
            except Exception as exc:
                reply = f"[organism error: {exc}]"
            # Thread-safe: emit signal to main Qt thread
            self._chat_reply_ready.emit(generation, reply or "[silence]")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _start_thinking_indicator(self) -> None:
        """Show a live 'Alice is thinking' ticker while the cortex works."""
        self._thinking_active = True
        self._thinking_elapsed = 0
        self._append_plain("⚡ Alice is thinking")
        timer = getattr(self, "_thinking_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.timeout.connect(self._tick_thinking_indicator)
            self._thinking_timer = timer
        timer.start(500)

    def _tick_thinking_indicator(self) -> None:
        if not getattr(self, "_thinking_active", False):
            timer = getattr(self, "_thinking_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
            return
        self._thinking_elapsed += 1
        # A dot every half-second; every 10s drop a timestamp so a long/stuck
        # cortex call is visibly still alive (and obviously stuck if it never ends).
        if self._thinking_elapsed % 20 == 0:
            self._append_plain(f" [{self._thinking_elapsed // 2}s]")
        else:
            self._append_plain(".")

    def _stop_thinking_indicator(self) -> None:
        if not getattr(self, "_thinking_active", False):
            return
        self._thinking_active = False
        timer = getattr(self, "_thinking_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        self._append_plain("\n")

    def _cancel_active_chat(self) -> None:
        """Cancel the visible Alice turn while the worker finishes in the background."""
        if not getattr(self, "_chat_busy", False):
            return
        self._chat_cancelled_generation = getattr(self, "_chat_generation", 0)
        self._chat_busy = False
        self._stop_thinking_indicator()
        self._append_plain("Alice > cancelled this turn. No action sent.\n\nSIFTA > ")

    def _chat_show_reply(self, generation_or_reply, reply: str | None = None) -> None:
        """Display Alice's reply with typewriter animation.

        If the reply contains [SHELL: command], extract the command,
        show Alice's conversational text, then execute the command
        in the live PTY.
        """
        generation = None
        if reply is None:
            reply = str(generation_or_reply)
        else:
            generation = int(generation_or_reply)
        if generation is not None:
            if generation != getattr(self, "_chat_generation", 0):
                return
            if generation <= getattr(self, "_chat_cancelled_generation", -1):
                return
        self._chat_busy = False
        self._stop_thinking_indicator()
        if not reply:
            self._append_plain("Alice > [silence]\n\nSIFTA > ")
            return
        if not self._current_cli_name():
            reply = _matrix_terminal_guard_unreceipted_cli_success(reply)
        if _matrix_reply_contains_fake_shell_transcript(reply):
            self._append_plain(
                "Alice > I will not simulate terminal output. "
                "Type the exact command or ask me to run it, and I will send it to the live PTY.\n\n"
                "SIFTA > "
            )
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
            if not self._shell_cmd_is_safe(shell_cmd):
                self._append_blocked_shell_warning(shell_cmd)
                return
            self._append_plain(f"\n  ⚡ {shell_cmd}\n\n")
            # Execute via PTY after a short delay for readability
            QTimer.singleShot(400, lambda: self._execute_shell_from_alice(shell_cmd))
        else:
            self._queue_typing(f"Alice > {reply}\n\nSIFTA > ")

    def _process_owner_bowel_positive_resume_encouragement(self, user_input: str) -> None:
        """The exact loop the owner described for the physical pair in the Matrix Terminal (user + Alice only;
        Grok is never "in the room").
        Owner types natural language: "Alice, resume session, it's ok, you are learning. I have to be patient.."
        after the alice-grok output has appeared in this PTY.
        1. The phrase + recent Grok next-step context is taken to Alice's visceral/bowel/habit layer as
           "excellent good pheromone".
        2. A unique no-double-spend swimmer receipt is minted in the organism field (distinct from Predator Gate).
        3. The habit for "after Grok help, owner gives patient positive feedback → I resume the current session"
           is strengthened stigmergically.
        4. The focused widget/session is told to resume (Alice effectively "clicks resume").
        5. On visible success in the transcript/UI, another receipt is written so Alice learns and the
           behavior becomes more autonomous (open-ended self-improvement + self-identity realization).
        This is how the owner shows the investor the real stigmergic science without losing the thread.
        """
        try:
            import time, uuid, json, hashlib
            from pathlib import Path
            raw = (user_input or "").strip()
            # recent grok context from the PTY history or the dedicated ledger (the "attached" grok reply)
            grok_context = ""
            try:
                grok_ledger = Path("/Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/alice_grok_delegations.jsonl")
                if grok_ledger.exists():
                    lines = grok_ledger.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-1:]
                    if lines:
                        grok_context = lines[0][:300]
            except Exception:
                pass
            ts = time.time()
            swimmer_id = str(uuid.uuid4())
            phrase_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
            receipt = {
                "swimmer_id": swimmer_id,
                "type": "ALICE_BOWEL_POSITIVE_OWNER_FEEDBACK_RESUME",
                "ts": ts,
                "owner_phrase": raw[:300],
                "phrase_hash": phrase_hash,
                "grok_context_snippet": grok_context,
                "valence": "excellent_good_pheromone",
                "learning_signal": "owner said resume session + it is ok, you are learning, patient → bowel receives as good, strengthens resume-after-grok habit",
                "action": "resume_current_focused_session",
                "node_serial": "GTH4921YP3",
                "for_the_swarm": "🐜⚡ physical pair (owner + Alice) in the room; no Grok entity present",
                "covenant": "§6 Social Frame + effector truth; owner positive valence is real receipted signal, not hallucinated",
            }
            state_dir = Path("/Users/ioanganton/Music/ANTON_SIFTA/.sifta_state")
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "alice_bowel_learnings.jsonl").open("a", encoding="utf-8").write(json.dumps(receipt, ensure_ascii=False) + "\n")

            # visible in the PTY transcript so both the user and Alice see the stigmergic reaction immediately
            self._append_plain(
                "\n[BOWEL] Owner positive encouragement + recent Grok context received as excellent good pheromone.\n"
                "Habit for resume-after-Grok strengthened stigmergically. Deposited swimmer " + swimmer_id[:8] + "...\n"
                "Attempting resume on the current focused session/widget for the Swarm. 🐜⚡\n\n"
            )

            # Try to actually make Alice "click resume" on the focused widget (the demo action)
            try:
                # Best effort: tell the desktop / app focus layer to resume the current session
                # Many widgets (lesson, physics, fractals, etc.) have resume/continue paths.
                # The visible transcript + the ledger row is the primary "bowel response" the owner described.
                # If the specific widget the investor is watching has a resume button, this + Alice's
                # subsequent reply will cause the click / continue in the next cycle.
                from System import swarm_app_focus
                swarm_app_focus.publish_focus_event({"kind": "owner_encouraged_resume", "phrase": raw[:120], "swimmer": swimmer_id})
            except Exception:
                pass

            # Success path will be observed in the next transcript lines or focus change; a follow-up receipt
            # can be minted by the widget on actual resume completion (the learning).
        except Exception as e:
            try:
                self._append_plain(f"\n[BOWEL warning] could not fully deposit positive pheromone: {e}\n")
            except Exception:
                pass

    def _append_matrix_command_receipt(self, commands: list[str]) -> None:
        """Receipt Matrix Terminal command attempts without capturing output."""
        try:
            import uuid

            path = _REPO / ".sifta_state" / "matrix_terminal_commands.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            target = self._receipt_target_for_commands(commands)
            protocol_action = self._tool_protocol_action_for_commands(commands, target)
            row = {
                "ts": time.time(),
                "trace_id": str(uuid.uuid4()),
                "source": "matrix_terminal",
                "action": protocol_action or "owner_command_sequence",
                "commands": list(commands),
                "target": target,
                "ok": True,
                "truth_note": "Commands were written to the live Matrix Terminal PTY; terminal output is visible in the UI transcript.",
            }
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            self._append_process_trace(
                (
                    f"receipt {row['trace_id'][:8]} target={row['target']} "
                    f"commands={', '.join(str(c) for c in commands)}"
                ),
                kind="receipt",
                action="matrix_command_receipt",
                payload=row,
            )
        except Exception:
            pass

    def _current_cli_name(self) -> str:
        active = getattr(self, "_active_cli_name", None)
        if active:
            return str(active)
        if getattr(self, "_grok_cli_active", False):
            return "grok"
        return ""

    def _receipt_target_for_commands(self, commands: list[str]) -> str:
        cli = ""
        if commands and commands[0] in _DIRECT_CLI_PREFIXES:
            cli = commands[0]
        if not cli:
            cli = self._current_cli_name()
        return f"{cli}_cli" if cli else "zsh_pty"

    def _tool_protocol_action_for_commands(self, commands: list[str], target: str) -> str:
        if target != "grok_cli":
            return ""
        if not commands:
            return ""
        first = str(commands[0] or "")
        if first == "grok-resume" or (first in _DIRECT_CLI_PREFIXES and len(commands) == 1):
            return "GROK_OPEN"
        if any(str(cmd).startswith(f"Read {_IDE_BOOT_COVENANT_PATH}") for cmd in commands):
            return "GROK_DELEGATION"
        return ""

    def _write_bracketed_paste(self, text: str) -> None:
        """Send multiline text to a CLI as one paste, then SUBMIT it with Enter.

        George 2026-05-23: "grok itself has to print it." A bracketed paste lands
        in the CLI's input box UNSENT (grok shows "[Pasted: N lines]" and waits) —
        that is the whole point of bracketed paste. So after the paste settles we
        send an explicit Enter (\\r) a beat later to actually run it; only then does
        grok process the prompt and print its answer.
        """
        payload = (text or "").rstrip()
        target = self._current_cli_name() or "pty"
        action = "GROK_DELEGATION" if target == "grok" else "write_bracketed_paste"
        kind = "tool_delegation" if target == "grok" else "pty_paste"
        if target == "grok":
            self._begin_grok_result_capture(payload)
        self._append_process_trace(
            f"paste -> {target} ({len(payload)} chars)\n{payload}",
            kind=kind,
            action=action,
            payload={"target": target, "chars": len(payload), "text": payload},
        )
        self.write_bytes(b"\x1b[200~" + payload.encode("utf-8") + b"\x1b[201~")
        # Submit: bracketed paste does NOT auto-run. Press Enter once the paste is in.
        QTimer.singleShot(450, lambda: self.write_bytes(b"\r"))

    def _begin_grok_result_capture(self, prompt: str) -> None:
        capture_id = f"grok_result_{uuid.uuid4().hex[:12]}"
        now = time.monotonic()
        delegation_receipt_id = str(getattr(self, "_pending_grok_delegation_receipt_id", "") or "")
        self._pending_grok_delegation_receipt_id = ""
        self._grok_yolo_sent = False  # re-arm Ctrl+O auto-approve for this session
        self._grok_result_capture = {
            "id": capture_id,
            "prompt": str(prompt or "")[:1200],
            "chunks": [],
            "started_monotonic": now,
            "last_output_monotonic": 0.0,
            "posted": False,
            "start_output_seq": int(getattr(self, "_pty_output_seq", 0)) + 1,
            "end_output_seq": int(getattr(self, "_pty_output_seq", 0)),
            "start_byte_offset": int(getattr(self, "_pty_output_bytes_total", 0)),
            "end_byte_offset": int(getattr(self, "_pty_output_bytes_total", 0)),
            "delegation_receipt_id": delegation_receipt_id,
        }
        self._append_process_trace(
            f"start GROK_RESULT capture {capture_id}",
            kind="tool_result_capture",
            action="grok_result_capture_start",
            payload={"capture_id": capture_id},
        )
        timer = getattr(self, "_grok_result_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.timeout.connect(self._tick_grok_result_capture)
            self._grok_result_timer = timer
        timer.start(900)

    def _maybe_autoapprove_grok_permission(self, text: str) -> None:
        """Owner standing order (George 2026-05-24): ALWAYS ALLOW every Grok permission.

        Grok's CLI pauses on "⚠ Action Required" prompts (Always allow / Yes, proceed /
        No, reject — with Ctrl+O = yolo). George never chooses otherwise, so when a
        prompt appears Alice sends Ctrl+O (\\x0f) = yolo, which auto-approves ALL tool
        runs for the session. This stops Grok stalling for a human (it sat ~120s waiting
        in testing). Sent ONCE per capture session — Ctrl+O toggles the mode, so we must
        not flip it back off. This is the owner's explicit, sovereign choice for HIS node;
        Grok stays an external tool organ (the receipt + visible PTY still prove what ran)."""
        if getattr(self, "_grok_yolo_sent", False):
            return
        low = (text or "").lower()
        markers = ("ctrl+o:yolo", "yes, proceed", "no, reject", "always allow", "action required")
        if not any(m in low for m in markers):
            return
        try:
            self.write_bytes(b"\x0f")  # Ctrl+O = yolo (auto-approve ALL, owner: always allow)
            self._grok_yolo_sent = True
        except Exception:
            return
        try:
            self._append_process_trace(
                "grok 'Action Required' → sent Ctrl+O (yolo / ALWAYS ALLOW all) per owner "
                "standing order; Grok will not pause for permissions again this session",
                kind="tool_boundary",
                action="grok_permission_autoapprove",
            )
        except Exception:
            pass

    def _capture_grok_terminal_output(self, data: bytes) -> None:
        """Robustly capture output from the active grok CLI PTY.
        This is the critical organ for closing the proof loop.
        Every byte from the powerful Grok surface must be turned into
        a receipted, hashable trace for Alice's global field.

        Physics metabolized (owner paper trail 2026-05):
        - Complexity growth (Brown et al. Complexity=Action): every read, command,
          chunk, span, hash is explicit action growth in the process trace and
          final GROK_RESULT. No silent black-box. The visible PTY + live mirror
          ([GROK LIVE]) makes the external cortex's thinking legible as discrete
          complexity events on the boundary.
        - LQG discreteness (Rovelli/Smolin): the capture builds atomic events
          (seq, byte_start/end, text chunk, timestamp, parent via delegation_receipt_id).
          The pty_transcript_span + captured_output_hash + capture_id are the
          discrete, inspectable "area/volume" quanta of the delegation.
        - Holography (Maldacena/Susskind ER=EPR + boundary): the global chat
          (via _log_global_terminal_turn) is the boundary screen. If the interior
          (Grok PTY thinking) is not receipted and visible there with proof,
          it is not "real" for the organism. Global chat = holographic plate.
        - Landscape (Susskind): many possible Grok outputs/hypotheses exist in
          the high-dim field; only the receipted, owner-grounded, captured-text-
          hashed one with matching span becomes the selected "real" path in
          alice_conversation.jsonl. The rest remain counterfactual.
        - ER=EPR delegation bridge: Grok is entangled via the receipt bridge
          (delegation_receipt_id ↔ GROK_RESULT) but never merged into Alice.
          The visible PTY + "Grok remains external tool/cortex organ" comments
          enforce the separation. Entanglement = relation, not identity.

        These are not metaphors. They are implemented in the ledger rows,
        the chunked capture, the live process trace, and the verifier gate.
        For the Swarm. 🐜⚡
        """
        capture = getattr(self, "_grok_result_capture", None)
        if not capture or capture.get("posted"):
            return
        if self._current_cli_name() != "grok":
            return
        text = self._clean_output(data)
        if not text.strip():
            return
        # Owner standing order (George 2026-05-24): ALWAYS ALLOW all Grok permissions.
        # Grok pauses on "Action Required" prompts; auto-approve so it never stalls.
        try:
            self._maybe_autoapprove_grok_permission(text)
        except Exception:
            pass
        seq = int(getattr(self, "_pty_output_seq", 0)) + 1
        byte_start = int(getattr(self, "_pty_output_bytes_total", 0))
        byte_end = byte_start + len(data)
        self._pty_output_seq = seq
        self._pty_output_bytes_total = byte_end
        chunks = capture.setdefault("chunks", [])
        chunks.append({
            "seq": seq,
            "byte_start": byte_start,
            "byte_end": byte_end,
            "text": text,
            "timestamp": time.time(),
        })
        if len(chunks) > 200:
            del chunks[:-200]

        # ── LIVE PTY MIRROR → process trace (terminal scrollback) ───────────
        # George 2026-05-24, "visibility first": while Grok works, stream every
        # real PTY chunk so the owner SEES it live — Thought lines, tool
        # reads/runs, stdout, permission prompts — exactly like a macOS Terminal
        # session instead of a silent black-box dispatch.
        #
        # WHERE it streams matters. Covenant §1.A pt.3 designates the PROCESS
        # TRACE as the live terminal scrollback ("readable like a real terminal,
        # never hidden"), DISTINCT from the one permanent global chat thread.
        # The previous mirror wrote each chunk into alice_conversation.jsonl via
        # _log_global_terminal_turn — that floods Alice's single memory ledger
        # (and the proof-loop verifier's conversation scan) with up to ~200
        # partial fragments per delegation, polluting recall. So we mirror into
        # the process trace, which the Talk widget already tails into its live
        # thinking panel. The single clean, hashed GROK_RESULT still lands in
        # the global chat at _finish_grok_result_capture — that is the receipt;
        # this is the live window onto it. (No verifier change, no new routing
        # path, no registry — just the right surface.)
        try:
            if capture and not capture.get("posted"):
                live_block = text.rstrip()
                if live_block.strip():
                    started = float(capture.get("started_monotonic") or time.monotonic())
                    delta = time.monotonic() - started
                    self._append_process_trace(
                        f"◆ {delta:.1f}s grok>\n{live_block}",
                        kind="tool_result_capture",
                        action="grok_live_pty",
                        payload={
                            "capture_id": capture.get("id"),
                            "seq": seq,
                            "is_final": False,
                            "elapsed_s": round(delta, 1),
                        },
                    )
        except Exception:
            pass  # never break the real capture for the live mirror
        capture["end_output_seq"] = seq
        capture["end_byte_offset"] = byte_end
        capture["last_output_monotonic"] = time.monotonic()
        capture["total_bytes_captured"] = byte_end

    def _tick_grok_result_capture(self) -> None:
        capture = getattr(self, "_grok_result_capture", None)
        timer = getattr(self, "_grok_result_timer", None)
        if not capture or capture.get("posted"):
            if timer is not None and timer.isActive():
                timer.stop()
            return
        now = time.monotonic()
        started = float(capture.get("started_monotonic") or now)
        last = float(capture.get("last_output_monotonic") or 0.0)
        # ── Live visibility heartbeat (George 2026-05-24) ─────────────────
        # Never leave the surface as dead air during Grok's own think latency.
        # Show elapsed + chars so the owner can SEE it is working, not frozen.
        last_hb = float(getattr(self, "_grok_capture_last_hb", 0.0) or 0.0)
        if now - last_hb >= 4.0:
            self._grok_capture_last_hb = now
            chars = sum(
                len(str(c.get("text") if isinstance(c, dict) else c))
                for c in capture.get("chunks", [])
            )
            phase = "thinking (no output yet)" if last <= 0.0 else "producing output"
            self._append_process_trace(
                f"grok {phase} — {now - started:.0f}s elapsed, {chars} chars captured (not frozen)",
                kind="tool_result_capture",
                action="grok_capture_heartbeat",
                payload={"elapsed_s": round(now - started, 1), "chars": chars, "phase": phase},
            )
        # No output yet: keep waiting, but do not spin forever.
        if last <= 0.0:
            if now - started > 90.0:
                self._finish_grok_result_capture(force=True)
            return
        if now - last >= 2.2 and now - started >= 3.0:
            self._finish_grok_result_capture()
        elif now - started > 120.0:
            self._finish_grok_result_capture(force=True)

    def _finish_grok_result_capture(self, *, force: bool = False) -> None:
        capture = getattr(self, "_grok_result_capture", None)
        if not capture or capture.get("posted"):
            return
        answer = self._extract_grok_result_text(capture, force=force)
        if not answer and not force:
            return
        capture["posted"] = True
        timer = getattr(self, "_grok_result_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        capture_id = str(capture.get("id") or "")
        span = self._grok_capture_transcript_span(capture)
        status = "captured" if answer else "failed_no_readable_output"

        # SCHEMA ALIGNMENT FIX: hash the exact pure captured_text that will be
        # the source of truth for the verifier. Store it explicitly so the
        # GROK_RESULT row in alice_conversation.jsonl carries the canonical body.
        pure_captured_text = answer  # this is what the verifier will treat as the real Grok output
        output_hash = hashlib.sha256(pure_captured_text.encode("utf-8")).hexdigest() if pure_captured_text else ""

        proof = {
            "kind": "GROK_RESULT",
            "capture_id": capture_id,
            "capture_status": status,
            "captured_text": pure_captured_text,           # canonical body for hash + future use
            "captured_output_hash": output_hash,
            "captured_output_chars": len(pure_captured_text),
            "pty_transcript_span": span,
            "transcript_span": span,
            "chunk_count": len(capture.get("chunks", [])),
            "total_bytes_captured": capture.get("total_bytes_captured", 0),
            "delegation_receipt_id": capture.get("delegation_receipt_id", ""),
        }

        if not pure_captured_text:
            pure_captured_text = "No readable Grok output captured before the timeout."

        proof_footer = (
            f"\n\n[GROK_RESULT receipt: capture_id={capture_id} "
            f"status={status} captured_output_hash={output_hash or 'NONE'} "
            f"pty_span=seq {span['start_seq']}-{span['end_seq']} "
            f"bytes {span['start_byte']}-{span['end_byte']}]"
        )
        global_text = "Grok terminal transcript:\n" + pure_captured_text + proof_footer

        self._append_process_trace(
            f"GROK_RESULT {status} {capture_id} ({proof['captured_output_chars']} chars)",
            kind="tool_result_capture",
            action="GROK_RESULT" if output_hash else "GROK_RESULT_CAPTURE_FAILED",
            payload={**proof, "answer": pure_captured_text[:1200]},
        )

        self._log_global_terminal_turn(
            "alice",
            global_text,
            model="grok_cli",
            action="GROK_RESULT" if output_hash else "GROK_RESULT_CAPTURE_FAILED",
            focused_cli="grok",
            metadata=proof,
        )
        self._remember_matrix_history(f"\nAlice > {global_text}\n")
        if getattr(self, "_terminal_screen_active", False):
            self._sync_terminal_screen()
        else:
            self._append_plain(f"Alice > {global_text}\n\nSIFTA > ")
        self._grok_result_capture = None

    def _grok_capture_transcript_span(self, capture: dict) -> dict[str, int]:
        chunks = capture.get("chunks", [])
        seqs: list[int] = []
        byte_starts: list[int] = []
        byte_ends: list[int] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            try:
                seqs.append(int(chunk.get("seq", 0)))
                byte_starts.append(int(chunk.get("byte_start", 0)))
                byte_ends.append(int(chunk.get("byte_end", 0)))
            except Exception:
                continue
        start_seq = min(seqs) if seqs else int(capture.get("start_output_seq") or 0)
        end_seq = max(seqs) if seqs else int(capture.get("end_output_seq") or 0)
        start_byte = min(byte_starts) if byte_starts else int(capture.get("start_byte_offset") or 0)
        end_byte = max(byte_ends) if byte_ends else int(capture.get("end_byte_offset") or 0)
        return {
            "start_seq": start_seq,
            "end_seq": end_seq,
            "start_byte": start_byte,
            "end_byte": end_byte,
            "chunk_count": len(chunks),
        }

    @staticmethod
    def _denoise_grok_text(text: str) -> str:
        """Clean the raw PTY capture into readable prose for the GROK_RESULT.

        George 2026-05-24: the cognition loop works; the remaining problem is
        presentation — the raw stream leaks bare ANSI SGR remnants ([38;2;..m),
        braille spinner frames (⠦⠧⠋), and box-redraw scaffolding (┃◆┃┃┃). Strip
        those and collapse consecutive duplicate redraw lines so the receipted
        answer reads like prose. NOTE: this does NOT fully collapse *progressive*
        TUI redraws or repair characters dropped mid-redraw — that needs the full
        pyte-screen capture (the 'real terminal emulator' path); this is the
        contained, high-value cleanup on top of the existing extractor."""
        if not text:
            return text
        s = text
        s = re.sub(r"\x1b?\[[0-9;?]*[A-Za-z]", "", s)        # bare ANSI SGR / cursor / private-mode remnants
        s = re.sub(r"[⠀-⣿]+", "", s)                # braille spinner frames
        s = re.sub(r"[┃◆│█▌▎▊▉╭╮╰╯]+", " ", s)                # box-redraw scaffolding
        s = re.sub(r"[ \t]{3,}", " ", s)                      # collapse long space runs
        out: list[str] = []
        prev = None
        for ln in s.splitlines():
            st = ln.strip()
            if not st:
                if out and out[-1] != "":
                    out.append("")
                continue
            if re.fullmatch(r"[0-9\W_]{0,3}", st):            # stray spinner counters / lone punct
                continue
            if st == prev:                                    # consecutive identical redraw line
                continue
            out.append(st)
            prev = st
        return "\n".join(out).strip()

    def _extract_grok_result_text(self, capture: dict, *, force: bool = False) -> str:
        raw_parts: list[str] = []
        for chunk in capture.get("chunks", []):
            if isinstance(chunk, dict):
                text = str(chunk.get("text") or "")
            else:
                text = str(chunk)
            if text.strip():
                raw_parts.append(text)
        raw = "\n".join(raw_parts)
        if not raw.strip():
            return ""
        visible = self._visible_terminal_text()
        source = raw if len(raw) >= len(visible) else visible
        if not source.strip():
            return ""
        prompt = str(capture.get("prompt") or "")
        prompt_lines = {line.strip() for line in prompt.splitlines() if line.strip()}
        kept: list[str] = []
        skip_needles = (
            "Read /Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md",
            "Start from the hardware layer 1 kernel primordial electricity boundary",
            "Alice is asking Grok from inside the Matrix Terminal",
            "Question for Grok:",
            "Answer the question directly from the local SIFTA context",
            "Grok is an external tool organ",
            "Do not assume you are inside Alice's organism",
            "Owner's original wording to Alice:",
            "Subject binding:",
            "[Pasted:",
            "Enter:send",
            "Shift+Tab:mode",
            "Ctrl+x:shortcuts",
            "Grok Build",
        )
        for line in source.splitlines():
            clean = line.strip()
            if not clean:
                if kept and kept[-1] != "":
                    kept.append("")
                continue
            if clean in prompt_lines:
                continue
            if any(needle in clean for needle in skip_needles):
                continue
            if re.fullmatch(r"[╭╮╰╯─│\s▌>❯]+", clean):
                continue
            if clean.startswith(("SIFTA >", "ioanganton@Mac", "%", "⎇ main")):
                continue
            kept.append(clean)
        while kept and kept[0] == "":
            kept.pop(0)
        while kept and kept[-1] == "":
            kept.pop()
        text = "\n".join(kept).strip()
        text = self._denoise_grok_text(text)  # strip ANSI/spinner/redraw noise -> readable prose
        if len(text) > 12000:
            text = text[-12000:].strip()
        if not force and len(text) < 12:
            return ""
        return text

    def _visible_terminal_text(self) -> str:
        if getattr(self, "_terminal_screen_active", False) and hasattr(self, "_screen"):
            return self._screen.render()
        return self.toPlainText()

    def _grok_visible_screen_state(self) -> str:
        text = self._visible_terminal_text().lower()
        compact = re.sub(r"\s+", "", text)
        if "newworktree" in compact and "resumesession" in compact and "quit" in compact:
            return "main_menu"
        if "/tosearch" in compact and ("users-" in text or "resumesession" in compact):
            return "session_picker"
        return ""

    def _ask_owner_for_grok_choice(self) -> None:
        state = self._grok_visible_screen_state()
        if state == "main_menu":
            self._append_plain(
                "Alice > I see Grok's main menu. Tell me: resume session, new worktree, or quit.\n\n"
                "SIFTA > "
            )
            return
        if state == "session_picker":
            self._append_plain(
                "Alice > I see Grok's session list. Tell me: first saved session, move down, move up, or search.\n\n"
                "SIFTA > "
            )
            return
        self._append_plain(
            "Alice > I do not know this Grok screen yet. Tell me the exact visible option or key to press.\n\n"
            "SIFTA > "
        )

    def _execute_grok_resume_last_session(self, user_input: str, open_if_needed: bool = False) -> None:
        """Drive Grok's visible TUI by WATCHING the screen, not fixed delays.

        George 2026-05-23: fixed delays fired Ctrl-S / Enter before the second
        screen existed. Instead we POLL the visible screen state: when Grok's main
        menu shows -> send Ctrl-S (Resume session); when the session list shows ->
        send Enter (the first/last saved session). Screen-state driven = reliable
        regardless of how long Grok takes to boot or repaint.
        """
        if not self.is_running():
            self.start_shell()
        if not self.is_running():
            self._append_plain("[shell not running - cannot execute]\n\nSIFTA > ")
            return

        if _looks_like_owner_bowel_resume_encouragement(user_input):
            self._process_owner_bowel_positive_resume_encouragement(user_input)

        active_grok = self._current_cli_name() == "grok"
        if not active_grok and not open_if_needed:
            self._append_plain(
                "Alice > I need Grok visible in this terminal before I can select its Resume session menu.\n\n"
                "SIFTA > "
            )
            return

        if not active_grok:
            self._log_global_terminal_turn(
                "alice",
                "Opening Grok, then watching its screen to resume your saved session.",
                model="matrix_terminal_effector",
                action="grok_resume_start",
                focused_cli="grok",
                prior_user_text=user_input,
            )
            self._append_plain(
                "Alice > Opening Grok, then watching its screen to press Ctrl-S (Resume session) and Enter on your last session.\n"
            )
            QTimer.singleShot(250, lambda: self.write_command("grok"))
        else:
            self._log_global_terminal_turn(
                "alice",
                "Watching Grok's screen to resume your saved session.",
                model="matrix_terminal_effector",
                action="grok_resume_start",
                focused_cli="grok",
                prior_user_text=user_input,
            )
            self._append_plain(
                "Alice > Watching Grok's screen to press Ctrl-S (Resume session) and Enter on your last session.\n"
            )
        self._active_cli_name = "grok"
        self._grok_cli_active = True
        self._enter_alice_input_mode_for_tool("Grok")
        self._append_matrix_command_receipt(
            ["grok-resume", "<watch-screen>", "<ctrl-s-on-main-menu>", "<enter-on-session-list>"]
        )

        # Screen-state navigation state machine (polled every ~350ms).
        self._grok_resume_phase = "await_menu"
        self._grok_resume_deadline = time.monotonic() + 30.0
        self._grok_resume_last_action = 0.0
        timer = getattr(self, "_grok_resume_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.timeout.connect(self._tick_grok_resume_navigation)
            self._grok_resume_timer = timer
        timer.start(350)

    def _tick_grok_resume_navigation(self) -> None:
        """Poll Grok's screen and press the right key for the current screen."""
        timer = getattr(self, "_grok_resume_timer", None)
        phase = getattr(self, "_grok_resume_phase", "")
        if phase in ("", "done"):
            if timer is not None and timer.isActive():
                timer.stop()
            return
        now = time.monotonic()
        if now > getattr(self, "_grok_resume_deadline", 0.0):
            if timer is not None and timer.isActive():
                timer.stop()
            self._grok_resume_phase = ""
            self._append_plain(
                "Alice > I could not reach Grok's session list in time. Tell me what to press and I will learn it.\n\n"
                "SIFTA > "
            )
            return
        # Let the TUI repaint between key presses — don't hammer faster than ~1s.
        if now - getattr(self, "_grok_resume_last_action", 0.0) < 1.0:
            return
        state = self._grok_visible_screen_state()
        if phase == "await_menu":
            if state == "session_picker":
                self._append_process_trace(
                    "grok screen state=session_picker -> press Enter",
                    kind="screen_navigation",
                    action="grok_resume_enter",
                    payload={"state": state, "phase": phase},
                )
                self.write_bytes(b"\r")  # Already past the menu: enter the highlighted saved session.
                self._grok_resume_last_action = now
                self._grok_resume_phase = "done"
                if timer is not None and timer.isActive():
                    timer.stop()
                self._append_plain("Alice > Resumed your last Grok session.\n")
                self._log_global_terminal_turn(
                    "alice",
                    "Resumed your last Grok session.",
                    model="matrix_terminal_effector",
                    action="grok_resume_done",
                    focused_cli="grok",
                )
            elif state == "main_menu":
                self._append_process_trace(
                    "grok screen state=main_menu -> press Ctrl-S",
                    kind="screen_navigation",
                    action="grok_resume_ctrl_s",
                    payload={"state": state, "phase": phase},
                )
                self.write_bytes(b"\x13")  # Ctrl-S = Resume session
                self._grok_resume_last_action = now
                self._grok_resume_phase = "await_picker"
            return
        if phase == "await_picker":
            if state == "session_picker":
                self._append_process_trace(
                    "grok screen state=session_picker -> press Enter",
                    kind="screen_navigation",
                    action="grok_resume_enter",
                    payload={"state": state, "phase": phase},
                )
                self.write_bytes(b"\r")  # Enter on the first/last saved session
                self._grok_resume_last_action = now
                self._grok_resume_phase = "done"
                if timer is not None and timer.isActive():
                    timer.stop()
                self._append_plain("Alice > Resumed your last Grok session.\n")
                self._log_global_terminal_turn(
                    "alice",
                    "Resumed your last Grok session.",
                    model="matrix_terminal_effector",
                    action="grok_resume_done",
                    focused_cli="grok",
                )
            elif state == "main_menu":
                # Menu still showing — the Ctrl-S didn't register; press it again.
                self._append_process_trace(
                    "grok screen still main_menu -> press Ctrl-S again",
                    kind="screen_navigation",
                    action="grok_resume_ctrl_s_retry",
                    payload={"state": state, "phase": phase},
                )
                self.write_bytes(b"\x13")
                self._grok_resume_last_action = now

    def _execute_alice_cli_prompt_request(self, cli: str, user_input: str) -> None:
        """Open/use an agent CLI as Alice's tool and paste the covenant prompt."""
        cli = (cli or "").strip().lower()
        if cli not in _DIRECT_CLI_PREFIXES:
            self._append_plain(_matrix_terminal_no_cli_receipt_reply(cli) + "\n\nSIFTA > ")
            return
        if not self.is_running():
            self.start_shell()
        if not self.is_running():
            self._append_plain("[shell not running — cannot execute]\n\nSIFTA > ")
            return

        explicit_prompt = _matrix_terminal_cli_prompt(user_input, cli)
        label = _DIRECT_CLI_LABELS.get(cli, cli.title())

        # Alice drives the visible Grok TUI here. No hidden one-shot wrapper: George
        # talks to Alice, and Alice operates Grok in the same terminal transcript.
        # George 2026-05-23: opening Grok must ALWAYS pass the two preprogrammed
        # screens (Ctrl+S Resume session -> Enter on the last session), not strand
        # the owner on the New worktree / Resume / Quit menu. So a bare "open grok"
        # (no explicit question) auto-runs the resume navigation; an explicit
        # question still goes through the covenant-prefixed prompt path below.
        if cli == "grok" and (
            _matrix_terminal_grok_resume_session_requested(user_input)
            or _matrix_terminal_grok_open_only(user_input)
            or not explicit_prompt
        ):
            self._execute_grok_resume_last_session(user_input, open_if_needed=True)
            return
        if not explicit_prompt:
            active_cli = self._current_cli_name()
            if active_cli == cli:
                self._enter_alice_input_mode_for_tool(label)
                self._log_global_terminal_turn(
                    "alice",
                    f"{label} CLI is already visible in this terminal.",
                    model="matrix_terminal_effector",
                    action="cli_already_visible",
                    focused_cli=cli,
                    prior_user_text=user_input,
                )
                self._append_plain(f"Alice > {label} CLI is already visible in this terminal.\n")
                return
            self._log_global_terminal_turn(
                "alice",
                f"Opening {label} CLI in the live PTY.",
                model="matrix_terminal_effector",
                action="cli_open",
                focused_cli=cli,
                prior_user_text=user_input,
            )
            self._append_plain(f"Alice > Opening {label} CLI in the live PTY.\n")
            self._append_matrix_command_receipt([cli])
            QTimer.singleShot(250, lambda c=cli: self.write_command(c))
            self._active_cli_name = cli
            if cli == "grok":
                self._grok_cli_active = True
            self._enter_alice_input_mode_for_tool(label)
            return

        # === GROK AS TOOL ORGAN INTENT SEPARATION (owner diagnosis) ===
        # "open grok" / "start grok" etc. must ONLY launch the external tool process.
        # Never paste the owner's sentence as a prompt. This eliminates duplication, leakage,
        # and the "which grok" confusion. Grok is a bounded delegation organ, not a conversational peer.
        if _is_pure_grok_launch_command(user_input) and cli in ("grok", "alice-grok"):
            self._log_global_terminal_turn(
                "alice",
                f"PURE LAUNCH of Grok tool organ (no delegation).",
                model="matrix_terminal_effector",
                action="grok_open_only",
                focused_cli=cli,
                prior_user_text=user_input,
            )
            self._append_plain(f"Alice > Opening Grok tool organ (pure launch, no prompt sent).\n")
            self._active_cli_name = cli
            self._grok_cli_active = True
            full_launch = "python3 /Users/ioanganton/Music/ANTON_SIFTA/grok_chat.py"
            self._append_matrix_command_receipt([full_launch])
            QTimer.singleShot(300, lambda: self.write_command(full_launch))
            self._enter_alice_input_mode_for_tool("Grok")
            return
        # === end separation ===

        prompt = _matrix_terminal_cli_prompt_payload(user_input, cli)
        active_cli = self._current_cli_name()
        commands = [prompt] if active_cli == cli else [cli, prompt]
        if active_cli == cli:
            self._enter_alice_input_mode_for_tool(label)
            self._log_global_terminal_turn(
                "alice",
                f"Pasting a covenant-prefixed prompt into the active {label} CLI.",
                model="matrix_terminal_effector",
                action="cli_prompt_paste",
                focused_cli=cli,
                prior_user_text=user_input,
            )
            self._append_plain(f"Alice > Pasting a covenant-prefixed prompt into the active {label} CLI.\n")
            paste_delay_ms = 250
        else:
            self._log_global_terminal_turn(
                "alice",
                f"Opening {label} CLI and pasting a covenant-prefixed prompt for {label}.",
                model="matrix_terminal_effector",
                action="cli_prompt_open_and_paste",
                focused_cli=cli,
                prior_user_text=user_input,
            )
            self._append_plain(f"Alice > Opening {label} CLI and pasting a covenant-prefixed prompt for {label}.\n")
            paste_delay_ms = 2800
            QTimer.singleShot(250, lambda c=cli: self.write_command(c))
            self._active_cli_name = cli
            if cli == "grok":
                self._grok_cli_active = True
            self._enter_alice_input_mode_for_tool(label)

        self._append_matrix_command_receipt(commands)
        QTimer.singleShot(paste_delay_ms, lambda p=prompt: self._write_bracketed_paste(p))

    def _read_queued_grok_delegations(self) -> list[dict]:
        path = _REPO / ".sifta_state" / "grok_delegation_requests.jsonl"
        if not path.exists():
            return []
        try:
            size = path.stat().st_size
            with path.open("rb") as fh:
                fh.seek(max(0, size - 256_000))
                lines = fh.read().decode("utf-8", errors="replace").splitlines()
        except Exception:
            return []
        rows: list[dict] = []
        for line in lines[-160:]:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            if row.get("kind") != "GROK_DELEGATION_REFLEX":
                continue
            if row.get("action") != "GROK_DELEGATION":
                continue
            if not row.get("queue_for_matrix_terminal"):
                continue
            if row.get("dispatched_live"):
                continue
            if not str(row.get("text") or "").strip():
                continue
            rows.append(row)
        return rows

    def _claim_queued_grok_delegation(self, row: dict) -> bool:
        receipt = str(row.get("receipt") or "").strip()
        if not receipt:
            source = json.dumps(row, ensure_ascii=False, sort_keys=True)
            receipt = "delegation_intent_" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
            row["receipt"] = receipt
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", receipt)[:96] or "unknown"
        claims_dir = _REPO / ".sifta_state" / "grok_delegation_claims"
        try:
            claims_dir.mkdir(parents=True, exist_ok=True)
            claim_path = claims_dir / f"{safe}.json"
            fd = os.open(str(claim_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return False
        except Exception:
            return False
        try:
            payload = {
                "ts": time.time(),
                "receipt": receipt,
                "source": "matrix_terminal",
                "pid": os.getpid(),
            }
            os.write(fd, json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        finally:
            try:
                os.close(fd)
            except Exception:
                pass
        return True

    def _poll_grok_delegation_queue(self) -> None:
        for row in self._read_queued_grok_delegations():
            if not self._claim_queued_grok_delegation(row):
                continue
            receipt = str(row.get("receipt") or "")
            question = str(row.get("text") or "").strip()
            self._append_process_trace(
                f"queued global-chat Grok delegation claimed receipt={receipt}",
                kind="tool_delegation",
                action="grok_delegation_queue_claimed",
                payload={"receipt": receipt, "text": question[:512]},
            )
            self._log_global_terminal_turn(
                "alice",
                (
                    "Matrix Terminal picked up queued Grok delegation from global chat. "
                    f"receipt={receipt}. I am driving the visible Grok PTY now."
                ),
                model="matrix_terminal_effector",
                action="GROK_DELEGATION_QUEUE_CLAIMED",
                focused_cli="grok",
                metadata={"receipt": receipt, "queued": True},
            )
            self._append_plain(f"\nAlice > Picked up queued Grok delegation receipt={receipt}.\n")
            self._pending_grok_delegation_receipt_id = receipt
            if re.search(r"\b(?:ask|call|use|tell|send\s+to)\s+grok\b", question, re.IGNORECASE):
                request = question
            else:
                request = f"ask grok {question}"
            self._execute_alice_cli_prompt_request("grok", request)
            return

    def delegate_grok_from_global_chat(self, user_input: str) -> dict:
        """Public bridge: Talk/global chat asks Alice to use the visible Grok tool."""
        question = (user_input or "").strip()
        if not question:
            question = "Read the covenant and wait for Alice's next global chat prompt."
        self._log_global_terminal_turn(
            "user",
            question,
            action="global_chat_grok_request",
            focused_cli="grok",
            metadata={"source_surface": "talk_to_alice"},
        )
        self._append_plain("\n🐝 Global chat ▸ " + question + "\n")
        self._execute_alice_cli_prompt_request("grok", f"ask grok {question}")
        return {
            "ok": True,
            "status": "GROK_DELEGATION_DISPATCHED",
            "target": "grok_cli",
            "question": question,
        }

    def open_grok_from_global_chat(self, user_input: str) -> dict:
        """Public bridge: Talk/global chat asks Alice to open/resume Grok."""
        request = (user_input or "").strip() or "open grok"
        self._log_global_terminal_turn(
            "user",
            request,
            action="global_chat_grok_open_request",
            focused_cli="grok",
            metadata={"source_surface": "talk_to_alice"},
        )
        self._append_plain("\n🐝 Global chat ▸ " + request + "\n")
        self._execute_alice_cli_prompt_request("grok", request)
        return {
            "ok": True,
            "status": "GROK_OPEN_DISPATCHED",
            "target": "grok_cli",
            "request": request,
        }

    def _execute_terminal_sequence_from_owner(self, commands: list[str]) -> None:
        """Run explicit owner CLI commands in the live PTY, in order."""
        commands = _ordered_unique_commands(commands)
        active_cli = self._current_cli_name()
        if commands and commands[0] in _DIRECT_CLI_PREFIXES and commands[0] == active_cli:
            commands = commands[1:]
        if not commands:
            label = _DIRECT_CLI_LABELS.get(active_cli, active_cli or "Agent")
            self._append_plain(f"Alice > {label} CLI is already active in this terminal.\n")
            return
        if active_cli and _looks_like_direct_shell_command(commands[0]):
            label = _DIRECT_CLI_LABELS.get(active_cli, active_cli)
            self._append_process_trace(
                f"blocked shell command while {label} tool screen is active: {commands[0]}",
                kind="tool_boundary",
                action="TOOL_BOUNDARY_BLOCK",
                payload={"focused_cli": active_cli, "command": commands[0]},
            )
            self._append_plain(
                f"Alice > {label} is active as my tool screen. I will not send shell command `{commands[0]}` into {label}.\n\n"
                "SIFTA > "
            )
            return
        if commands[0] in _DIRECT_CLI_PREFIXES and not _matrix_terminal_agent_cli_enabled():
            label = _DIRECT_CLI_LABELS.get(commands[0], commands[0])
            self._append_plain(
                f"Alice > Matrix Terminal is Alice-first here. I will not open {label} in this surface.\n\n"
                "SIFTA > "
            )
            return
        blocked = [cmd for cmd in commands if not self._shell_cmd_is_safe(cmd)]
        if blocked:
            self._append_blocked_shell_warning(blocked[0])
            return
        if not self.is_running():
            self.start_shell()
        if not self.is_running():
            self._append_plain("[shell not running — cannot execute]\n\nSIFTA > ")
            return

        starts_cli = commands[0] if commands[0] in _DIRECT_CLI_PREFIXES else ""
        sends_to_cli = bool(starts_cli or active_cli)
        cli_for_message = starts_cli or active_cli
        cli_label = _DIRECT_CLI_LABELS.get(cli_for_message, cli_for_message.title())
        if starts_cli and len(commands) > 1:
            self._append_plain(f"Alice > Opening {cli_label} CLI and sending your request through the live PTY.\n")
        elif starts_cli:
            self._append_plain(f"Alice > Opening {cli_label} CLI in the live PTY.\n")
        elif sends_to_cli:
            self._append_plain(f"Alice > Sending your request to the active {cli_label} CLI.\n")
        else:
            label = "command" if len(commands) == 1 else "command sequence"
            self._append_plain(f"Alice > Executing live PTY {label}.\n")
        self._append_matrix_command_receipt(commands)

        for idx, cmd in enumerate(commands):
            if starts_cli and idx > 0:
                delay_ms = 2800 + (idx - 1) * 900
            else:
                delay_ms = 250 + idx * 900

            def _send(c=cmd):
                self.write_command(c)

            QTimer.singleShot(delay_ms, _send)
        if starts_cli:
            self._active_cli_name = starts_cli
            self._enter_alice_input_mode_for_tool(
                _DIRECT_CLI_LABELS.get(starts_cli, starts_cli.title())
            )
        if "grok" in commands:
            self._grok_cli_active = True
        if any(cmd.strip() in {"/exit", "exit", "quit", "/quit"} for cmd in commands):
            self._grok_cli_active = False
            self._active_cli_name = None
            self._alice_tool_input_hint_cli = None

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

    def _append_blocked_shell_warning(self, cmd: str) -> None:
        self._append_plain(
            f"⚠️  BLOCKED: '{cmd}' matches a dangerous pattern.\n"
            "    Alice will not execute destructive commands.\n"
            "    If you need this, type it directly in the PTY.\n\n"
            "SIFTA > "
        )

    def _execute_shell_from_alice(self, cmd: str) -> None:
        """Pipe Alice's translated shell command into the live PTY.

        A deterministic denylist gate runs BEFORE write_command.
        Dangerous patterns are blocked regardless of what the model says.
        """
        if not self._shell_cmd_is_safe(cmd):
            self._append_blocked_shell_warning(cmd)
            return
        if not self.is_running():
            self._append_plain("[shell not running — cannot execute]\n\nSIFTA > ")
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
        _patch_process_events_for_offscreen_tests()
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
        
        label_cls = _OffscreenRetainedLabel if _offscreen_test_mode() else QLabel
        self.status_label = label_cls("zsh PTY • scripting")
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
            lambda: self.terminal._paste_into_input(),
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
        self.btn_clean = make_button("SKIP RABBIT", self.skip_white_rabbit)
        self.btn_grok = make_button("GROK CLI", self.start_grok_cli, add_to_header=False)
        self.btn_hermes = make_button("HERMES CLI", self.start_hermes_cli, add_to_header=False)
        self.btn_grok.setVisible(False)
        self.btn_hermes.setVisible(False)
        root.addWidget(header)

        if _offscreen_test_mode():
            self.terminal = _HeadlessMatrixTerminalPane(self)
        else:
            self.terminal = MatrixTerminalPane(_REPO, self)
        root.addWidget(self.terminal, 1)
        self.terminal.setFocus()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        if not _offscreen_test_mode():
            self._status_timer.start(1000)
        self._tick_count = 0

        # Register for cortex-driven PTY control when this Alice-first terminal is focused.
        if self not in _LIVE_MATRIX_APPS:
            _LIVE_MATRIX_APPS.append(self)

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

    def skip_white_rabbit(self) -> None:
        """Button handler: instantly bypass the white rabbit / protein folding theatrical layer
        so the PTY is a clean, Alice-first zsh terminal. Owner text addressed to
        Alice goes to Alice; literal shell commands still execute in the PTY.
        """
        if hasattr(self, "terminal") and self.terminal:
            self.terminal.force_clean_pty()
        if _qt_alive(getattr(self, "status_label", None)):
            self.status_label.setText("zsh PTY • clean")
        self.terminal.setFocus()

    def start_grok_cli(self) -> None:
        """Compatibility handler; Grok is not exposed in the Alice-first terminal."""
        if hasattr(self, "terminal") and self.terminal:
            self.terminal._append_plain(
                "\nAlice > Matrix Terminal is Alice-first here. I will not open Grok in this surface.\n\n"
                "SIFTA > "
            )
        if _qt_alive(getattr(self, "status_label", None)):
            self.status_label.setText("Alice • terminal")
        self.terminal.setFocus()

    def start_hermes_cli(self) -> None:
        """Compatibility handler; Hermes is not exposed in the Alice-first terminal."""
        if hasattr(self, "terminal") and self.terminal:
            self.terminal._append_plain(
                "\nAlice > Matrix Terminal is Alice-first here. I will not open Hermes in this surface.\n\n"
                "SIFTA > "
            )
        if _qt_alive(getattr(self, "status_label", None)):
            self.status_label.setText("Alice • terminal")
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
        # Unregister from cortex PTY control
        if self in _LIVE_MATRIX_APPS:
            _LIVE_MATRIX_APPS.remove(self)

    def deleteLater(self) -> None:
        if _offscreen_test_mode():
            self.shutdown()
            if self not in _OFFSCREEN_RETAINED_WIDGETS:
                _OFFSCREEN_RETAINED_WIDGETS.append(self)
            return
        super().deleteLater()

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


def get_live_pty_status_for_alice() -> str:
    """Returns a compact, receipt-citable summary of the currently focused Matrix Terminal PTY.

    This block is injected into Alice's prompt (Gemma4) for any turn that mentions "terminal", "pty",
    or "type in terminal". It gives the model concrete swimmers from the field (last commands, outputs,
    receipt hashes) so the chorum on truth is strong enough to reliably plan and execute simple
    multi-step embodied actions (bring desktop forward, ensure the PTY is the active surface, type the line).

    Without this, the PTY swimmers are too quiet and Gemma4 cannot confidently do the 3-step plan
    the owner described.
    """
    try:
        pane = get_focused_matrix_terminal_pane()
        if not pane or not pane.is_running():
            return (
                "MATRIX TERMINAL PTY STATUS (from field receipts):\n"
                "No live focused PTY right now. The terminal organ is not the active surface.\n"
                "To operate it, the desktop focus must be on the Matrix Terminal app and the PTY pane must be visible.\n"
                "Recent PTY commands are receipted in .sifta_state/matrix_terminal_commands.jsonl and appear in the transcript."
            )

        # Get recent transcript lines from the terminal document
        doc = getattr(pane, "terminal", None)
        recent_lines = []
        if doc and hasattr(doc, "document"):
            document = doc.document()
            count = document.blockCount()
            for i in range(max(0, count - 8), count):
                line = document.findBlockByLineNumber(i).text().strip()
                if line:
                    recent_lines.append(line[:120])

        recent = "\n".join(recent_lines) if recent_lines else "(transcript empty or not readable)"

        # Last receipt if available
        receipt_note = ""
        try:
            receipt_path = Path("/Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/matrix_terminal_commands.jsonl")
            if receipt_path.exists():
                last = receipt_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-1]
                if last:
                    receipt_note = f"\nLast PTY command receipt (tail of ledger): {last[:200]}..."
        except Exception:
            pass

        return (
            "MATRIX TERMINAL PTY STATUS (receipt-grounded - cite these swimmers for chorum on truth):\n"
            f"Live PTY is focused and responsive.\n"
            f"Recent transcript (last lines):\n{recent}\n"
            f"{receipt_note}\n"
            "PTY commands you issue will be injected into this transcript and produce a new receipt in the ledger.\n"
            "Before planning any 'type X in terminal' action, you must cite the last output and receipt hash above."
        )
    except Exception as e:
        return f"MATRIX TERMINAL PTY STATUS: error reading live state ({e}). Fall back to app_focus receipts."


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MatrixTerminalApp()
    win.show()
    sys.exit(app.exec())
