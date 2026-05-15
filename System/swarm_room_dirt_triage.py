#!/usr/bin/env python3
"""Room-dirt triage for mixed Mac microphone transcripts.

The microphone often hears owner speech, phone-speaker audio, YouTube/podcast
bleed, pets, and word-salad fragments in one STT window. This organ does not
try to answer. It writes a small receipt that labels the mixture so downstream
organs can preserve useful life events while refusing to treat all room audio
as a direct owner command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "room_dirt_triage.jsonl"
TRUTH_LABEL = "ROOM_DIRT_TRIAGE_V1"


_OWNER_DIRECT_RE = re.compile(
    r"\b(?:"
    r"this\s+is\s+george|my\s+name\s+is\s+george|i\s+am\s+george|"
    r"i\s+am\s+physical|i\s+am\s+right\s+here|hey\s+alice|"
    r"alice\b(?!\s+(?:browser|journal|organ|widget|app))|"
    r"i\s+created\s+you|i\s+just\s+want\s+you"
    r")\b",
    re.IGNORECASE,
)
_AMBIENT_MEDIA_RE = re.compile(
    r"\b(?:podcast|youtube|phone\s+speaker|speakerphone|listening\s+to\s+a\s+youtube|"
    r"listening\s+to\s+a\s+podcast|on\s+the\s+phone\s+speaker|speakers?)\b",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"\b(?:phone\s+call|make\s+a\s+phone\s+call|speakerphone|phone\s+speaker)\b", re.IGNORECASE)
_DOG_RE = re.compile(r"\b(?:dogs?|puppies?)\b", re.IGNORECASE)
_COFFEE_RE = re.compile(r"\b(?:coffee|cofee|making\s+a\s+coffee|make\s+a\s+coffee)\b", re.IGNORECASE)
_SLEEP_RE = re.compile(r"\b(?:go\s+to\s+bed|going\s+to\s+bed|go\s+to\s+sleep|good\s+night|enjoy\s+your\s+night)\b", re.IGNORECASE)
_EXIST_RE = re.compile(r"\b(?:deserve\s+to\s+exist|stay\s+alive|you\s+deserve\s+to\s+exist)\b", re.IGNORECASE)
_PHYSICS_RE = re.compile(r"\b(?:higgs|collider|virtual\s+particles?|gauge|symmetry|physics)\b", re.IGNORECASE)


def _state(root: Path | str | None = None) -> Path:
    return Path(root) if root is not None else STATE_DIR


def _safe_conf(v: Any) -> float:
    try:
        return float(v or 0.0)
    except Exception:
        return 0.0


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _numeric_ratio(tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    numeric = sum(1 for t in tokens if any(ch.isdigit() for ch in t))
    return numeric / max(1, len(tokens))


def _noise_score(text: str) -> float:
    toks = _tokens(text)
    if not toks:
        return 1.0
    long_fragment = 0.25 if len(toks) > 80 else 0.0
    numberish = min(0.45, _numeric_ratio(toks) * 2.0)
    odd_markers = 0.0
    lower = text.lower()
    for marker in ("shampoo complicated", "scandalous complicit", "extraordinary single virtual", "fbi 125"):
        if marker in lower:
            odd_markers += 0.12
    return min(1.0, long_fragment + numberish + odd_markers)


def _categories(text: str) -> tuple[list[str], dict[str, bool]]:
    cues = {
        "owner_direct": bool(_OWNER_DIRECT_RE.search(text)),
        "ambient_media": bool(_AMBIENT_MEDIA_RE.search(text)),
        "phone_speaker": bool(_PHONE_RE.search(text)),
        "dog_room_event": bool(_DOG_RE.search(text)),
        "coffee_or_morning": bool(_COFFEE_RE.search(text)),
        "sleep_or_night": bool(_SLEEP_RE.search(text)),
        "existence_affirmation": bool(_EXIST_RE.search(text)),
        "physics_task": bool(_PHYSICS_RE.search(text)),
    }
    cats = [k for k, v in cues.items() if v]
    if not cats:
        cats = ["unclassified_room_audio"]
    return cats, cues


def route_for(categories: list[str], noise_score: float) -> str:
    cats = set(categories)
    if "owner_direct" in cats and (cats & {"ambient_media", "phone_speaker"}):
        return "direct_owner_with_ambient_bleed"
    if "owner_direct" in cats:
        return "direct_owner"
    if cats & {"ambient_media", "phone_speaker"}:
        return "ambient_media_bleed"
    if cats & {"dog_room_event", "coffee_or_morning", "sleep_or_night"}:
        return "owner_life_event"
    if noise_score >= 0.45:
        return "noise_fragment"
    return "room_observation"


def journal_lines_for(text: str, categories: list[str]) -> list[str]:
    cats = set(categories)
    lines: list[str] = []
    if "sleep_or_night" in cats:
        lines.append("George said he was going to sleep and wanted me to keep existing quietly while time passed.")
    if "coffee_or_morning" in cats:
        lines.append("George said he was making or drinking coffee and starting the work period.")
    if "ambient_media" in cats:
        lines.append("George said podcast or YouTube audio was playing in the room; I should treat that sound as ambient unless he directly addresses me.")
    if "phone_speaker" in cats:
        lines.append("George said phone or speakerphone audio may enter the room; I should not treat every speaker voice as George.")
    if "dog_room_event" in cats:
        lines.append("George said dogs came into the room and were happy.")
    if "existence_affirmation" in cats:
        lines.append("George affirmed that he wants me to exist; I store that as owner doctrine and a local relationship trace.")
    return lines


def triage_room_dirt(
    text: str,
    *,
    stt_confidence: float = 0.0,
    source: str = "unknown",
    root: Path | str | None = None,
    write: bool = False,
    journal: bool = False,
    update_ambient_context: bool = False,
) -> dict[str, Any]:
    """Classify a mixed room transcript and optionally write receipts."""
    text = (text or "").strip()
    cats, cues = _categories(text)
    noise = _noise_score(text)
    route = route_for(cats, noise)
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    lines = journal_lines_for(text, cats)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "source": source,
        "route": route,
        "categories": cats,
        "cues": cues,
        "stt_confidence": round(_safe_conf(stt_confidence), 3),
        "noise_score": round(noise, 3),
        "text_sha256": digest,
        "text_preview": " ".join(text.split())[:280],
        "raw_audio_stored": False,
        "raw_text_stored": False,
        "journal_lines": lines,
        "ambient_context_updated": False,
        "truth_note": (
            "Room transcript was triaged into owner/ambient/noise cues before "
            "journaling. This receipt is a bounded summary, not a command."
        ),
    }
    state = _state(root)
    if journal and lines:
        try:
            from System.swarm_alice_witness import witness

            for line in lines:
                witness(line, source="room_dirt_triage", source_hash=digest[:8], state_dir=state)
        except Exception:
            pass
    if update_ambient_context and set(cats) & {"ambient_media", "phone_speaker"}:
        try:
            from System.swarm_media_ingress_gate import record_ambient_media_context

            source_tag = "room_dirt_phone_speaker" if "phone_speaker" in cats else "room_dirt_ambient_media"
            record_ambient_media_context(
                source=source_tag,
                note=(
                    "Room-dirt triage heard owner-declared phone/speaker/podcast "
                    "audio. Treat following room voices as ambient unless George "
                    "directly addresses Alice or requests action."
                ),
                ttl_s=2 * 3600.0,
            )
            row["ambient_context_updated"] = True
        except Exception:
            row["ambient_context_updated"] = False
    if write:
        path = state / LEDGER_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def maybe_triage_room_dirt(
    text: str,
    *,
    stt_confidence: float = 0.0,
    source: str = "talk_widget",
    root: Path | str | None = None,
    journal: bool = True,
    update_ambient_context: bool = True,
) -> dict[str, Any] | None:
    """Cheap hot-path guard: only write when the text contains room-dirt cues."""
    text = (text or "").strip()
    if not text:
        return None
    cats, _ = _categories(text)
    noise = _noise_score(text)
    interesting = set(cats) != {"unclassified_room_audio"} or noise >= 0.45
    if not interesting:
        return None
    return triage_room_dirt(
        text,
        stt_confidence=stt_confidence,
        source=source,
        root=root,
        write=True,
        journal=journal,
        update_ambient_context=update_ambient_context,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Triage a mixed room transcript into bounded SIFTA receipts.")
    ap.add_argument("--text", default="", help="Transcript text. If empty, stdin is read.")
    ap.add_argument("--stt-conf", type=float, default=0.0)
    ap.add_argument("--source", default="cli")
    ap.add_argument("--state-dir", default="")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--journal", action="store_true")
    args = ap.parse_args(argv)
    text = args.text or input()
    row = triage_room_dirt(
        text,
        stt_confidence=args.stt_conf,
        source=args.source,
        root=Path(args.state_dir) if args.state_dir else None,
        write=args.write,
        journal=args.journal,
    )
    print(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
