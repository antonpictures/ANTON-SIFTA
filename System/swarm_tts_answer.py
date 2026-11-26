#!/usr/bin/env python3
"""swarm_tts_answer.py — Speak one of Alice's answers aloud (local voice).

Pipeline: text -> edge-tts (Ava neural, local) -> mp3 -> 16kHz mono wav -> afplay
Usage: python3 System/swarm_tts_answer.py "Your sentence here"
Saves to /tmp/alice_tts_reply.mp3 and plays it through the speakers.
"""
from __future__ import annotations

import subprocess
import sys

VOICE = "en-US-AvaNeural"  # Microsoft Edge neural — natural female voice, local

# Speak on/off master switch (George 2026-11-25: "add button speak on / off").
# Wired into the body so OpenCode (and the Talk window, when running) share one
# gate. State lives in .sifta_state/speak_enabled (default: on).
def _speak_enabled() -> bool:
    try:
        from pathlib import Path
        f = Path(__file__).resolve().parents[1] / ".sifta_state" / "speak_enabled"
        if f.exists():
            return f.read_text().strip().lower() not in ("0", "false", "off", "no")
    except Exception:
        pass
    return True



def speak(text: str, out_mp3: str = "/tmp/alice_tts_reply.mp3") -> str:
    """Convert text to speech and play it aloud. Returns the mp3 path.

    Honors the body's speak on/off gate (.sifta_state/speak_enabled).
    """
    if not _speak_enabled():
        print("speak off — skipping.", file=sys.stderr)
        return out_mp3
    import asyncio

    import edge_tts

    async def _run() -> None:
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(out_mp3)

    asyncio.run(_run())

    wav = out_mp3.replace(".mp3", ".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", out_mp3, "-ar", "16000", "-ac", "1",
         "-c:a", "pcm_s16le", wav],
        check=True, timeout=30, capture_output=True,
    )
    subprocess.run(["afplay", wav], check=True, timeout=60, capture_output=True)
    return out_mp3


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python3 System/swarm_tts_answer.py "Your sentence here"')
        sys.exit(1)
    sentence = " ".join(sys.argv[1:])
    try:
        path = speak(sentence)
        print(path)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
