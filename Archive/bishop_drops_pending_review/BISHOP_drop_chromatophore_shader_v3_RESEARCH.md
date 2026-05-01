# Bishop — Chromatophore shader **v3** — full research spine (chemotaxis + prior v2 stack)

**Novel code:** [`BISHOP_drop_chromatophore_shader_v3.novel`](BISHOP_drop_chromatophore_shader_v3.novel)  
**Prior:** [`BISHOP_drop_chromatophore_shader_v2_RESEARCH.md`](BISHOP_drop_chromatophore_shader_v2_RESEARCH.md)  
**Covenant:** [IDE_BOOT_COVENANT.md](../../Documents/IDE_BOOT_COVENANT.md) §7.11 — `u_chemotaxis_gradient` is a **shader knob** until fed from a **receipted** trace-gradient organ (e.g. pheromone / JSONL spatial diff); do not claim Keller–Segel is “running on the GPU” because of one uniform.

**For the Swarm.** 🐜⚡

---

## Uniform → mechanism → citation

| Uniform | Biology / math anchor | Primary literature |
|:---|:---|:---|
| `u_chemotaxis_gradient` | **Bacterial chemotaxis** along attractant gradients; **drift / run–tumble** | Berg, H. C. & Brown, D. A. (1972). Chemotaxis in Escherichia coli analysed by Three-dimensional Tracking. **Nature** 239, 500–504. [DOI 10.1038/239500a0](https://doi.org/10.1038/239500a0) |
| `u_chemotaxis_gradient` | **PDE / aggregation** (macroscopic chemotaxis) | Keller, E. F. & Segel, L. A. (1970). Initiation of slime mold aggregation viewed as an instability. **J. Theor. Biol.** 26, 399–415. [DOI 10.1016/0022-5193(70)90092-5](https://doi.org/10.1016/0022-5193(70)90092-5) |
| `u_chemotaxis_gradient` | **Modern review** (gradient sensing noise) | Endres, R. G. & Wingreen, N. S. (2008). Accuracy of direct gradient sensing by single cells. **PNAS** 105, 15749–15754. [DOI 10.1073/pnas.0804688105](https://doi.org/10.1073/pnas.0804688105) |
| `u_quorum_signal` | **QS** density dependence | Fuqua *et al.* (1994) — see v2 RESEARCH table. |
| `u_cot_factor` / `u_metabolic_scope` | **COT / scaling** | Taylor *et al.* (1982); Kleiber (1932); West *et al.* (1997) — v2 table. |
| `u_stigmergic_drive` + pulse | **Neural oscillations + sensory gain** (metaphor only) | Friston (2010) free-energy survey — [DOI 10.1038/nrn2787](https://doi.org/10.1038/nrn2787); **not** a claim of biophysical EOD. |

---

## Battle tasks (from UI follow-ups → engineering)

| Suggested lane | Research anchor | Next falsifiable step |
|:---|:---|:---|
| **Chemotaxis gradient integration** | Keller–Segel + Berg run–tumble | Define **one** scalar from repo: e.g. finite difference on `ide_stigmergic_trace.jsonl` time-density or FoldSwarm field export → uniform **with** receipt row. |
| **Quorum sensing visuals** | Fuqua *et al.*; Bassler review | Map `quorum_votes.jsonl` tail (if/when hardened) → `u_quorum_signal`; **no** fake vote totals without crypto (see [`BISHOP_drop_quorum_sensing_v1.dirt`](BISHOP_drop_quorum_sensing_v1.dirt)). |
| **Chromatophore pulse rhythm** | Messenger (2001) neuromuscular chromatophores | Expose pulse **freq/phase** as uniforms from `biology_drive_plasticity.json` or body_brain TD EMA; **pytest** snapshot hash for deterministic CI. |

---

*CG55M@cursor — Bishop bibliography extension; homeworld_serial GTH4921YP3.*
