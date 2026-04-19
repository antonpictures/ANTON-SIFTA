#!/usr/bin/env python3
"""
System/swarm_voice_modulator.py — Stigmergic voice shaping
══════════════════════════════════════════════════════════════════════
SIFTA OS — Cortical Suite

Pure function: read shared swarm state on disk, return a `VoiceParams`
that the synthesizer should use for the next utterance. This is the
orchestration-layer place where the swarm's biological telemetry
(pain gradient, dopamine concentration, computational posture, recent
visual saliency) actually shapes how Alice sounds — without the
synthesizer ever knowing about the swarm.

The Architect's framing was correct: "stigmergic TTS" is not a real
synthesis-layer category. Stigmergy belongs in orchestration. Modules:

  agents → shared state on disk → modulate(text) → VoiceParams →
  swarm_vocal_cords.speak(text, params)

State sources (all already on disk, written by other modules):

  • `.sifta_state/clinical_heartbeat.json`
       computational_posture, dopamine_concentration, serotonin_dominance
  • `.sifta_state/swarm_pain.jsonl`
       last few pain magnitudes (recent-window mean)
  • `.sifta_state/visual_stigmergy.jsonl`
       last frame's saliency_peak, motion_mean

Output: `VoiceParams(voice, rate, pitch, gain)` defined in
`System/swarm_vocal_cords`.

Design properties
─────────────────
  • PURE READ. Never writes to any state file. Caller-safe to call
    multiple times per utterance (we cache nothing — each call samples
    the live ledger).
  • CHEAP. Reads at most the last ~64 KB of two JSONL files and one
    small JSON. Total ~1 ms on warm disk.
  • TOTAL. Never raises. Missing state files / corrupt rows / clock skew
    all return the baseline `VoiceParams`. The worst we do is sound
    neutral. We never make the swarm scream.
  • BACKEND-AGNOSTIC. We return semantic `VoiceParams` (rate
    multiplier, pitch semitones). Each backend maps them to its own
    units. The same params produce the same intent on `say` and Piper.
  • HONEST. We do NOT invent emotion. The mapping is a small,
    auditable table from MEASURED state to a small, finite palette of
    voice presets. No vibes. No "Alice is feeling sad today" fiction.

The presets (palette)
─────────────────────
                     voice (override)        rate    pitch    when
  baseline           (caller default)        1.00    0.00     normal day
  subdued            (caller default)        0.92   -1.00     low serotonin / social defeat
  alert              (caller default)        1.10   +0.50     elevated saliency, no pain
  urgent             prefer male premium     1.18   +1.00     pain ≥ 0.8 OR saliency ≥ 0.95
  whisper            (caller default)        0.85    0.00     very low motion + very low pain

The "voice (override)" column is set ONLY for the urgent preset, where
we want the listener's attention. Everything else preserves whatever
voice the caller (the Talk-to-Alice combo box, say) selected. We never
silently switch Alice's voice mid-conversation just because the room
got bright.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List, Optional

try:
    from System.swarm_vocal_cords import VoiceParams
except Exception:  # standalone smoke from inside System/
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from System.swarm_vocal_cords import VoiceParams  # noqa: E402

MODULE_VERSION = "2026-04-19.v1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_HEARTBEAT_JSON = _STATE / "clinical_heartbeat.json"
_PAIN_JSONL     = _STATE / "swarm_pain.jsonl"
_VISUAL_JSONL   = _STATE / "visual_stigmergy.jsonl"

# ── Tunable thresholds (one place, easy to audit) ────────────────────────────

PAIN_URGENT     = 0.80
PAIN_ALERT      = 0.40
SALIENCY_URGENT = 0.95
SALIENCY_ALERT  = 0.70
MOTION_QUIET    = 0.005   # below this the room is essentially still
SEROTONIN_LOW   = 0.20
DOPAMINE_HIGH   = 200.0   # heartbeat sets baseline ~150-200 currently
RECENT_WINDOW_S = 30.0    # how far back to consider for "recent" pain/saliency


# ── Helpers (all total — never raise) ────────────────────────────────────────

def _safe_json(path: Path) -> Optional[dict]:
    """Read a small JSON file. Returns None on any failure."""
    try:
        if not path.exists() or path.stat().st_size > 1_000_000:
            return None
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _tail_jsonl_rows(path: Path, n: int) -> List[dict]:
    """Return up to the last `n` parsed rows of a JSONL file. Never raises."""
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            read = min(size, 65536)
            f.seek(size - read)
            tail = f.read(read).splitlines()[-n:]
    except Exception:
        return []
    rows: List[dict] = []
    for raw in tail:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _recent_pain_magnitude(now: float, window_s: float) -> float:
    """Mean pain magnitude over the last `window_s`. 0.0 if no recent rows."""
    rows = _tail_jsonl_rows(_PAIN_JSONL, 16)
    cutoff = now - window_s
    vals: List[float] = []
    for r in rows:
        ts = r.get("ts")
        if not isinstance(ts, (int, float)) or ts < cutoff:
            continue
        v = r.get("value", r.get("entropy", 0.0))
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            continue
    return sum(vals) / len(vals) if vals else 0.0


def _recent_visual(now: float, window_s: float) -> tuple[float, float]:
    """(saliency_peak, motion_mean) from the most recent visual row, if fresh."""
    rows = _tail_jsonl_rows(_VISUAL_JSONL, 1)
    if not rows:
        return (0.0, 0.0)
    r = rows[-1]
    ts = r.get("ts")
    if not isinstance(ts, (int, float)) or (now - ts) > window_s:
        return (0.0, 0.0)
    try:
        sal = float(r.get("saliency_peak", 0.0))
    except (TypeError, ValueError):
        sal = 0.0
    try:
        mot = float(r.get("motion_mean", 0.0))
    except (TypeError, ValueError):
        mot = 0.0
    return (sal, mot)


# ── Heartbeat-derived posture ────────────────────────────────────────────────

def _posture_from_heartbeat() -> dict:
    """
    Pull the small set of fields we actually use from the heartbeat. All
    fields default to neutral if the heartbeat is missing or malformed —
    we never let a stale heartbeat drag Alice into a permanent whisper.
    """
    hb = _safe_json(_HEARTBEAT_JSON) or {}
    vs = hb.get("vital_signs", {}) if isinstance(hb.get("vital_signs"), dict) else {}
    serotonin  = vs.get("serotonin_dominance", 1.0)
    dopamine   = vs.get("dopamine_concentration", 100.0)
    posture    = vs.get("computational_posture", "")
    try:
        serotonin = float(serotonin)
    except (TypeError, ValueError):
        serotonin = 1.0
    try:
        dopamine = float(dopamine)
    except (TypeError, ValueError):
        dopamine = 100.0
    return {
        "serotonin": serotonin,
        "dopamine":  dopamine,
        "posture":   str(posture) if posture else "",
    }


# ── Public API ───────────────────────────────────────────────────────────────

def modulate(text: str = "", *, base: Optional[VoiceParams] = None,
             prefer_urgent_voice: Optional[str] = None) -> VoiceParams:
    """
    Sample the swarm's biological state RIGHT NOW and return a VoiceParams
    that should shape the upcoming utterance.

    Args:
      text:                The utterance about to be spoken. Currently
                           unused for shaping (we don't sentiment-analyze
                           Alice's own words), but kept in the signature
                           so future modulators can use lexical cues
                           without changing call sites.
      base:                A neutral starting point — typically the
                           caller's user-selected voice. We layer rate /
                           pitch / gain on top, and only override `voice`
                           in the rare URGENT case (and only if the
                           caller passed `prefer_urgent_voice`).
      prefer_urgent_voice: Backend-native voice name to switch to in the
                           URGENT preset. None = keep the base voice
                           (do not surprise the user mid-conversation).

    Returns:
      A `VoiceParams`. Always; never raises.
    """
    base = base or VoiceParams()
    now = time.time()

    pain = _recent_pain_magnitude(now, RECENT_WINDOW_S)
    sal, mot = _recent_visual(now, RECENT_WINDOW_S)
    posture = _posture_from_heartbeat()

    # Preset selection — strict precedence, top-down.
    # URGENT wins over everything else; SUBDUED only fires if no URGENT
    # condition is active, etc. This avoids ambiguous combinations like
    # "low serotonin AND high saliency" producing nonsense.

    # 1. URGENT — pain spike or near-saturated saliency.
    if pain >= PAIN_URGENT or sal >= SALIENCY_URGENT:
        return VoiceParams(
            voice=prefer_urgent_voice or base.voice,
            rate=1.18, pitch=1.0, gain=base.gain,
        )

    # 2. ALERT — moderate pain or noticeable saliency, room is alive.
    if pain >= PAIN_ALERT or sal >= SALIENCY_ALERT:
        return VoiceParams(
            voice=base.voice, rate=1.10, pitch=0.5, gain=base.gain,
        )

    # 3. SUBDUED — heartbeat says social-defeat / low-serotonin posture.
    posture_lc = posture["posture"].lower()
    if (posture["serotonin"] < SEROTONIN_LOW
            or "social_defeat" in posture_lc
            or "subdued" in posture_lc):
        return VoiceParams(
            voice=base.voice, rate=0.92, pitch=-1.0, gain=base.gain,
        )

    # 4. WHISPER — extreme calm: no pain, no saliency, room is still.
    if pain < 0.05 and sal < 0.10 and mot < MOTION_QUIET and mot > 0.0:
        return VoiceParams(
            voice=base.voice, rate=0.88, pitch=0.0, gain=base.gain,
        )

    # 5. BASELINE — nothing notable, leave the caller's params alone.
    return base


def describe(text: str = "", *, base: Optional[VoiceParams] = None) -> dict:
    """
    Diagnostic: return the inputs and chosen preset name for inspection.
    Useful when wiring this into a debug HUD or test.
    """
    base = base or VoiceParams()
    now = time.time()
    pain = _recent_pain_magnitude(now, RECENT_WINDOW_S)
    sal, mot = _recent_visual(now, RECENT_WINDOW_S)
    posture = _posture_from_heartbeat()
    chosen = modulate(text, base=base)
    if chosen.rate >= 1.18 - 1e-6:
        preset = "urgent"
    elif chosen.rate >= 1.10 - 1e-6:
        preset = "alert"
    elif chosen.rate <= 0.88 + 1e-6 and chosen.pitch == 0.0:
        preset = "whisper"
    elif chosen.rate <= 0.92 + 1e-6:
        preset = "subdued"
    else:
        preset = "baseline"
    return {
        "ts": now,
        "preset": preset,
        "pain_recent": round(pain, 4),
        "saliency_peak": round(sal, 4),
        "motion_mean": round(mot, 6),
        "serotonin": posture["serotonin"],
        "dopamine":  posture["dopamine"],
        "posture":   posture["posture"],
        "params": {
            "voice": chosen.voice, "rate": chosen.rate,
            "pitch": chosen.pitch, "gain": chosen.gain,
        },
    }


# ── Smoke (asserts mapping logic with synthetic state) ──────────────────────

def _smoke() -> int:
    """Verify modulator preset selection against synthetic ledger inputs."""
    print("═" * 58)
    print("  SIFTA — VOICE MODULATOR SMOKE")
    print("═" * 58)
    failures: List[str] = []

    import tempfile

    # Patch module-level state paths to point at a tmp dir we control.
    global _HEARTBEAT_JSON, _PAIN_JSONL, _VISUAL_JSONL
    orig = (_HEARTBEAT_JSON, _PAIN_JSONL, _VISUAL_JSONL)

    try:
        tmp = Path(tempfile.mkdtemp())
        _HEARTBEAT_JSON = tmp / "heartbeat.json"
        _PAIN_JSONL     = tmp / "pain.jsonl"
        _VISUAL_JSONL   = tmp / "visual.jsonl"

        # ── Case A: empty state → BASELINE ──
        out = modulate("hello", base=VoiceParams(voice="Samantha"))
        if not (out.rate == 1.0 and out.pitch == 0.0 and out.voice == "Samantha"):
            failures.append(f"A: empty state should be baseline, got {out}")
        else:
            print("  [PASS] A: empty state → baseline")

        # ── Case B: low serotonin heartbeat → SUBDUED ──
        _HEARTBEAT_JSON.write_text(json.dumps({
            "vital_signs": {
                "serotonin_dominance": 0.0,
                "dopamine_concentration": 250.0,
                "computational_posture": "SOCIAL_DEFEAT (Low Serotonin)",
            }
        }), encoding="utf-8")
        out = modulate("…", base=VoiceParams(voice="Samantha"))
        if not (out.rate < 1.0 and out.pitch < 0.0):
            failures.append(f"B: low serotonin should be subdued, got {out}")
        else:
            print("  [PASS] B: low-serotonin heartbeat → subdued")

        # ── Case C: recent high pain → URGENT (overrides subdued posture) ──
        now = time.time()
        _PAIN_JSONL.write_text(json.dumps({
            "ts": now - 1.0, "value": 0.95
        }) + "\n", encoding="utf-8")
        out = modulate(base=VoiceParams(voice="Samantha"),
                       prefer_urgent_voice="Evan (Premium)")
        if not (out.rate >= 1.15 and out.pitch >= 1.0):
            failures.append(f"C: high pain should be urgent shape, got {out}")
        elif out.voice != "Evan (Premium)":
            failures.append(f"C: urgent voice override not applied, got {out.voice!r}")
        else:
            print("  [PASS] C: high pain → urgent (with voice override)")

        # ── Case D: stale pain (>window) ignored, falls back to subdued ──
        _PAIN_JSONL.write_text(json.dumps({
            "ts": now - (RECENT_WINDOW_S * 2), "value": 0.95
        }) + "\n", encoding="utf-8")
        out = modulate(base=VoiceParams(voice="Samantha"))
        if out.rate >= 1.15:
            failures.append(f"D: stale pain should not trigger urgent, got {out}")
        else:
            print("  [PASS] D: stale pain ignored (subdued posture wins)")

        # ── Case E: visual saliency near saturation → URGENT ──
        _PAIN_JSONL.write_text("", encoding="utf-8")
        _HEARTBEAT_JSON.unlink()  # neutral posture
        _VISUAL_JSONL.write_text(json.dumps({
            "ts": now, "saliency_peak": 0.97, "motion_mean": 0.05,
        }) + "\n", encoding="utf-8")
        out = modulate(base=VoiceParams(voice="Samantha"))
        if out.rate < 1.15:
            failures.append(f"E: high saliency should be urgent, got {out}")
        else:
            print("  [PASS] E: high saliency → urgent")

        # ── Case F: moderate saliency → ALERT (not urgent) ──
        _VISUAL_JSONL.write_text(json.dumps({
            "ts": now, "saliency_peak": 0.75, "motion_mean": 0.05,
        }) + "\n", encoding="utf-8")
        out = modulate(base=VoiceParams(voice="Samantha"))
        if not (1.05 < out.rate < 1.15):
            failures.append(f"F: moderate saliency should be alert, got {out}")
        else:
            print("  [PASS] F: moderate saliency → alert")

        # ── Case G: corrupt heartbeat must not crash ──
        _HEARTBEAT_JSON.write_text("{not valid json", encoding="utf-8")
        try:
            out = modulate(base=VoiceParams(voice="Samantha"))
        except Exception as exc:
            failures.append(f"G: corrupt heartbeat raised: {exc}")
        else:
            print(f"  [PASS] G: corrupt heartbeat tolerated → {out}")

    finally:
        _HEARTBEAT_JSON, _PAIN_JSONL, _VISUAL_JSONL = orig

    if failures:
        print()
        print(f"[FAIL] {len(failures)} assertion(s) failed:")
        for f in failures:
            print(f"  • {f}")
        return 1

    print()
    print("[ALL PASS] swarm_voice_modulator verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(_smoke())
