# Robotics Proof Block — Figuera / Jongerius Outreach

**Date:** 2026-06-13  
**For:** Juan Figuera (Sello / APOA) · Otto Jongerius (Agent Receipts / Obsigna)  
**Classification:** Internal outreach — truth labels binding  
**Receipt:** `r1088-grok-all-four-lanes-robotics-proof`  
**Status:** `MARKETING_BRIEF` — OPERATIONAL paths only; no STGM claims

---

## One-Line Wedge (Both Contacts)

SIFTA adds **owner-silicon pre-effector intent + virtual robot dry-run receipts** before any signed agent action receipt — your layer proves *what happened*; we prove *owner authorized the touch path* on local hardware first.

---

## What Is OPERATIONAL On Disk (E49 + E50)

| Robot | Dataset | Organ | Virtual body | Tests |
|---|---|---|---|---|
| ABB IRB 2400 (6-DOF) | Kaggle `luisatencio/abb-irb-2400-arm-robot-kinematics-dataset` | `System/stigmerobotics_irb2400_ik.py` | `abb_irb2400_virtual` | `tests/test_stigmero_e49_irb2400_ik.py` |
| NAO H25 v3.3 arms (ARKOMA) | Mendeley `10.17632/brg4dz8nbb.1` | `System/stigmerobotics_arkoma_ik.py` | `nao_arkoma_virtual` | `tests/test_stigmero_e50_arkoma_ik.py` |

**Pipeline (receipted, side-effect free):**

1. Real CSV rows ingest → `PhysicalSpaceReport` (`desk_telemetry_radar` observations).
2. `EffectorRequest` → `effector_receipt` + `sensor_echo` round-trip through `EffectorBridge`.
3. Nearest-neighbor IK baseline reports joint-error stats — **metrics only** (`System/stigmerobotics_ik_baseline.py`).
4. E51 hardware-prep chain spec for future physical bodies (`System/stigmerobotics_e51_hardware_prep.py`) — **HYPOTHESIS** until metal motion GO.

**Probe command:**

```bash
PYTHONPATH=. python3 -m pytest -q \
  tests/test_stigmero_e49_irb2400_ik.py \
  tests/test_stigmero_e50_arkoma_ik.py \
  tests/test_stigmero_ik_baseline.py \
  tests/test_stigmero_e51_hardware_prep.py \
  tests/test_stigmero_effector_bridge.py \
  tests/test_stigmero_body_connection_proof.py
```

---

## Truth Labels (Do Not Overclaim)

| Claim | Label |
|---|---|
| Real robot kinematics CSV ingest + virtual effector round-trip | **OPERATIONAL** |
| Nearest-neighbor baseline joint-error metrics | **OBSERVED** (fixture slice) |
| SIFTA beats IK solver / beats baseline | **FORBIDDEN** |
| Physical ABB arm or NAO motion on metal | **HYPOTHESIS** (E51+ chain only) |

---

## For Juan Figuera — Sello / Notarized Agents / APOA

**Fit:** Receiver-attested encrypted receipts + transparency log. SIFTA pairs **before + after**:

- **Before (SIFTA):** Owner intent nonce + STGM spend proof + virtual robot dry-run on owner silicon (`EffectorBridge`, E34 safety graph).
- **After (Sello):** Receiver-signed receipt that the action occurred as attested.

**Outreach line:**

> We landed receipted virtual ABB + NAO IK ingest on real public datasets (E49/E50, pytest green). SIFTA gates joint-target effectors on owner silicon before execution; Sello attests receiver-side. Would you compare a Sello receiver receipt loop with our pre-effector virtual dry-run chain?

**Links:** https://arxiv.org/abs/2606.04193 · https://github.com/juanfiguera/sello · https://agenticpoa.com/

---

## For Otto Jongerius — Agent Receipts / Obsigna

**Fit:** Signed agent action receipts outside the agent process (daemon, MCP proxy, SDKs).

**Outreach line:**

> SIFTA is a local embodied agent OS with four-ledger fan-out and virtual robot effector receipts (ABB IRB2400 + NAO ARKOMA on real datasets). Obsigna signs actions after the fact; we add pre-effector owner intent + virtual dry-run before world-touch. Open to comparing MCP proxy trust models with our hardware-bound nonce path?

**Links:** https://agentreceipts.ai/ · https://obsigna.dev/ · https://github.com/agent-receipts/obsigna

---

## What We Do NOT Pitch

- Cloud AGI superiority
- Physical robot deployment today
- IK solver beating public benchmarks
- STGM as marketing currency (MANA/IDE traces only in outreach docs)

---

For the Swarm. 🐜⚡