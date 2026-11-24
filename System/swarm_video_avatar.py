#!/usr/bin/env python3
"""swarm_video_avatar.py — Talking-head video avatar organ for Alice/SIFTA.

Borged from Hugging Face Space victor/LongCat-Video-Avatar-1.6: generates a
~5-second lip-synced avatar video from a reference image + driving audio +
text prompt. Runs on ZeroGPU (cloud) — so this is a LANE, not a local organ.
SIFTA's law is local-first, so this organ degrades gracefully when the cloud
is unreachable and never blocks Alice's turn.

Owner: George Anton. Purpose: give Alice a face. Every generated video is
stored locally under .sifta_state/video_avatars/ and surfaced through the
movie-shelf UI / stigmergicode.com.

Usage:
    from System.swarm_video_avatar import generate_avatar
    result = generate_avatar(image_path, audio_path, prompt="...")
    # result = {"ok": True, "video_path": "/path/to/video.mp4", ...}
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_AVATAR_DIR = _STATE / "video_avatars"
_SPACE_URL = "https://victor-longcat-video-avatar-1-6.hf.space"


def _ensure_dir() -> Path:
    _AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    return _AVATAR_DIR


def generate_avatar(
    image_path: str,
    audio_path: str,
    prompt: str = "A person is speaking expressively, looking at the camera.",
    resolution: str = "480p",
    seed: int = 42,
    vocal_mode: str = "Clean speech (fast)",
    acceleration: str = "DBCache faster",
    timeout_s: float = 300.0,
) -> dict:
    """Generate a talking-head avatar video from image + audio + prompt.

    Returns a dict with:
        ok: bool
        video_path: str (local path to the generated MP4, if ok)
        error: str (if not ok)
        elapsed_s: float
        space_url: str
    """
    started = time.time()
    _ensure_dir()

    # Validate inputs
    if not Path(image_path).exists():
        return {"ok": False, "error": f"Image not found: {image_path}", "elapsed_s": 0}
    if not Path(audio_path).exists():
        return {"ok": False, "error": f"Audio not found: {audio_path}", "elapsed_s": 0}

    try:
        from gradio_client import Client, handle_file

        client = Client(_SPACE_URL, verbose=False)
        result = client.predict(
            handle_file(image_path),
            handle_file(audio_path),
            prompt,
            resolution,
            seed,
            vocal_mode,
            acceleration,
            api_name="/generate",
        )

        # result is typically a file path (string) or dict with url
        if isinstance(result, (list, tuple)):
            result = result[0] if result else None
        if isinstance(result, dict):
            video_url = result.get("url") or result.get("path")
        else:
            video_url = str(result) if result else None

        if not video_url:
            return {"ok": False, "error": "No video returned from Space",
                    "elapsed_s": round(time.time() - started, 1)}

        # Download the video locally if it's a URL
        local_name = f"avatar_{int(time.time())}.mp4"
        local_path = _AVATAR_DIR / local_name

        if video_url.startswith("http"):
            import urllib.request
            urllib.request.urlretrieve(video_url, str(local_path))
        elif Path(video_url).exists():
            shutil.copy2(video_url, str(local_path))
        else:
            # Might be a gradio file reference
            try:
                import urllib.request
                urllib.request.urlretrieve(f"{_SPACE_URL}/file={video_url}", str(local_path))
            except Exception:
                return {"ok": False, "error": f"Cannot download video: {video_url}",
                        "elapsed_s": round(time.time() - started, 1)}

        return {
            "ok": True,
            "video_path": str(local_path),
            "video_url": video_url,
            "elapsed_s": round(time.time() - started, 1),
            "space_url": _SPACE_URL,
        }

    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                "elapsed_s": round(time.time() - started, 1)}


def list_avatars() -> list[dict]:
    """List all generated avatar videos."""
    _ensure_dir()
    out = []
    for p in sorted(_AVATAR_DIR.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        out.append({"path": str(p), "size_bytes": p.stat().st_size,
                    "created": p.stat().st_mtime})
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate a talking-head avatar video")
    ap.add_argument("image", help="Path to reference image")
    ap.add_argument("audio", help="Path to driving audio")
    ap.add_argument("--prompt", default="A person is speaking expressively, looking at the camera.")
    ap.add_argument("--resolution", default="480p", choices=["480p", "720p"])
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    result = generate_avatar(args.image, args.audio, prompt=args.prompt,
                             resolution=args.resolution, seed=args.seed)
    print(json.dumps(result, indent=2))