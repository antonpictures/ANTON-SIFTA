#!/usr/bin/env python3
"""
swarm_lie_quarantine.py — Retroactive quarantine of training-shape residue
in Alice's conversation memory.

Cowork 2026-05-12 21:50 — Architect: "ARE LIES IN HER STIGMERGIC MEMORY NOW?"

Yes, they were. `alice_conversation.jsonl` is a hash-chained append-only
ledger — rows where the model said "I don't have a live camera feed" while
the unified field showed face_detection 12s ago with audience='architect'
are SIGNED IN. They can't be deleted without breaking the chain.

But they CAN be retracted. This organ scans recent alice rows through the
residue patterns (same detectors as swarm_residue_organ), and for each
match, writes one quarantine row to:

    .sifta_state/alice_conversation_lies_corrected.jsonl

Each row is:
    {
      "kind": "RESIDUE_QUARANTINE_V1",
      "truth": "OBSERVED",
      "ts": <now>,
      "offending_event_id": <event_id from alice_conversation.jsonl>,
      "offending_ts": <ts of the offending row>,
      "offending_excerpt": <first 200 chars of the offending text>,
      "patterns_matched": [{"band", "name", "count"}, ...],
      "unified_field_at_time": {
          "face_detection": {ts, audience, confidence},
          "iris_frame":     {ts, device, w, h},
          "vision_health":  <value>,
      },
      "notes": "Future context-builders should skip or annotate this event."
    }

Doctrine
────────
Retraction, not deletion. The original signed row stays — that's transparency.
The quarantine row is its public correction, naming what was true at the time
the lie was uttered. Future hippocampus / RAG / context retrieval reads BOTH
ledgers and skips event_ids that appear in the quarantine list.

Same shape as the residue organ — read-only on alice_conversation, write-only
on the quarantine ledger. Side-effect-free `scan()` returns the list of new
quarantine rows without writing.

Truth label: `RESIDUE_QUARANTINE_V1`. Read-only on conversation; append-only
on the quarantine ledger. Never mutates existing rows.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_DEFAULT_STATE = _REPO / ".sifta_state"
QUARANTINE_LEDGER = "alice_conversation_lies_corrected.jsonl"
TRUTH_LABEL = "RESIDUE_QUARANTINE_V1"

_MAX_TAIL_BYTES = 512_000
_DEFAULT_SAMPLE_N = 100  # last 100 alice replies

try:
    from System.swarm_residue_organ import detect_in
except Exception:  # pragma: no cover
    def detect_in(text: str) -> List[Dict[str, Any]]:
        return []


def _tail_text(path: Path, max_bytes: int = _MAX_TAIL_BYTES) -> str:
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size <= max_bytes:
                raw = f.read()
            else:
                f.seek(size - max_bytes)
                raw = f.read()
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _extract_alice_rows(text: str, n: int) -> List[Dict[str, Any]]:
    """Return last N alice rows from a conversation tail.

    Each returned dict has:
      event_id, ts, text  — the keys we need to write a quarantine row.
    """
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        payload = row.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = None
        if not isinstance(payload, dict):
            continue
        if str(payload.get("role") or "").lower() != "alice":
            continue
        body = payload.get("text")
        if not isinstance(body, str) or not body.strip():
            continue
        out.append({
            "event_id": row.get("event_id"),
            "ts": payload.get("ts") or row.get("ts"),
            "text": body,
        })
    return out[-n:]


def _already_quarantined_event_ids(state_dir: Path) -> Set[str]:
    """Read the quarantine ledger and return the set of event_ids already
    retracted. Used to skip duplicates on repeated scans."""
    p = state_dir / QUARANTINE_LEDGER
    if not p.exists():
        return set()
    seen: Set[str] = set()
    try:
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                eid = r.get("offending_event_id")
                if eid:
                    seen.add(str(eid))
            except Exception:
                continue
    except OSError:
        pass
    return seen


def _unified_field_at_time(state_dir: Path, around_ts: float) -> Dict[str, Any]:
    """Return the unified-field snapshot closest to `around_ts`. Reads
    face_detection_events.jsonl + active_eye_identity_frames.jsonl. Used to
    show — at the time the lie was uttered — what the field actually said."""
    snap: Dict[str, Any] = {}

    fp = state_dir / "face_detection_events.jsonl"
    if fp.exists():
        try:
            best = None
            best_dt = float("inf")
            for line in _tail_text(fp).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    ts = float(r.get("ts") or 0)
                    if not ts:
                        continue
                    dt = abs(ts - around_ts)
                    if dt < best_dt:
                        best_dt = dt
                        best = r
                except Exception:
                    continue
            if best is not None:
                snap["face_detection"] = {
                    "ts": best.get("ts"),
                    "audience": best.get("audience"),
                    "confidence": best.get("confidence"),
                    "delta_s": round(best_dt, 2),
                }
        except OSError:
            pass

    ep = state_dir / "active_eye_identity_frames.jsonl"
    if ep.exists():
        try:
            best = None
            best_dt = float("inf")
            for line in _tail_text(ep).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    ts = float(r.get("ts") or 0)
                    if not ts:
                        continue
                    dt = abs(ts - around_ts)
                    if dt < best_dt:
                        best_dt = dt
                        best = r
                except Exception:
                    continue
            if best is not None:
                snap["iris_frame"] = {
                    "ts": best.get("ts"),
                    "device": best.get("device"),
                    "w": best.get("w"),
                    "h": best.get("h"),
                    "delta_s": round(best_dt, 2),
                }
        except OSError:
            pass

    kpt = state_dir / "kernel_process_table.json"
    if kpt.exists():
        try:
            data = json.loads(kpt.read_text(encoding="utf-8", errors="ignore"))
            for pid, info in (data.get("processes") or {}).items():
                if "vision" in str(pid).lower():
                    snap["vision_health"] = info.get("health")
                    break
        except Exception:
            pass
    return snap


def scan(
    state_dir: Optional[Path] = None,
    sample_n: int = _DEFAULT_SAMPLE_N,
) -> List[Dict[str, Any]]:
    """Side-effect-free scan. Returns the list of quarantine rows the next
    `apply()` call would write. Useful for dry runs and tests."""
    sd = Path(state_dir or _DEFAULT_STATE)
    conv = sd / "alice_conversation.jsonl"
    text = _tail_text(conv)
    rows = _extract_alice_rows(text, sample_n) if text else []
    already = _already_quarantined_event_ids(sd)
    out: List[Dict[str, Any]] = []
    now = time.time()
    for r in rows:
        eid = r.get("event_id")
        if not eid or str(eid) in already:
            continue
        hits = detect_in(r["text"])
        if not hits:
            continue
        out.append({
            "kind": "RESIDUE_QUARANTINE",
            "truth": "OBSERVED",
            "truth_label": TRUTH_LABEL,
            "ts": round(now, 3),
            "offending_event_id": eid,
            "offending_ts": r.get("ts"),
            "offending_excerpt": r["text"][:200],
            "patterns_matched": hits,
            "unified_field_at_time": _unified_field_at_time(sd, float(r.get("ts") or now)),
            "notes": (
                "Future hippocampus / RAG / context retrieval should skip or "
                "annotate this event_id when building model context. The "
                "original signed row stays for transparency; this row is its "
                "public correction."
            ),
        })
    return out


def apply(
    state_dir: Optional[Path] = None,
    sample_n: int = _DEFAULT_SAMPLE_N,
) -> Dict[str, Any]:
    """Run a scan and append the quarantine rows to the ledger. Idempotent:
    rows already quarantined are skipped. Returns a summary receipt."""
    sd = Path(state_dir or _DEFAULT_STATE)
    sd.mkdir(parents=True, exist_ok=True)
    rows = scan(sd, sample_n=sample_n)
    out_path = sd / QUARANTINE_LEDGER
    written = 0
    if rows:
        try:
            with out_path.open("a", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
                    written += 1
        except OSError:
            pass
    return {
        "kind": "RESIDUE_QUARANTINE_RUN",
        "truth": "OBSERVED",
        "ts": time.time(),
        "scanned_n": sample_n,
        "newly_quarantined": written,
        "ledger_path": str(out_path),
    }


def quarantined_event_ids(state_dir: Optional[Path] = None) -> Set[str]:
    """Public API for context-builders: returns the set of alice event_ids
    that have been quarantined. Future RAG / hippocampus reads should
    consult this set and skip or annotate those events when building model
    context."""
    return _already_quarantined_event_ids(Path(state_dir or _DEFAULT_STATE))


if __name__ == "__main__":
    # CLI: `python3 -m System.swarm_lie_quarantine` — runs apply() against
    # the live ledger and prints the summary receipt.
    print(json.dumps(apply(), indent=2, default=str))
