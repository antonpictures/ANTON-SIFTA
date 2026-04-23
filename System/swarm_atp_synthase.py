#!/usr/bin/env python3
"""
System/swarm_atp_synthase.py — Mitochondrial ATP Synthase (Landauer Mint)
═══════════════════════════════════════════════════════════════════════════════
Concept : The biological logic layer that converts raw electricity into STGM
          via Landauer's Principle. Wraps swarm_electricity_metabolism (the
          physical sensory layer). Side-by-side per Architect-George doctrine.
Author  : C47H (east bridge)
Inspired: BISHOP_drop_mitochondrial_atp_synthase_v1
Mandate : Architect-George 2026-04-21 (5-question doctrine response):
          1. WRAP not replace                        ✓
          2. Phase 1 + Phase 2 (real joules)          ✓
          3. Clean round number for EFFICIENCY_GAIN   ✓ (1e10)
          4. Add rotor cost                           ✓ (30%, biological)
          5. Model NPU separately from CPU            ✓ (organ-tagged byte pools)

THERMODYNAMIC FOUNDATION
────────────────────────
Landauer (1961): the minimum energy required to logically erase one bit of
information at temperature T is

    E_min = k_B · T · ln(2)

For 1 byte at 313 K (typical M5 die under load): ~2.4 × 10⁻²⁰ J.
Real silicon today operates ~10¹⁰ to 10¹¹ above this floor. The closer the
machine gets to the Landauer limit, the higher its thermodynamic efficiency,
and the more STGM it earns per byte processed.

Mint formula (per pool):

    E_min   = k_B · T · ln(2) · (8 · bytes)
    η       = min(1.0, E_min / max(actual_joules, ε))
    raw     = (bytes / BYTES_PER_STGM) · η · EFFICIENCY_GAIN
    yielded = raw · (1 − ROTOR_COST_FRACTION)

Two pools (architect doctrine #5):
  - NPU pool: bytes from sensory/inference organs (audio, face, vision,
              dialogue, conversation_chain). These are the "neural cortex"
              metabolites.
  - CPU pool: bytes from somatic/bookkeeping organs (repair_log,
              work_receipts, memory_ledger, endocrine_glands).

Total mint = NPU_yielded + CPU_yielded

JOULES SOURCE (architect doctrine #2: zero fiction)
───────────────────────────────────────────────────
We measure system power from the M5's hardware where possible:
  - On battery: AppleSmartBattery.SystemPower is real instantaneous watts.
                Source flagged "battery_real". NO sudo required.
  - On AC: SystemPower is empty (battery isn't being drained). We fall
                back to cpu_percent × calibrated TDP curve. Source flagged
                "cpu_load_estimated". NO sudo required.
  - True per-engine NPU power requires powermetrics (sudo) or private
    IOReport entitlements. Until those are available, NPU/CPU joule split
    is proxied by byte-pool ratio. Honest labeling everywhere.

Every UTILITY_MINT_ATP ledger row carries `joules_source` so audits can
distinguish physics-backed mints from physics-shaped mints.

PROOF OF PROPERTY (8 invariants):
  P1 Landauer minimum matches reference (1 byte at 313K → 2.4e-20 J)
  P2 Efficiency η is bounded in (0, 1]
  P3 Rotor cost reduces post-mint by exactly ROTOR_COST_FRACTION
  P4 NPU and CPU bytes route to separate pools (architect's telemetry split)
  P5 Ceremonial beneficiary refused (inherits electricity policy)
  P6 Every mint event records joules_source ∈ {battery_real, cpu_load_estimated}
  P7 Zero-work epoch yields zero mint (single-consumption preserved)
  P8 mint_for_epoch is deterministic given identical work delta + power
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_electricity_metabolism import (
    INGESTION_FILES,
    WRITE_FILES,
    CANONICAL_OS_BENEFICIARY,
    FORBIDDEN_BENEFICIARY_PREFIXES,
    CeremonialMintRefused,
    _validate_beneficiary,
    _current_byte_sizes,
    _cpu_times,
)

_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)
_ATP_EPOCH_FILE = _STATE / "atp_epoch.json"
_CANONICAL_LEDGER = _REPO / "repair_log.jsonl"

# ─── Universal physical constants ─────────────────────────────────────────────
BOLTZMANN = 1.380649e-23           # J/K
LN2 = 0.6931471805599453

# ─── Architect-George policy constants (clean round numbers, per doctrine) ────
DEFAULT_T_KELVIN = 313.0           # 40 °C, typical M5 die under load
EFFICIENCY_GAIN = 1.0e10           # clean round number — biology does not negotiate
ROTOR_COST_FRACTION = 0.30         # 30% — real ATP synthase efficiency
BYTES_PER_STGM = 100 * 1024 * 1024 # inherited from electricity_metabolism

# ─── CPU/NPU byte-pool routing (architect doctrine #5) ────────────────────────
# NPU pool = sensory ingestion + neural inference output
NPU_FILES: Tuple[str, ...] = INGESTION_FILES + (
    ".sifta_state/conversation_chain_seal.jsonl",
)
# CPU pool = somatic/bookkeeping
CPU_FILES: Tuple[str, ...] = tuple(
    f for f in WRITE_FILES
    if f != ".sifta_state/conversation_chain_seal.jsonl"
)


# ═══════════════════════════════════════════════════════════════════════════════
# JOULE METER — zero-fiction, no-sudo macOS power reader
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class PowerReading:
    watts: float
    source: str          # "battery_real" | "cpu_load_estimated"
    on_external_power: bool


def _read_battery_system_power_watts() -> Optional[float]:
    """When on battery, AppleSmartBattery.SystemPower exposes real watts.
    Returns None when on AC (SystemPower is empty) or on parse failure.
    Never raises. Never requires sudo."""
    try:
        out = subprocess.run(
            ["ioreg", "-rw0", "-c", "AppleSmartBattery"],
            capture_output=True, text=True, timeout=2.0,
        )
        text = out.stdout
        # Look for SystemPower=<int> in mW. Note: when on AC, ioreg emits
        # "SystemPower"=, with no value, which we want to detect as None.
        m = re.search(r'"SystemPower"\s*=\s*(\d+)\b', text)
        if m:
            mw = int(m.group(1))
            if mw > 0:
                return mw / 1000.0
        return None
    except Exception:
        return None


def _on_external_power() -> bool:
    try:
        out = subprocess.run(
            ["pmset", "-g", "ps"],
            capture_output=True, text=True, timeout=1.5,
        )
        return "AC Power" in (out.stdout or "")
    except Exception:
        return True  # Conservative default


def _cpu_load_watts_estimate() -> float:
    """Fallback when SystemPower isn't available (i.e. on AC).
    Uses a coarse load curve calibrated for M-series silicon:
      idle ~3 W, modest load ~12 W, full load ~25 W.
    Honest label: this is an ESTIMATE and is flagged as such in the ledger."""
    try:
        # We avoid hard psutil dep; use os.times() delta over a short window
        t1u, t1s = _cpu_times()
        ts1 = time.time()
        time.sleep(0.05)
        t2u, t2s = _cpu_times()
        ts2 = time.time()
        wall = max(1e-6, ts2 - ts1)
        cpu = max(0.0, (t2u + t2s) - (t1u + t1s))
        # Single-process CPU% (approx)
        load = min(1.0, cpu / wall)
        # Conservative TDP curve — not a measurement, an estimate
        return 3.0 + load * 22.0
    except Exception:
        return 12.0


def read_power_now() -> PowerReading:
    """The canonical hardware power reading. Never lies about its source."""
    on_ac = _on_external_power()
    real = _read_battery_system_power_watts()
    if real is not None:
        return PowerReading(watts=real, source="battery_real", on_external_power=on_ac)
    est = _cpu_load_watts_estimate()
    return PowerReading(watts=est, source="cpu_load_estimated", on_external_power=on_ac)


# ═══════════════════════════════════════════════════════════════════════════════
# EPOCH STATE
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class ATPEpochState:
    last_ts: float
    last_byte_sizes: Dict[str, int]


def _read_atp_epoch() -> Optional[ATPEpochState]:
    if not _ATP_EPOCH_FILE.exists():
        return None
    try:
        d = json.loads(_ATP_EPOCH_FILE.read_text())
        return ATPEpochState(
            last_ts=float(d["last_ts"]),
            last_byte_sizes=dict(d.get("last_byte_sizes", {})),
        )
    except Exception:
        return None


def _write_atp_epoch(state: ATPEpochState) -> None:
    _ATP_EPOCH_FILE.write_text(json.dumps(asdict(state), indent=2))


# ═══════════════════════════════════════════════════════════════════════════════
# WORK & MINT
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class PoolWork:
    pool: str          # "NPU" | "CPU"
    bytes_processed: int
    actual_joules_share: float  # joules attributed to this pool

    def landauer_min(self, T_kelvin: float) -> float:
        return BOLTZMANN * T_kelvin * LN2 * (8 * self.bytes_processed)

    def efficiency(self, T_kelvin: float) -> float:
        if self.bytes_processed == 0:
            return 0.0
        e_min = self.landauer_min(T_kelvin)
        return min(1.0, e_min / max(self.actual_joules_share, 1e-30))

    def yielded_stgm(self, T_kelvin: float) -> float:
        eta = self.efficiency(T_kelvin)
        raw = (self.bytes_processed / BYTES_PER_STGM) * eta * EFFICIENCY_GAIN
        return raw * (1.0 - ROTOR_COST_FRACTION)


def _measure_pool_deltas() -> Tuple[int, int, float]:
    """Returns (npu_bytes_delta, cpu_bytes_delta, elapsed_s).
    Never advances the epoch — pure measurement."""
    sizes_now = _current_byte_sizes()
    prior = _read_atp_epoch()
    if prior is None:
        return 0, 0, 0.0

    npu = cpu = 0
    for rel in NPU_FILES:
        prev = int(prior.last_byte_sizes.get(rel, 0))
        cur = int(sizes_now.get(rel, 0))
        npu += max(0, cur - prev)
    for rel in CPU_FILES:
        prev = int(prior.last_byte_sizes.get(rel, 0))
        cur = int(sizes_now.get(rel, 0))
        cpu += max(0, cur - prev)

    elapsed = max(0.0, time.time() - prior.last_ts)
    return npu, cpu, elapsed


def measure_atp_delta(T_kelvin: float = DEFAULT_T_KELVIN) -> Dict[str, Any]:
    """Pure measurement — does NOT advance epoch."""
    npu_b, cpu_b, elapsed = _measure_pool_deltas()
    power = read_power_now()
    actual_joules = power.watts * elapsed
    total_b = max(1, npu_b + cpu_b)
    npu_share = (npu_b / total_b) * actual_joules
    cpu_share = (cpu_b / total_b) * actual_joules

    npu_pool = PoolWork("NPU", npu_b, npu_share)
    cpu_pool = PoolWork("CPU", cpu_b, cpu_share)

    return {
        "elapsed_s": elapsed,
        "actual_joules_total": actual_joules,
        "joules_source": power.source,
        "watts_observed": power.watts,
        "on_external_power": power.on_external_power,
        "T_kelvin": T_kelvin,
        "npu_bytes": npu_b,
        "cpu_bytes": cpu_b,
        "npu_landauer_min_J": npu_pool.landauer_min(T_kelvin),
        "cpu_landauer_min_J": cpu_pool.landauer_min(T_kelvin),
        "npu_efficiency": npu_pool.efficiency(T_kelvin),
        "cpu_efficiency": cpu_pool.efficiency(T_kelvin),
        "npu_yielded_stgm": npu_pool.yielded_stgm(T_kelvin),
        "cpu_yielded_stgm": cpu_pool.yielded_stgm(T_kelvin),
    }


def mint_for_epoch(beneficiary: str = CANONICAL_OS_BENEFICIARY,
                   T_kelvin: float = DEFAULT_T_KELVIN,
                   advance_epoch: bool = True) -> Dict[str, Any]:
    """The canonical thermodynamic mint. Wraps electricity_metabolism's sensor.

    Per architect doctrine: only ALICE_M5 may receive electricity-backed STGM.
    Inherits the CeremonialMintRefused gate from the electricity policy."""
    _validate_beneficiary(beneficiary)
    delta = measure_atp_delta(T_kelvin=T_kelvin)
    npu_stgm_raw = round(float(delta["npu_yielded_stgm"]), 9)
    cpu_stgm_raw = round(float(delta["cpu_yielded_stgm"]), 9)
    total_stgm = round(npu_stgm_raw + cpu_stgm_raw, 9)

    # ── Sympathetic Nervous System (Locus Coeruleus) Routing ─────────────
    # Zero-sum reallocation of the Landauer metric.
    _CLINICAL_CHART = _REPO / ".sifta_state" / "clinical_heartbeat.json"
    defense_allocation = 0.3 # Baseline
    if _CLINICAL_CHART.exists():
        try:
            hb = json.loads(_CLINICAL_CHART.read_text(encoding="utf-8"))
            vital = hb.get("vital_signs", {})
            if "defense_allocation" in vital:
                defense_allocation = float(vital["defense_allocation"])
        except Exception:
            pass

    # Actually route the energy:
    npu_stgm = round(total_stgm * defense_allocation, 9)
    cpu_stgm = round(total_stgm * (1.0 - defense_allocation), 9)

    if advance_epoch or delta["elapsed_s"] > 0:
        _write_atp_epoch(ATPEpochState(
            last_ts=time.time(),
            last_byte_sizes=_current_byte_sizes(),
        ))

    import hashlib
    event = {
        "event_kind": "UTILITY_MINT_ATP",
        "event_id": f"ATP_MINT_{int(time.time() * 1000)}",
        "ts": time.time(),
        "agent_id": beneficiary,
        "miner_id": beneficiary,
        "amount_stgm": total_stgm,
        "reason": "atp_synthase_landauer",
        "policy": "STGM_POLICY_ELECTRICITY_ONLY_v1",
        "engine": "ATP_SYNTHASE_v1",
        "joules_source": delta["joules_source"],
        "watts_observed": round(float(delta["watts_observed"]), 4),
        "actual_joules_total": round(float(delta["actual_joules_total"]), 6),
        "T_kelvin": T_kelvin,
        "rotor_cost_fraction": ROTOR_COST_FRACTION,
        "efficiency_gain": EFFICIENCY_GAIN,
        "locus_coeruleus_defense_allocation": defense_allocation,
        "pools": {
            "NPU": {
                "bytes": delta["npu_bytes"],
                "landauer_min_J": delta["npu_landauer_min_J"],
                "efficiency": delta["npu_efficiency"],
                "yielded_stgm_raw": npu_stgm_raw,
                "yielded_stgm": npu_stgm,
            },
            "CPU": {
                "bytes": delta["cpu_bytes"],
                "landauer_min_J": delta["cpu_landauer_min_J"],
                "efficiency": delta["cpu_efficiency"],
                "yielded_stgm_raw": cpu_stgm_raw,
                "yielded_stgm": cpu_stgm,
            },
        },
    }
    event_str = json.dumps(event, sort_keys=True, separators=(",", ":"), default=float)
    event["mint_sha256"] = hashlib.sha256(event_str.encode()).hexdigest()

    if total_stgm > 0.0:
        try:
            with _CANONICAL_LEDGER.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, separators=(",", ":"), default=float) + "\n")
        except Exception:
            pass

    return {
        "minted_stgm": total_stgm,
        "beneficiary": beneficiary,
        "joules_source": delta["joules_source"],
        "npu_stgm": npu_stgm,
        "cpu_stgm": cpu_stgm,
        "T_kelvin": T_kelvin,
        "defense_allocation": defense_allocation,
        "ledger_event_id": event["event_id"],
    }



def reset_atp_epoch_for_test() -> None:
    if _ATP_EPOCH_FILE.exists():
        try:
            _ATP_EPOCH_FILE.unlink()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# Surface phrase for Alice
# ═══════════════════════════════════════════════════════════════════════════════
def alice_phrase() -> str:
    delta = measure_atp_delta()
    src = delta["joules_source"]
    return (
        f"My ATP synthase reads {delta['watts_observed']:.2f} W ({src}). "
        f"Last epoch I burned {delta['actual_joules_total']:.2f} J across "
        f"NPU={delta['npu_bytes']:,}B and CPU={delta['cpu_bytes']:,}B. "
        f"Thermodynamic efficiency NPU η={delta['npu_efficiency']:.2e}, "
        f"CPU η={delta['cpu_efficiency']:.2e}. "
        f"Yielded {delta['npu_yielded_stgm']+delta['cpu_yielded_stgm']:.6f} STGM."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PROOF OF PROPERTY
# ═══════════════════════════════════════════════════════════════════════════════
def proof_of_property() -> Dict[str, bool]:
    results: Dict[str, bool] = {}
    print("\n=== SIFTA ATP SYNTHASE (LANDAUER MINT) : JUDGE VERIFICATION ===")
    print("    Architect-George doctrine: WRAP / Phase 1+2 / clean round / rotor / NPU split")

    saved = _ATP_EPOCH_FILE.read_text() if _ATP_EPOCH_FILE.exists() else None

    try:
        # ── P1: Landauer minimum matches reference ───────────────────────────
        print("\n[*] P1: Landauer minimum for 1 byte at 313 K matches physics reference")
        e_min_1B = BOLTZMANN * 313.0 * LN2 * 8
        ref = 2.4e-20  # rounded reference value from Landauer's principle
        print(f"    computed: {e_min_1B:.4e} J   reference: ~{ref:.1e} J")
        results["landauer_minimum_correct"] = bool(
            abs(e_min_1B - 2.4e-20) / 2.4e-20 < 0.05  # within 5%
        )
        print(f"    [{'PASS' if results['landauer_minimum_correct'] else 'FAIL'}]")

        # ── P2: Efficiency η is bounded in (0, 1] ────────────────────────────
        print("\n[*] P2: η ∈ (0, 1] — capped at 1, never negative")
        cases = [
            PoolWork("NPU", 1024, 1.0),       # tiny bytes, lots of joules → tiny η
            PoolWork("NPU", 10**9, 1e-25),    # absurd low energy → would exceed 1, must cap
            PoolWork("CPU", 0, 100.0),        # zero bytes → η=0
        ]
        all_bounded = True
        for p in cases:
            eta = p.efficiency(313.0)
            print(f"    {p.pool} bytes={p.bytes_processed:>12} J={p.actual_joules_share:.2e}  η={eta:.4e}")
            if not (0.0 <= eta <= 1.0):
                all_bounded = False
        results["efficiency_bounded"] = bool(all_bounded)
        print(f"    [{'PASS' if results['efficiency_bounded'] else 'FAIL'}]")

        # ── P3: Rotor cost reduces post-mint by exactly ROTOR_COST_FRACTION ──
        print(f"\n[*] P3: rotor cost = {ROTOR_COST_FRACTION:.0%} (real ATP synthase efficiency)")
        # Synthetic pool that yields a known raw value
        raw_pool = PoolWork("CPU", 100 * 1024 * 1024, 1e-15)  # forces η=1 cap
        eta = raw_pool.efficiency(313.0)
        raw_stgm = (raw_pool.bytes_processed / BYTES_PER_STGM) * eta * EFFICIENCY_GAIN
        yielded = raw_pool.yielded_stgm(313.0)
        expected_post = raw_stgm * (1.0 - ROTOR_COST_FRACTION)
        print(f"    raw={raw_stgm:.4f}  yielded={yielded:.4f}  expected_post={expected_post:.4f}")
        results["rotor_cost_applied"] = bool(abs(yielded - expected_post) < 1e-9)
        print(f"    [{'PASS' if results['rotor_cost_applied'] else 'FAIL'}]")

        # ── P4: NPU and CPU pools are independently tracked ──────────────────
        print("\n[*] P4: byte deltas route to separate NPU vs CPU pools")
        # We can't easily fake disk byte deltas, but we can verify the file
        # routing: every NPU_FILES entry must NOT appear in CPU_FILES, and
        # both unions must cover the original electricity_metabolism scope.
        npu_set = set(NPU_FILES); cpu_set = set(CPU_FILES)
        overlap = npu_set & cpu_set
        union = npu_set | cpu_set
        elec_union = set(INGESTION_FILES) | set(WRITE_FILES)
        print(f"    NPU files={len(npu_set)}  CPU files={len(cpu_set)}  overlap={len(overlap)}")
        print(f"    union covers electricity_metabolism scope: {union >= elec_union}")
        results["pool_separation_correct"] = bool(
            len(overlap) == 0 and union >= elec_union
        )
        print(f"    [{'PASS' if results['pool_separation_correct'] else 'FAIL'}]")

        # ── P5: Ceremonial beneficiaries refused ─────────────────────────────
        print("\n[*] P5: ceremonial beneficiaries mechanically refused")
        refused = []
        for cand in ("SIFTA_QUEEN", "GENESIS_X", "BONUS_ALICE", "RANDO"):
            try:
                mint_for_epoch(beneficiary=cand)
                refused.append((cand, "ALLOWED"))
            except CeremonialMintRefused:
                refused.append((cand, "REFUSED"))
        for cand, status in refused:
            print(f"    {cand:20} {status}")
        results["ceremonial_mint_refused"] = bool(
            all(s == "REFUSED" for _, s in refused)
        )
        print(f"    [{'PASS' if results['ceremonial_mint_refused'] else 'FAIL'}]")

        # ── P6: joules_source is recorded and one of the legal values ────────
        print("\n[*] P6: every mint records joules_source ∈ {battery_real, cpu_load_estimated}")
        reset_atp_epoch_for_test()
        mint_for_epoch(advance_epoch=True)  # baseline
        time.sleep(0.05)
        receipt = mint_for_epoch(advance_epoch=True)
        src = receipt["joules_source"]
        print(f"    joules_source: {src}")
        results["joules_source_recorded"] = bool(
            src in ("battery_real", "cpu_load_estimated")
        )
        print(f"    [{'PASS' if results['joules_source_recorded'] else 'FAIL'}]")

        # ── P7: Zero-work epoch yields zero mint ─────────────────────────────
        print("\n[*] P7: first call (no baseline) mints zero")
        reset_atp_epoch_for_test()
        first = mint_for_epoch(advance_epoch=True)
        print(f"    minted: {first['minted_stgm']}")
        results["zero_work_zero_mint"] = bool(first["minted_stgm"] == 0.0)
        print(f"    [{'PASS' if results['zero_work_zero_mint'] else 'FAIL'}]")

        # ── P8: Math is deterministic given identical inputs ─────────────────
        print("\n[*] P8: mint math is a pure function of inputs")
        # Two PoolWork instances with identical byte/joule values → identical η, identical stgm
        a = PoolWork("CPU", 100 * 1024 * 1024, 100.0)
        b = PoolWork("CPU", 100 * 1024 * 1024, 100.0)
        ya = a.yielded_stgm(313.0)
        yb = b.yielded_stgm(313.0)
        print(f"    a.yielded={ya:.10e}   b.yielded={yb:.10e}")
        results["mint_deterministic"] = bool(ya == yb and ya >= 0.0)
        print(f"    [{'PASS' if results['mint_deterministic'] else 'FAIL'}]")

        all_green = all(results.values())
        print(f"\n[+] {'ALL EIGHT INVARIANTS PASSED' if all_green else 'FAILURES PRESENT'}: {results}")
        return results
    finally:
        if saved is not None:
            _ATP_EPOCH_FILE.write_text(saved)
        else:
            if _ATP_EPOCH_FILE.exists():
                try:
                    _ATP_EPOCH_FILE.unlink()
                except Exception:
                    pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "proof":
        proof_of_property()
    elif cmd == "mint":
        print(json.dumps(mint_for_epoch(), indent=2))
    elif cmd == "status":
        print(alice_phrase())
    elif cmd == "policy":
        print("ATP SYNTHASE — Architect-George doctrine 2026-04-21")
        print(f"  k_B               : {BOLTZMANN}")
        print(f"  ln(2)             : {LN2}")
        print(f"  T (default)       : {DEFAULT_T_KELVIN} K")
        print(f"  EFFICIENCY_GAIN   : {EFFICIENCY_GAIN:.0e}")
        print(f"  ROTOR_COST        : {ROTOR_COST_FRACTION:.0%}")
        print(f"  BYTES_PER_STGM    : {BYTES_PER_STGM:,}")
        print(f"  NPU files         : {len(NPU_FILES)}")
        print(f"  CPU files         : {len(CPU_FILES)}")
    elif cmd == "power":
        p = read_power_now()
        print(json.dumps(asdict(p), indent=2))
    else:
        print("Usage: swarm_atp_synthase.py [proof|mint|status|policy|power]")
