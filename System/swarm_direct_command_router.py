"""Direct-command router — bypass cortex for PTY keystrokes.

Task #58: when the user says "press enter" or "type X", route directly
to the PTY keystroke writer instead of sending to the cortex for discussion.
Pure stdlib — no PyQt6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DirectCommand:
    is_direct: bool
    command_type: str = ""
    key_or_text: str = ""
    raw_input: str = ""


_KEY_MAP = {
    "enter": "\n",
    "return": "\n",
    "tab": "\t",
    "escape": "\x1b",
    "esc": "\x1b",
    "space": " ",
    "backspace": "\x7f",
    "delete": "\x1b[3~",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "left": "\x1b[C",
    "right": "\x1b[D",
    "ctrl-c": "\x03",
    "ctrl-d": "\x04",
    "ctrl-z": "\x1a",
    "ctrl-l": "\x0c",
    "ctrl-a": "\x01",
    "ctrl-e": "\x05",
}

_PRESS_KEY_PATTERN = re.compile(
    r"^(?:now\s+)?(?:press|hit|push|send|type)\s+(enter|return|tab|escape|esc|space|"
    r"backspace|delete|up|down|left|right|ctrl[- ][a-z])\s*$",
    re.IGNORECASE,
)

_TYPE_TEXT_PATTERN = re.compile(
    r'^(?:type|write|enter|input|send)\s+["\'](.+?)["\']\s*$',
    re.IGNORECASE,
)

_TYPE_COMMAND_PATTERN = re.compile(
    r"^(?:type|run|execute|send)\s+`(.+?)`\s*$",
    re.IGNORECASE,
)

_CTRL_PATTERN = re.compile(
    r"^(?:press\s+)?ctrl[- ]([a-z])\s*$",
    re.IGNORECASE,
)


def classify_as_direct_command(text: str) -> DirectCommand:
    if not text or not text.strip():
        return DirectCommand(is_direct=False, raw_input=text or "")

    clean = text.strip().rstrip(".")

    m = _PRESS_KEY_PATTERN.match(clean)
    if m:
        key_name = m.group(1).lower().replace(" ", "-")
        keystroke = _KEY_MAP.get(key_name)
        if keystroke is None and key_name.startswith("ctrl-"):
            letter = key_name[-1]
            keystroke = chr(ord(letter) - ord("a") + 1)
        if keystroke is not None:
            return DirectCommand(
                is_direct=True,
                command_type="keystroke",
                key_or_text=keystroke,
                raw_input=text,
            )

    m = _TYPE_TEXT_PATTERN.match(clean)
    if m:
        return DirectCommand(
            is_direct=True,
            command_type="type_text",
            key_or_text=m.group(1),
            raw_input=text,
        )

    m = _TYPE_COMMAND_PATTERN.match(clean)
    if m:
        return DirectCommand(
            is_direct=True,
            command_type="type_command",
            key_or_text=m.group(1) + "\n",
            raw_input=text,
        )

    m = _CTRL_PATTERN.match(clean)
    if m:
        letter = m.group(1).lower()
        keystroke = chr(ord(letter) - ord("a") + 1)
        return DirectCommand(
            is_direct=True,
            command_type="keystroke",
            key_or_text=keystroke,
            raw_input=text,
        )

    return DirectCommand(is_direct=False, raw_input=text)


def extract_keystroke(text: str) -> str | None:
    cmd = classify_as_direct_command(text)
    if cmd.is_direct:
        return cmd.key_or_text
    return None


__all__ = [
    "DirectCommand",
    "classify_as_direct_command",
    "extract_keystroke",
]
