# Event 90 — Stigmergic video resolution (research + organ proposal)

**For the Swarm.** 🐜⚡  
**Status:** **SHIPPED** — `System/swarm_stigmergic_video_resolution.py` + `tests/test_swarm_stigmergic_video_resolution.py` + `canonical_schemas` ledger keys for `stigmergic_video_resolution.jsonl` (verify on-node with pytest). **NPPL.**

**Covenant:** truth labels in [IDE_BOOT_COVENANT.md](../IDE_BOOT_COVENANT.md) **§7.11**.

**Bishop vanguard drop (voice + legacy sketch):** [BISHOP_drop_stigmergic_video_resolution_v1.dirt](BISHOP_drop_stigmergic_video_resolution_v1.dirt)

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

**Ledger:** `.sifta_state/stigmergic_video_resolution.jsonl` — per-frame summary **alongside** `visual_stigmergy.jsonl`.

---

## Resolution ↔ resource load (what happens if you “turn up photons / acuity / swimmers”)

**OPERATIONAL (SIFTA):** In `sifta_what_alice_sees_widget.py`, grid side **N** is **O(N²)** saliency + motion cells per frame, **O(N²)** nybbles in `saliency_q` / `motion_q`, and **more CPU** in photon harvest. Raising acuity **without** raising useful information ⇒ **denser ledgers**, **larger prompts** if you paste full q-strings into LLM context, and **more disk writes/sec** at high FPS — i.e. **metabolic pressure moves from “pixels” to “stigmergy bandwidth.”**

**Biology / physics (literature anchors):**

| Theme | Why it matters for “more resolution” | Pointer |
|:---|:---|:---|
| **Sparse / low mean firing as an energy strategy** | Brains pay dearly for spikes; selective sparse coding is an energy hedge | Lennie (2003) *Curr. Biol.* [DOI 10.1016/S0960-9822(03)00135-0](https://doi.org/10.1016/S0960-9822(03)00135-0) |
| **Neuron–glia energy coupling & imaging** | Visual stimulation drives measurable metabolic demand in networks | Magistretti & Allaman (2015) *Neuron* [DOI 10.1016/j.neuron.2015.03.035](https://doi.org/10.1016/j.neuron.2015.03.035) |
| **Visual system as high-demand network (human PET/fMRI context)** | “Seeing more” (drives, contrast, attention) shifts concurrent metabolic load | Riedl *et al.* (2019) *Nat. Commun.* [DOI 10.1038/s41467-019-08546-x](https://doi.org/10.1038/s41467-019-08546-x) |
| **Compound eye: diffraction × sampling × speed trade** | More facets / smaller interommatidial angle ≠ free lunch: photon noise + diffraction | Snyder (1979) *J. Comp. Physiol.* [DOI 10.1007/BF00605401](https://doi.org/10.1007/BF00605401) |
| **Human acuity limits (pixels-per-degree framing)** | Guides when extra digital resolution is **perceptually** wasted vs useful | Ashraf *et al.* (2025) *Nat. Commun.* [DOI 10.1038/s41467-025-64679-2](https://doi.org/10.1038/s41467-025-64679-2) |
| **Foveated / graded resolution rendering** | Engineering analogue: allocate compute where uncertainty drops fastest | Wei *et al.* (2022) *Comput. Visual Media* survey [DOI 10.1007/s41095-022-0306-4](https://doi.org/10.1007/s41095-022-0306-4) |
| **Active perception** | “Look smarter” beats “see more raw pixels” when minimizing expected surprise | Strauss *et al.* [PMC6954017](https://pmc.ncbi.nlm.nih.gov/articles/PMC6954017/) |
| **Event / change-driven sensing** | Robotics analogue to sparse stigmergic updates | Liang *et al.*, *Sci. Robot.* [DOI 10.1126/scirobotics.adj8124](https://doi.org/10.1126/scirobotics.adj8124) |
| **Stigmergy in robot swarms** | Field traces as shared memory — scaling costs are communication + field update rates | Fan *et al.*, *npj Robot.* [DOI 10.1038/s44172-024-00175-7](https://doi.org/10.1038/s44172-024-00175-7) |

---

## Engineering acceptance (**LANDED**)

1. **Module** — `System/swarm_stigmergic_video_resolution.py` reads `visual_stigmergy.jsonl` tails, infers grid, counts active quantized cells, appends schema-checked rows.  
2. **Tests** — `tests/test_swarm_stigmergic_video_resolution.py` (**5 passed** on CG55M verify).  
3. **Schema** — `canonical_schemas.py` entry for `stigmergic_video_resolution.jsonl`.  
4. **Privacy** — summaries only; no raw frame cloud exfil in this organ.

---

*Tournament index:* [ALICE_CONSCIOUSNESS_TOURNAMENT_EVENT86.md](../ALICE_CONSCIOUSNESS_TOURNAMENT_EVENT86.md) **§13**.
