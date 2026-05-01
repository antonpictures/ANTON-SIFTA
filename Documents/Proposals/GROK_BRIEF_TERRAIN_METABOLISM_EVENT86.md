# GROK brief — terrain · metabolism · competition → SIFTA cost knobs

**For the Swarm.** 🐜⚡
**Binding:** [IDE_BOOT_COVENANT.md](../IDE_BOOT_COVENANT.md) — substrate honesty; NPPL.
**Tournament SoT:** [PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md](../PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md) **§10.8** (prompt) + **§9–10** (Events 85–86).

**Status:** Ingested narrative + equation sketches from external pass (2026-04-30). **Every equation below must be checked against primary sources before any runtime coefficient ships.**

---

## 1 — Quantitative biological models → `{compute, latency, GB, routing}`

Structured ingest (Grok-style pass). **Mapping column = analogy spec**, not deployed physics.

| # | Domain | Core idea (sketch) | SIFTA knob mapping (honest) |
|:---:|:---|:---|:---|
| **1** | **Locomotion / terrain COT** | Metabolic power scales with **force × stride frequency**; **cost of transport** (energy per mass·distance) rises on compliant substrates (sand), slope (grade), and aquatic locomotion where drag dominates. Kram–Taylor–Full style **inverted-pendulum / collisional** models relate stance work to speed. | **Compute cost:** integrate “power” proxy over task duration. **Latency:** energy-limited metaphor → throttle / queue. **Routing:** prefer route with lower empirical COT (measured ms + J if instrumented). **GB:** do not force M^{3/4} into silicon without measurement — optional normalization only. |
| **2** | **Drag across media** | \(F_d \approx \tfrac{1}{2}\rho v^2 C_d A\) (inertial); Stokes \(F_s = 6\pi\eta r v\) (viscous). **Re** selects regime. Water vs air ⇒ huge \(\rho\) gap → “remote call through dense medium” metaphor. | **Latency:** cap effective \(v\) (throughput). **Routing:** high-drag path = congested network or cold cache. **Model size:** \(A\) or \(L\) as “frontal” context / KV footprint — metaphor only. |
| **3** | **Metabolic scaling (Kleiber / WBE)** | Basal rate \(B \propto M^{3/4}\) (Kleiber; West–Brown–Enquist alternative mechanism). Specific rate \(B/M \propto M^{-1/4}\). Brain is costly tissue; allometry literature ties mass to glucose/O₂ demand. | **rest_budget** / **STGM** burn: sublinear “budget per unit capability” story — **fit coefficients from receipts**, do not assert biological exponents for GPUs. |
| **4** | **Chemotaxis / Keller–Segel** | PDE form: cells \(u\) drift up gradient of signal \(v\) with sensitivity \(\chi\); diffusion \(D_u, D_v\). Run-and-tumble: bias tumble rate vs \(\nabla c\). | **Stigmergic routing:** climb trace density on `MemoryBus` / JSONL fields; **quorum** = threshold crossing on accumulated signal (see §6). |
| **5** | **Lotka–Volterra competition** | \(dN_i/dt = r_i N_i (K_i - N_i - \sum_j \alpha_{ij} N_j)/K_i\). Coexistence vs exclusion depends on \(\alpha_{ij}\), \(K_i\). | **IDE collision model:** destructive overlap = high \(\alpha_{ij}\); **niche partitioning** lowers \(\alpha\). Doc / sim only unless instrumented. |
| **6** | **Quorum sensing** | Autoinducer production ∝ density; decay/diffusion; threshold \(>\) \(Q_{th}\) flips gene program; bistability possible. | **`accept_patch`** (§10.2): tests + SCAR + **≥2 independent votes**; trace accumulation = AI concentration metaphor. |

### 1.1 — Patch / foraging (seeded formulas, verify)

- **Marginal value theorem (Charnov):** leave patch when marginal gain rate in patch equals average rate including travel — maps to **when to stop context stuffing** and **when to spawn sub-agent**.
- **Central place foraging (Orians & Pearson):** load size vs round-trip time — maps to **batch size** vs **round-trip latency** for tool/API calls.
- **Risk-sensitive foraging, giving-up time, IFD, economic defendability, interference** — map to **explore/exploit** in router under variance; cite in §2 table.

---

## 2 — Consolidated research nuggets (cross-thread bibliography seed)

Use this as **starting cites** for C55M/Cursor literature pass — replace weak links with DOIs as you tighten.

| Topic | Stable pointer | Notes for SIFTA |
|:---|:---|:---|
| Long-context placement | [arXiv:2307.03172](https://arxiv.org/abs/2307.03172) Liu *et al.* *Lost in the Middle* | Policy in **code** + head/tail placement for covenants. |
| Brain metabolic allometry | [PMC3587279](https://pmc.ncbi.nlm.nih.gov/articles/PMC3587279/) | **`rest_budget`** / mass on disk narrative. |
| Bacterial stigmergy / biofilms | [PMC4306409](https://pmc.ncbi.nlm.nih.gov/articles/PMC4306409/) | **`.sifta_state`** as substrate pheromone. |
| Red Queen | Van Valen (1973) *Evolutionary Theory* 1:1–30 | Tournament never finishes — governance tone. |
| Competitive coevolution | Rosin & Belew (1997); PBT / AlphaStar-style self-play (survey cites) | MARL colosseum **analogy** only. |
| Information geometry | Amari (2016) *Information Geometry and Its Applications* (Springer) | Natural gradient / trust region — rigorous dual to “mass” metaphors. |
| Adversarial program evolution | [Sakana DRQ](https://sakana.ai/drq/) | Red Queen for **code** — not kinetic. |
| Opaque routing | [arXiv:2403.12031](https://arxiv.org/abs/2403.12031) RouterBench | Pairs with `AUTO_OPAQUE` / tier truth. |
| Federation / heterogeneity | FedAvg [arXiv:1602.05629](https://arxiv.org/abs/1602.05629); Ben-Nun & Hoefler ML parallel survey (2019) | Node mass budgets differ. |
| Stigmergy / ACO | Bonabeau *et al.* (1999); Dorigo & Stützle (2004) | Trail reinforcement = JSONL / receipts. |
| Kleiber scaling | Kleiber (1932) *Hilgardia* 6:315–353 | \(3/4\) **hypothesis** — fit from telemetry if used at all. |
| Marginal value | Charnov (1976) *The American Naturalist* | Patch leaving = context / sub-task boundaries. |
| Central place | Orians & Pearson (1979) *Ecological Monographs* | Batching vs latency. |
| Keller–Segel | Keller & Segel (1970) *J. Theor. Biol.* | Gradient following on traces. |
| Energy-aware inference | Kang *et al.* (2017) **Neurosurgeon** ASPLOS [DOI 10.1145/3037697.3037698](https://doi.org/10.1145/3037697.3037698) | Edge/cloud split inference with latency/energy profiling — good DOI-locked software analogue; measure first before routing policy. |

### 2.1 — DOI-locked locomotion + hypoxia layer (C55M/Codex strike — transferable math only)

```text
STATUS: DOI_LOCKED — SAFE FOR SCAR COEFFICIENTS (PENDING VALIDATION)
```

Constants and ranges below are **quoted from primary abstracts / secondary summaries** in this pass — **re-open each PDF** before freezing production coefficients. **Biological objective (carry forward):** animals minimize **energy per distance (COT)**, not energy per stride — SIFTA analogue: minimize **`cost_per_successful_task`**, not raw `cost_per_inference`.

| Paper (short) | Equation / law (transferable form) | Domain | Parameter mapping → `{compute, latency, GB, routing}` | Confidence |
|:---|:---|:---|:---|:---|
| Kram & Taylor (1990) *Nature* [DOI 10.1038/346265a0](https://doi.org/10.1038/346265a0) | Running \(\dot{E}\) scales with **how fast** the body must **generate support force**; **inverse** relation between metabolic rate and **foot–ground contact time** \(t_c\) at a given speed (shorter \(t_c\) ⇒ higher rate of force production ⇒ higher \(\dot{E}\)). | Terrestrial running, force–time tradeoff | **`latency`:** shorter allowed “stance” per sub-task ⇒ higher power draw. **`compute`:** \(\dot{E} \sim 1/t_c\) proxy for **scheduler quantum** under fixed throughput. **`routing`:** prefer organ with **longer sustainable \(t_c\)** (stable batch) for same quality bar. | **Med** (human running; verify exponents for metaphor use) |
| Taylor, Heglund & Maloiy (1982) *J. Exp. Biol.* I [DOI 10.1242/jeb.97.1.1](https://doi.org/10.1242/jeb.97.1.1) | Metabolic power vs speed often **plateaus** above trot–gallop transition; **mass scaling** of transport: birds/mammals share similar **cost of transport** trends vs size at equivalent gait. | Terrestrial locomotion, allometry | **`GB` / model tier:** mass-class bins, not continuous \(M^{3/4}\) on disk. **`cost_per_successful_task`:** integrate over **distance-equivalent** tokens, not single-call cost. **`routing`:** switch gait (model tier) when marginal \(\dot{E}\) vs speed flattens. | **Med** |
| Heglund, Fedak, Taylor *et al.* (1982) *J. Exp. Biol.* III [DOI 10.1242/jeb.97.1.41](https://doi.org/10.1242/jeb.97.1.41) | **Mechanical work** to lift and re-accelerate CoM each step; links **measured external work** to **metabolic cost** across speed/size. | COM work, gait | **`compute`:** external work proxy = **useful output tokens / quality**; metabolic gap = overhead. **`latency`:** stride frequency ↔ **pipeline steps / sec**. | **Med** |
| Full & Tu (1990) *J. Exp. Biol.* [DOI 10.1242/jeb.148.1.129](https://doi.org/10.1242/jeb.148.1.129) | Six-legged runners: **mass-specific energy** ~ **0.9 J·kg⁻¹·m⁻¹** (order-of-magnitude **COT** anchor); bouncing gait, common constraints across leg number. | Comparative legged mechanics | **`routing`:** baseline **COT_ref** for “cheap reflex” lane. **`GB`:** \(m\) = effective payload mass class. | **High** (numeric anchor cited in secondary lit; verify in PDF) |
| Minetti *et al.* (2002) *J. Appl. Physiol.* [DOI 10.1152/japplphysiol.01177.2001](https://doi.org/10.1152/japplphysiol.01177.2001) | **Energy cost per distance** vs **gradient** (uphill/downhill); strong nonlinearity; **U-shaped** / extrema vs slope angle (empirical curves). | Human walk/run, slope | **`terrain_cost[grade]`:** lookup table on **CPU load / thermal / backlog slope**. **`routing`:** penalize “uphill” paths (RAM pressure + slope). | **High** (empirical curves; re-measure for silicon) |
| Lejeune, Willems & Heglund (1992) *Eur. J. Appl. Physiol.* [DOI 10.1007/BF00705078](https://doi.org/10.1007/BF00705078) | Sand vs firm: **~1.8×** walk cost (speed-dependent); **~1.2×** run cost; compliance reduces elastic recovery. | Substrate compliance | **`terrain_cost['disk_io']` / `network'`:** multiplicative **compliance factor** \(k_{\mathrm{sand}} > 1\). **`latency`:** same work ⇒ longer clock time. | **High** |
| Pontzer *et al.* (2016) *Current Biology* [DOI 10.1016/j.cub.2015.12.046](https://doi.org/10.1016/j.cub.2015.12.046); [PMC4803033](https://pmc.ncbi.nlm.nih.gov/articles/PMC4803033/) | **Total energy expenditure vs physical activity:** strong rise at **low** activity, **plateau** at **high** activity (constrained TEE hypothesis). | Human energy budget, adaptation | **`rest_budget` / governor:** **saturate** penalty after sustained STGM burst — do not assume linear burn forever. **`compute`:** piecewise: linear low regime + **flat** high regime. | **High** (humans; map cautiously to node thermals) |
| Saunders, Pyne & Gore (2009) *High Alt. Med. Biol.* [DOI 10.1089/ham.2008.1092](https://doi.org/10.1089/ham.2008.1092) | Acute moderate altitude lowers maximal aerobic power / \( \dot{V}O_2max \) by roughly **15–20%** in endurance athletes; acclimatization changes capacity but not the immediate oxygen-limit story. | Altitude / hypoxia / metabolic scope | **`thermal_throttle` / `oxygen_limit`:** when substrate supply narrows, cap peak work and require longer recovery. **`routing`:** prefer lower-power lanes under oxygen/thermal scarcity; do not convert altitude directly into SCAR coefficients without local telemetry. | **Med** (human physiology; scope metaphor only) |
| Taylor & Heglund (1982) *Annu. Rev. Physiol.* [DOI 10.1146/annurev.ph.44.030182.000525](https://doi.org/10.1146/annurev.ph.44.030182.000525) | Review: links **energetics** and **mechanics** of terrestrial locomotion (integrates series I–III). | Review / pedagogy | **`SCAR` doc cross-links**; no new equation required — bounds literature variance before coefficients. | **High** (review) |

---

## 3 — SCAR + Event 85 alignment (single SoT)

- **SCAR:** `STIGMERGIC_FILE_WEIGHT_ALLOMETRY` — see tournament **§10.1** `rest_budget` law.
- **Event 85:** `metabolic_cost`, router `utility − cost`, fallback experiment — **§9**.
- **Event 86:** quorum, Red Queen narrative, Lotka doc orders — **§10.2–10.4**.

---

## 4 — Next clean deltas (triple-IDE)

| Owner | Artifact |
|:---|:---|
| **C55M** | **DONE:** altitude / hypoxia row + DOI-locked **Neurosurgeon** energy-aware inference cite; still doc-only until Event 85 code + tests. |
| **AG31** | Optional: one-page “altitude / hypoxia / metabolic scope” for **thermal_throttle** organ alignment (vendor + review cites). |
| **CG55M** | Land **§9** deterministic router test when router accepts cost vector; **no** mesh scalar / **no** SCAR coefficient activation until Event 85 code + tests. |

---

*Ingest version: 2026-04-30 — CG55M + Codex pre-physics follow-up; **§2.1** DOI-locked locomotion/COT + altitude/hypoxia strike + [EVENT_86_LOTKA_IDE_MODEL.md](../EVENT_86_LOTKA_IDE_MODEL.md) + [EVENT_86_QUORUM_MERGE_GATE.md](../EVENT_86_QUORUM_MERGE_GATE.md).*
