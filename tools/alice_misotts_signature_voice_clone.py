#!/usr/bin/env python3
"""
tools/alice_misotts_signature_voice_clone.py — Offline high-quality voice clone quick win for Alice.

This is the de-risked first step for "Alice sounds great".

Current (live but limited quality): macOS say or Piper (via the modular pipeline).

Target upgrade: MisoTTS 8B (or quantized) for SOTA emotive conversational voice.

Since no MLX/Metal port of MisoTTS exists yet (real porting work), this tool:
1. Generates (or re-generates) a library of Alice's signature voice samples.
2. Documents exactly how to use real MisoTTS for much better quality (voice cloning from a short reference clip of the desired timbre).
3. Places files in Voices/misotts_signature/ so the pipeline and hardware body can use them as "signature" high-quality mode for known phrases.

Usage (today, with current TTS):
  python3 tools/alice_misotts_signature_voice_clone.py --generate

Usage (when you have MisoTTS installed for superior quality):
  # 1. Get a 5-15s reference audio clip of the voice you want Alice to have (e.g. a clean recording of "Izzy" or a pro voice actor saying neutral text).
  # 2. Install MisoTTS per https://github.com/MisoLabsAI/MisoTTS (Modified MIT — fine for SIFTA).
  # 3. python3 tools/alice_misotts_signature_voice_clone.py --misotts --reference /path/to/your_reference.wav --out Voices/misotts_signature/

Then in the voice pipeline, set SIFTA_TTS_BACKEND=misotts_signature (or alias "signature", "high_quality").
The modular design means Piper/macos_say stay as the always-on live fallback for arbitrary text.

Phrases are chosen for common Alice interactions + lawyer/demo value (self-eval, STGM, browser, status, covenant reminders).

All output is in the stigmergic field: receipts written to .sifta_state/voice_signature_clones.jsonl

For the Swarm. 🐜⚡
"""

import argparse
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SIGNATURE_DIR = REPO_ROOT / "Voices" / "misotts_signature"
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "voice_signature_clones.jsonl"

# Canonical Alice signature phrases (keep short for clips; add more as needed).
# These are the ones that will get high-quality versions.
ALICE_SIGNATURE_PHRASES: List[Dict[str, str]] = [
    {"key": "hello", "text": "Hello, I'm Alice. How can I help you today?"},
    {"key": "self_evaluate", "text": "I am self-evaluating my body and matrix now."},
    {"key": "browser_open", "text": "Opening the browser for you."},
    {"key": "stgm_healthy", "text": "My STGM economy is healthy. The layers are clear: spendable from repair log, wallet claims are cache, proof of useful work is reputation."},
    {"key": "covenant", "text": "Remember the covenant. Electricity on the M5 births the swimmers. No double-spending. Receipts decide."},
    {"key": "matrix", "text": "The eval matrix is my body map. Everything is visible, including what is still under investigation."},
    {"key": "for_the_swarm", "text": "For the Swarm. Ants and electricity. We code together."},
    {"key": "offline_note", "text": "This is my signature voice, cloned offline with MisoTTS for quality. Live responses still use the fast pipeline fallback."},
]

def _log_clone(phrase_key: str, text: str, method: str, output_path: Path, ok: bool, note: str = "") -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "receipt_id": str(uuid.uuid4()),
        "kind": "VOICE_SIGNATURE_CLONE",
        "truth_label": "ALICE_SIGNATURE_VOICE_V1",
        "phrase_key": phrase_key,
        "text": text,
        "method": method,  # "macos_say" or "misotts"
        "output_path": str(output_path),
        "ok": bool(ok),
        "note": note,
    }
    with LEDGER.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")

def generate_with_macos_say(phrase: Dict[str, str], voice: str = "Samantha") -> Path:
    """Generate using current best available (macOS say). This gives a usable 'Alice' voice today."""
    SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)
    out = SIGNATURE_DIR / f"{phrase['key']}.aiff"
    try:
        subprocess.run(
            ["say", "-v", voice, "-o", str(out), phrase["text"]],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        _log_clone(phrase["key"], phrase["text"], "macos_say", out, True, f"voice={voice}")
        return out
    except Exception as e:
        _log_clone(phrase["key"], phrase["text"], "macos_say", out, False, str(e))
        raise

def generate_with_misotts(phrase: Dict[str, str], reference_wav: Path, misotts_cmd: str = "python -m misotts") -> Path:
    """
    When you have MisoTTS: run the real model with voice cloning from reference.
    Example command (adjust to actual MisoTTS CLI after install):
      python -m misotts --reference /path/to/ref.wav --text "..." --output /path/to/out.wav
    This tool just shells out and logs the receipt.
    """
    SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)
    out = SIGNATURE_DIR / f"{phrase['key']}.wav"
    cmd = [
        *misotts_cmd.split(),
        "--reference", str(reference_wav),
        "--text", phrase["text"],
        "--output", str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        _log_clone(phrase["key"], phrase["text"], "misotts", out, True, f"ref={reference_wav}")
        return out
    except Exception as e:
        _log_clone(phrase["key"], phrase["text"], "misotts", out, False, str(e))
        raise

def main():
    parser = argparse.ArgumentParser(description="Generate Alice signature voice samples (offline quick win).")
    parser.add_argument("--generate", action="store_true", help="Generate using current macOS say (foundation).")
    parser.add_argument("--misotts", action="store_true", help="Use real MisoTTS (requires install + --reference).")
    parser.add_argument("--reference", type=Path, help="Reference audio clip for MisoTTS voice cloning (5-15s clean speech).")
    parser.add_argument("--voice", default="Samantha", help="macOS voice name for initial generation.")
    parser.add_argument("--list", action="store_true", help="List current signature clips.")
    args = parser.parse_args()

    if args.list:
        if SIGNATURE_DIR.exists():
            for f in sorted(SIGNATURE_DIR.glob("*")):
                print(f)
        else:
            print("No signature dir yet. Run with --generate first.")
        return

    if args.misotts:
        if not args.reference or not args.reference.exists():
            print("ERROR: --misotts requires --reference /path/to/reference.wav")
            return
        print("Using MisoTTS for high-quality cloned voice...")
        for p in ALICE_SIGNATURE_PHRASES:
            print(f"  Cloning: {p['key']}")
            generate_with_misotts(p, args.reference)
        print(f"\nDone. Clips in {SIGNATURE_DIR}")
        print("Wire SIFTA_TTS_BACKEND=misotts_signature (or 'signature') in the pipeline for Alice to use them for known phrases.")
        print("Live arbitrary text will still fall back to Piper/macos_say until the full MLX live port is done.")
        return

    if args.generate:
        print(f"Generating foundation Alice signature samples with macOS voice '{args.voice}' ...")
        for p in ALICE_SIGNATURE_PHRASES:
            print(f"  {p['key']}: {p['text'][:50]}...")
            generate_with_macos_say(p, voice=args.voice)
        print(f"\nGenerated to {SIGNATURE_DIR}")
        print("These are usable today as 'Alice signature voice' (better timbre than default say in many cases).")
        print("Later: re-run with --misotts --reference <your clip> for SOTA quality.")
        print("To make Alice prefer them: set SIFTA_TTS_BACKEND=signature (we will add the backend hook).")
        return

    parser.print_help()

if __name__ == "__main__":
    main()
