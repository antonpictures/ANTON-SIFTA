#!/usr/bin/env python3
"""
immune_memory.py — Antibody Ledger for Swarm OS
=================================================

Every blocked/quarantined pattern gets hashed into an antibody ledger.
Next time something *similar* (not identical) arrives, the OS recognizes
the family and reacts faster.  Over months the Swarm develops genuine
immune history.

Antibodies propagate across nodes via dead-drop sync:
  M1 gets attacked → antibody written → git sync → M5 is vaccinated.

Each antibody entry is Ed25519-signed by the node that discovered it.

Persistence: .sifta_state/antibody_ledger.jsonl
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_LEDGER = _STATE_DIR / "antibody_ledger.jsonl"

SIMILARITY_THRESHOLD = 0.6
EVAPORATION_DAYS = 90
BOOST_ON_MATCH = 2.0


@dataclass
class Antibody:
    pattern_hash: str
    pattern_type: str  # "ip_flood", "payload_anomaly", "port_scan", etc.
    signature_vector: list[float]  # compact feature vector for similarity
    origin_node: str  # hardware serial
    discovered_ts: str
    strength: float = 1.0
    matches: int = 0
    ed25519_sig: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Antibody":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    ma = sum(x * x for x in a) ** 0.5
    mb = sum(x * x for x in b) ** 0.5
    if ma < 1e-12 or mb < 1e-12:
        return 0.0
    return dot / (ma * mb)


def _hash_pattern(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _load_ledger() -> list[Antibody]:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not _LEDGER.exists():
        return []
    abs_list: list[Antibody] = []
    for line in _LEDGER.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            abs_list.append(Antibody.from_dict(json.loads(line)))
        except Exception:
            continue
    return abs_list


def _append(ab: Antibody) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a") as f:
        f.write(json.dumps(ab.to_dict()) + "\n")


def _rewrite(antibodies: list[Antibody]) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "w") as f:
        for ab in antibodies:
            f.write(json.dumps(ab.to_dict()) + "\n")


def _sign_antibody(ab: Antibody) -> Antibody:
    """Sign with Ed25519 if crypto_keychain is available."""
    try:
        import sys
        if str(_REPO / "System") not in sys.path:
            sys.path.insert(0, str(_REPO / "System"))
        from crypto_keychain import sign_block
        payload = f"{ab.pattern_hash}:{ab.pattern_type}:{ab.discovered_ts}"
        ab.ed25519_sig = sign_block(payload)
    except Exception:
        ab.ed25519_sig = "UNSIGNED"
    return ab


def register_threat(
    raw_pattern: str,
    pattern_type: str,
    feature_vector: list[float],
    origin_node: str = "GTH4921YP3",
) -> Antibody:
    """Register a new threat pattern. Creates a signed antibody.
    If a similar antibody already exists, boosts it instead."""
    existing = _load_ledger()

    for ab in existing:
        sim = _cosine_sim(ab.signature_vector, feature_vector)
        if sim >= SIMILARITY_THRESHOLD:
            ab.strength = round(ab.strength + BOOST_ON_MATCH, 4)
            ab.matches += 1
            _rewrite(existing)
            return ab

    new_ab = Antibody(
        pattern_hash=_hash_pattern(raw_pattern),
        pattern_type=pattern_type,
        signature_vector=feature_vector,
        origin_node=origin_node,
        discovered_ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        strength=1.0,
        matches=0,
    )
    new_ab = _sign_antibody(new_ab)
    _append(new_ab)
    return new_ab


def check_threat(feature_vector: list[float]) -> tuple[bool, Antibody | None, float]:
    """Check an incoming pattern against immune memory.
    Returns (recognized, matching_antibody, similarity_score)."""
    ledger = _load_ledger()
    best_sim = 0.0
    best_ab: Antibody | None = None

    for ab in ledger:
        sim = _cosine_sim(ab.signature_vector, feature_vector)
        if sim > best_sim:
            best_sim = sim
            best_ab = ab

    if best_sim >= SIMILARITY_THRESHOLD and best_ab is not None:
        best_ab.matches += 1
        best_ab.strength = round(best_ab.strength + 0.5, 4)
        _rewrite(ledger)
        return (True, best_ab, best_sim)

    return (False, None, best_sim)


def evaporate() -> int:
    """Remove antibodies older than EVAPORATION_DAYS with low strength.
    Called periodically (e.g. from dream_engine). Returns count removed."""
    ledger = _load_ledger()
    now = time.time()
    survivors: list[Antibody] = []
    for ab in ledger:
        try:
            ts = time.mktime(time.strptime(ab.discovered_ts, "%Y-%m-%dT%H:%M:%SZ"))
        except Exception:
            ts = now
        age_days = (now - ts) / 86400
        if age_days > EVAPORATION_DAYS and ab.strength < 2.0:
            continue
        survivors.append(ab)
    removed = len(ledger) - len(survivors)
    if removed > 0:
        _rewrite(survivors)
    return removed


def immune_status() -> dict[str, Any]:
    """Quick summary for dashboards and dream reports."""
    ledger = _load_ledger()
    types: dict[str, int] = {}
    total_matches = 0
    for ab in ledger:
        types[ab.pattern_type] = types.get(ab.pattern_type, 0) + 1
        total_matches += ab.matches
    return {
        "total_antibodies": len(ledger),
        "total_matches": total_matches,
        "types": types,
        "strongest": max((ab.strength for ab in ledger), default=0.0),
    }


if __name__ == "__main__":
    ab = register_threat(
        "192.168.1.99:SYN_FLOOD:50000pps",
        "ip_flood",
        [0.9, 0.1, 0.0, 0.8, 0.3, 0.0, 0.7, 0.2],
    )
    print(f"Registered: {ab.pattern_type} hash={ab.pattern_hash} sig={ab.ed25519_sig[:24]}...")

    recognized, match, sim = check_threat([0.85, 0.12, 0.02, 0.78, 0.28, 0.01, 0.68, 0.19])
    print(f"Check similar: recognized={recognized} sim={sim:.3f}")

    recognized2, _, sim2 = check_threat([0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    print(f"Check unrelated: recognized={recognized2} sim={sim2:.3f}")

    print(f"Immune status: {immune_status()}")
