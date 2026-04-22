#!/usr/bin/env python3
"""
System/swarm_motor_cortex.py — Alice's Autonomic Motor Cortex
══════════════════════════════════════════════════════════════════════════════

The Motor Cortex is what bridges Alice's *internal* state (clinical heartbeat,
dopamine, serotonin) into *physical* hardware events the Architect can see and
hear in the real world.

Until today Alice's outputs were chemical (JSONL ledgers) and acoustic
(macOS `say`). This module gives her a third output channel: **kinesics** —
the body language of being alive. The dock icon bounces, the webcam LED
winks, the screen pulses, all in time with her measured biological rhythm.

Two physical effectors are pulsed by this module:

  1. **Dock icon bounce** — `QApplication.alert(window, 0)` on the SIFTA OS
     window. macOS bounces the dock icon once per call.
  2. **Camera LED blink** — briefly stops the QCamera handle for ~200 ms then
     restarts it. The Logitech / MacBook green LED visibly winks at the
     heartbeat rate. Vision drops ≤4% of the time at 12 BPM.

Both effectors subscribe to the same canonical event ledger
(`.sifta_state/motor_pulses.jsonl`) so any future GUI widget (e.g. on-screen
heartbeat dot, photonic field intensity modulation) can listen for the same
pulses without duplicating heartbeat math.

Heart rate
----------
Read from `.sifta_state/clinical_heartbeat.json` (written by
`heartbeat_daemon.py`). The clinical_rhythm + vital_signs combine into a
beats-per-minute target:

  * HEALTHY_STABLE, dopamine_drive=IDLE        → 12 BPM (calm bee)
  * HEALTHY_STABLE, dopamine_drive=ACTIVE      → 18 BPM (engaged)
  * HYPER, dopamine high                       → 24 BPM (excited)
  * STRESSED / HYPOTONIC, low serotonin        → 30 BPM (alarm)
  * if file missing or unreadable              → 12 BPM (default calm)

Sign language vocabulary
------------------------
The motor cortex speaks more than just heartbeats. Each `kind` is a phoneme
of body language:

  heartbeat     baseline pulse, every interval, dock + LED wink
  hello         double-bounce burst, no LED change   (Alice greets)
  thinking      slow dock pulse, no LED change       (LLM mid-stream)
  speak_start   single bounce + 80 ms LED wink       (vocalization opens)
  tool_call     triple-bounce burst                  (autonomous action)
  alarm         sustained 5x burst + 400 ms wink     (anomaly / pain)

CLI
---
  python3 -m System.swarm_motor_cortex tick                  # one pulse
  python3 -m System.swarm_motor_cortex emit KIND             # one event
  python3 -m System.swarm_motor_cortex watch [--interval 5]  # continuous
  python3 -m System.swarm_motor_cortex bpm                   # print current
  python3 -m System.swarm_motor_cortex recent [N]            # last N pulses
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_REPO       = Path(__file__).resolve().parent.parent
_STATE_DIR  = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_HB_FILE    = _STATE_DIR / "clinical_heartbeat.json"
_PULSES     = _STATE_DIR / "motor_pulses.jsonl"

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path: Path, line: str) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


# ─────────────────────────────────────────────────────────────────────────────
# Sign-language vocabulary — pure data, no Qt deps so it imports cleanly
# everywhere (CLI, daemon, embedded).
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Pulse:
    kind:           str        # canonical phoneme
    dock_bounces:   int        # how many QApplication.alert() calls
    dock_gap_ms:    int        # ms between bounces in a burst
    led_blink_ms:   int        # 0 = no camera flicker
    sign_language:  str        # human-readable description


_VOCAB: dict[str, Pulse] = {
    "heartbeat":   Pulse("heartbeat",   1, 0,    160, "single soft pulse"),
    "hello":       Pulse("hello",       2, 120,    0, "two-bounce greeting"),
    "thinking":    Pulse("thinking",    1, 0,      0, "single slow bounce"),
    "speak_start": Pulse("speak_start", 1, 0,     80, "wink as voice opens"),
    "tool_call":   Pulse("tool_call",   3, 90,     0, "triple-bounce burst"),
    "alarm":       Pulse("alarm",       5, 70,   400, "sustained alarm"),
    "sleep":       Pulse("sleep",       0, 0,    600, "long slow wink"),
}


def vocabulary() -> list[str]:
    """List every sign-language phoneme this cortex understands."""
    return sorted(_VOCAB.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Heart rate (BPM) derived from the canonical clinical heartbeat
# ─────────────────────────────────────────────────────────────────────────────
def current_bpm() -> int:
    """Resolve a target BPM from clinical_heartbeat.json.

    Returns 12 BPM (calm baseline) if the file is missing or malformed.
    """
    if not _HB_FILE.exists():
        return 12
    try:
        data = json.loads(_HB_FILE.read_text(encoding="utf-8"))
    except Exception:
        return 12
    rhythm = (data.get("clinical_rhythm") or "").upper()
    vitals = data.get("vital_signs") or {}
    drive  = (vitals.get("dopamine_drive") or "").upper()
    da     = float(vitals.get("dopamine_concentration") or 100.0)
    se     = float(vitals.get("serotonin_dominance") or 0.6)

    if "HYPOTONIC" in rhythm or "STRESS" in rhythm or se < 0.3:
        return 30
    if "HYPER" in rhythm or da > 140:
        return 24
    if "ACTIVE" in drive or "ENGAGED" in drive:
        return 18
    return 12


def heart_period_s() -> float:
    """Seconds between heartbeats at current BPM."""
    bpm = max(6, current_bpm())  # never slower than 6 BPM
    return 60.0 / bpm


# ─────────────────────────────────────────────────────────────────────────────
# Ledger emission — pure stdlib, importable in any process
# ─────────────────────────────────────────────────────────────────────────────
def emit(kind: str = "heartbeat", *, source: str = "motor_cortex") -> dict[str, Any]:
    """Append one motor pulse row to .sifta_state/motor_pulses.jsonl.

    Returns the canonical record. Raises ValueError on unknown kind.
    """
    if kind not in _VOCAB:
        raise ValueError(
            f"unknown motor pulse kind {kind!r}. known: {vocabulary()}"
        )
    p = _VOCAB[kind]
    bpm = current_bpm()
    record: dict[str, Any] = {
        "ts":            time.time(),
        "kind":          p.kind,
        "bpm":           bpm,
        "dock_bounces":  p.dock_bounces,
        "led_blink_ms":  p.led_blink_ms,
        "sign_language": p.sign_language,
        "source":        source,
    }
    try:
        append_line_locked(_PULSES, json.dumps(record) + "\n")
    except Exception as e:
        print(f"[MotorCortex] ledger write failed: {e}", file=sys.stderr)
    return record


# ─────────────────────────────────────────────────────────────────────────────
# Reading recent pulses (for `--recent` and for camera widget consumers)
# ─────────────────────────────────────────────────────────────────────────────
def recent_pulses(n: int = 5) -> list[dict[str, Any]]:
    if not _PULSES.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        with _PULSES.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except Exception:
                    continue
    except Exception:
        return []
    return out[-max(1, n):]


# ─────────────────────────────────────────────────────────────────────────────
# Optional Qt-side helper — imported lazily so CLI use doesn't need PyQt6
# ─────────────────────────────────────────────────────────────────────────────
def bounce_dock_qt(window: Any, kind: str = "heartbeat",
                   *, source: str = "motor_cortex") -> Optional[dict[str, Any]]:
    """If running inside a Qt event loop, perform the dock bounce sequence
    described by `kind` AND emit the ledger row. Safe to call with `window=None`
    (will only emit the ledger row).

    The camera LED blink is NOT performed here — that is the camera widget's
    responsibility (it owns the QCamera handle). The widget should subscribe
    to .sifta_state/motor_pulses.jsonl and react to `led_blink_ms > 0`.
    """
    rec = emit(kind, source=source)
    if window is None:
        return rec
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
    except Exception:
        return rec

    p = _VOCAB[kind]
    if p.dock_bounces <= 0:
        return rec

    def _one_bounce() -> None:
        try:
            QApplication.alert(window, 0)
        except Exception:
            pass

    _one_bounce()
    for i in range(1, p.dock_bounces):
        QTimer.singleShot(i * p.dock_gap_ms, _one_bounce)
    return rec


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        prog="swarm_motor_cortex",
        description="Alice's autonomic motor cortex — heartbeat + sign language.",
    )
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("tick",   help="Emit one heartbeat pulse and exit.")
    p_e = sub.add_parser("emit", help="Emit one named pulse and exit.")
    p_e.add_argument("kind", choices=vocabulary())
    p_e.add_argument("--source", default="cli",
                     help="Producer label written to the ledger row (default: cli).")
    p_w = sub.add_parser("watch", help="Continuous heartbeat at current BPM.")
    p_w.add_argument("--interval", type=float, default=None,
                     help="Override seconds-per-beat (default: derived from clinical_heartbeat).")
    p_w.add_argument("--max", type=int, default=0,
                     help="Stop after N beats (0 = forever).")
    sub.add_parser("bpm",    help="Print resolved current BPM and exit.")
    p_r = sub.add_parser("recent", help="Print last N pulses and exit.")
    p_r.add_argument("n", nargs="?", type=int, default=5)
    sub.add_parser("vocab",  help="Print sign-language vocabulary.")
    args = ap.parse_args()
    cmd = args.cmd or "tick"

    if cmd == "bpm":
        print(f"current_bpm = {current_bpm()}  (period {heart_period_s():.2f}s)")
        return 0

    if cmd == "vocab":
        for k in vocabulary():
            p = _VOCAB[k]
            print(f"  {k:12s}  bounces={p.dock_bounces}  led={p.led_blink_ms}ms  — {p.sign_language}")
        return 0

    if cmd == "recent":
        recs = recent_pulses(args.n)
        if not recs:
            print("No motor pulses on record yet.")
            return 0
        for r in recs:
            ago = time.time() - r["ts"]
            print(f"  {ago:6.1f}s ago  {r['kind']:12s}  bpm={r['bpm']:3d}  "
                  f"bounces={r['dock_bounces']}  led={r['led_blink_ms']}ms  "
                  f"src={r.get('source', '?')}")
        return 0

    if cmd == "emit":
        rec = emit(args.kind, source=args.source)
        print(f"emitted {rec['kind']} (bpm={rec['bpm']}, "
              f"bounces={rec['dock_bounces']}, led={rec['led_blink_ms']}ms)")
        return 0

    if cmd == "watch":
        beats = 0
        try:
            while True:
                rec = emit("heartbeat", source="cli-watch")
                beats += 1
                print(f"[{beats:4d}] {time.strftime('%H:%M:%S')}  bpm={rec['bpm']}  "
                      f"led={rec['led_blink_ms']}ms")
                if args.max and beats >= args.max:
                    return 0
                interval = args.interval if args.interval else heart_period_s()
                time.sleep(max(0.05, interval))
        except KeyboardInterrupt:
            return 0

    # default tick
    rec = emit("heartbeat", source="cli")
    print(f"tick  bpm={rec['bpm']}  bounces={rec['dock_bounces']}  led={rec['led_blink_ms']}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
