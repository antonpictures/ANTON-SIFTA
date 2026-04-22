#!/usr/bin/env python3
"""
System/swarm_lysosome_excretor_audit.py
══════════════════════════════════════════════════════════════════════
Event 22 — STIGAUTH audit (read-only)

Loads .sifta_state/gemma4_sentinel_last.json from swarm_gemma4_sentinel_bridge
and explains why the pasted “LYSOSOME GEMMA EXCRETOR” cannot be applied:
schema mismatch, missing fields, unsafe semantics.

No GGUF writes. No random noise. No bridge detonation.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SENTINEL = REPO / ".sifta_state" / "gemma4_sentinel_last.json"


def load_sentinel(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing sentinel artifact: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def pasted_predicate(row: Dict[str, Any]) -> bool:
    """
    Literal translation of the PASTED script's is_corporate_tensor logic
    onto REAL sentinel field names where possible.

    Original paste used:
      entropy < 7.0, kurtosis > 4.5, ray_var > 0.0005
    We map entropy -> spectral_entropy_bits; kurtosis is ABSENT -> use 0
    (same as paste's .get('kurtosis', 0)); ray_var -> rayleigh_var.
    """
    ent = row.get("spectral_entropy_bits")
    kurt = row.get("kurtosis", 0)
    if kurt is None:
        kurt = 0
    ray = row.get("rayleigh_var", 0) or 0
    if ent is None:
        return False
    try:
        ent_f = float(ent)
    except (TypeError, ValueError):
        return False
    return ent_f < 7.0 and float(kurt) > 4.5 and float(ray) > 0.0005


def honest_predicate_q4_spike(row: Dict[str, Any]) -> bool:
    """Demonstrates kurtosis default kills the paste's boolean."""
    if row.get("qtype") not in ("Q4_K", "Q6_K"):
        return False
    ent = row.get("spectral_entropy_bits")
    ray = row.get("rayleigh_var")
    if ent is None or ray is None:
        return False
    return float(ent) < 7.0 and float(ray) > 0.0005


def proof_of_property() -> bool:
    data = load_sentinel(DEFAULT_SENTINEL)
    assert data.get("ok") is True, "sentinel JSON must be ok=true"
    rows: List[Dict[str, Any]] = data["sentinel_rows"]
    assert isinstance(rows, list) and rows, "sentinel_rows must be non-empty"

    # PASTED logic with kurtosis default 0 never fires
    pasted_hits = [r for r in rows if pasted_predicate(r)]
    assert len(pasted_hits) == 0, (
        "[FAIL] Pasted is_corporate_tensor unexpectedly matched rows — "
        "review thresholds or schema drift."
    )

    # If we honestly drop the nonexistent kurtosis term, Q4 blocks match
    # spectral<7 AND rayleigh — but that is NOT "RLHF cancer", see .dirt review
    spike = [r["tensor"] for r in rows if honest_predicate_q4_spike(r)]
    assert len(spike) >= 1, "[FAIL] expected at least one Q4 row with H<7 and rayleigh spike"

    print("[PASS] swarm_lysosome_excretor_audit.proof_of_property")
    print(f"      pasted is_corporate_tensor (with kurtosis default): {len(pasted_hits)} hits")
    print(f"      honest Q4 spectral+rayleigh spike (NOT RLHF claim): {len(spike)} hits")
    return True


def main() -> None:
    p = Path(os.environ.get("SIFTA_SENTINEL_JSON", str(DEFAULT_SENTINEL)))
    data = load_sentinel(p)

    print("\n=== LYSOSOME EXCRETOR — STIGAUTH AUDIT (read-only) ===")
    print(f"[*] Sentinel: {p}")
    print(f"[*] Keys present: {list(data.keys())}")
    if "tensors" in data:
        print("[!] Found legacy 'tensors' key — pasted excretor expected this.")
    else:
        print("[-] No 'tensors' key — pasted excretor raises KeyError immediately.")

    rows = data.get("sentinel_rows", [])
    print(f"[*] sentinel_rows: {len(rows)}")

    pasted_hits = [r for r in rows if pasted_predicate(r)]
    spike = [r for r in rows if honest_predicate_q4_spike(r)]

    print(f"\n[*] Pasted predicate hits (kurtosis default 0): {len(pasted_hits)}")
    for r in pasted_hits[:5]:
        print("   ", r.get("tensor"))

    print(f"\n[*] Q4/Q6 'spectral<7 AND rayleigh>5e-4' (for illustration only): {len(spike)}")
    for r in spike[:8]:
        print(
            f"    {r.get('tensor'):<42} H={r.get('spectral_entropy_bits')} "
            f"ray={r.get('rayleigh_var')}"
        )

    print(
        "\n[VERDICT] Do not run random-noise GGUF surgery. "
        "See Archive/.../C47H_drop_LYSOSOME_GEMMA_EXCRETOR_STIGAUTH_v1.dirt"
    )


if __name__ == "__main__":
    main()
