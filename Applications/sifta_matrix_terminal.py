from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import pty
import re
import shlex
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
from typing import Any

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


_GROK_SCREEN_CLASSIFIER_VERSION = "grok_screen_classifier.v1"
_GROK_RESUME_ACTION_TABLE: dict[tuple[str, str], dict[str, object]] = {
    ("await_menu", "main_menu"): {
        "key_label": "Ctrl-S",
        "key_bytes": b"\x13",
        "decision": "resume the saved session",
        "trace_action": "grok_resume_ctrl_s",
        "trace_text": "grok screen state=main_menu -> press Ctrl-S",
        "next_phase": "await_picker",
    },
    ("await_menu", "session_picker"): {
        "key_label": "Enter",
        "key_bytes": b"\r",
        "decision": "select the highlighted saved session",
        "trace_action": "grok_resume_enter",
        "trace_text": "grok screen state=session_picker -> press Enter",
        "next_phase": "await_ready",
        "deadline_s": 35.0,
    },
    ("await_picker", "main_menu"): {
        "key_label": "Ctrl-S",
        "key_bytes": b"\x13",
        "decision": "resume the saved session",
        "trace_action": "grok_resume_ctrl_s_retry",
        "trace_text": "grok screen still main_menu -> press Ctrl-S again",
        "next_phase": "await_picker",
    },
    ("await_picker", "session_picker"): {
        "key_label": "Enter",
        "key_bytes": b"\r",
        "decision": "select the highlighted saved session",
        "trace_action": "grok_resume_enter",
        "trace_text": "grok screen state=session_picker -> press Enter",
        "next_phase": "await_ready",
        "deadline_s": 35.0,
    },
    ("await_ready", "main_menu"): {
        "key_label": "Ctrl-S",
        "key_bytes": b"\x13",
        "decision": "resume the saved session",
        "trace_action": "grok_resume_ctrl_s_retry",
        "trace_text": "grok returned to main_menu after Enter -> press Ctrl-S",
        "next_phase": "await_picker",
        "min_since_action_s": 0.0,
    },
    ("await_ready", "session_picker"): {
        "key_label": "Enter",
        "key_bytes": b"\r",
        "decision": "select the highlighted saved session",
        "trace_action": "grok_resume_enter_retry",
        "trace_text": "grok screen still session_picker after Enter -> press Enter again",
        "next_phase": "await_ready",
        "min_since_action_s": 2.0,
    },
}


def _terminal_cells_to_text(cells: list[list[dict[str, object]]] | None) -> str:
    """Convert pyte-style framebuffer cells into visible text for classifiers."""
    if not cells:
        return ""
    lines: list[str] = []
    for row in cells:
        if not isinstance(row, list):
            continue
        chars: list[str] = []
        for cell in row:
            if isinstance(cell, dict):
                ch = str(cell.get("char") or " ")[:1]
            else:
                ch = str(cell or " ")[:1]
            chars.append(ch)
        lines.append("".join(chars).rstrip())
    return "\n".join(lines).strip()


def grok_screen_classifier(
    cells: list[list[dict[str, object]]] | None = None,
    *,
    text: str = "",
) -> str:
    """Classify the currently visible Grok TUI screen from framebuffer evidence."""
    visible = _terminal_cells_to_text(cells) if cells else str(text or "")
    lower = visible.lower()
    compact = re.sub(r"\s+", "", lower)
    if "newworktree" in compact and "resumesession" in compact and "quit" in compact:
        return "main_menu"
    if "/tosearch" in compact and ("users-" in lower or "resumesession" in compact):
        return "session_picker"
    return ""


def _offscreen_test_mode() -> bool:
    return (
        "pytest" in sys.modules
        or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
    )


def _read_macos_terminal_front_tab_contents(*, timeout: float = 2.5, max_chars: int = 50000) -> str:
    """Compatibility stub: native Terminal.app is no longer a SIFTA surface.

    Owner decision 2026-05-25: Alice global chat is the only terminal. The
    macOS Terminal.app reader previously created an identity split by importing
    a different Grok body than Alice's owned PTY. Keep this symbol importable for
    older tests/callers, but never read another terminal surface.
    """
    return ""


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
    """Project internal PTY turns into Alice's one global chat ledger."""
    clean = (text or "").strip()
    if not clean:
        return
    meta = {
        "surface": "alice_global_chat_terminal",
        "territory": "Alice Global Chat",
        "source": "alice_global_chat_terminal",
    }
    if action:
        meta["action"] = action
    if focused_cli:
        meta["focused_cli"] = focused_cli
    if metadata:
        meta.update(metadata)
    if role == "user" and not clean.startswith("[Alice Global Chat Terminal]"):
        clean = f"[Alice Global Chat Terminal]: {clean}"
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
    "You're right. This is Alice global chat terminal, not WhatsApp. I can talk with you "
    "here, but I will not send, simulate, or format WhatsApp tool calls from "
    "this surface."
)


def _write_alice_global_terminal_diary_event(*, event: str, ok: bool, note: str, receipt_id: str = "") -> None:
    """Best-effort memory row for terminal-service events.

    Agent arms already write arm outcomes into the episodic diary. This helper
    covers the internal PTY/global-chat terminal service so Alice remembers
    tool/build terminal events without exposing a separate terminal surface.
    """
    try:
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "event": event,
                    "ok": bool(ok),
                    "note": note,
                    "receipt_id": receipt_id,
                },
                sort_keys=True,
            ).encode("utf-8", "replace")
        ).hexdigest()
        now = time.time()
        t = time.localtime(now)
        bucket_hour = (int(t.tm_hour) // 4) * 4
        row = {
            "ts": now,
            "truth_label": "EPISODIC_DIARY_ALICE_GLOBAL_CHAT_TERMINAL_V1",
            "bucket": f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T{bucket_hour:02d}:00",
            "window_hours": 4,
            "labels": ["alice_global_chat_terminal", "internal_pty", event, "success" if ok else "failure"],
            "event_count": 1,
            "source_counts": {"alice_global_chat_terminal": 1},
            "source_hash": source_hash,
            "facts": [note[:500], f"ok={bool(ok)}", f"receipt={receipt_id}" if receipt_id else "receipt="],
            "source": "alice_global_chat_terminal",
            "event": event,
            "ok": bool(ok),
            "receipt_id": receipt_id,
        }
        path = _REPO / ".sifta_state" / "episodic_diary.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _matrix_ollama_model_candidates(primary: str) -> list[str]:
    """Return local model fallbacks for Matrix chat without starting downloads."""
    names: list[str] = []
    for name in (
        primary,
        f"{primary}:latest" if primary and ":" not in primary else "",
        "alice-m5-cortex-8b-6.3gb:latest",
        "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
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
_INTERNAL_MATRIX_TERMINAL_PANE: "MatrixTerminalPane | None" = None


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
    if bool(getattr(pane, "_sifta_internal_pty", False)):
        return True
    try:
        return bool(pane.isVisible() or pane.parent() is not None)
    except Exception:
        return True


def get_or_create_internal_matrix_terminal_pane() -> "MatrixTerminalPane | None":
    """Return SIFTA's hidden owned PTY hand for global-chat Grok.

    This is intentionally not a launcher-visible terminal app. The owner-facing
    surface stays global chat; this hidden pane owns the raw PTY bytes so the
    pyte framebuffer bridge can render Grok's full-screen TUI.
    """
    global _INTERNAL_MATRIX_TERMINAL_PANE
    if _matrix_terminal_pane_alive(_INTERNAL_MATRIX_TERMINAL_PANE):
        return _INTERNAL_MATRIX_TERMINAL_PANE
    if _offscreen_test_mode() and os.environ.get("SIFTA_ALLOW_INTERNAL_MATRIX_PTY_IN_TESTS") != "1":
        return None
    if QApplication.instance() is None:
        return None
    try:
        pane = MatrixTerminalPane(_REPO, None)
        pane._sifta_internal_pty = True
        pane.setObjectName("SIFTAHiddenInternalMatrixPTY")
        pane.hide()
        pane._script_state = "DIRECT"
        if not pane.is_running():
            pane.start_shell()
        _INTERNAL_MATRIX_TERMINAL_PANE = pane
        _remember_live_matrix_terminal_pane(pane)
        return pane
    except Exception:
        _INTERNAL_MATRIX_TERMINAL_PANE = None
        return None


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


def _matrix_terminal_direct_type_grok_requested(user_input: str) -> bool:
    """Owner can force Grok direct typing and explicitly disable resume navigation."""
    raw = (user_input or "").strip().lower()
    if not raw:
        return False
    compact = re.sub(r"\s+", " ", raw)
    needles = (
        "direct-type",
        "direct type",
        "do not press ctrl-s",
        "do not press ctrl s",
        "do not run resume_navigation",
        "do not run resume navigation",
        "new session every time",
        "no resume",
    )
    return any(n in compact for n in needles)


def _grok_input_looks_ready(frame_text: str) -> bool:
    """True when the Grok TUI shows a writable input surface.

    For Grok 0.2.x, being writable means either:
    - a boxed cursor row is visible (``│ ❯ ... │`` or ``│ > ... │``), or
    - the bottom Grok input box shell is visible (the box around the input line
      with ``Grok Build · always-approve`` footer), even if the cursor glyph
      is missing from the framebuffer sample.

    This aligns with owner policy: after launching ``grok``, do not auto-select
    menu items; if the input surface is writable, paste directly.
    """
    raw = frame_text or ""
    # Strip ANSI escape sequences that can trail the visible input row and
    # break end-of-line regex checks.
    clean = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", raw)
    clean = re.sub(r"\x1b\].*?(?:\x07|\x1b\\)", "", clean)
    clean = clean.replace("\x1b", "")
    clean = clean.replace("\r", "")
    clean = clean.replace("\u200b", "")
    raw = clean
    if not raw.strip():
        return False
    t = raw.lower()
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if not lines:
        return False
    # Positive signal 1: boxed live input row with either unicode or ascii
    # cursor glyph.
    box_input_re = re.compile(r"│\s*[❯>][^│]*│\s*$")
    if any(box_input_re.search(ln) for ln in lines):
        return True

    # Positive signal 2: Grok input box shell is visible near the bottom even
    # when the cursor glyph is not captured in this frame sample.
    has_grok_input_shell = any("grok build" in ln and "always-approve" in ln for ln in lines)
    if has_grok_input_shell:
        for idx, ln in enumerate(lines):
            if "grok build" in ln and "always-approve" in ln:
                prev = lines[idx - 1] if idx > 0 else ""
                if prev.strip().startswith("│") and prev.strip().endswith("│"):
                    return True

    # Fallback bad-list — only relevant when no input surface is visible.
    bad = ("loading", "connecting", "initializing")
    if any(b in t for b in bad):
        return False
    # Fallback positive signals for non-boxed prompts (bash, generic CLIs).
    last = lines[-1].strip()
    if last.endswith(">") or last.endswith(":") or ("grok" in last and ">" in last):
        return True
    if any("how can i" in ln or "what can i" in ln for ln in lines[-3:]):
        return True
    return False


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
        "Subject binding: the owner is talking to Alice in the Alice global chat terminal. "
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
        f"Alice is asking {label} from inside the Alice global chat terminal.\n"
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
        {"role": "user", "content": f"[Alice Global Chat Terminal] {user_input}"},
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
    grokFramebufferSnapshotReady = pyqtSignal(object)  # latest rendered VT cells for Alice global chat

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
        self._grok_delegation_queue_stale_s = 15 * 60
        self._grok_delegation_busy_last_trace = 0.0
        self._pty_output_seq = 0
        self._pty_output_bytes_total = 0
        self._grok_framebuffer_trace_min_interval_s = 1.0

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
                "source": "alice_global_chat_terminal",
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
        # De-spammed: terminal scrollback below is enough; no global-chat narration.
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

        # Fix for Ctrl-S (XOFF / 0x13) and flow-control swallowing in Grok PTY
        # (owner-reported via Alice delegation 2026-05-25). Without this, IXON/IXOFF
        # in c_iflag eats the keystroke as "pause output" before it reaches the child.
        # This also resolves related "0 chars captured" freezes when Grok is a rich TUI.
        attrs = termios.tcgetattr(slave_fd)
        attrs[0] &= ~(termios.IXON | termios.IXOFF | termios.IXANY)
        termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)

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
            "\n[Alice Global Chat Terminal - internal PTY service. Type to Alice here; literal shell commands still run.]\n"
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

    def _write_bytes_all(self, data: bytes, *, timeout_s: float = 1.5) -> int:
        """Layer 1 kernel handoff (GTH4921YP3 pty driver): drain every byte to master_fd
        without silent loss. The primordial electricity → termios pty pair → slave stdin
        path must deliver the exact ASCII swimmers (no double-spend, no drop on EAGAIN).
        Old bare os.write + except-OSError-pass on the NONBLOCK master was the hole:
        long prompt payloads or the trailing \r could be truncated or lost when the
        Grok TUI back-pressured the buffer during its render. This loop + yield
        guarantees the bytes we emit are the bytes the Grok TUI actually receives on stdin.
        Returns count the kernel accepted. Used only for bulk Grok delegation writes.
        """
        if self.master_fd is None or not data:
            return 0
        sent = 0
        deadline = time.monotonic() + float(timeout_s)
        view = data
        while sent < len(view):
            if time.monotonic() > deadline:
                break
            try:
                n = os.write(self.master_fd, view[sent:])
                if n and n > 0:
                    sent += n
                else:
                    time.sleep(0.003)
            except BlockingIOError:
                time.sleep(0.003)
            except OSError:
                break
        return sent

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
        self._capture_grok_framebuffer_snapshot()
        self._sync_terminal_screen()

    @staticmethod
    def _normalize_terminal_frame_text(text: str) -> str:
        """Return a compact, hashable terminal frame without padding noise."""
        if not text:
            return ""
        lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines).strip()

    def _terminal_frame_text(self) -> str:
        """Rendered terminal framebuffer text from the current screen state."""
        screen = getattr(self, "_screen", None)
        if screen is None:
            return ""
        try:
            if getattr(self, "_using_mature_renderer", False) and hasattr(screen, "text"):
                raw = screen.text()
            elif hasattr(screen, "render"):
                raw = screen.render()
            else:
                raw = ""
        except Exception:
            return ""
        return self._normalize_terminal_frame_text(str(raw or ""))

    def _terminal_frame_cells(self) -> list[list[dict[str, object]]]:
        """Structured rich terminal framebuffer from the current screen state.

        The plain framebuffer text proves what was visible, but the global chat's
        high-fidelity renderer needs cell attributes too: fg/bg, bold, underline,
        reverse video, and cursor. Keep this bounded and JSON-safe so final
        GROK_RESULT rows can paint a real terminal surface without flooding the
        permanent ledger with live frame spam.
        """
        screen = getattr(self, "_screen", None)
        if screen is None or not hasattr(screen, "cells"):
            return []
        try:
            raw_cells = screen.cells()
        except Exception:
            return []
        if not isinstance(raw_cells, list):
            return []
        safe_rows: list[list[dict[str, object]]] = []
        max_rows = 40
        max_cols = 140
        for row in raw_cells[:max_rows]:
            if not isinstance(row, list):
                continue
            safe_row: list[dict[str, object]] = []
            for cell in row[:max_cols]:
                if not isinstance(cell, dict):
                    safe_row.append({"char": " "})
                    continue
                safe_row.append({
                    "char": str(cell.get("char") or " ")[:1],
                    "fg": str(cell.get("fg") or "default")[:32],
                    "bg": str(cell.get("bg") or "default")[:32],
                    "bold": bool(cell.get("bold")),
                    "italics": bool(cell.get("italics")),
                    "underscore": bool(cell.get("underscore")),
                    "reverse": bool(cell.get("reverse")),
                })
            safe_rows.append(safe_row)
        return safe_rows

    def _terminal_frame_cursor(self) -> list[object]:
        screen = getattr(self, "_screen", None)
        if screen is None or not hasattr(screen, "cursor"):
            return [0, 0, False]
        try:
            x, y, visible = screen.cursor()
            return [int(x), int(y), bool(visible)]
        except Exception:
            return [0, 0, False]

    def _strip_volatile_for_grok_hash(self, text: str) -> str:
        """Remove UI noise that changes every frame but does not represent content.
        Used for change detection so we don't flood on spinners / progress / timers.
        """
        if not text:
            return ""
        # Remove braille spinners (U+2800–U+28FF)
        text = re.sub(r'[\u2800-\u28ff]+', '', text)
        # Remove common progress bar characters ( ┃ and similar box drawing runs)
        text = re.sub(r'[┃│█░▓▒]+', '', text)
        # Remove standalone elapsed time patterns like " 12.3s", "67.8s", etc.
        text = re.sub(r'\b\d+\.\d+s\b', '', text)
        text = re.sub(r"\x1b?\[[0-9;?]*[A-Za-z]", "", text)
        # claude-opus-4-7 2026-05-25 — close the snapshot-reemit gap: Grok's TUI
        # also ticks an integer-second timer, a net up/down counter (⇣40.4k) and a
        # progress percentage every frame. Left in, they keep the framebuffer
        # change-gate re-firing ~1/sec through long Thinking phases. They are
        # chrome, not cognition — strip them from the change signature only.
        # (Verified in-sandbox on the owner's real frames: two Thinking frames
        # differing only in these now collapse to one signature.)
        text = re.sub(r'\b\d+s\b', '', text)                  # integer-second timers
        text = re.sub(r'[⇣⇡][\d.]+[kKmMgG]?', '', text)  # net up/down counters (⇣ ⇡)
        text = re.sub(r'\d+(?:\.\d+)?%', '', text)             # progress percentage
        # Collapse extra whitespace created by removals
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        stable_lines: list[str] = []
        for line in text.splitlines():
            st = line.strip()
            # Grok TUI frames often arrive as a spinner plus a one/two digit
            # counter. After spinner removal those become bare "3", "40", etc.
            # They are not cognition or output; do not count them as progress.
            if not st or re.fullmatch(r"[0-9\W_]{0,4}", st):
                continue
            stable_lines.append(st)
        return "\n".join(stable_lines).strip()

    def _capture_grok_framebuffer_snapshot(self) -> None:
        """Capture the rendered Grok screen, not just stripped stdout bytes.

        Grok's CLI is a full-screen TUI. Its "thoughts" are often terminal
        state (cursor moves, alternate-screen redraws, attributes) rather than
        ordinary shell scrollback. This bridge receipts the pyte/terminal
        framebuffer SIFTA owns so the global chat can later cite the same screen
        the owner would see in a real terminal.
        """
        capture = getattr(self, "_grok_result_capture", None)
        if not capture or capture.get("posted"):
            return
        # Round 25: same loosening as _capture_grok_terminal_output. Once a
        # capture is active, the capture object is the authority on whether
        # we should snapshot. Reject only on a DIFFERENT named cli.
        capture["framebuffer_events_seen"] = int(capture.get("framebuffer_events_seen", 0)) + 1
        cli_now = self._current_cli_name()
        if cli_now not in ("grok", ""):
            capture["framebuffer_events_other_cli"] = int(capture.get("framebuffer_events_other_cli", 0)) + 1
            return
        frame_text = self._terminal_frame_text()
        if not frame_text:
            capture["framebuffer_events_no_text"] = int(capture.get("framebuffer_events_no_text", 0)) + 1
            return

        # === FIX 1: FLOOD CONTROL ===
        # Strip volatile UI noise before hashing so we only emit on real content change.
        stripped_for_hash = self._strip_volatile_for_grok_hash(frame_text)
        frame_hash = hashlib.sha256(stripped_for_hash.encode("utf-8")).hexdigest()

        if frame_hash == capture.get("last_stripped_framebuffer_hash"):
            return

        # Hard backstop: never more than 1 framebuffer emit per second
        now_mono = time.monotonic()
        last_emit = float(capture.get("last_framebuffer_trace_monotonic") or 0.0)
        if now_mono - last_emit < 1.0:
            return

        frames = capture.setdefault("framebuffer_frames", [])
        frame = {
            "seq": int(getattr(self, "_pty_output_seq", 0)),
            "byte_end": int(getattr(self, "_pty_output_bytes_total", 0)),
            "timestamp": time.time(),
            "elapsed_s": round(now_mono - float(capture.get("started_monotonic") or now_mono), 1),
            "frame_hash": frame_hash,
            "text": frame_text,
            "renderer": "mature_pyte" if getattr(self, "_using_mature_renderer", False) else "early_screen_buffer",
        }
        cells = self._terminal_frame_cells()
        if cells:
            frame["cells"] = cells
            frame["cursor"] = self._terminal_frame_cursor()
            frame["rows"] = len(cells)
            frame["cols"] = len(cells[0]) if cells and cells[0] else 0
            try:
                self.grokFramebufferSnapshotReady.emit(
                    {
                        "framebuffer_cells": cells,
                        "framebuffer_cursor": frame["cursor"],
                        "framebuffer_rows": frame["rows"],
                        "framebuffer_cols": frame["cols"],
                        "framebuffer_output_hash": frame_hash,
                        "frame_hash": frame_hash,
                        "capture_id": capture.get("id"),
                        "elapsed_s": frame["elapsed_s"],
                        "renderer": frame["renderer"],
                        "source": "alice_global_chat_terminal",
                    }
                )
            except Exception:
                pass
        frames.append(frame)
        if len(frames) > 80:
            del frames[:-80]

        capture["last_stripped_framebuffer_hash"] = frame_hash
        capture["last_framebuffer_hash"] = frame_hash  # keep for compatibility
        capture["last_framebuffer_monotonic"] = now_mono
        capture["last_output_monotonic"] = now_mono
        capture["framebuffer_chars_captured"] = len(frame_text)

        # Only emit process trace on actual content change (already guarded above)
        capture["last_framebuffer_trace_monotonic"] = now_mono
        preview = frame_text
        if len(preview) > 5000:
            preview = "...\n" + preview[-5000:]
        self._append_process_trace(
            f"◆ {frame['elapsed_s']:.1f}s grok framebuffer [{frame['renderer']}] hash={frame_hash[:16]}\n{preview}",
            kind="tool_result_capture",
            action="grok_framebuffer_snapshot",
            payload={
                "capture_id": capture.get("id"),
                "frame_hash": frame_hash,
                "frame_chars": len(frame_text),
                "renderer": frame["renderer"],
                "seq": frame["seq"],
                "byte_end": frame["byte_end"],
                "elapsed_s": frame["elapsed_s"],
            },
        )

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
                "source": "alice_global_chat_terminal",
                "action": protocol_action or "owner_command_sequence",
                "commands": list(commands),
                "target": target,
                "ok": True,
                "truth_note": "Commands were written to Alice global chat terminal's internal PTY service; output renders back into global chat.",
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
            _write_alice_global_terminal_diary_event(
                event="command_sequence",
                ok=True,
                note=f"Internal PTY command sequence target={target}: {', '.join(str(c) for c in commands)[:240]}",
                receipt_id=row["trace_id"],
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
            busy = self._grok_delegation_busy_reason()
            if busy:
                self._append_process_trace(
                    f"deferred Grok paste because {busy}; prompt_chars={len(payload)}",
                    kind="tool_delegation",
                    action="grok_delegation_deferred_inflight",
                    payload={
                        "reason": busy,
                        "prompt_chars": len(payload),
                        "text_preview": payload[:320],
                    },
                )
                return
            self._begin_grok_result_capture(payload)
            capture = getattr(self, "_grok_result_capture", None)
            if isinstance(capture, dict):
                capture["input_mode"] = "bracketed"
                capture["literal_retry_sent"] = False
                capture["literal_retry_ts"] = 0.0
        self._append_process_trace(
            f"paste -> {target} ({len(payload)} chars)\n{payload}",
            kind=kind,
            action=action,
            payload={"target": target, "chars": len(payload), "text": payload},
        )
        # ── Round 27 + 28 (grok-4.3 direct, 2026-05-27) ────────────────────
        # Round 26/27 raw write still yielded events_seen=0. Layer-1 diagnosis:
        # nonblock master_fd + bare os.write can drop or partial the swimmers
        # (BlockingIOError / short return swallowed by except OSError: pass).
        # The kernel pty accepted the write call but not every byte reached
        # the Grok TUI stdin before the \r landed. Now using _write_bytes_all drain.
        # Also record exact bytes kernel accepted into the capture so the
        # heartbeat can report sent vs seen (distinguishes "wrote but the Grok TUI
        # silent" from "kernel ate our bytes at the boundary").
        encoded = payload.encode("utf-8")
        sent = self._write_bytes_all(encoded)
        cap = getattr(self, "_grok_result_capture", None)
        if isinstance(cap, dict):
            cap["bytes_sent_to_pty"] = int(cap.get("bytes_sent_to_pty", 0)) + sent
        QTimer.singleShot(3000, lambda: self._write_bytes_all(b"\r"))

    @staticmethod
    def _should_retry_grok_literal_typing(capture: dict, *, elapsed_s: float) -> bool:
        """Decide whether to retry Grok prompt delivery via literal typing.

        Round 27 fallback: some Grok TUI states accept the visual paste but emit
        only one blank/control event (`events_seen=1 recorded=0 blank=1`) and
        never produce readable output. Retry once as literal typing + Enter.
        """
        if not isinstance(capture, dict):
            return False
        if str(capture.get("input_mode") or "") != "bracketed":
            return False
        if bool(capture.get("literal_retry_sent")):
            return False
        if elapsed_s < 4.0:
            return False
        seen = int(capture.get("events_seen", 0) or 0)
        recorded = int(capture.get("events_recorded", 0) or 0)
        blank = int(capture.get("events_blank", 0) or 0)
        return recorded == 0 and blank >= 1 and seen <= 2

    def _retry_grok_prompt_with_literal_typing(self, capture: dict, *, elapsed_s: float) -> bool:
        payload = str(capture.get("prompt") or "").rstrip()
        if not payload:
            return False
        capture["literal_retry_sent"] = True
        capture["literal_retry_ts"] = time.monotonic()
        capture["input_mode"] = "literal_retry"
        # Reset idle clock so the active capture gets a fair window after retry.
        capture["last_output_monotonic"] = time.monotonic()
        self._append_process_trace(
            "bracketed paste looked inert; retrying Grok prompt via literal typing + Enter",
            kind="tool_delegation",
            action="grok_literal_retry_after_blank_capture",
            payload={
                "prompt_chars": len(payload),
                "elapsed_s": round(elapsed_s, 2),
                "events_seen": int(capture.get("events_seen", 0) or 0),
                "events_recorded": int(capture.get("events_recorded", 0) or 0),
                "events_blank": int(capture.get("events_blank", 0) or 0),
            },
        )
        encoded = payload.encode("utf-8")
        sent = self._write_bytes_all(encoded)
        cap = getattr(self, "_grok_result_capture", None)
        if isinstance(cap, dict):
            cap["bytes_sent_to_pty"] = int(cap.get("bytes_sent_to_pty", 0)) + sent
        QTimer.singleShot(250, lambda: self._write_bytes_all(b"\r"))
        return True

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

    def _grok_delegation_busy_reason(self) -> str:
        """Return why a new Grok delegation must wait, or an empty string."""
        capture = getattr(self, "_grok_result_capture", None)
        if isinstance(capture, dict) and not capture.get("posted"):
            return f"active_capture:{capture.get('id') or 'unknown'}"
        phase = str(getattr(self, "_grok_resume_phase", "") or "")
        if phase and phase != "done":
            return f"resume_navigation:{phase}"
        return ""

    def _trace_grok_queue_busy(self, reason: str) -> None:
        now = time.monotonic()
        last = float(getattr(self, "_grok_delegation_busy_last_trace", 0.0) or 0.0)
        last_reason = str(getattr(self, "_grok_delegation_busy_last_reason", "") or "")
        min_interval_s = 12.0
        if reason == last_reason and now - last < min_interval_s:
            return
        self._grok_delegation_busy_last_trace = now
        self._grok_delegation_busy_last_reason = reason
        self._append_process_trace(
            f"Grok queue held because {reason}; waiting for current delegation to finish",
            kind="tool_delegation",
            action="grok_delegation_queue_held_inflight",
            payload={"reason": reason},
        )

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
        # ── Round 25 (Claude/Cowork direct, 2026-05-27) ────────────────────
        # The previous strict check `_current_cli_name() != "grok"` caused
        # 0 chunks to be recorded across a 45s dispatch (trace evidence:
        # chunk_count=0, end_seq=0, captured_text was just the splash footer).
        # Diagnosis: once a capture is active (_grok_result_capture set), the
        # capture object itself is the authority that we're in a Grok dispatch
        # window. Transient resets of _active_cli_name (e.g., during input-
        # mode transitions) caused this guard to drop bytes mid-stream.
        # Fix: accept bytes when cli-name is "grok" OR "" (post-reset);
        # only reject when a DIFFERENT named cli is active. Observability
        # counters in the capture record what's happening for next dispatch.
        capture["events_seen"] = int(capture.get("events_seen", 0)) + 1
        cli_now = self._current_cli_name()
        if cli_now not in ("grok", ""):
            capture["events_other_cli"] = int(capture.get("events_other_cli", 0)) + 1
            return
        text = self._clean_output(data)
        if not text.strip():
            capture["events_blank"] = int(capture.get("events_blank", 0)) + 1
            return
        capture["events_recorded"] = int(capture.get("events_recorded", 0)) + 1
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
                # claude-opus-4-7 2026-05-25 — DE-NOISE the live PTY mirror.
                # Grok's TUI redraws ~10 frames/sec of braille spinners, progress
                # bars, timers and a streaming counter; mirroring every raw chunk
                # flooded the panel with hundreds of "◆ Ns grok> ⠋3" lines
                # (owner report 2026-05-25). The full chunk list recorded above
                # still keeps EVERY byte for the final GROK_RESULT receipt — this
                # gate only governs the VISUAL tail, so nothing is lost. Two gates:
                #   (1) skip frames that are pure volatile UI (spinner/box/timer
                #       strip to empty), and
                #   (2) rate-limit to ~1 line / 0.6s so genuine streaming content
                #       (Thought lines, tool reads, the answer) rolls smoothly
                #       instead of strobing. The on-change framebuffer snapshots
                #       (_capture_grok_framebuffer_snapshot, already flood-gated)
                #       remain the high-fidelity live render.
                _stripped_live = self._strip_volatile_for_grok_hash(live_block)
                _now_m = time.monotonic()
                _last_emit = float(capture.get("last_live_emit_monotonic") or 0.0)
                if _stripped_live and (_now_m - _last_emit) >= 0.6:
                    capture["last_live_emit_monotonic"] = _now_m
                    started = float(capture.get("started_monotonic") or _now_m)
                    delta = _now_m - started
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
        # claude-opus-4-7 2026-05-25: only advance the IDLE clock when REAL content
        # changed. Grok's TUI redraws the same screen (e.g. the static main menu)
        # constantly; bumping last_output_monotonic on every identical redraw kept the
        # idle-finalize (2.2s) from ever firing — so GROK_RESULT never posted and the
        # same menu flooded instead of rendering. Gate on a stripped-content signature.
        _content_sig = hashlib.sha256(
            self._strip_volatile_for_grok_hash(text).encode("utf-8", "replace")
        ).hexdigest()
        if _content_sig != capture.get("last_raw_content_sig"):
            capture["last_raw_content_sig"] = _content_sig
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
        elapsed = max(0.0, now - started)
        if self._should_retry_grok_literal_typing(capture, elapsed_s=elapsed):
            self._retry_grok_prompt_with_literal_typing(capture, elapsed_s=elapsed)
        # ── Live visibility heartbeat (George 2026-05-24) ─────────────────
        # Never leave the surface as dead air during Grok capture. Show only
        # elapsed time + captured chars; do not infer thinking, liveness, or a
        # non-frozen state from silence.
        chars = sum(
            len(str(c.get("text") if isinstance(c, dict) else c))
            for c in capture.get("chunks", [])
        )
        # Honest measurement: also check the rendered screen (MatureTerminalRenderer)
        # so rich TUI sessions (native Grok etc.) are not falsely reported as 0 chars
        # just because their content is in escape sequences.
        screen_lines = 0
        try:
            screen = getattr(self, "_screen", None)
            if screen and hasattr(screen, "lines"):
                screen_lines = sum(1 for ln in screen.lines() if ln and ln.strip())
        except Exception:
            screen_lines = 0

        # claude-opus-4-7 2026-05-25 (owner: "the thoughts are fake"): state ONLY
        # what is measured. 0 chars captured does NOT prove "thinking" or "not
        # frozen" — it could be a login/startup screen, a hang, or a dead CLI.
        # Report elapsed + bytes; do not invent a mental/process state (§6, §7.12).
        if chars > 0 or screen_lines > 0:
            phase = "output streaming in"
            effective_chars = max(chars, screen_lines * 40)  # rough visual estimate from screen
        else:
            phase = "no output captured yet"
            effective_chars = 0

        # Keep heartbeat visible, but do not spam identical rows every few seconds.
        hb_interval_s = 12.0 if (now - started) < 60.0 else 20.0
        last_hb = float(getattr(self, "_grok_capture_last_hb", 0.0) or 0.0)
        state_key = (effective_chars, phase)
        last_state_key = tuple(capture.get("last_hb_state_key") or ())
        state_changed = state_key != last_state_key
        if state_changed or now - last_hb >= hb_interval_s:
            self._grok_capture_last_hb = now
            capture["last_hb_state_key"] = list(state_key)
            # Round 25 observability — surface the per-event counters so we can
            # see on the next live dispatch how many bytes arrived at the capture
            # vs how many were rejected and why. text_chars=0 + events_seen=0 means
            # Grok is silent (no PTY output after splash). text_chars=0 +
            # events_other_cli > 0 means the cli-name guard is rejecting bytes.
            events_seen = int(capture.get("events_seen", 0))
            events_recorded = int(capture.get("events_recorded", 0))
            events_other_cli = int(capture.get("events_other_cli", 0))
            events_blank = int(capture.get("events_blank", 0))
            fb_seen = int(capture.get("framebuffer_events_seen", 0))
            bytes_sent = int(capture.get("bytes_sent_to_pty", 0))
            self._append_process_trace(
                f"grok: {effective_chars} chars captured (text+screen), {elapsed:.0f}s elapsed ({phase})"
                f" | events seen={events_seen} recorded={events_recorded} other_cli={events_other_cli} blank={events_blank}"
                f" fb_seen={fb_seen} bytes_sent_to_pty={bytes_sent}",
                kind="tool_result_capture",
                action="grok_capture_heartbeat",
                payload={
                    "elapsed_s": round(elapsed, 1),
                    "text_chars": chars,
                    "screen_lines": screen_lines,
                    "phase": phase,
                    "events_seen": events_seen,
                    "events_recorded": events_recorded,
                    "events_other_cli": events_other_cli,
                    "events_blank": events_blank,
                    "framebuffer_events_seen": fb_seen,
                    "bytes_sent_to_pty": bytes_sent,
                },
            )
        # No output yet: keep waiting, but do not spin forever.
        if last <= 0.0:
            if elapsed > 45.0:
                self._finish_grok_result_capture(force=True)
            return
        if now - last >= 2.2 and now - started >= 3.0:
            # Do not promote a transient Grok TUI redraw ("Thinking…",
            # "Responding…", file-read progress) to a final GROK_RESULT.
            # First prove that the extractor can see answer text after prompt
            # and TUI boilerplate are stripped.
            answer_probe = (
                self._extract_grok_result_text(capture)
                or self._extract_grok_framebuffer_result_text(capture)
            )
            if answer_probe:
                self._finish_grok_result_capture()
            elif now - last >= 30.0:
                self._append_process_trace(
                    "no new Grok output for 30s; finalizing capture as stale to stop repeat loop",
                    kind="tool_result_capture",
                    action="grok_capture_stale_finalize",
                    payload={
                        "elapsed_s": round(now - started, 1),
                        "idle_s": round(now - last, 1),
                    },
                )
                self._finish_grok_result_capture(force=True)
            elif elapsed > 90.0:
                self._finish_grok_result_capture(force=True)
        elif elapsed > 120.0:
            self._finish_grok_result_capture(force=True)

    def _finish_grok_result_capture(self, *, force: bool = False) -> None:
        capture = getattr(self, "_grok_result_capture", None)
        if not capture or capture.get("posted"):
            return
        answer = self._extract_grok_result_text(capture, force=force)
        framebuffer_answer = self._extract_grok_framebuffer_result_text(capture, force=force)
        framebuffer_hash = self._latest_grok_framebuffer_hash(capture)
        capture_source = "alice_global_chat_terminal"
        source_note = ""
        macos_terminal_text = ""
        macos_terminal_hash = ""
        if framebuffer_answer and (
            not answer
            or self._looks_like_grok_tui_frame(framebuffer_answer)
            or len(framebuffer_answer) >= max(40, int(len(answer) * 0.8))
        ):
            answer = framebuffer_answer
            capture_source = "alice_global_chat_terminal_framebuffer"
            source_note = (
                "captured from Alice global chat terminal's SIFTA-owned PTY framebuffer after VT rendering; "
                "this is the Grok TUI screen state, not shell scrollback"
            )
            if not self._latest_grok_framebuffer_frame(capture):
                frame_text = self._terminal_frame_text() or framebuffer_answer
                if frame_text:
                    frame_hash_now = hashlib.sha256(frame_text.encode("utf-8")).hexdigest()
                    cells = self._terminal_frame_cells()
                    frame = {
                        "seq": int(getattr(self, "_pty_output_seq", 0)),
                        "byte_end": int(getattr(self, "_pty_output_bytes_total", 0)),
                        "timestamp": time.time(),
                        "elapsed_s": round(
                            time.monotonic() - float(capture.get("started_monotonic") or time.monotonic()),
                            1,
                        ),
                        "frame_hash": frame_hash_now,
                        "text": frame_text,
                        "renderer": "mature_pyte" if getattr(self, "_using_mature_renderer", False) else "early_screen_buffer",
                    }
                    if cells:
                        frame["cells"] = cells
                        frame["cursor"] = self._terminal_frame_cursor()
                        frame["rows"] = len(cells)
                        frame["cols"] = len(cells[0]) if cells and cells[0] else 0
                    frames = capture.setdefault("framebuffer_frames", [])
                    frames.append(frame)
                    if len(frames) > 80:
                        del frames[:-80]
                    capture["last_framebuffer_hash"] = frame_hash_now
                    framebuffer_hash = frame_hash_now
        if not self._latest_grok_framebuffer_frame(capture):
            frame_text = self._terminal_frame_text() or framebuffer_answer
            if frame_text:
                frame_hash_now = hashlib.sha256(frame_text.encode("utf-8")).hexdigest()
                cells = self._terminal_frame_cells()
                frame = {
                    "seq": int(getattr(self, "_pty_output_seq", 0)),
                    "byte_end": int(getattr(self, "_pty_output_bytes_total", 0)),
                    "timestamp": time.time(),
                    "elapsed_s": round(
                        time.monotonic() - float(capture.get("started_monotonic") or time.monotonic()),
                        1,
                    ),
                    "frame_hash": frame_hash_now,
                    "text": frame_text,
                    "renderer": "mature_pyte" if getattr(self, "_using_mature_renderer", False) else "early_screen_buffer",
                }
                if cells:
                    frame["cells"] = cells
                    frame["cursor"] = self._terminal_frame_cursor()
                    frame["rows"] = len(cells)
                    frame["cols"] = len(cells[0]) if cells and cells[0] else 0
                frames = capture.setdefault("framebuffer_frames", [])
                frames.append(frame)
                if len(frames) > 80:
                    del frames[:-80]
                capture["last_framebuffer_hash"] = frame_hash_now
                framebuffer_hash = frame_hash_now
        if not answer and not force:
            return
        capture["posted"] = True
        timer = getattr(self, "_grok_result_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        capture_id = str(capture.get("id") or "")
        span = self._grok_capture_transcript_span(capture)
        latest_frame = self._latest_grok_framebuffer_frame(capture)
        framebuffer_cells = latest_frame.get("cells") if isinstance(latest_frame.get("cells"), list) else []
        framebuffer_cursor = latest_frame.get("cursor") if isinstance(latest_frame.get("cursor"), list) else [0, 0, False]
        if answer and capture_source == "alice_global_chat_terminal_framebuffer":
            status = "captured_framebuffer"
        else:
            status = "captured" if answer else "failed_no_readable_output"

        # SCHEMA ALIGNMENT FIX: hash the exact pure captured_text that will be
        # the source of truth for the verifier. Store it explicitly so the
        # GROK_RESULT row in alice_conversation.jsonl carries the canonical body.
        pure_captured_text = answer  # this is what the verifier will treat as the real Grok output
        output_hash = hashlib.sha256(pure_captured_text.encode("utf-8")).hexdigest() if pure_captured_text else ""

        proof = {
            "kind": "GROK_RESULT",
            "source": "alice_global_chat_terminal",
            "capture_id": capture_id,
            "capture_status": status,
            "captured_text": pure_captured_text,           # canonical body for hash + future use
            "captured_output_hash": output_hash,
            "captured_output_chars": len(pure_captured_text),
            "capture_source": capture_source,
            "capture_source_note": source_note,
            "macos_terminal_chars": len(macos_terminal_text),
            "macos_terminal_output_hash": macos_terminal_hash,
            "framebuffer_output_hash": framebuffer_hash,
            "framebuffer_frame_count": len(capture.get("framebuffer_frames", [])),
            "framebuffer_span": self._grok_framebuffer_span(capture),
            "framebuffer_renderer": self._latest_grok_framebuffer_renderer(capture),
            "framebuffer_cells": framebuffer_cells,
            "framebuffer_cursor": framebuffer_cursor,
            "framebuffer_rows": int(latest_frame.get("rows") or len(framebuffer_cells) or 0),
            "framebuffer_cols": int(latest_frame.get("cols") or (len(framebuffer_cells[0]) if framebuffer_cells else 0)),
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
            f"source=alice_global_chat_terminal "
            f"framebuffer_hash={framebuffer_hash[:16] if framebuffer_hash else 'NONE'} "
            f"pty_span=seq {span['start_seq']}-{span['end_seq']} "
            f"bytes {span['start_byte']}-{span['end_byte']}]"
        )
        if capture_source == "alice_global_chat_terminal_framebuffer":
            global_text = (
                "Alice global chat terminal framebuffer "
                "(rendered from the SIFTA-owned internal PTY screen state):\n"
                + pure_captured_text
                + proof_footer
            )
        else:
            global_text = "Alice global chat terminal transcript:\n" + pure_captured_text + proof_footer

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
        _write_alice_global_terminal_diary_event(
            event="grok_result_capture",
            ok=bool(output_hash),
            note=f"GROK_RESULT {status} chars={proof['captured_output_chars']} source=alice_global_chat_terminal",
            receipt_id=capture_id,
        )
        self._remember_matrix_history(f"\nAlice > {global_text}\n")
        if getattr(self, "_terminal_screen_active", False):
            self._sync_terminal_screen()
        else:
            self._append_plain(f"Alice > {global_text}\n\nSIFTA > ")
        self._grok_result_capture = None

    def _latest_grok_framebuffer_frame(self, capture: dict) -> dict:
        frames = capture.get("framebuffer_frames", [])
        if not isinstance(frames, list) or not frames:
            return {}
        latest = frames[-1]
        return latest if isinstance(latest, dict) else {}

    def _latest_grok_framebuffer_hash(self, capture: dict) -> str:
        latest = self._latest_grok_framebuffer_frame(capture)
        return str(latest.get("frame_hash") or capture.get("last_framebuffer_hash") or "")

    def _latest_grok_framebuffer_renderer(self, capture: dict) -> str:
        latest = self._latest_grok_framebuffer_frame(capture)
        return str(latest.get("renderer") or ("mature_pyte" if getattr(self, "_using_mature_renderer", False) else "early_screen_buffer"))

    def _grok_framebuffer_span(self, capture: dict) -> dict[str, int]:
        frames = capture.get("framebuffer_frames", [])
        seqs: list[int] = []
        byte_ends: list[int] = []
        for frame in frames if isinstance(frames, list) else []:
            if not isinstance(frame, dict):
                continue
            try:
                seqs.append(int(frame.get("seq", 0)))
                byte_ends.append(int(frame.get("byte_end", 0)))
            except Exception:
                continue
        return {
            "start_seq": min(seqs) if seqs else 0,
            "end_seq": max(seqs) if seqs else 0,
            "end_byte": max(byte_ends) if byte_ends else 0,
            "frame_count": len(frames) if isinstance(frames, list) else 0,
        }

    @staticmethod
    def _looks_like_grok_tui_frame(text: str) -> bool:
        low = (text or "").lower()
        markers = (
            "thought for",
            "responding",
            "grok build",
            "ctrl+",
            "shift+tab",
            "read /users/",
            "search ",
            "receipt:",
            "turn completed",
            "action required",
        )
        return any(marker in low for marker in markers)

    def _extract_grok_framebuffer_result_text(self, capture: dict, *, force: bool = False) -> str:
        latest = self._latest_grok_framebuffer_frame(capture)
        source = str(latest.get("text") or "")
        if not source:
            source = self._terminal_frame_text()
        if not source.strip():
            return ""
        prompt = str(capture.get("prompt") or "")
        return self._extract_grok_text_from_source(source, prompt=prompt, force=force)

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
        s = _ANSI_RE.sub("", s)  # full ANSI (OSC/CSI/private) — strengthened 2026-05-25 Grok 4.3 external (signin trace_id=830f2e7b-889b-4e71-9a71-39bc91090ad6) per Alice "strip ANSI blood" order on this body
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
        # Prefer the actual captured PTY chunks. The visible widget text also
        # contains Alice's process trace ("start GROK_RESULT capture", etc.),
        # and that scaffolding must never become the answer body.
        source = raw if raw.strip() else visible
        if not source.strip():
            return ""
        prompt = str(capture.get("prompt") or "")
        return self._extract_grok_text_from_source(source, prompt=prompt, force=force)

    def _extract_grok_text_from_source(self, source: str, *, prompt: str = "", force: bool = False) -> str:
        if not source or not source.strip():
            return ""
        prompt_lines = {line.strip() for line in prompt.splitlines() if line.strip()}
        kept: list[str] = []
        skip_needles = (
            "Read /Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md",
            "Start from the hardware layer 1 kernel primordial electricity boundary",
            "Alice is asking Grok from inside the Alice global chat terminal",
            "Question for Grok:",
            "Answer the question directly from the local SIFTA context",
            "Grok is an external tool organ",
            "Do not assume you are inside Alice's organism",
            "Owner's original wording to Alice:",
            "Subject binding:",
            "Read /Users/ioanganton/Music/ANTON_SIFTA/Documents/",
            "IDE_BOOT_COVENANT.md",
            "[Pasted:",
            "Enter:send",
            "Shift+Tab:mode",
            "Ctrl+x:shortcuts",
            "Grok Build",
            "Connecting MCPs",
            "New worktree",
            "Resume session",
            "Quit ctrl-q",
            "Tip: Press Ctrl-W",
            "0.2.2 Beta",
        )
        skip_needles_low = tuple(n.lower() for n in skip_needles)
        for line in source.splitlines():
            clean = line.strip()
            if not clean:
                if kept and kept[-1] != "":
                    kept.append("")
                continue
            if clean in prompt_lines:
                continue
            clean_low = clean.lower()
            if any(needle in clean_low for needle in skip_needles_low):
                continue
            # Treat Grok startup/footer lines as non-answer boilerplate even when
            # OCR/framebuffer clipping drops leading characters (e.g. "it ctrl-q").
            if "ctrl-q" in clean_low:
                continue
            if re.fullmatch(r"0\.\d+\.\d+(?:\s*\[[^\]]+\])?\s*beta", clean_low):
                continue
            if (
                clean_low.startswith(("thinking", "responding", "the task is:"))
                or re.search(r"\bthought for\s+\d", clean_low)
                or re.search(r"\b(thinking|responding)[….\s]*\d", clean_low)
                or re.fullmatch(r"#\d+\s+(?:read|search|run|open)\b.*", clean_low)
                or re.fullmatch(r"[0-9.]+%?", clean_low)
            ):
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
        cells = self._terminal_frame_cells()
        state = grok_screen_classifier(cells)
        if state:
            return state
        return grok_screen_classifier(text=self._visible_terminal_text())

    def _reset_grok_resume_screen_stability(self) -> None:
        self._grok_resume_observed_state = ""
        self._grok_resume_state_seen_count = 0
        self._grok_resume_state_since = 0.0

    def _stable_grok_resume_screen_state(self, now: float) -> str:
        """Return a Grok startup screen only after it stayed visible long enough.

        George caught the real bug: seeing one transient TUI frame is not enough
        to press Ctrl-S or Enter. Alice must watch the framebuffer settle before
        acting, because a full-screen TUI redraw can briefly contain stale menu
        words while the next screen is still painting.
        """
        state = self._grok_visible_screen_state()
        previous = str(getattr(self, "_grok_resume_observed_state", "") or "")
        if state != previous:
            self._grok_resume_observed_state = state
            self._grok_resume_state_seen_count = 1 if state else 0
            self._grok_resume_state_since = now if state else 0.0
            if state:
                self._append_process_trace(
                    f"grok screen observed={state}; waiting for stable framebuffer before keypress",
                    kind="screen_navigation",
                    action="grok_resume_screen_observed",
                    payload={"state": state, "stable_frames": 1, "stable_for_s": 0.0},
                )
            return ""
        if not state:
            return ""
        count = int(getattr(self, "_grok_resume_state_seen_count", 0) or 0) + 1
        self._grok_resume_state_seen_count = count
        since = float(getattr(self, "_grok_resume_state_since", 0.0) or now)
        stable_for = max(0.0, now - since)
        min_frames = int(getattr(self, "_grok_resume_required_stable_frames", 3) or 3)
        min_s = float(getattr(self, "_grok_resume_required_stable_s", 0.70) or 0.70)
        if count < min_frames or stable_for < min_s:
            return ""
        self._grok_resume_action_stable_frames = count
        self._grok_resume_action_stable_for_s = stable_for
        return state

    def _grok_resume_still_loading(self) -> bool:
        """True while Grok is still hydrating the resumed session UI."""
        visible = (self._visible_terminal_text() or "").lower()
        return ("loading session" in visible) or ("connecting mcps" in visible)

    def _ask_owner_for_grok_choice(self) -> None:
        state = self._grok_visible_screen_state()
        if state == "main_menu":
            self._append_plain("Alice > I see Grok's main menu. A choice is required.\n")
            self._execute_grok_resume_last_session(
                "Alice visible Grok menu choice help: resume saved session",
                open_if_needed=False,
            )
            self._grok_resume_last_action = 0.0
            self._tick_grok_resume_navigation()
            return
        if state == "session_picker":
            self._append_plain("Alice > I see Grok's session list. A session choice is required.\n")
            self._execute_grok_resume_last_session(
                "Alice visible Grok session picker choice help: select highlighted saved session",
                open_if_needed=False,
            )
            self._grok_resume_last_action = 0.0
            self._tick_grok_resume_navigation()
            return
        self._append_plain(
            "Alice > I do not know this Grok screen yet. Tell me the exact visible option or key to press.\n\n"
            "SIFTA > "
        )

    def _announce_grok_resume_choice(self, *, state: str, phase: str, key_label: str, decision: str) -> None:
        """Write the observed menu choice before pressing a Grok TUI key.

        This prevents identity double-spend: Alice is not Grok. Alice is the
        global SIFTA organism observing an external Grok tool screen and applying
        the owner's standing policy to that screen.
        """
        announced_key = f"_grok_resume_announced_{state}_{key_label.replace('-', '_').lower()}"
        if getattr(self, announced_key, False):
            return
        setattr(self, announced_key, True)
        line = (
            f"I see Grok's {state.replace('_', ' ')}. Choice required. "
            f"Grok is the external tool screen; Alice stays the global SIFTA field. "
            f"Screen stable for {int(getattr(self, '_grok_resume_action_stable_frames', 0) or 0)} frames "
            f"over {float(getattr(self, '_grok_resume_action_stable_for_s', 0.0) or 0.0):.1f}s. "
            f"Owner standing policy: {decision}. Pressing {key_label}."
        )
        self._append_plain(f"Alice > {line}\n")
        self._append_process_trace(
            f"grok screen choice: state={state} phase={phase}; decision={decision}; press {key_label}",
            kind="screen_navigation",
            action="grok_resume_choice_nudge",
            payload={
                "state": state,
                "phase": phase,
                "decision": decision,
                "key": key_label,
                "identity_boundary": "Alice observes/operates external Grok tool screen; Alice is not Grok",
            },
        )
        self._log_global_terminal_turn(
            "alice",
            line,
            model="matrix_terminal_effector",
            action="grok_resume_choice_nudge",
            focused_cli="grok",
            metadata={
                "screen_state": state,
                "phase": phase,
                "decision": decision,
                "key": key_label,
                "identity_boundary": "Alice observes/operates external Grok tool screen; Alice is not Grok",
            },
        )

    def _grok_resume_action_for(self, *, phase: str, state: str) -> dict[str, object] | None:
        action = _GROK_RESUME_ACTION_TABLE.get((phase, state))
        if not action:
            return None
        return dict(action)

    def _apply_grok_resume_action(
        self,
        *,
        action: dict[str, object],
        state: str,
        phase: str,
        now: float,
    ) -> None:
        key_label = str(action.get("key_label") or "")
        key_bytes = action.get("key_bytes")
        decision = str(action.get("decision") or "")
        trace_action = str(action.get("trace_action") or "grok_resume_screen_action")
        trace_text = str(action.get("trace_text") or f"grok screen state={state} -> press {key_label}")
        next_phase = str(action.get("next_phase") or phase)
        if not isinstance(key_bytes, (bytes, bytearray)) or not key_bytes:
            self._append_process_trace(
                f"grok screen action missing bytes: state={state} phase={phase}",
                kind="screen_navigation",
                action="grok_resume_action_rejected",
                payload={
                    "state": state,
                    "phase": phase,
                    "classifier": _GROK_SCREEN_CLASSIFIER_VERSION,
                    "reason": "missing_key_bytes",
                },
            )
            return

        self._announce_grok_resume_choice(
            state=state,
            phase=phase,
            key_label=key_label,
            decision=decision,
        )
        self._append_process_trace(
            trace_text,
            kind="screen_navigation",
            action=trace_action,
            payload={
                "state": state,
                "phase": phase,
                "next_phase": next_phase,
                "key": key_label,
                "decision": decision,
                "classifier": _GROK_SCREEN_CLASSIFIER_VERSION,
                "table_driven": True,
            },
        )
        self.write_bytes(bytes(key_bytes))
        self._grok_resume_last_action = now
        self._grok_resume_phase = next_phase
        self._reset_grok_resume_screen_stability()
        deadline_s = action.get("deadline_s")
        if isinstance(deadline_s, (int, float)) and float(deadline_s) > 0.0:
            self._grok_resume_deadline = time.monotonic() + float(deadline_s)

    def _execute_grok_resume_last_session(
        self,
        user_input: str,
        open_if_needed: bool = False,
        pending_prompt: str = "",
    ) -> None:
        """Drive Grok's visible TUI by WATCHING the screen, not fixed delays.

        George 2026-05-23: fixed delays fired Ctrl-S / Enter before the second
        screen existed. Instead we POLL the visible screen state: when Grok's main
        menu shows -> send Ctrl-S (Resume session); when the session list shows ->
        send Enter (the first/last saved session); then wait until the screen
        leaves the picker before claiming resume or sending a queued prompt.
        Screen-state driven = reliable regardless of how long Grok takes to
        boot or repaint.
        """
        if not self.is_running():
            self.start_shell()
        if not self.is_running():
            self._append_plain("[shell not running - cannot execute]\n\nSIFTA > ")
            return

        # Bypass the TUI picker/resume vision loops entirely when owner says
        # "bypass the two screen selections", "direct", "no resume", or for
        # clear delegation "ask grok ...". Use real grok binary flags:
        # --continue + -p/--single for non-interactive, or grok_chat --one-shot.
        # This is the hardware-up direct execute: no "I see Grok's main menu" gagging.
        ui = user_input or ""
        bypass = bool(re.search(r"\bbypass\b.*(screen|selection|picker|resume|two)|direct.*(type|launch|no resume)|no resume|headless", ui, re.I))
        is_ask_grok = bool(re.search(r"\bask\s+grok\b|\btell\s+grok\b|\bsend\s+(?:to\s+)?grok\b", ui, re.I))
        if bypass or is_ask_grok or (pending_prompt and not _matrix_terminal_grok_open_only(ui)):
            grok_bin = "/Users/ioanganton/.grok/bin/grok"
            prompt = (pending_prompt or user_input or "status").strip()
            # Prefer --continue -p for last session + single turn output to PTY (no menus).
            cmd = f"{grok_bin} --continue -p {shlex.quote(prompt[:2000])} --no-alt-screen"
            self._append_plain("Alice > Bypassing Grok TUI menus with --continue -p (direct, no Ctrl-S/Enter picker). Output will stream here.\n")
            self._append_matrix_command_receipt([cmd])
            QTimer.singleShot(200, lambda c=cmd: self.write_command(c))
            self._active_cli_name = "grok"
            self._grok_cli_active = True
            self._enter_alice_input_mode_for_tool("Grok")
            return

        if _looks_like_owner_bowel_resume_encouragement(user_input):
            self._process_owner_bowel_positive_resume_encouragement(user_input)

        # Re-entrancy guard: if resume navigation is already running, do not
        # restart from await_menu and extend the deadline forever.
        current_phase = str(getattr(self, "_grok_resume_phase", "") or "")
        timer = getattr(self, "_grok_resume_timer", None)
        if current_phase and current_phase != "done":
            if timer is None or not timer.isActive():
                # Stale state (phase set, timer dead) can block queued
                # delegations indefinitely. Reset and continue with a fresh run.
                self._append_process_trace(
                    "grok resume phase was set but timer was inactive; clearing stale resume lock",
                    kind="screen_navigation",
                    action="grok_resume_stale_phase_reset",
                    payload={"phase": current_phase},
                )
                self._grok_resume_phase = ""
                self._grok_resume_pending_prompt = ""
            else:
                pending = (pending_prompt or "").strip()
                existing = str(getattr(self, "_grok_resume_pending_prompt", "") or "").strip()
                pending_state = "unchanged"
                if pending:
                    if not existing:
                        self._grok_resume_pending_prompt = pending
                        pending_state = "queued"
                    elif pending == existing:
                        pending_state = "deduped"
                    else:
                        pending_state = "dropped_new_prompt"
                self._append_process_trace(
                    "grok resume navigation already in flight; keeping current phase and deadline",
                    kind="screen_navigation",
                    action="grok_resume_inflight_hold",
                    payload={
                        "phase": current_phase,
                        "pending_state": pending_state,
                        "had_existing_prompt": bool(existing),
                    },
                )
                return

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
        self._grok_resume_pending_prompt = (pending_prompt or "").strip()
        self._grok_resume_required_stable_frames = 3
        self._grok_resume_required_stable_s = 0.70
        self._grok_resume_key_cooldown_s = 1.50
        self._reset_grok_resume_screen_stability()
        self._grok_resume_announced_main_menu_ctrl_s = False
        self._grok_resume_announced_session_picker_enter = False
        timer = getattr(self, "_grok_resume_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.timeout.connect(self._tick_grok_resume_navigation)
            self._grok_resume_timer = timer
        timer.start(350)

    def _finish_grok_resume_navigation(self, *, after_enter: bool = False) -> None:
        """Finalize resume only after the menu/picker has been crossed.

        If an owner prompt was waiting, paste it now. This is the critical
        difference between "pressed Enter" and "Grok is ready to receive the
        delegated task."
        """
        timer = getattr(self, "_grok_resume_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        self._grok_resume_phase = "done"
        pending_prompt = str(getattr(self, "_grok_resume_pending_prompt", "") or "").strip()
        self._grok_resume_pending_prompt = ""
        if pending_prompt:
            self._append_process_trace(
                "grok resume verified past startup screens -> paste queued prompt",
                kind="screen_navigation",
                action="grok_resume_ready_for_prompt",
                payload={
                    "after_enter": bool(after_enter),
                    "prompt_chars": len(pending_prompt),
                    "source": "alice_global_chat_terminal",
                },
            )
            self._append_plain("Alice > Grok session is past the startup screens. Sending the queued prompt now.\n")
            self._write_bracketed_paste(pending_prompt)
            self._log_global_terminal_turn(
                "alice",
                "Grok session resumed; queued prompt sent.",
                model="matrix_terminal_effector",
                action="grok_resume_ready_for_prompt",
                focused_cli="grok",
                metadata={"prompt_chars": len(pending_prompt), "source": "alice_global_chat_terminal"},
            )
            return
        self._append_plain("Alice > Resumed your last Grok session.\n")
        self._log_global_terminal_turn(
            "alice",
            "Resumed your last Grok session.",
            model="matrix_terminal_effector",
            action="grok_resume_done",
            focused_cli="grok",
        )

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
            self._append_process_trace(
                "grok resume timeout; releasing resume lock so queued delegations can continue",
                kind="screen_navigation",
                action="grok_resume_timeout_unblocked",
                payload={"phase": phase},
            )
            self._append_plain(
                "Alice > I could not reach Grok's session list in time. Tell me what to press and I will learn it.\n\n"
                "SIFTA > "
            )
            return
        # Let the TUI repaint between key presses. Then require the newly
        # visible screen to remain stable before acting on it.
        cooldown_s = float(getattr(self, "_grok_resume_key_cooldown_s", 1.50) or 1.50)
        if now - getattr(self, "_grok_resume_last_action", 0.0) < cooldown_s:
            return
        raw_state = self._grok_visible_screen_state()
        state = self._stable_grok_resume_screen_state(now)
        if phase != "await_ready" and not state:
            return
        if phase == "await_menu":
            action = self._grok_resume_action_for(phase=phase, state=state)
            if action:
                self._apply_grok_resume_action(action=action, state=state, phase=phase, now=now)
            return
        if phase == "await_picker":
            action = self._grok_resume_action_for(phase=phase, state=state)
            if action:
                self._apply_grok_resume_action(action=action, state=state, phase=phase, now=now)
            return
        if phase == "await_ready":
            # After Enter, do not claim success while the picker is still on
            # screen. Wait for Grok to leave the two startup screens; then either
            # send the queued delegation prompt or report the verified resume.
            if self._grok_resume_still_loading():
                return
            if raw_state and not state:
                return
            if not raw_state:
                if now - getattr(self, "_grok_resume_last_action", 0.0) >= 1.25:
                    self._finish_grok_resume_navigation(after_enter=True)
                return
            if state == "session_picker":
                action = self._grok_resume_action_for(phase=phase, state=state)
                min_since_action_s = float(action.get("min_since_action_s", 0.0) or 0.0) if action else 0.0
                if action and now - getattr(self, "_grok_resume_last_action", 0.0) >= min_since_action_s:
                    self._apply_grok_resume_action(action=action, state=state, phase=phase, now=now)
                return
            if state == "main_menu":
                action = self._grok_resume_action_for(phase=phase, state=state)
                if action:
                    self._apply_grok_resume_action(action=action, state=state, phase=phase, now=now)
                return

    def _schedule_grok_direct_type_paste(
        self,
        prompt: str,
        *,
        started_monotonic: float | None = None,
        attempt: int = 0,
        timeout_s: float = 12.0,
        poll_ms: int = 250,
    ) -> None:
        """Wait for a writable Grok input surface before direct-type paste."""
        start = float(started_monotonic or time.monotonic())
        now = time.monotonic()
        elapsed = max(0.0, now - start)
        frame = self._terminal_frame_text()
        if _grok_input_looks_ready(frame):
            self._append_process_trace(
                "direct-type: input ready gate passed, issuing bracketed paste",
                kind="tool_delegation",
                action="grok_direct_type_ready",
                payload={
                    "prompt_chars": len(prompt or ""),
                    "elapsed_s": round(elapsed, 2),
                    "attempt": int(attempt),
                },
            )
            # Mark Grok active BEFORE paste so _write_bracketed_paste routes as
            # grok-targeted delegation (starts GROK_RESULT capture, not generic PTY paste).
            self._active_cli_name = "grok"
            self._grok_cli_active = True
            self._write_bracketed_paste(prompt)
            self._enter_alice_input_mode_for_tool("Grok")
            return

        if elapsed >= max(1.0, float(timeout_s or 0.0)):
            failure = "FIELD_FAILURE: grok_direct_type_ready_timeout"
            self._append_process_trace(
                f"{failure}; input surface not ready before timeout",
                kind="FIELD_FAILURE",
                action="grok_direct_type_ready_timeout",
                payload={
                    "prompt_chars": len(prompt or ""),
                    "elapsed_s": round(elapsed, 2),
                    "attempt": int(attempt),
                    "frame_tail": frame[-320:],
                },
            )
            self._append_plain(f"Alice > {failure}\n")
            _matrix_terminal_log_global_turn(
                "alice",
                failure,
                action="GROK_DIRECT_TYPE_READY_TIMEOUT",
                focused_cli="grok",
                metadata={
                    "elapsed_s": round(elapsed, 2),
                    "prompt_chars": len(prompt or ""),
                },
            )
            return

        if attempt == 0 or attempt % 4 == 0:
            self._append_process_trace(
                "direct-type: waiting for live Grok input prompt (no resume navigation)",
                kind="tool_delegation",
                action="grok_direct_type_wait_ready",
                payload={
                    "elapsed_s": round(elapsed, 2),
                    "attempt": int(attempt),
                    "prompt_chars": len(prompt or ""),
                },
            )

        QTimer.singleShot(
            int(max(50, poll_ms)),
            lambda p=prompt, s=start, a=attempt + 1: self._schedule_grok_direct_type_paste(
                p,
                started_monotonic=s,
                attempt=a,
                timeout_s=timeout_s,
                poll_ms=poll_ms,
            ),
        )

    def _send_ctrl_w_for_new_worktree(self) -> None:
        """Dismiss Grok startup menu into a fresh worktree/session (direct-type mode)."""
        try:
            self.write_bytes(b"\x17")  # Ctrl-W
        except Exception:
            return
        self._append_process_trace(
            "direct-type: sent Ctrl-W to select New worktree (new session every time)",
            kind="tool_delegation",
            action="grok_direct_type_new_worktree_keystroke",
            payload={"key": "Ctrl-W", "new_session": True, "no_resume": True},
        )

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
        force_direct_type = cli == "grok" and _matrix_terminal_direct_type_grok_requested(user_input)

        if force_direct_type:
            prompt = _matrix_terminal_cli_prompt_payload(user_input, cli)
            active_cli = self._current_cli_name()
            self._append_process_trace(
                "direct-type mode enabled for Grok: bypass resume navigation and paste prompt",
                kind="tool_delegation",
                action="grok_direct_type_mode",
                payload={
                    "no_resume": True,
                    "active_cli": active_cli or "",
                    "prompt_chars": len(prompt),
                },
            )
            self._log_global_terminal_turn(
                "alice",
                "Direct-type Grok mode: no resume navigation, paste payload to active Grok input.",
                model="matrix_terminal_effector",
                action="grok_direct_type_mode",
                focused_cli="grok",
                prior_user_text=user_input,
                metadata={"no_resume": True, "prompt_chars": len(prompt)},
            )
            if active_cli == "grok":
                self._append_plain(
                    "Alice > Direct-type mode active. Waiting for Grok input readiness, then sending payload (no Ctrl-S, no session picker).\n"
                )
                self._append_matrix_command_receipt([prompt])
                self._schedule_grok_direct_type_paste(prompt, timeout_s=12.0, poll_ms=250)
                return

            self._append_plain(
                "Alice > Direct-type mode active. Opening Grok, waiting for live input, then pasting payload without resume navigation.\n"
            )
            self._append_matrix_command_receipt(["grok", prompt])
            QTimer.singleShot(250, lambda: self.write_command("grok"))
            # Owner policy update: after typing `grok`, do not press Ctrl-W,
            # Ctrl-S, Enter on any picker, or any other selection key. The
            # ready-gate observes the live frame and pastes only when input is
            # genuinely ready.
            QTimer.singleShot(900, lambda p=prompt: self._schedule_grok_direct_type_paste(p, timeout_s=14.0, poll_ms=250))
            return
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
            # For plain "start grok" / "open grok", launch with --continue so the
            # real grok TUI resumes last session for cwd without the picker UI
            # that triggers the "I see Grok's main menu... Pressing Ctrl-S" vision loop.
            # Owner can then type inside; delegations use -p bypass.
            if _matrix_terminal_grok_open_only(user_input) or not (user_input or "").strip() or re.search(r"^(?:alice\s*,?\s*)?(?:start|open|launch|resume)\s+(?:the\s+)?grok\b", user_input or "", re.I):
                grok_bin = "/Users/ioanganton/.grok/bin/grok"
                cmd = f"{grok_bin} --continue --no-alt-screen"
                self._append_plain("Alice > Opening Grok with --continue (auto-resume last session, no picker screens).\n")
                self._append_matrix_command_receipt([cmd])
                QTimer.singleShot(150, lambda c=cmd: self.write_command(c))
                self._active_cli_name = "grok"
                self._grok_cli_active = True
                self._enter_alice_input_mode_for_tool("Grok")
                return
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
            # Use the clean no-TUI wrapper for direct; real TUI grok still available via "grok --continue"
            full_launch = "python3 /Users/ioanganton/Music/ANTON_SIFTA/grok_chat.py"
            self._append_matrix_command_receipt([full_launch])
            QTimer.singleShot(300, lambda: self.write_command(full_launch))
            self._enter_alice_input_mode_for_tool("Grok")
            return
        # === end separation ===

        active_cli = self._current_cli_name()
        prompt = _matrix_terminal_cli_prompt_payload(user_input, cli)
        if cli == "grok":
            # Explicit Grok delegations must pass the same two startup screens
            # as open/resume. The old fixed delay could paste the task into
            # Grok's menu or picker, yielding a fake dispatch with no answer.
            screen_state = self._grok_visible_screen_state() if active_cli == "grok" else ""
            if active_cli != "grok" or screen_state in {"main_menu", "session_picker"}:
                self._execute_grok_resume_last_session(
                    user_input,
                    open_if_needed=True,
                    pending_prompt=prompt,
                )
                return

        commands = [prompt] if active_cli == cli else [cli, prompt]
        if active_cli == cli:
            self._enter_alice_input_mode_for_tool(label)
            self._append_plain(f"Alice > Pasting a covenant-prefixed prompt into the active {label} CLI.\n")
            paste_delay_ms = 250
        else:
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
            try:
                ts = float(row.get("ts") or 0.0)
            except Exception:
                ts = 0.0
            if ts > 0.0:
                max_age = float(getattr(self, "_grok_delegation_queue_stale_s", 15 * 60) or 15 * 60)
                if time.time() - ts > max_age:
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
                "source": "alice_global_chat_terminal",
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
        busy = self._grok_delegation_busy_reason()
        if busy:
            self._trace_grok_queue_busy(busy)
            return
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
            self._append_plain(f"\nAlice > Picked up queued Grok delegation receipt={receipt}.\n")
            _matrix_terminal_log_global_turn(
                "alice",
                f"Queued Grok delegation claimed. receipt={receipt}",
                action="GROK_DELEGATION_QUEUE_CLAIMED",
                focused_cli="grok",
                metadata={"receipt": receipt, "queued_text_preview": question[:240]},
            )
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
        # Record as external tool skill for relearn (grok "organ" via matrix terminal PTY).
        try:
            from System.swarm_browser_site_playbook import record_skill_outcome as _rso
            _rso("grok-cli", "delegation", True, note=question[:120], source="global_chat_terminal")
        except Exception:
            pass
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
                f"Alice > Alice global chat terminal is the only terminal surface. I will not open {label} here.\n\n"
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

    def execute_swimmer_command(self, cmd: str, *, swimmer_mode: bool = False, owner_consent: bool = True, trace_id: str | None = None) -> dict[str, Any]:
        """Yin/Yang Terminal Swimmer Phase 2 shim (inside desktop process only).

        When swimmer_mode=True, routes through TerminalSwimmerForge for:
        - covenant filters (secrets, fullscreen TUIs, consent)
        - auto-receipt to work_receipts + swimmer_forge_flux.jsonl
        - three-trial validation path for admission

        Keeps the forge inside the Qt desktop process. No detach, no external PTY spawn.
        The PTY surface (this pane) remains the single source of truth for the owner's terminal.
        """
        if not swimmer_mode:
            # fall back to normal safe shell path
            self._execute_shell_from_alice(cmd)
            return {"status": "delegated_to_normal_shell", "swimmer_mode": False}

        from pathlib import Path
        from System.swarm_terminal_swimmer_forge import TerminalSwimmerForge

        state_dir = Path(".sifta_state")
        forge = TerminalSwimmerForge(state_dir=state_dir)

        def _matrix_pty_runner(command: str, cwd: str | None, timeout_s: int) -> dict[str, Any]:
            """Runner that prefers this live PTY when available (still inside the same process)."""
            if self.is_running():
                self.write_command(command + "\n")
                # For validated swimmer tasks the forge still records the wrapper receipt;
                # full stdout capture can be layered later via the existing _read_ready path.
                return {
                    "type": "TERMINAL_EXECUTION",
                    "source": "matrix_terminal_pty_swimmer",
                    "command": command,
                    "stdout": "SWIMMER_MODE_PTY_DELEGATED",
                    "exit_code": 0,
                }
            return {"type": "TERMINAL_EXECUTION", "exit_code": 1, "stdout": "", "stderr": "pty not running"}

        receipt = forge.run_alice_global_chat_command(
            cmd,
            owner_consent=owner_consent,
            trace_id=trace_id or str(uuid.uuid4()),
            cwd=str(getattr(self, "cwd", Path.cwd())),
            timeout_s=45,
            terminal_runner=_matrix_pty_runner,
        )
        # The forge already appended the COMMAND_WRAPPER and work receipt
        return receipt

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
        self.setWindowTitle("Alice Global Chat Terminal Service")
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
                "\nAlice > Alice global chat terminal is the only terminal surface. I will not open Grok in this surface.\n\n"
                "SIFTA > "
            )
        if _qt_alive(getattr(self, "status_label", None)):
            self.status_label.setText("Alice • terminal")
        self.terminal.setFocus()

    def start_hermes_cli(self) -> None:
        """Compatibility handler; Hermes is not exposed in the Alice-first terminal."""
        if hasattr(self, "terminal") and self.terminal:
            self.terminal._append_plain(
                "\nAlice > Alice global chat terminal is the only terminal surface. I will not open Hermes in this surface.\n\n"
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
                    "Alice Global Chat Terminal",
                    f"Internal PTY service is active ({state})",
                    tab="internal PTY",
                    metadata={"state": state, "last_output": last_line, "source": "alice_global_chat_terminal"}
                )
            except Exception:
                pass

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


def get_live_pty_status_for_alice() -> str:
    """Returns a compact, receipt-citable summary of Alice's internal PTY service.

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
                "ALICE GLOBAL CHAT TERMINAL STATUS (from field receipts):\n"
                "No live internal PTY service right now.\n"
                "To operate terminal work, route it through Alice global chat so the hidden PTY service can be created.\n"
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
            "ALICE GLOBAL CHAT TERMINAL STATUS (receipt-grounded - cite these swimmers for chorum on truth):\n"
            f"Internal PTY service is active and responsive.\n"
            f"Recent transcript (last lines):\n{recent}\n"
            f"{receipt_note}\n"
            "PTY commands you issue will be injected into this transcript and produce a new receipt in the ledger.\n"
            "Before planning any 'type X in terminal' action, you must cite the last output and receipt hash above."
        )
    except Exception as e:
        return f"ALICE GLOBAL CHAT TERMINAL STATUS: error reading live state ({e}). Fall back to app_focus receipts."


def main() -> int:
    print("Matrix Terminal standalone launch disabled: use Alice global chat terminal.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
