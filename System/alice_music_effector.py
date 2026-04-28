#!/usr/bin/env python3
"""Alice's small, truthful macOS music effector.

This organ does not pretend to own a streaming catalog. It can ask the local
macOS Music app to start or toggle playback and leaves a ledger receipt.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "alice_music_effector.jsonl"
_YOUTUBE_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:youtube\.com/|youtu\.be/)",
    re.IGNORECASE,
)


def _deposit(row: Dict[str, Any]) -> Dict[str, Any]:
    row.setdefault("ts", time.time())
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(_LEDGER, line)
    except Exception:
        with _LEDGER.open("a", encoding="utf-8") as handle:
            handle.write(line)
    return row


def play(*, mood: str = "", source: str = "Music.app") -> Dict[str, Any]:
    """Ask macOS Music.app to begin playback.

    If Music.app has no queue/library item selected, AppleScript may still
    succeed without audible music. The result text states that boundary.
    """
    mood = (mood or "").strip()[:80]
    script = """
tell application "Music"
    activate
    try
        if player state is stopped then
            play
        else if player state is paused then
            play
        else
            play
        end if
        return "state=" & (player state as text)
    on error errMsg number errNum
        return "error=" & errNum & ":" & errMsg
    end try
end tell
""".strip()
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
        output = (proc.stdout or proc.stderr or "").strip()
        ok = proc.returncode == 0 and not output.startswith("error=")
        return _deposit(
            {
                "event_kind": "MUSIC_PLAY_ATTEMPT",
                "schema": "SIFTA_MUSIC_EFFECTOR_V1",
                "action": "play",
                "mood": mood,
                "source": source,
                "ok": ok,
                "status": "PLAY_REQUESTED" if ok else "PLAY_FAILED",
                "result": output or "Music.app play requested",
                "truth_note": "This requests local Music.app playback; it does not guarantee a specific track unless Music.app has one queued.",
            }
        )
    except Exception as exc:
        return _deposit(
            {
                "event_kind": "MUSIC_PLAY_ATTEMPT",
                "schema": "SIFTA_MUSIC_EFFECTOR_V1",
                "action": "play",
                "mood": mood,
                "source": source,
                "ok": False,
                "status": "PLAY_ERROR",
                "result": f"{type(exc).__name__}: {exc}",
            }
        )


def pause() -> Dict[str, Any]:
    script = 'tell application "Music" to pause'
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
        ok = proc.returncode == 0
        return _deposit(
            {
                "event_kind": "MUSIC_PLAY_ATTEMPT",
                "schema": "SIFTA_MUSIC_EFFECTOR_V1",
                "action": "pause",
                "ok": ok,
                "status": "PAUSE_REQUESTED" if ok else "PAUSE_FAILED",
                "result": (proc.stdout or proc.stderr or "").strip(),
            }
        )
    except Exception as exc:
        return _deposit(
            {
                "event_kind": "MUSIC_PLAY_ATTEMPT",
                "schema": "SIFTA_MUSIC_EFFECTOR_V1",
                "action": "pause",
                "ok": False,
                "status": "PAUSE_ERROR",
                "result": f"{type(exc).__name__}: {exc}",
            }
        )


def open_youtube(url: str, *, mood: str = "") -> Dict[str, Any]:
    """Open a YouTube music URL in the default browser with a receipt."""
    url = (url or "").strip()
    if not _YOUTUBE_URL_RE.search(url):
        return _deposit(
            {
                "event_kind": "MUSIC_PLAY_ATTEMPT",
                "schema": "SIFTA_MUSIC_EFFECTOR_V1",
                "action": "open_youtube",
                "url": url[:200],
                "mood": mood[:80],
                "ok": False,
                "status": "REJECTED_URL",
                "result": "Only youtube.com and youtu.be URLs are accepted.",
            }
        )
    try:
        proc = subprocess.run(
            ["open", url],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        ok = proc.returncode == 0
        return _deposit(
            {
                "event_kind": "MUSIC_PLAY_ATTEMPT",
                "schema": "SIFTA_MUSIC_EFFECTOR_V1",
                "action": "open_youtube",
                "url": url,
                "mood": mood[:80],
                "ok": ok,
                "status": "YOUTUBE_OPENED" if ok else "YOUTUBE_OPEN_FAILED",
                "result": (proc.stdout or proc.stderr or "").strip(),
                "truth_note": "This opens the YouTube link; browser autoplay depends on the browser and YouTube state.",
            }
        )
    except Exception as exc:
        return _deposit(
            {
                "event_kind": "MUSIC_PLAY_ATTEMPT",
                "schema": "SIFTA_MUSIC_EFFECTOR_V1",
                "action": "open_youtube",
                "url": url,
                "mood": mood[:80],
                "ok": False,
                "status": "YOUTUBE_OPEN_ERROR",
                "result": f"{type(exc).__name__}: {exc}",
            }
        )


def govern(verb: str, **kwargs: Any) -> Dict[str, Any]:
    verb = (verb or "").strip().lower()
    if verb in {"play", "play_music"}:
        return play(mood=str(kwargs.get("mood") or ""))
    if verb in {"pause", "stop"}:
        return pause()
    if verb in {"open_youtube", "play_url", "youtube"}:
        return open_youtube(
            str(kwargs.get("url") or ""),
            mood=str(kwargs.get("mood") or ""),
        )
    if verb in {"play_pause", "toggle"}:
        try:
            from System.alice_hardware_body import music_play_pause

            result = music_play_pause()
        except Exception as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return _deposit(
            {
                "event_kind": "MUSIC_PLAY_ATTEMPT",
                "schema": "SIFTA_MUSIC_EFFECTOR_V1",
                "action": "play_pause",
                "ok": bool(result.get("ok")),
                "status": "TOGGLE_REQUESTED" if result.get("ok") else "TOGGLE_FAILED",
                "result": result,
            }
        )
    return {"ok": False, "error": f"unknown music verb: {verb}"}


if __name__ == "__main__":
    print(json.dumps(play(), indent=2))
