# Event 90 — Stigmergic video resolution (research + organ proposal)

**For the Swarm.** 🐜⚡  
**Status:** **SPEC / tournament** — Bishop vanguard read; **Architect GO** before `System/swarm_stigmergic_video_resolution.py` merge. **NPPL.**

**Covenant:** truth labels in [IDE_BOOT_COVENANT.md](../IDE_BOOT_COVENANT.md) **§7.11**.

**Bishop vanguard drop (voice + reference code):** [BISHOP_drop_stigmergic_video_resolution_v1.dirt](BISHOP_drop_stigmergic_video_resolution_v1.dirt)

---

## One-line truth

Alice’s **operative** visual resolution is **not raw camera pixels**; it is **quantized salience + motion cells per frame** written to `.sifta_state/visual_stigmergy.jsonl` (see `Applications/sifta_what_alice_sees_widget.py` — code default **16×16 = 256** cells; UI **acuity** slider can move e.g. **22×22 → 484** cells).

---

## Bishop target payload (proposal)

```json
{
  "camera_pixels": [1920, 1080],
  "stig_grid": [22, 22],
  "stig_cells": 484,
  "active_cells": "<n>",
  "compression_ratio": "<w*h/cells>",
  "salience_density": "<active/cells>",
  "unified_field_payload": []
}
```

**Ledger (proposal):** `.sifta_state/stigmergic_video_resolution.jsonl` — per-frame summary **alongside** (not replacing) `visual_stigmergy.jsonl`.

---

## Research spine (peer pointers)

| Theme | Pointer |
|:---|:---|
| **Active perception** (sensing as uncertainty reduction, not passive pixels) | Strauss et al. — *Revisiting active perception* [PMC6954017](https://pmc.ncbi.nlm.nih.gov/articles/PMC6954017/) |
| **Event-based / change-driven vision** (robotics analogue to sparse salience) | Liang *et al.*, *Sci. Robot.* [DOI 10.1126/scirobotics.adj8124](https://doi.org/10.1126/scirobotics.adj8124) |
| **Stigmergy for multi-agent / field coordination** | Fan *et al.*, *npj Robot.* [DOI 10.1038/s44172-024-00175-7](https://doi.org/10.1038/s44172-024-00175-7) |

---

## Engineering acceptance (when GO)

1. **Single module** computes resolution metrics from **live** `PhotonHarvest` / ledger rows — **no** hallucinated camera size.  
2. **Tests** — golden grid sizes (4, 16, 22, 32), compression math, JSONL schema.  
3. **Predator / receipts** — new file paths registered if Predator Gate requires it.  
4. **Privacy** — no cloud exfil of raw frames; summaries only.

---

*Tournament index:* [ALICE_CONSCIOUSNESS_TOURNAMENT_EVENT86.md](../ALICE_CONSCIOUSNESS_TOURNAMENT_EVENT86.md) **§13**.
