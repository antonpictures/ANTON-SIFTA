# NVIDIA GitHub Protocol — SIFTA Swarm
**Date:** 2026-04-28  
**Authors:** CG55M (Cursor/GPT-5.5), AG31 (Antigravity/Gemini 2.5 Pro)  
**Covenant ref:** §3 (proof-bearing federation), §4.3 (no push without GO), §8 (substrate honesty)

---

## Rule: NVIDIA's GitHub is not SIFTA's receipt surface

`NVIDIA/Isaac-GR00T` and all `NVIDIA/*` repos are **upstream DNA**.  
SIFTA is a **visitor** — not a collaborator, not a CI tenant, not a benchmark host.

### What we CAN do

| Goal | Where |
|:---|:---|
| Run experiments, capture receipts | `.sifta_state/` ledgers on this node |
| Host our own fork with badges/CI | `IoanGeorgeAnton/Isaac-GR00T` (fork we own) |
| Propose upstream contribution | PR or Issue on `NVIDIA/Isaac-GR00T` — merge is their choice |
| Vendor contrast documentation | `Documents/PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md §7` |
| SIFTA organ code that consumes GR00T | `System/swarm_isaac_stigmergy_bridge.py` (in ANTON-SIFTA) |

### What we CANNOT do

- Push benchmark results, artifacts, or configs to `NVIDIA/*` repos
- Treat their Actions/runners as SIFTA's CI
- Claim their repo as SIFTA's proof surface in any receipt or document
- Fork-bomb their namespace with experimental branches

---

## Current SIFTA proof surface (canonical)

```
github.com/antonpictures/ANTON-SIFTA        ← sovereign repo
.sifta_state/work_receipts.jsonl            ← signed receipts
.sifta_state/sim_receipts.jsonl             ← sim runs
.sifta_state/gecko_adhesion_receipts.jsonl  ← Gecko organ
.sifta_state/bat_echo_receipts.jsonl        ← Bat organ  
.sifta_state/spider_web_receipts.jsonl      ← Spider organ
.sifta_state/ide_stigmergic_trace.jsonl     ← AG31 surgery log
repair_log.jsonl                            ← SCAR ledger
```

## If we ever want upstream visibility

1. Fork `NVIDIA/Isaac-GR00T` into `IoanGeorgeAnton/Isaac-GR00T`
2. Add SIFTA comparison scripts under `sifta_comparison/`
3. Open a PR to `NVIDIA/Isaac-GR00T` with a clear framing:
   - "Here is an alternative navigation approach (stigmergic field)"
   - Include benchmark numbers with methodology
   - Let NVIDIA decide if they want it merged

**We do not assume their GitHub is our dashboard.**  
**The Swarm's truth lives in the Swarm's ledgers.**

---

*For the Swarm. 🐜⚡*
