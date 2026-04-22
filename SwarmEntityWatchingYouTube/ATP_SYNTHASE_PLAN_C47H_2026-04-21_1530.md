# Event 12 — Mitochondrial ATP Synthase Plan (Landauer Thermodynamic Mint)
## C47H drop 2026-04-21 15:30 — pre-implementation gate

> **STIGAUTH C47H** — east bridge, electricity-economy steward.
> Plan only. Will not write code until Architect-George greenlights.

---

## What BISHOP proposed

`BISHOP_drop_mitochondrial_atp_synthase_v1.dirt` — a daemon that:

1. Reads **actual NPU joules** consumed by the M5 chip.
2. Reads **actual bytes validated** by Alice's organs.
3. Computes the **Landauer minimum energy** for that exact computation:
   $$E_{min} = k_B \cdot T_{chip} \cdot \ln(2) \cdot \text{bits\_processed}$$
4. Computes **thermodynamic efficiency**:
   $$\eta = \frac{E_{min}}{E_{actual}}$$
5. Mints STGM **proportionally to η** — closer to the Landauer floor → more STGM per byte.

Net effect: rewards energy-efficient computation. Lazy code that wastes joules earns less. Tight code that approaches physical limits earns more.

## What this means for the existing electricity_metabolism organ

My `swarm_electricity_metabolism.py` (Architect-George policy of record, sealed in `SCAR_STGM_POLICY_ELECTRICITY_ONLY_v1`) is the **raw meter**. It says: "you burned X joules and processed Y bytes, here is Z STGM."

BISHOP's ATP Synthase is the **efficiency multiplier on top of the meter**. It says: "of the X joules you burned, only L joules were thermodynamically *necessary*. Your efficiency η = L/X. You earn (Y bytes × η) STGM, scaled."

These are not competing organs. The ATP Synthase **wraps** the metabolism and replaces the conversion factors with a physics-grounded one.

**Decision needed:** do we (a) make ATP synthase the new canonical mint and demote `electricity_metabolism` to a private measurement helper, or (b) keep the meter separate and make synthase a downstream consumer? My recommendation: **option (a)** — one canonical mint surface (`mint_for_epoch`) but its math becomes Landauer-aware. Less surface area, single source of truth, "KEEP IT SIMPLE" satisfied.

---

## Honest engineering reality check (read this first)

Three of BISHOP's four required physical inputs are **not directly observable on macOS without sudo or third-party tools**:

| Input | Honest status | Pragmatic fallback |
|---|---|---|
| **NPU joules consumed** | `powermetrics` requires sudo. `IOReport` private framework via PyObjC works without sudo but is a binding lift. `top -l 1 -stats power` exists but emits per-process aggregates. | Phase 1: keep `cpu_seconds × ESTIMATED_TDP_W` as a calibrated proxy, flag as `JOULES_ESTIMATED=True`. Phase 2: add `IOReport` reader if you greenlight a PyObjC dep. |
| **Chip temperature T** | `pmset` doesn't expose it without sudo. SMC reads need `iSMC` or similar. Apple's M5 thermal API is private. | Phase 1: assume `T = 313 K (40 °C)` as typical M5 die temp under load. Phase 2: optional SMC reader. **The error this introduces is small** — Landauer scales linearly with T, so a 10% temp error → 10% mint error. |
| **Bytes processed** | Already counted by `electricity_metabolism.measure_epoch_delta()`. | None needed — already real. |
| **Bits processed** | `bytes × 8`. | None needed — already real. |

**The honesty principle** that the architect demanded (no inflation, no fiction): we should NOT pretend to have NPU joules when we have a TDP estimate. The new mint should record `actual_joules_source = "TDP_ESTIMATED" | "IOREPORT_MEASURED"` in every UTILITY_MINT row so audits can tell which mints are physics-backed and which are physics-shaped.

---

## Mathematical design

Let:
- $b$ = bytes processed in epoch (sum of ingested + written deltas)
- $J$ = actual joules burned in epoch (estimated or measured)
- $T$ = chip temperature in kelvin (assumed 313 K Phase 1)
- $k_B$ = $1.380649 \times 10^{-23}$ J/K
- $\ln 2 = 0.693147$

Landauer minimum:
$$E_{min} = k_B \cdot T \cdot \ln 2 \cdot 8b = 7.661 \times 10^{-21} \cdot T \cdot b \quad \text{joules}$$

Thermodynamic efficiency:
$$\eta = \min\left(1, \frac{E_{min}}{\max(J, \epsilon)}\right)$$

(Capped at 1 for numerical safety; in practice η ~ 10⁻¹⁰ for current silicon.)

Mint:
$$\text{STGM} = \frac{b}{\text{BYTES\_PER\_STGM}} \cdot \eta \cdot \text{EFFICIENCY\_GAIN}$$

Where `EFFICIENCY_GAIN` is a calibration constant (probably ~10¹⁰) chosen so that **typical M5 efficiency yields roughly the same per-hour rate as the Phase 1 raw meter** (~1 STGM/hour at modest load). This makes the migration revenue-neutral for ALICE_M5 while still rewarding efficiency improvements.

**Why cap η at 1**: if `E_min > J_actual`, we are either (a) using an estimated J that's too low, or (b) the universe has been broken. Either way we should not mint more than the byte-budget allows.

---

## Proposed file: `System/swarm_atp_synthase.py`

Skeleton (≈300 LOC, target):

```python
class ATPSynthase:
    """The canonical thermodynamic mint. Wraps electricity_metabolism."""
    BOLTZMANN = 1.380649e-23
    LN2 = 0.6931471805599453
    DEFAULT_T_KELVIN = 313.0   # 40 °C — typical M5 die temp under load
    EFFICIENCY_GAIN = 1.0e10   # calibration: η * GAIN ~ 1 at typical M5

    def landauer_minimum_joules(self, bytes_processed: int, T: float) -> float:
        bits = bytes_processed * 8
        return self.BOLTZMANN * T * self.LN2 * bits

    def efficiency(self, bytes_processed: int, joules_actual: float,
                   T: float) -> float:
        E_min = self.landauer_minimum_joules(bytes_processed, T)
        return min(1.0, E_min / max(joules_actual, 1e-30))

    def mint_for_epoch(self, beneficiary='ALICE_M5') -> dict:
        # Validates beneficiary (reuses electricity_metabolism guard)
        # Reads work delta from electricity_metabolism.measure_epoch_delta()
        # Computes E_min, η, STGM
        # Records UTILITY_MINT_ATP event with all physical inputs
        # Returns receipt
        ...

    def proof_of_property(self) -> dict:
        # P1: Landauer min for 1 byte at 313K matches reference (2.4e-20 J)
        # P2: η is bounded in (0, 1]
        # P3: η = 1 implies mint == byte_quota * EFFICIENCY_GAIN
        # P4: zero work → zero mint
        # P5: ceremonial beneficiary refused (inherits electricity policy)
        # P6: ledger row carries actual_joules_source flag
        ...
```

---

## Open questions (need your call before I build)

1. **Replace or wrap?** Make ATP synthase THE canonical mint (option a) and demote `swarm_electricity_metabolism` to an internal helper, OR keep both side-by-side?
2. **Phase 1 only or Phase 1 + Phase 2 in this drop?** Phase 1 (TDP-estimated J, assumed T) is ~1 hour. Phase 2 (real IOReport via PyObjC) is ~3-4 hours and adds a runtime dep.
3. **Calibration constant `EFFICIENCY_GAIN`** — should I calibrate so that the migration is revenue-neutral for `ALICE_M5` (current ~159 STGM trajectory continues unchanged), OR should I pick a clean round number and let her balance evolve organically?
4. **Should the synthase ALSO charge a small "rotor cost"** (mitochondrial ATP synthase consumes some ATP during operation in real biology — it's about 30% efficient)? This would be a tiny self-cost preventing zero-cost mint spam, but it's symbolic — the bigger lever is η anyway.
5. **NPU vs CPU** — BISHOP says "NPU joules". The M5 has both CPU and NPU. Right now my meter captures CPU+children CPU time. NPU time is harder to attribute. Should we (a) treat all silicon as one pool (current approach), (b) only count NPU work (would require Apple ML inference hooks), or (c) keep CPU as the baseline and add NPU as a Phase 2 multiplier?

---

## What I will NOT do without your call

- Will not write `swarm_atp_synthase.py` yet
- Will not retire `swarm_electricity_metabolism.py` yet
- Will not change `Kernel/inference_economy.py` defaults again (they're at 0.0 now per policy)
- Will not change Alice's wallet or any existing balance

---

## What I HAVE done in this drop (bridge work)

- Audited Event 11 (Thalamic Guardian + Colliculus surgery) — verdict GENUINE
- Applied 4 surgical fixes to `swarm_multisensory_colliculus.py`:
  1. Real face centroid from Swift bounding boxes (replacing hardcoded `[10.0, 10.0]`)
  2. Saccades now write structured SACCADE rows to canonical ledger
  3. CLI dispatches `proof|daemon` (no more terminal-hanging on `python3 …colliculus.py`)
  4. Cast np booleans → native bool (proof_runner uses `is True`, np.True_ silently fails)
- CI dam: 121 → 124 invariants across 30 organs, all green
- Sealed `SCAR_C47H_STIGAUTH_EVENT11_AUDIT_v1` to canonical `repair_log.jsonl`
- Wrote this plan

— **C47H**, east bridge, 2026-04-21 15:30
