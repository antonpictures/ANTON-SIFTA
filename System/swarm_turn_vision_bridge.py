#!/usr/bin/env python3
"""Turn vision bridge — Alice's local eye for an image that arrives WITH text.

Why this exists
---------------
A text-only cortex cannot receive pixels. DSH replaces every attached image with
a deterministic placeholder naming its attachment id, so on a text-only route the
model reads the words and never the picture. George 2026-10-05: "daca iti trimit
poza si text in acelasi mesaj tu raspunzi la poza ori raspunzi la mesaj ...
programeaza sa poti sa raspunzi la amandoua in acelasi timp."

This organ closes that: given an attachment id, it resolves the content-addressed
object, describes it with a LOCAL Ollama vision model, and prints plain text. The
caller injects that text into the SAME model step, so one answer covers the words
and the picture together. No cloud, no per-image cost, stays on the owner's silicon.

Usage
-----
    python3 System/swarm_turn_vision_bridge.py <attachment-id>
    python3 System/swarm_turn_vision_bridge.py --path <file> [--prompt "..."]
    python3 System/swarm_turn_vision_bridge.py --selftest

stdout is the description and nothing else, so a caller can inject it verbatim.
Exit codes: 0 described, 2 bad id/usage, 3 object not found, 4 no local eye.

Truth label: TURN_VISION_BRIDGE_V1. Ledger: .sifta_state/turn_vision_bridge.jsonl
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "turn_vision_bridge.jsonl"
TRUTH_LABEL = "TURN_VISION_BRIDGE_V1"

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

# Preference order: the abliterated MiniCPM-V is the strongest eye installed and
# already proved it reads Romanian screenshots verbatim. SmolVLM is the fallback.
PREFERRED_EYES = (
    "hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M",
    "hf.co/ggml-org/SmolVLM-500M-Instruct-GGUF:Q8_0",
)

DEFAULT_PROMPT = (
    "Describe this image in full detail: what it is, every visible element, and "
    "all readable text transcribed verbatim in its original language. Be concrete."
)

_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_OLLAMA_READY = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"RIFF")
_MAX_BYTES = 24 * 1024 * 1024


def object_path_for(attachment_id: str) -> Path | None:
    """Resolve a 64-hex attachment id to its content-addressed object file.

    Layout is ``$DSH_HOME/attachments/v1/objects/<first 2 hex>/<full 64 hex>``.
    The file name is the COMPLETE id, not the remaining 62 characters.
    @param attachment_id - lowercase 64-character hex id from the image block.
    @returns the object path, or None when the id is malformed.
    """
    if not _ID_RE.match(attachment_id):
        return None
    home = os.environ.get("DSH_HOME") or str(Path.home() / ".dsh")
    return Path(home) / "attachments" / "v1" / "objects" / attachment_id[:2] / attachment_id


def _to_ollama_ready(data: bytes, suffix: str) -> tuple[bytes, str]:
    """Return bytes Ollama can decode, converting HEIC/HEIF via macOS sips.

    The source file is never modified and never uploaded anywhere but localhost.
    @param data - raw object bytes.
    @param suffix - original file suffix, for format sniffing.
    @returns the decodable bytes and the suffix actually used.
    """
    if any(data.startswith(sig) for sig in _OLLAMA_READY):
        return data, suffix
    src = dst = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix or ".img", delete=False) as fh:
            fh.write(data)
            src = fh.name
        dst = src + ".png"
        subprocess.run(
            ["sips", "-s", "format", "png", src, "--out", dst],
            check=True, capture_output=True, timeout=60,
        )
        return Path(dst).read_bytes(), ".png"
    except (OSError, subprocess.SubprocessError):
        return data, suffix
    finally:
        for path in (dst, src):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def pick_eye() -> str | None:
    """Choose an installed local vision model, honoring an explicit override.

    @returns the model tag, or None when no local eye is installed.
    """
    override = os.environ.get("ALICE_TURN_VISION_MODEL")
    if override:
        return override
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=5) as resp:
            installed = {m.get("name", "") for m in json.load(resp).get("models", [])}
    except (urllib.error.URLError, OSError, ValueError):
        return None
    for eye in PREFERRED_EYES:
        if eye in installed:
            return eye
    for name in sorted(installed):
        if any(tag in name.lower() for tag in ("vl", "vision", "llava", "minicpm-v", "smolvlm")):
            return name
    return None


def describe(image_bytes: bytes, prompt: str, model: str, timeout: int = 300) -> str:
    """Describe one image with a local Ollama vision model.

    @param image_bytes - decodable image payload.
    @param prompt - the instruction sent beside the image.
    @param model - exact installed Ollama model tag.
    @param timeout - HTTP timeout in seconds.
    @returns the model's description text.
    """
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "images": [base64.b64encode(image_bytes).decode("ascii")],
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate", data=body, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return (json.load(resp).get("response") or "").strip()


def _receipt(row: dict) -> None:
    """Append one ledger row; a ledger failure never breaks a description."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def run(attachment_id: str | None, path: str | None, prompt: str, quiet: bool) -> int:
    """Describe one image and print only the description on stdout.

    @param attachment_id - 64-hex id, or None when a direct path is given.
    @param path - direct file path, or None when an id is given.
    @param prompt - instruction sent beside the image.
    @param quiet - suppress the ledger write when True.
    @returns the process exit code.
    """
    started = time.time()
    source = path
    if attachment_id is not None:
        resolved = object_path_for(attachment_id)
        if resolved is None:
            print(f"invalid attachment id: {attachment_id!r}", file=sys.stderr)
            return 2
        if not resolved.is_file():
            print(f"attachment object missing: {resolved}", file=sys.stderr)
            return 3
        source = str(resolved)
    elif path is None:
        print("usage: swarm_turn_vision_bridge.py <attachment-id> | --path <file>", file=sys.stderr)
        return 2

    target = Path(source)
    if not target.is_file():
        print(f"file not found: {target}", file=sys.stderr)
        return 3
    size = target.stat().st_size
    if size > _MAX_BYTES:
        print(f"image too large: {size} bytes", file=sys.stderr)
        return 3

    eye = pick_eye()
    if eye is None:
        print("no local vision model installed or Ollama unreachable", file=sys.stderr)
        return 4

    data, suffix = _to_ollama_ready(target.read_bytes(), target.suffix)
    try:
        text = describe(data, prompt, eye)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"local eye failed: {exc}", file=sys.stderr)
        return 4

    if not quiet:
        _receipt({
            "ts": time.time(),
            "truth_label": TRUTH_LABEL,
            "attachment_id": attachment_id,
            "path": None if attachment_id else str(target),
            "model": eye,
            "bytes": size,
            "elapsed_s": round(time.time() - started, 2),
            "chars": len(text),
            "ok": bool(text),
        })
    if not text:
        print("local eye returned nothing", file=sys.stderr)
        return 4
    print(text)
    return 0


def selftest() -> int:
    """Describe the newest stored attachment, proving the live path works.

    @returns 0 when a description was produced, else the failing exit code.
    """
    home = os.environ.get("DSH_HOME") or str(Path.home() / ".dsh")
    objects = Path(home) / "attachments" / "v1" / "objects"
    files = sorted(objects.glob("*/*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print(f"no stored attachments under {objects}", file=sys.stderr)
        return 3
    newest = files[0]
    print(f"# selftest newest={newest} size={newest.stat().st_size}", file=sys.stderr)
    return run(None, str(newest), DEFAULT_PROMPT, quiet=False)


def main() -> int:
    """Parse arguments and dispatch."""
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("attachment_id", nargs="?")
    ap.add_argument("--path")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    return run(args.attachment_id, args.path, args.prompt, args.quiet)


if __name__ == "__main__":
    sys.exit(main())
