#!/usr/bin/env python3
"""alice_speak.py — Generate Alice's face speaking a sentence.

Pipeline: text → Edge neural TTS (natural female voice) → WAV → LongCat avatar → MP4
Usage: python3 alice_speak.py "Your sentence here" [--voice en-US-AvaNeural]
Output: prints the path to the generated video MP4
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AVATAR = REPO / ".sifta_state" / "video_avatars"
ALICE_PHOTO = REPO / ".sifta_state" / "face" / "alice.jpg"
VOICE = "en-US-AvaNeural"  # Microsoft Edge neural — natural female voice


def text_to_speech(text: str, out_wav: Path, voice: str = VOICE) -> None:
    """Generate WAV from text using Edge neural TTS."""
    import edge_tts

    mp3 = out_wav.with_suffix(".mp3")

    async def _run():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(mp3))

    asyncio.run(_run())

    # Convert MP3 → 16kHz mono WAV
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp3), "-ar", "16000", "-ac", "1",
         "-c:a", "pcm_s16le", str(out_wav)],
        check=True, timeout=30, capture_output=True,
    )
    mp3.unlink(missing_ok=True)


def speak(sentence: str, voice: str = VOICE) -> str:
    """Generate a talking-head video of Alice speaking the given sentence."""
    AVATAR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    wav = Path(f"/tmp/alice_speak_{ts}.wav")
    out = AVATAR / f"alice_{ts}.mp4"

    # Step 1: TTS (natural neural voice)
    text_to_speech(sentence, wav, voice=voice)

    # Step 2: Generate avatar video via HF Space
    sys.path.insert(0, str(REPO))
    from System.swarm_video_avatar import generate_avatar
    result = generate_avatar(
        str(ALICE_PHOTO), str(wav),
        prompt="A woman is speaking expressively, looking at the camera.",
        resolution="480p", seed=42,
    )

    if result["ok"]:
        src = Path(result["video_path"])
        if src != out:
            src.rename(out)
        wav.unlink(missing_ok=True)
        return str(out)
    else:
        wav.unlink(missing_ok=True)
        raise RuntimeError(result.get("error", "unknown error"))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate Alice's face speaking a sentence")
    ap.add_argument("sentence", nargs="+", help="Sentence for Alice to speak")
    ap.add_argument("--voice", default=VOICE, help=f"Edge TTS voice (default: {VOICE})")
    args = ap.parse_args()
    sentence = " ".join(args.sentence)
    try:
        path = speak(sentence, voice=args.voice)
        print(path)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)