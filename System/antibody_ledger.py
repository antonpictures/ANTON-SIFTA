#!/usr/bin/env python3
"""
SIFTA Antibody Ledger — Persistent Swarm Immune Memory
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Like biological memory B-cells: once the Swarm kills a hostile,
the attack signature is hashed and stored permanently. Any future
hostile matching a known signature is rejected instantly — the
Swarm is vaccinated.

Cross-node sync via git: antibody_ledger.jsonl is versioned,
so when M1 pulls from M5, it inherits all vaccinations.

Usage:
    from antibody_ledger import record_kill, is_vaccinated, get_antibody_count

    # After a swimmer kills a hostile:
    record_kill("UNSIGNED_PACEMAKER_SET", "heart", "HERMES_04", "GTH4921YP3")

    # Before allowing any action:
    if is_vaccinated("UNSIGNED_PACEMAKER_SET"):
        reject_immediately()  # known threat — zero-cost block

Storage: .sifta_state/antibody_ledger.jsonl (append-only, flock-locked)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

# ── Paths ──────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
ANTIBODY_LEDGER = _STATE_DIR / "antibody_ledger.jsonl"

# ── Import locked append ──────────────────────────────────────────
import sys
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))

try:
    from System.ledger_append import append_jsonl_line as _append
except ImportError:
    def _append(path, row):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


def _signature_hash(payload: str) -> str:
    """
    Create a stable fingerprint of an attack payload.
    This normalizes casing and whitespace so variants of the same
    attack pattern map to the same antibody.
    """
    normalized = payload.strip().upper().replace(" ", "_")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


# ═══════════════════════════════════════════════════════════════════
#  IN-MEMORY CACHE — loaded once, updated on write
# ═══════════════════════════════════════════════════════════════════

_antibody_cache: Optional[Dict[str, dict]] = None  # sig_hash → ledger row


def _load_cache() -> Dict[str, dict]:
    """Load all known antibodies from disk into memory."""
    global _antibody_cache
    if _antibody_cache is not None:
        return _antibody_cache

    _antibody_cache = {}
    if not ANTIBODY_LEDGER.exists():
        return _antibody_cache

    for line in ANTIBODY_LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            sig = row.get("signature_hash", "")
            if sig:
                _antibody_cache[sig] = row
        except (json.JSONDecodeError, KeyError):
            continue

    return _antibody_cache


def reload_cache() -> int:
    """Force-reload from disk. Returns count of known antibodies."""
    global _antibody_cache
    _antibody_cache = None
    return len(_load_cache())


# ═══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════

def record_kill(
    payload: str,
    target_organ: str,
    killer_swimmer: str,
    node_serial: str = "",
    extra: Optional[dict] = None,
) -> dict:
    """
    Record a hostile kill → create an antibody for the attack signature.

    Returns the antibody record (also appended to antibody_ledger.jsonl).
    If the signature is already known, returns the existing record
    without duplicating (idempotent vaccination).
    """
    sig_hash = _signature_hash(payload)
    cache = _load_cache()

    # Already vaccinated — return existing antibody
    if sig_hash in cache:
        existing = cache[sig_hash]
        existing["_cached"] = True
        # Increment encounter count in memory (not re-appended)
        existing["encounters"] = existing.get("encounters", 1) + 1
        return existing

    # New antibody — first encounter
    _STATE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from silicon_serial import get_silicon_serial
        local_serial = node_serial or get_silicon_serial()
    except Exception:
        local_serial = node_serial or "UNKNOWN"

    record = {
        "event": "ANTIBODY_CREATED",
        "timestamp": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "signature_hash": sig_hash,
        "payload_raw": payload,
        "payload_normalized": payload.strip().upper().replace(" ", "_"),
        "target_organ": target_organ,
        "killer_swimmer": killer_swimmer,
        "origin_node": local_serial,
        "encounters": 1,
    }
    if extra:
        record["extra"] = extra

    _append(ANTIBODY_LEDGER, record)
    cache[sig_hash] = record
    return record


def is_vaccinated(payload: str) -> bool:
    """
    Check if the Swarm has seen this attack signature before.
    O(1) hash lookup — zero-cost immune check.
    """
    sig_hash = _signature_hash(payload)
    return sig_hash in _load_cache()


def get_antibody(payload: str) -> Optional[dict]:
    """Get the full antibody record for a payload, or None."""
    sig_hash = _signature_hash(payload)
    return _load_cache().get(sig_hash)


def get_all_antibodies() -> List[dict]:
    """Return all known antibodies (for dashboard / cross-node sync)."""
    return list(_load_cache().values())


def get_antibody_count() -> int:
    """Number of unique attack signatures the Swarm remembers."""
    return len(_load_cache())


def get_vaccination_report() -> dict:
    """Summary for Finance dashboard / swarm_state API."""
    cache = _load_cache()
    organs_hit: Dict[str, int] = {}
    total_encounters = 0
    for ab in cache.values():
        organ = ab.get("target_organ", "unknown")
        organs_hit[organ] = organs_hit.get(organ, 0) + 1
        total_encounters += ab.get("encounters", 1)

    return {
        "unique_antibodies": len(cache),
        "total_encounters": total_encounters,
        "organs_targeted": organs_hit,
        "ledger_path": str(ANTIBODY_LEDGER),
    }


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys as _sys

    if "--report" in _sys.argv:
        report = get_vaccination_report()
        print(json.dumps(report, indent=2))
    elif "--check" in _sys.argv and len(_sys.argv) > 2:
        payload = " ".join(_sys.argv[_sys.argv.index("--check") + 1:])
        if is_vaccinated(payload):
            ab = get_antibody(payload)
            print(f"✅ VACCINATED: {payload}")
            print(f"   First seen: {ab.get('ts_iso', '?')}")
            print(f"   Killed by:  {ab.get('killer_swimmer', '?')}")
            print(f"   On node:    {ab.get('origin_node', '?')}")
        else:
            print(f"❌ UNKNOWN: {payload} — no antibody exists")
    else:
        count = reload_cache()
        print(f"SIFTA Antibody Ledger: {count} unique antibodies")
        print(f"  Path: {ANTIBODY_LEDGER}")
        print(f"\nUsage:")
        print(f"  python3 {_sys.argv[0]} --report")
        print(f"  python3 {_sys.argv[0]} --check UNSIGNED_PACEMAKER_SET")
