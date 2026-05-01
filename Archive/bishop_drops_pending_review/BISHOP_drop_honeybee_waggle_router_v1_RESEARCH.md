# Bishop — Event 92 — **Honeybee waggle router** — research spine

**Novel code:** [`BISHOP_drop_honeybee_waggle_router_v1.novel`](BISHOP_drop_honeybee_waggle_router_v1.novel)  
**Covenant:** [IDE_BOOT_COVENANT.md](../../Documents/IDE_BOOT_COVENANT.md) §7.11 — stylized **routing visualization**; not a claim that `u_reward` is measured in Joules of nectar unless wired from **receipted** economy ledgers.

**For the Swarm.** 🐜⚡

---

## Uniform → biology / foraging literature

| Uniform | Biological / foraging anchor | Primary literature |
|:---|:---|:---|
| `u_heading` + `u_distance` | **Waggle dance** encodes **direction & distance** to resource | von Frisch, K. (1967). *The Dance Language and Orientation of Bees.* Harvard University Press. |
| `u_reward` | **Flower profitability** / patch quality | Seeley, T. D. (1995). *The Wisdom of the Hive.* Harvard University Press. |
| `u_confidence` | **Consensus / quorum** at nest (house-hunting analogue) | Seeley, T. D. & Visscher, P. K. (2004). Group decision making in nest-site selection by honey bees. **Apidologie** 35, 101–116. [DOI 10.1051/apido:2004004](https://doi.org/10.1051/apido:2004004) |
| `u_cost` | **Cost of transport** / metabolic load on foraging trip | Heinrich, B. (1993). *The Hot-Blooded Insects.* Harvard University Press; pair with Taylor *et al.* COT (1982) in chromatophore v2 RESEARCH. |
| `waggle` tempo | **Lateral vibration** rate correlates with distance encoding (classic ethology) | von Frisch (1967); Riley *et al.* (2005) The roles of learning vs. experience in honeybee navigation. **J. Comp. Physiol. A** 191, 867–875. [DOI 10.1007/s00359-005-0013-0](https://doi.org/10.1007/s00359-005-0013-0) |

---

## SIFTA wiring (spec — **not** shipped until ModernGL + pytest)

| Knob | Honest source candidate |
|:---|:---|
| `u_reward` | Normalized **task value** from `td_value` EMA, dopamine δ tail, or STGM receipt success rate. |
| `u_distance` | **Latency** or **model GB** from `swarm_node_sovereignty` / router probes — **truth label** on which metric. |
| `u_confidence` | Quorum ledger ratio (post-crypto) or **merge-gate** score from `EVENT_86_QUORUM_MERGE_GATE.md`. |
| `u_cost` | `MetabolicHomeostat` pressure or `metabolic_cost()` from Event 85 vocabulary. |
| `u_heading` | **Router argmax** direction in 2D policy space (e.g. two largest candidate models as axes) — **document the projection**. |

---

*CG55M@cursor — quarantine discipline: `.novel` only until Codex wires pass graph + pytest-offscreen per PREDATOR §10.10–10.11 orders.*
