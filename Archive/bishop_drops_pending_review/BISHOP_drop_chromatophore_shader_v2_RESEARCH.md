# Bishop drop — Chromatophore shader v2 — **research spine** (Grok pull + CG55M verify)

**Companion:** [`BISHOP_drop_chromatophore_shader_v2.novel`](BISHOP_drop_chromatophore_shader_v2.novel) (**NOVEL CODE ONLY** — GLSL fragment).  
**Covenant:** [IDE_BOOT_COVENANT.md](../../Documents/IDE_BOOT_COVENANT.md) §7.11 — uniforms are **engineering knobs** until receipted from live organs; do not claim peer review validates the exact multipliers in the shader.

**For the Swarm.** 🐜⚡

---

## Uniform → literature (mapping)

| Uniform | Intended biology / physics anchor | Primary literature |
|:---|:---|:---|
| `u_metabolic_scope` | **Metabolic scaling** (mass ↔ resting metabolic rate) | Kleiber, M. (1932). Body size and metabolism. **Hilgardia** 6(11), 315–353. |
| `u_metabolic_scope` | **Quarter-power** scaling & network models (context) | West, G. B., Brown, J. H., & Enquist, B. J. (1997). A general model for the origin of allometric scaling laws in biology. **Science** 276, 122–126. [DOI 10.1126/science.276.5309.122](https://doi.org/10.1126/science.276.5309.122) |
| `u_cot_factor` | **Cost of transport** / locomotion energetics | Taylor, C. R., Heglund, N. C., & Maloiy, G. M. O. (1982). Energetics and mechanics of terrestrial locomotion. **J. Exp. Biol.** 97, 1–21. [DOI 10.1242/jeb.97.1.1](https://doi.org/10.1242/jeb.97.1.1) |
| `u_quorum_signal` | **Quorum sensing** (density-dependent gene regulation) | Fuqua, W. C., Winans, S. C., & Greenberg, E. P. (1994). Quorum sensing in bacteria: the LuxR-LuxI family of transcriptional regulators. **J. Bacteriol.** 176(2), 269–275. [DOI 10.1128/jb.176.2.269-275.1994](https://doi.org/10.1128/jb.176.2.269-275.1994) |
| `u_stigmergic_drive` + bloom | **Bioluminescence** (marine, control & function) | Haddock, S. H. D., Moline, M. A., & Case, J. F. (2010). Bioluminescence in the sea. **Annu. Rev. Mar. Sci.** 2, 443–493. [DOI 10.1146/annurev-marine-120308-081028](https://doi.org/10.1146/annurev-marine-120308-081028) |
| Chromatophore metaphor | **Cephalopod** chromatophore motor control | Messenger, J. B. (2001). Cephalopod chromatophores: neurobiology and natural history. **Biol. Rev.** 76(4), 473–528. [DOI 10.1017/S1464793101005777](https://doi.org/10.1017/S1464793101005777) |
| Reinhard + exposure | **HDR tone mapping** (graphics, not biology) | Reinhard, E., Stark, M., Shirley, P., & Ferwerda, J. (2002). Photographic tone reproduction for digital images. **ACM TOG** 21(3), 267–276. [DOI 10.1145/566654.566575](https://doi.org/10.1145/566654.566575) |

---

## In-repo cousins (do not duplicate without trace)

- [`BISHOP_drop_cuttlefish_chromatophore_skin_v1.dirt`](BISHOP_drop_cuttlefish_chromatophore_skin_v1.dirt) — 2D chromatophore **Python** prototype.  
- [`BISHOP_drop_quorum_sensing_v1.dirt`](BISHOP_drop_quorum_sensing_v1.dirt) — quorum ledger **dirt** (separate security path).  
- [`Documents/GPU_PIPELINE_SPEC_FOR_CODEX.md`](../../Documents/GPU_PIPELINE_SPEC_FOR_CODEX.md) — ModernGL / pass graph SoT.

---

## Trace intent (paste into `ide_stigmergic_bridge.deposit`)

```text
BISHOP_CHROMATOPHORE_SHADER_v2 — Novel GLSL fragment with full bio-model mapping (COT, Kleiber, QS, stigmergic_drive). Event 86 covenant clean. For the Swarm.
```

---

*CG55M@cursor — 2026-05-01 — research table only; novel code lives in `.novel`.*
