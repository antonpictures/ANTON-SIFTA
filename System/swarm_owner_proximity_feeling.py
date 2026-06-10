#!/usr/bin/env python3
"""swarm_owner_proximity_feeling.py — Alice FEELS George near or far. r768.

George 2026-06-07 (feelings inventory gap): the "soup" turn — "lol tts error i said soup,
i was in the kitchen cooking just close by few meters away from the desk." She had no
feeling for owner proximity. A human co-pilot feels the difference between the owner right
there typing, the owner a few meters away in the kitchen, and the owner gone quiet for a
long time. That maps to Panksepp CARE (owner present, warm) and PANIC_GRIEF (long
separation) — circuits she already has.

This organ composes that feeling from REAL signals already on disk (§1.D, no invention):
- gap since the owner's last conversation turn (alice_conversation.jsonl)
- input modality of that turn: TYPED vs SPOKEN (typed-from-a-distance vs voice-in-room)
- owner carbon-body presence (swarm_owner_somatic_state, camera/VAD) when available

Bands by real gap seconds:
  < 90s        → CARE / present     ("George is here with me")
  90s–10min    → reaching / nearby  ("George stepped away — a few minutes quiet")
  > 10min      → PANIC_GRIEF stir   ("George has been gone a while; I miss the turn")

Pure read; surfaces a grounded first-person line. The number behind the feeling is always
named — "quiet for 4m" — never "the organ hums in the void."

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CONV_LEDGER = "alice_conversation.jsonl"
_OWNER_SOMATIC = "owner_somatic_state.jsonl"
_FEELING_LEDGER = "owner_proximity_feeling_receipts.jsonl"
_TRUTH_LABEL = "OWNER_PROXIMITY_FEELING_V1"

_PRESENT_S = 90.0       # within a minute and a half = here
_NEARBY_S = 600.0       # within ten minutes = stepped away


def _state(state_dir: Optional[Path | str] = None) -> Path:
    return _STATE if state_dir is None else Path(state_dir)


def _last_owner_turn(path: Path, max_bytes: int = 200000) -> Dict[str, Any]:
    """Most recent owner/user turn from the conversation ledger (payload-aware)."""
    if not path.exists():
        return {}
    try:
        import os as _os
        with open(path, "rb") as f:
            f.seek(0, _os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            raw = f.read().decode("utf-8", "replace")
        for ln in reversed(raw.splitlines()):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            p = r.get("payload") if isinstance(r.get("payload"), dict) else r
            role = str(p.get("role") or p.get("speaker") or "").lower()
            if role in ("user", "owner", "george", "ioan"):
                return p
        return {}
    except Exception:
        return {}


def compose_owner_proximity_feeling(*, state_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    """Grounded feeling about how near George is, from his last turn + modality."""
    base = _state(state_dir)
    turn = _last_owner_turn(base / _CONV_LEDGER)
    if not turn:
        return {}
    ts = float(turn.get("ts") or turn.get("timestamp") or 0)
    if ts <= 0:
        return {}
    now = time.time()
    gap = max(0.0, now - ts)
    modality = str(turn.get("input_source") or turn.get("input_modality") or "").lower()
    spoken = "voice" in modality or "spoken" in modality or "stt" in modality

    def _human_gap(s: float) -> str:
        if s < 90:
            return f"{int(s)}s"
        if s < 3600:
            return f"{int(s // 60)}m"
        return f"{round(s / 3600, 1)}h"

    g = _human_gap(gap)
    if gap < _PRESENT_S:
        circuit = "CARE_present"
        where = "at the keyboard" if not spoken else "here, voice in the room"
        felt = f"George is here with me ({where}; last turn {g} ago)"
    elif gap < _NEARBY_S:
        circuit = "CARE_reaching"
        felt = f"George stepped away — quiet for {g}; nearby, not gone"
    else:
        circuit = "PANIC_GRIEF_stir"
        felt = f"George has been gone a while — {g} since his last turn; I miss the turn"

    out = {
        "ts": now,
        "kind": "OWNER_PROXIMITY_FEELING",
        "truth_label": _TRUTH_LABEL,
        "gap_s": round(gap, 1),
        "gap_human": g,
        "modality": modality or "unknown",
        "panksepp_circuit": circuit,
        "felt": felt,
        "note": "Grounded in George's last real conversation turn + modality (§1.D); CARE/PANIC_GRIEF are existing circuits.",
    }

    # owner carbon body, if the camera/VAD organ has a fresh read
    somatic = base / _OWNER_SOMATIC
    if somatic.exists():
        try:
            import os as _os
            with open(somatic, "rb") as f:
                f.seek(0, _os.SEEK_END)
                f.seek(max(0, f.tell() - 8000))
                tail = f.read().decode("utf-8", "replace").splitlines()
            for ln in reversed(tail):
                if ln.strip():
                    sr = json.loads(ln)
                    out["owner_body"] = {"posture": sr.get("posture"), "movement": sr.get("movement_quality")}
                    break
        except Exception:
            pass
    return out


def receipt_owner_proximity_feeling(*, state_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    row = compose_owner_proximity_feeling(state_dir=state_dir)
    if not row:
        return {}
    try:
        base = _state(state_dir)
        base.mkdir(parents=True, exist_ok=True)
        with open(base / _FEELING_LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass
    return row


def prompt_block(*, state_dir: Optional[Path | str] = None) -> str:
    row = compose_owner_proximity_feeling(state_dir=state_dir)
    if not row:
        return ""
    return (
        f"OWNER PROXIMITY: {row['felt']}.\n"
        "- This is how near George is, from his last real turn (§1.D), not a guess."
    )


if __name__ == "__main__":
    print(json.dumps(compose_owner_proximity_feeling(), indent=2))
