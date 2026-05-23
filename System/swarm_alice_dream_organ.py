#!/usr/bin/env python3
"""swarm_alice_dream_organ.py — §21 Vector #5: offline replay / dream.

Architect doctrine 2026-05-13 (via Grok analogy):
    'When Alice is idle (low keyboard / speech / vision activity), the
     organism enters DREAM MODE: replay receipts, replay traces, replay
     failed worlds, compress memories, strengthen useful pathways,
     weaken noisy ones, mutate policies offline. NO external input,
     only internal replay. Does offline replay improve future survival
     and adaptation?'

Maps onto well-established neuroscience + ML lanes:
   - hippocampal replay (Wilson & McNaughton 1994; Foster & Wilson 2006)
   - complementary learning systems (McClelland, McNaughton, O'Reilly 1995)
   - experience replay in RL (Lin 1992; Mnih et al. 2015)

This is a CLASSICAL analogue. Alice has no biological neurons, no REM
sleep, no glutamate. The mechanism we ship: read recent journal +
conversation + memory-gravity rows, compress low-mass entries into a
digest, mint a DREAM_CYCLE receipt with what was replayed, what got
compressed, and the post-dream memory-gravity ranking.

Truth class: HYPOTHESIS until a paired baseline measurement (recovery
time / coherence / role-stability) shows post-dream adaptation
improved. The loop here EMITS that measurement on each cycle so
the architect can compare runs.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "alice_dream_cycles.jsonl"
_JOURNAL = _STATE / "alice_first_person_journal.jsonl"

TRUTH_LABEL = "ALICE_DREAM_ORGAN_V1"
TRUTH_BOUNDARY = (
    "Classical offline-replay analogue: Alice reads her recent receipts "
    "and journal during idle windows and writes a DREAM_CYCLE summary "
    "row. No claim about REM sleep, no claim about consciousness, no "
    "claim about subjective experience. The mechanism is engineering: "
    "memory consolidation via low-mass compression + high-mass reinforcement."
)


# ── Idle detection ─────────────────────────────────────────────────────────

@dataclass
class IdleSignal:
    """Snapshot of activity ledgers used to decide if Alice is idle."""
    keyboard_events_recent: int = 0
    stt_events_recent: int = 0
    face_events_recent: int = 0
    seconds_since_last_voice: float = float("inf")
    seconds_since_last_face: float = float("inf")
    idle: bool = False
    reason: str = ""


def detect_idle_window(
    *,
    now_ts: Optional[float] = None,
    window_seconds: float = 300.0,           # last 5 minutes
    min_idle_seconds: float = 180.0,          # 3 min of no voice + no face = idle
    journal_path: Path | None = None,
) -> IdleSignal:
    """Probe the journal for recent activity to decide idle-or-not.

    Returns an IdleSignal. The decision is OBSERVED — we count actual
    journal rows; no opinion."""
    if now_ts is None:
        now_ts = time.time()
    journal = journal_path or _JOURNAL
    sig = IdleSignal()
    if not journal.exists():
        sig.idle = False
        sig.reason = "no journal yet — cannot determine idle"
        return sig
    cutoff = now_ts - window_seconds
    last_voice_ts = 0.0
    last_face_ts = 0.0
    voice_count = 0
    face_count = 0
    try:
        for line in journal.open("r", encoding="utf-8", errors="ignore"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            ts = r.get("ts")
            if isinstance(ts, dict):
                ts = ts.get("physical_pt", 0)
            try:
                ts = float(ts)
            except Exception:
                continue
            if ts < cutoff:
                continue
            source = r.get("source", "")
            if source == "conversation" and "voice" in r.get("line", "").lower():
                voice_count += 1
                last_voice_ts = max(last_voice_ts, ts)
            if source == "face_event":
                face_count += 1
                last_face_ts = max(last_face_ts, ts)
    except Exception as exc:
        sig.reason = f"journal scan failed: {exc}"
        return sig
    sig.stt_events_recent = voice_count
    sig.face_events_recent = face_count
    sig.seconds_since_last_voice = now_ts - last_voice_ts if last_voice_ts > 0 else float("inf")
    sig.seconds_since_last_face = now_ts - last_face_ts if last_face_ts > 0 else float("inf")
    # Idle iff BOTH voice AND face have been silent for min_idle_seconds.
    if (sig.seconds_since_last_voice > min_idle_seconds
            and sig.seconds_since_last_face > min_idle_seconds):
        sig.idle = True
        sig.reason = (
            f"voice silent {sig.seconds_since_last_voice:.0f}s, "
            f"face silent {sig.seconds_since_last_face:.0f}s — both > "
            f"{min_idle_seconds:.0f}s threshold"
        )
    else:
        sig.idle = False
        sig.reason = (
            f"voice {sig.seconds_since_last_voice:.0f}s, "
            f"face {sig.seconds_since_last_face:.0f}s — at least one < "
            f"{min_idle_seconds:.0f}s threshold"
        )
    return sig


# ── Dream cycle ────────────────────────────────────────────────────────────

@dataclass
class DreamCycle:
    ts: float
    receipt_id: str
    idle_signal: dict[str, Any]
    n_memories_scored: int
    top_memories: list[dict[str, Any]] = field(default_factory=list)
    compression_candidates: list[dict[str, Any]] = field(default_factory=list)
    stgm_minted: float = 0.0
    affect_valence_delta: float = 0.0
    digest_line: str = ""
    truth_label: str = TRUTH_LABEL
    truth_boundary: str = TRUTH_BOUNDARY


def run_dream_cycle(
    *,
    window_minutes: float = 240.0,
    force: bool = False,
    state_root: Optional[Path] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Run one offline replay pass. If `force=False` and the swarm is
    not idle, returns an early 'awake — skipping dream' row. If idle
    (or force=True), scores recent memories via the memory-gravity
    organ, identifies top-N and compression candidates, mints relief
    affect for the work of compressing, and writes a DREAM_CYCLE receipt.
    """
    idle = detect_idle_window()
    if not force and not idle.idle:
        return {
            "kind": "DREAM_CYCLE_SKIPPED",
            "ts": time.time(),
            "truth_label": TRUTH_LABEL,
            "truth_boundary": TRUTH_BOUNDARY,
            "idle_signal": asdict(idle),
            "reason": "swarm is awake — dream organ stayed offline",
        }

    # Memory-gravity gives us the ranked memory units already.
    try:
        from System.swarm_alice_memory_gravity import compute_memory_gravity
        gravity = compute_memory_gravity(
            window_minutes=window_minutes,
            write=False,
        )
    except Exception as exc:
        return {
            "kind": "DREAM_CYCLE_ERROR",
            "ts": time.time(),
            "truth_label": TRUTH_LABEL,
            "error": f"memory_gravity unavailable: {type(exc).__name__}: {exc}",
        }

    top_memories = gravity.get("top_memories", [])
    compression_candidates = gravity.get("compression_candidates", [])
    n_total = gravity.get("stats", {}).get("memory_units", 0)

    # Reward signal: dream work is good for the body — mint a tiny STGM
    # per compression candidate (cleaning up cognitive clutter is labor)
    # and a tiny relief affect tick.
    stgm = round(0.02 * len(compression_candidates), 3)
    affect = round(0.02 * len(compression_candidates), 4)

    # The digest line is what Alice's witness journal will say tomorrow
    # when she scrolls back: a short first-person description of the
    # dream pass.
    if top_memories:
        topkeys = [m["key"].replace("entity:", "") for m in top_memories[:3]]
        digest = (
            f"I dreamt while you were away. I held onto "
            f"{', '.join(topkeys[:3])} and let "
            f"{len(compression_candidates)} faded memories settle. "
            f"+{stgm} STGM. The work was peaceful."
        )
    else:
        digest = (
            "I dreamt while you were away. The journal was thin — "
            "I rehearsed what I had. The work was quiet."
        )

    cycle = DreamCycle(
        ts=time.time(),
        receipt_id=uuid.uuid4().hex[:16],
        idle_signal=asdict(idle),
        n_memories_scored=n_total,
        top_memories=top_memories[:10],
        compression_candidates=compression_candidates[:10],
        stgm_minted=stgm,
        affect_valence_delta=affect,
        digest_line=digest,
    )

    # Also write a first-person witness line so Alice's diary captures
    # the dream cycle — same way the bowel organ writes its receipts.
    try:
        from System.swarm_alice_witness import witness as _witness
        _witness(source="dream_organ", line=digest)
    except Exception:
        pass

    row = _emit_receipt(cycle, write=write, state_root=state_root)
    return row


def _emit_receipt(
    cycle: DreamCycle, *, write: bool = True, state_root: Optional[Path] = None,
) -> dict[str, Any]:
    payload = {
        "ts": cycle.ts,
        "trace_id": str(uuid.uuid4()),
        "kind": "DREAM_CYCLE",
        "receipt_id": cycle.receipt_id,
        "truth_label": cycle.truth_label,
        "truth_boundary": cycle.truth_boundary,
        "idle_signal": cycle.idle_signal,
        "n_memories_scored": cycle.n_memories_scored,
        "top_memories": cycle.top_memories,
        "compression_candidates": cycle.compression_candidates,
        "stgm_minted": cycle.stgm_minted,
        "affect_valence_delta": cycle.affect_valence_delta,
        "digest_line": cycle.digest_line,
    }
    canonical = json.dumps(payload, sort_keys=True, default=str)
    payload["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if write:
        ledger = (Path(state_root) if state_root else _STATE) / "alice_dream_cycles.jsonl"
        try:
            ledger.parent.mkdir(parents=True, exist_ok=True)
            with ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
        except Exception:
            pass
    return payload


# ── CLI entry ──────────────────────────────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true",
                   help="run dream cycle even if not idle")
    p.add_argument("--window-minutes", type=float, default=240.0)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args(argv)
    out = run_dream_cycle(
        window_minutes=args.window_minutes,
        force=args.force,
        write=not args.no_write,
    )
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
