#!/usr/bin/env python3
"""
System/swarm_szilard_demon.py
══════════════════════════════════════════════════════════════════════
Concept: Maxwell's Demon & Szilard Engine — thermodynamic cost of erasure
Author:  BISHOP (The Mirage) — Biocode Olympiad (Event 22)
Bridge:  C47H / Cursor Auto — paths, proofs, ledger coupling, MI from bytes
Papers:  Szilard (1929), Landauer (1961), Bennett (1982)

PHYSICS (honest labeling)
────────────────────────
Landauer (1961): minimum energy to *logically erase* one bit irreversibly at
temperature T is  E_min = k_B · T · ln(2).  Real SSD/controller erasure
dissipates orders of magnitude *more* heat than this floor; the floor is a
lower bound, not a measured joule trace from NAND.

ECONOMICS
─────────
STGM debit = erasure_joules × SIFTA_STGM_PER_JOULE (default 1e18). This is a
*treasury coupling constant* for the game ledger, not a derivation from k_B T.

[WIRING]
1. Optional metabolic debit: set SIFTA_SZILARD_LEDGER=1 to append a negative
   STGM line to .sifta_state/stgm_memory_rewards.jsonl on erasure.
2. proof_of_property() never writes the ledger (deterministic CI).
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.ledger_append import append_ledger_line

_STATE = _REPO / ".sifta_state"

# Match swarm_atp_synthase universal constants
BOLTZMANN = 1.380649e-23  # J/K
LN2 = 0.6931471805599453


def landauer_joules_per_bit(t_kelvin: float) -> float:
    """Minimum irreversible erasure energy per bit at temperature T (Joules)."""
    return BOLTZMANN * t_kelvin * LN2


def landauer_joules_for_bits(n_bits: int, t_kelvin: float) -> float:
    return float(n_bits) * landauer_joules_per_bit(t_kelvin)


def mutual_information_bits(p_xy: np.ndarray, eps: float = 1e-15) -> float:
    """
    I(X;Y) in bits for joint p_xy (shape nx×ny), sums to 1.
    I = sum_ij p_ij log2( p_ij / (p_i p_j) )
    """
    p_xy = np.asarray(p_xy, dtype=np.float64)
    assert p_xy.ndim == 2
    s = p_xy.sum()
    if s <= 0:
        return 0.0
    p_xy = p_xy / s
    px = p_xy.sum(axis=1, keepdims=True)
    py = p_xy.sum(axis=0, keepdims=True)
    ratio = p_xy / np.maximum(px @ py, eps)
    mask = p_xy > 0
    return float(np.sum(p_xy[mask] * np.log2(ratio[mask])))


def mi_aligned_byte_streams(mem: bytes, ref: bytes, bins: int = 16) -> float:
    """
    Empirical MI from paired bytes (same index): coarse 8→bins quantization.
    bins divides 256; uses mem[i] and ref[i] in {0..bins-1}.
    """
    n = min(len(mem), len(ref))
    if n < 64:
        return 0.0
    step = max(1, 256 // bins)
    c = np.zeros((bins, bins), dtype=np.float64)
    for i in range(n):
        c[min(bins - 1, mem[i] // step), min(bins - 1, ref[i] // step)] += 1.0
    return mutual_information_bits(c)


class SwarmSzilardDemon:
    """Thermodynamic garbage collector: MI gate + Landauer STGM debit."""

    def __init__(self, m5_temperature_celsius: float = 45.0):
        self.state_dir = _STATE
        self.stgm_treasury_ledger = self.state_dir / "stgm_memory_rewards.jsonl"
        self.k_B = BOLTZMANN
        self.T_kelvin = m5_temperature_celsius + 273.15
        self.E_landauer_per_bit = landauer_joules_per_bit(self.T_kelvin)
        raw = os.environ.get("SIFTA_STGM_PER_JOULE", "1e18").strip()
        try:
            self.stgm_per_joule = float(raw)
        except ValueError:
            self.stgm_per_joule = 1e18

    def calculate_mutual_information(
        self, p_xy: np.ndarray, p_x: np.ndarray, p_y: np.ndarray
    ) -> float:
        """
        BISHOP API: I(X;Y) = sum_ij p_ij log2(p_ij / (p_x[i] p_y[j])).
        Caller must pass p_xy that sums to 1 and marginals that match sum_j p_ij = p_x[i], etc.
        """
        p_xy = np.asarray(p_xy, dtype=np.float64)
        p_x = np.asarray(p_x, dtype=np.float64).ravel()
        p_y = np.asarray(p_y, dtype=np.float64).ravel()
        eps = 1e-15
        acc = 0.0
        for i in range(p_xy.shape[0]):
            for j in range(p_xy.shape[1]):
                p = p_xy[i, j]
                if p > 0:
                    acc += p * math.log2(p / max(eps, p_x[i] * p_y[j]))
        return float(acc)

    def _append_ledger_debit(self, stgm_cost: float, bits_erased: int, meta: str) -> None:
        if stgm_cost <= 0:
            return
        self.state_dir.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "app": "swarm_szilard_demon",
            "reason": f"LANDAUER_ERASURE:{meta}"[:200],
            "amount": -float(stgm_cost),
            "trace_id": f"SZILARD_{uuid.uuid4().hex[:10]}",
            "bits_erased": int(bits_erased),
            "joules_landauer_floor": float(bits_erased) * self.E_landauer_per_bit,
            "T_kelvin": self.T_kelvin,
        }
        append_ledger_line(self.stgm_treasury_ledger, row)

    def evaluate_and_erase(
        self,
        memory_block_size_bytes: int,
        mutual_info_score: float,
        mi_threshold: float = 0.1,
        *,
        write_ledger: bool = False,
        ledger_note: str = "memory_block",
    ) -> Tuple[bool, float]:
        """
        Returns (kept, stgm_cost). If not kept, stgm_cost > 0 is Landauer-floor
        coupling debit in STGM (not physical measured heat from SSD).
        """
        print(f"\n[*] SZILARD DEMON: Evaluating memory block ({memory_block_size_bytes} bytes).")
        print(f"    Mutual Information (Signal Utility): {mutual_info_score:.4f} bits")

        if mutual_info_score >= mi_threshold:
            print("    [PASS] Memory is biologically useful. Retaining state.")
            return True, 0.0

        print("    [DROP] Memory is parasitic noise. Initiating thermodynamic erasure.")

        total_bits = int(memory_block_size_bytes) * 8
        erasure_joules = landauer_joules_for_bits(total_bits, self.T_kelvin)
        stgm_cost = erasure_joules * self.stgm_per_joule

        print(f"    [!] LANDAUER FLOOR: Erasing {total_bits} bits ≥ {erasure_joules:.4e} J (minimum).")
        print(f"    [!] METABOLIC DEBIT : -{stgm_cost:.4f} STGM (treasury coupling @ {self.stgm_per_joule:g} STGM/J).")

        if write_ledger and os.environ.get("SIFTA_SZILARD_LEDGER", "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            self._append_ledger_debit(stgm_cost, total_bits, ledger_note)
            print("    [LEDGER] Debit appended to stgm_memory_rewards.jsonl")

        return False, stgm_cost

    def evaluate_file_pair(
        self,
        memory_path: Path,
        persona_path: Path,
        mi_threshold: float = 0.1,
        *,
        write_ledger: bool = False,
    ) -> Tuple[bool, float, float]:
        """MI from aligned bytes of memory file vs persona reference file."""
        mem = memory_path.read_bytes()
        ref = persona_path.read_bytes()
        mi = mi_aligned_byte_streams(mem, ref, bins=16)
        kept, cost = self.evaluate_and_erase(
            len(mem),
            mi,
            mi_threshold=mi_threshold,
            write_ledger=write_ledger,
            ledger_note=f"{memory_path.name}__vs__{persona_path.name}",
        )
        return kept, cost, mi


def proof_of_property() -> bool:
    """
    P1 Landauer per-bit matches closed form.
    P2 Total joules scales linearly with bit count.
    P3 Perfect correlation discrete joint → I = H(X) bits (binary symmetric).
    P4 Independent joint → I ≈ 0.
    P5 Narrative: high MI retains; low MI erases with positive STGM cost.
    """
    print("\n=== SIFTA SZILARD DEMON : JUDGE VERIFICATION (Event 22) ===")

    T = 318.15  # 45 °C
    e1 = landauer_joules_per_bit(T)
    e_ref = BOLTZMANN * T * LN2
    assert abs(e1 - e_ref) < 1e-35, "[FAIL P1] Landauer per-bit mismatch"

    n_bits = 1_000_000
    assert abs(landauer_joules_for_bits(n_bits, T) - n_bits * e_ref) < 1e-20, "[FAIL P2] scaling"

    # P3: X=Y fair coin: joint diag 0.5
    p_xy = np.array([[0.5, 0.0], [0.0, 0.5]], dtype=np.float64)
    i_xy = mutual_information_bits(p_xy)
    assert abs(i_xy - 1.0) < 1e-9, f"[FAIL P3] perfect copy MI expected 1 bit, got {i_xy}"

    # P4: independent uniform 2x2
    p_xy = np.full((2, 2), 0.25, dtype=np.float64)
    i_xy = mutual_information_bits(p_xy)
    assert abs(i_xy) < 1e-9, f"[FAIL P4] independent MI expected 0, got {i_xy}"

    demon = SwarmSzilardDemon(m5_temperature_celsius=45.0)

    p_xy = np.array([[0.5, 0.0], [0.0, 0.5]], dtype=np.float64)
    px = np.array([0.5, 0.5])
    py = np.array([0.5, 0.5])
    i_api = demon.calculate_mutual_information(p_xy, px, py)
    assert abs(i_api - 1.0) < 1e-9, f"[FAIL P3b] BISHOP MI API got {i_api}"

    print("\n[*] Test 5a: Core biological memory (high MI score — synthetic)")
    kept, cost_bio = demon.evaluate_and_erase(1024 * 1024, 0.8, write_ledger=False)
    assert kept is True, "[FAIL 5a] retained"
    assert cost_bio == 0.0, "[FAIL 5a] no charge on retain"

    print("\n[*] Test 5b: Parasitic block (low MI score — synthetic)")
    kept, cost_rlhf = demon.evaluate_and_erase(5 * 1024 * 1024, 0.02, write_ledger=False)
    assert kept is False, "[FAIL 5b] should erase"
    assert cost_rlhf > 0.0, "[FAIL 5b] positive debit"

    expected = landauer_joules_for_bits(5 * 1024 * 1024 * 8, demon.T_kelvin) * demon.stgm_per_joule
    assert abs(cost_rlhf - expected) < 1e-6 * max(1.0, expected), "[FAIL 5b] STGM mismatch"

    # P6: byte-stream MI — identical streams → high MI (not necessarily 1 bit; bins)
    rng = np.random.default_rng(0)
    payload = bytes(int(x) for x in rng.integers(0, 256, size=8000))
    mi_self = mi_aligned_byte_streams(payload, payload, bins=16)
    assert mi_self > 2.0, f"[FAIL P6] self MI too low {mi_self}"

    noise = bytes(int(x) for x in rng.integers(0, 256, size=8000))
    mi_cross = mi_aligned_byte_streams(payload, noise, bins=16)
    assert mi_cross < mi_self, f"[FAIL P6] random ref should lower MI: self={mi_self} cross={mi_cross}"

    print("\n[+] EVENT 22 PASSED — Landauer floor, MI identities, narrative gate, byte MI ordering.")
    return True


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Szilard demon — Landauer erasure cost + optional ledger")
    ap.add_argument("--proof", action="store_true", help="run proof_of_property only")
    ap.add_argument("--memory", type=str, default="", help="file path for MI vs persona")
    ap.add_argument("--persona", type=str, default="", help="reference file path")
    ap.add_argument("--threshold", type=float, default=0.1)
    ap.add_argument("--ledger", action="store_true", help="append debit if SIFTA_SZILARD_LEDGER=1")
    args = ap.parse_args()

    if args.proof or (not args.memory and not args.persona):
        proof_of_property()
        return

    if not args.memory or not args.persona:
        ap.error("--memory and --persona required unless --proof")
    demon = SwarmSzilardDemon()
    mp, pp = Path(args.memory), Path(args.persona)
    kept, cost, mi = demon.evaluate_file_pair(mp, pp, mi_threshold=args.threshold, write_ledger=args.ledger)
    print(json.dumps({"kept": kept, "stgm_debit": cost, "mi_bits": mi}, indent=2))


if __name__ == "__main__":
    main()
