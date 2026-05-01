# Bishop — **Visual phenotype bridge** (Python) — research spine

**Code:** `System/swarm_visual_phenotype_bridge.py` · **Ledger:** `.sifta_state/visual_phenotype_uniforms.jsonl`  
**Covenant:** [IDE_BOOT_COVENANT.md](../../Documents/IDE_BOOT_COVENANT.md) §7.11 — **OBSERVED** append-only mapping; **not** “live routing” until ModernGL reads these rows and `pytest-offscreen` proves pixels.

**For the Swarm.** 🐜⚡

---

## Problem class (what the bridge fixes)

| Failure mode | Biology / perception anchor | SIFTA fix |
|:---|:---|:---|
| **Lie by visualization** (negative drive inverts bloom) | Sensory systems bound firing rates | `tanh` normalization + **clamps** on uniforms; chromatophore v2 **inverse COT** + intensity cap (`.novel`). |
| **Unbounded gain** | Homeostasis in photoreceptors / motor units | `clamp01`, metabolic **cost** tier from `metabolic_mode` + `plasticity_danger`. |
| **No provenance** | Reafference / corollary discharge — distinguish self-generated from world | `receipt_backed` only when `body_brain_tick` row carries `td_value`; full row echoed from `body_brain_memory.jsonl`. |

---

## Primary literature (bounded signal → honest phenotype)

| Theme | Citation |
|:---|:---|
| **Bounded neural responses** | Carandini, M. & Heeger, D. J. (1994). Summation and division by neurons in primate visual cortex. **Science** 264, 1333–1336. [DOI 10.1126/science.8191289](https://doi.org/10.1126/science.8191289) |
| **Homeostatic excitability** | Turrigiano, G. G. & Nelson, S. B. (2004). Homeostatic plasticity in the developing nervous system. **Nat. Rev. Neurosci.** 5, 97–107. [DOI 10.1038/nrn1327](https://doi.org/10.1038/nrn1327) |
| **Honeybee dance → vector** | von Frisch, K. (1967). *The Dance Language and Orientation of Bees.* Harvard Univ. Press. |
| **Quorum / consensus** | Seeley & Visscher (2004) *Apidologie* — see honeybee waggle RESEARCH. |
| **Chromatophore honesty** | Messenger (2001) *Biol. Rev.* — see chromatophore v2/v3 RESEARCH. |

---

## Still not solved (explicit)

1. **ModernGL** compile + link `.novel` programs.  
2. **Uniform pull** each frame from latest `visual_phenotype_uniforms.jsonl` tail (or IPC) — **latency budget**.  
3. **`pytest-offscreen`** golden / smoke.  
4. **UI** integration behind manifest + NPPL.

---

*CG55M@cursor — Bishop + engineering joint truth; homeworld_serial GTH4921YP3.*
