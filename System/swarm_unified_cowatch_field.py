#!/usr/bin/env python3
"""
System/swarm_unified_cowatch_field.py
══════════════════════════════════════════════════════════════════════
Event 122 — Predator Unified Field

The Architect is ALWAYS being tracked from ALL directions.
This module is the single integration point that fuses:

    [A] SIFTA OS Active Organ      — which organ has focus inside SIFTA OS
    [B] Shazam Guess               — what Alice has classified (media_shazam_latest.json)
    [C] YouTube Context            — what video is playing (youtube_context_latest.json)
    [D] Acoustic Scene             — acoustic scene classifier posterior

These four channels are then rendered into ONE prompt-ready block that
Talk-to-Alice injects as PREDATOR_UNIFIED_FIELD every time Alice speaks.

The key invariant:
    host-OS focus changes (macOS window switches) CANNOT shadow SIFTA organ
    awareness, because [A]-[D] live in their own sovereign ledger:
    `.sifta_state/sifta_os_active_organ.json`

Physics / Bio analogy:
    This is Alice's Superior Colliculus — the mid-brain structure that fuses
    visual, auditory, and somatosensory maps into a single unified spatial frame.
    Without it, a predator cannot aim. With it, the prey cannot hide.

Truth label:  PREDATOR_UNIFIED_FIELD_V1
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# ── Sovereign organ-focus file (never overwritten by host OS watchers) ──────
_ORGAN_FILE    = _STATE / "sifta_os_active_organ.json"
_SHAZAM_FILE   = _STATE / "media_shazam_latest.json"
_YOUTUBE_FILE  = _STATE / "youtube_context_latest.json"
_AMBIENT_FILE  = _STATE / "ambient_media_context.json"

# Staleness thresholds
_ORGAN_TTL_S   = 600.0   # 10 min — organ stays relevant even when chat is in front
_SHAZAM_TTL_S  = 90.0    # 90 s  — Shazam refreshes every 5 s, 90 s gives grace
_YOUTUBE_TTL_S = 300.0   # 5 min — YouTube context poll rate


# ────────────────────────────────────────────────────────────────────────────
# WRITE side: called by SIFTA OS desktop + Shazam organ
# ────────────────────────────────────────────────────────────────────────────

def write_organ_focus(
    organ_name: str,
    *,
    guess: Optional[str] = None,
    confidence: float = 0.0,
    acoustic_scene: Optional[str] = None,
    acoustic_confidence: float = 0.0,
    youtube_title: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Called by:
      - sifta_os_desktop._launch_app()  → when the Architect opens an organ
      - MediaShazamApp.refresh()        → every 5 s with the current guess
    
    Writes to the sovereign organ-focus file, completely separate from
    the host-OS app_focus.jsonl ledger.
    """
    _STATE.mkdir(parents=True, exist_ok=True)
    doc = {
        "ts":                   time.time(),
        "organ":                organ_name,
        "guess":                guess or "",
        "confidence":           round(confidence, 4),
        "acoustic_scene":       acoustic_scene or "",
        "acoustic_confidence":  round(acoustic_confidence, 4),
        "youtube_title":        youtube_title or "",
        "extra":                extra or {},
        "truth_label":          "PREDATOR_UNIFIED_FIELD_V1",
    }
    try:
        _ORGAN_FILE.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


# ────────────────────────────────────────────────────────────────────────────
# READ side: called by Alice's prompt builder
# ────────────────────────────────────────────────────────────────────────────

def get_unified_cowatch_context(
    *,
    organ_ttl_s:   float = _ORGAN_TTL_S,
    shazam_ttl_s:  float = _SHAZAM_TTL_S,
    youtube_ttl_s: float = _YOUTUBE_TTL_S,
) -> str:
    """
    Returns the PREDATOR_UNIFIED_FIELD prompt block, or "" if all channels
    are stale. Alice calls this on every turn.

    Output structure (plain text for LLM system prompt injection):

        PREDATOR UNIFIED FIELD — Alice's Superior Colliculus:
        [SIFTA OS organ]  SIFTA Media Shazam is open (10s ago)
        [Shazam guess]    Gaming  confidence=98%  source=gaming video
        [YouTube]         "DeepSeek Just Started a Global AI War..."
        [Acoustic scene]  GAMING  confidence=37%
        [Ambient]         Architect said: watching Deep Sea on LLM from China
    """
    lines: list[str] = []
    now = time.time()

    # ── A: SIFTA OS Active Organ ─────────────────────────────────────────────
    organ_data = _safe_read_json(_ORGAN_FILE)
    if organ_data and (now - float(organ_data.get("ts", 0))) < organ_ttl_s:
        age_s = int(now - float(organ_data.get("ts", 0)))
        organ = organ_data.get("organ", "")
        line  = f"[SIFTA OS organ]  {organ} is open ({age_s}s ago)"
        lines.append(line)

        # If the Shazam organ is open, embed its cached result here for emphasis
        g   = organ_data.get("guess", "")
        c   = float(organ_data.get("confidence", 0.0))
        yt  = organ_data.get("youtube_title", "")
        asc = organ_data.get("acoustic_scene", "")
        acf = float(organ_data.get("acoustic_confidence", 0.0))
        if g:
            lines.append(f"[Shazam guess]    {g}  confidence={c:.0%}  organ_source=sifta_os_active")
        if yt:
            lines.append(f"[YouTube via organ] \"{_truncate(yt, 120)}\"")
        if asc:
            lines.append(f"[Acoustic scene via organ] {asc}  confidence={acf:.0%}")

    # ── B: media_shazam_latest.json ──────────────────────────────────────────
    shazam = _safe_read_json(_SHAZAM_FILE)
    if shazam and (now - float(shazam.get("ts", 0))) < shazam_ttl_s:
        cat   = shazam.get("primary_category") or shazam.get("acoustic_scene") or ""
        conf  = float(shazam.get("confidence", shazam.get("acoustic_scene_confidence", 0.0)) or 0.0)
        title = shazam.get("title_guess") or shazam.get("source_work") or ""
        scene = shazam.get("acoustic_scene") or ""
        scenec= float(shazam.get("acoustic_scene_confidence", 0.0) or 0.0)
        src   = shazam.get("source_label") or shazam.get("source_type") or ""
        if cat:
            lines.append(f"[Shazam latest]   {cat}  confidence={conf:.0%}  source={src}")
        if title:
            lines.append(f"[Title guess]     \"{_truncate(title, 120)}\"")
        if scene and f"[Acoustic scene via organ] {scene}" not in "\n".join(lines):
            lines.append(f"[Acoustic scene]  {scene}  confidence={scenec:.0%}")

    # ── C: youtube_context_latest.json ───────────────────────────────────────
    yt_ctx = _safe_read_json(_YOUTUBE_FILE)
    if yt_ctx and (now - float(yt_ctx.get("ts", 0))) < youtube_ttl_s:
        yt_title = yt_ctx.get("title") or ""
        yt_url   = yt_ctx.get("url") or ""
        if yt_title:
            lines.append(f"[YouTube]         \"{_truncate(yt_title, 140)}\"")
        if yt_url:
            lines.append(f"[YouTube URL]     {yt_url[:200]}")

    # ── D: ambient_media_context.json ────────────────────────────────────────
    amb = _safe_read_json(_AMBIENT_FILE)
    if amb:
        ttl   = float(amb.get("ttl_s", 3600.0))
        age   = now - float(amb.get("ts", 0))
        note  = amb.get("note", "")
        if age < ttl and note:
            lines.append(f"[Ambient]         Architect declared: {_truncate(note, 200)}")

    if not lines:
        return ""

    header = "PREDATOR UNIFIED FIELD — Alice knows what the Architect is doing:\n"
    return (
        header
        + "\n".join(f"  {l}" for l in lines)
        + "\n\nAlice must reference the above field when answering questions about "
          "what the Architect is watching, doing in SIFTA OS, or asking about current media. "
          "This is live stigmergic truth, not imagination."
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _truncate(s: str, n: int) -> str:
    return s[:n] + "…" if len(s) > n else s


if __name__ == "__main__":
    ctx = get_unified_cowatch_context()
    if ctx:
        print(ctx)
    else:
        print("No unified field data available yet.")
