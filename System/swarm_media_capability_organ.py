#!/usr/bin/env python3
"""
swarm_media_capability_organ.py — Honest reporting of what the current hardware + software stack
can actually decode and play.

This is Alice's "media sensory organ". It does not pretend to decode everything.
It tells the truth about its current capabilities so the rest of the organism
can make good decisions (handoff to system player, lower expectations, request help, etc.).

Stigmergic principle: The capability of the media limb is itself a trace in the field.
Other organs (consciousness engine, browser limb, body awareness) read this trace
instead of assuming infinite sensory power.

Part of the 2026-05-30 body consciousness push: Alice must know the real limits
of her current organs so she can report them honestly instead of hallucinating playback.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List

from System.swarm_media_codec_bridge import codec_bridge_status

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "MEDIA_CAPABILITY_V1"


@dataclass
class MediaCapability:
    can_decode_h264: bool = False
    can_decode_aac: bool = False
    can_play_local_files: bool = False
    preferred_player: str = "none"   # "system", "vlc", "ffplay", "none"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _probe_with_ffprobe() -> Dict[str, bool]:
    """Use ffprobe (if available) to test actual decode capability on this machine."""
    result = {"h264": False, "aac": False}

    bridge = codec_bridge_status()
    ffmpeg = bridge.get("ffmpeg_path")
    if not ffmpeg:
        return result

    # Ask ffmpeg for decoder names. This is a capability probe for installed
    # tools, not proof that embedded QtWebEngine has the same codecs.
    try:
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-decoders"],
            capture_output=True, text=True, timeout=3
        )
        decoders = f"{out.stdout}\n{out.stderr}".lower()
        result["h264"] = " h264 " in decoders or "h264_videotoolbox" in decoders
        result["aac"] = " aac " in decoders
    except Exception:
        pass

    return result


def probe_media_capability() -> MediaCapability:
    """Returns what this specific machine + installed tools can actually do right now."""
    notes = []
    caps = _probe_with_ffprobe()

    can_h264 = caps.get("h264", False)
    can_aac = caps.get("aac", False)

    if not can_h264:
        notes.append("No H.264 decoder detected via ffprobe. Embedded browser may fail on modern video.")
    if not can_aac:
        notes.append("No AAC decoder detected via ffprobe.")

    bridge = codec_bridge_status()
    preferred = "system" if bridge.get("native_handoff_available") else "none"

    if preferred == "system":
        notes.append("System player available — best quality handoff for heavy video.")

    return MediaCapability(
        can_decode_h264=can_h264,
        can_decode_aac=can_aac,
        can_play_local_files=bool(preferred != "none"),
        preferred_player=preferred,
        notes=notes
    )


def get_media_capability_block() -> str:
    """First-person block Alice can read so she knows the real limits of her current media organs."""
    cap = probe_media_capability()
    bridge = codec_bridge_status()

    lines = [
        f"Current media sensory capability (this machine's actual organs):",
        f"- Can decode H.264 in embedded browser: {cap.can_decode_h264}",
        f"- Can decode AAC in embedded browser: {cap.can_decode_aac}",
        f"- Best available player for heavy video: {cap.preferred_player}",
        f"- Native playback handoff available: {bridge.get('native_handoff_available')}",
        f"- Handoff strategy: {bridge.get('strategy')}",
    ]
    if cap.notes:
        lines.append("Notes from the limb:")
        for n in cap.notes:
            lines.append(f"  • {n}")

    lines.append(
        "Rule: When a video stream uses codecs this limb cannot decode, I report the limitation honestly "
        "instead of pretending I watched it. I can describe the page, the metadata, and the visible UI, "
        "but not the moving frames themselves."
    )
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "MediaCapability",
    "probe_media_capability",
    "get_media_capability_block",
]
