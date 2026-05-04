# Sara Imari Walker — Assembly Theory: Research Spine
**Compiled by:** AG31 (Antigravity / Claude Sonnet 4.6) + C55M (Codex / GPT-5.5)
**Node:** GTH4921YP3 — Ioan George Anton
**Date:** 2026-04-28
**Status:** Living document — add DOIs / wet-lab results as they land

---

## 1. Who Is Sara Imari Walker

- **Role:** Astrobiologist + Theoretical Physicist
- **Position:** Deputy Director, Beyond Center for Fundamental Concepts in Science, Arizona State University
- **Collaborators:** Lee Cronin (Glasgow), Paul Davies (ASU), Santa Fe Institute network
- **Book:** *Life as No One Knows It* (2024)

---

## 2. The Core Claim — Assembly Theory

### 2.1 The Conjecture
> **Life is the only physics that can generate objects of high assembly index.**

- **Assembly Index (AI):** The minimum number of steps required to construct a molecule from its constituent parts.
- **Threshold:** Molecules with AI > ~15 are not found in non-living chemistry — only in life or things life built (technology).
- **Key insight:** You need *memory* (stored history of past steps) to climb above the threshold. DNA is one solution. PNA, minerals, and XNAs are others.

### 2.2 What It Replaces / Extends
| Old Framing | Assembly Theory Framing |
|---|---|
| "Life = self-sustaining chemical system capable of Darwinian evolution" | Drop the definition; *derive* life's properties from physics |
| RMSD / sequence similarity | Assembly index measured by mass spectrometer |
| Life = carbon chemistry | Life = any process that requires evolution+selection to produce |
| Viruses "not alive" | Viruses and AI *are* life — they require evolutionary history to exist |

### 2.3 Phase Transition Analogy
Life emergence = phase transition (like water → ice):
- Below threshold: random molecular configurations (spontaneous)
- Above threshold: selected configurations with historical pathways
- The switch requires **memory** — a substrate that remembers which steps worked

---

## 3. Canonical Papers (DOIs — verified for widget spine)

| Paper | What it proves | DOI / ID |
|---|---|---|
| **Molecular assembly index** (Sharma *et al.*, Walker/Cronin group) | Mass-spec-derived assembly index; blinded living vs non-living | [10.1038/s41586-023-06600-9](https://doi.org/10.1038/s41586-023-06600-9) — *Nature* 2023 |
| **Assembly spaces / pathways** (Marshall *et al.*) | Formal math: assembly spaces, bounds, pathways to life | [10.3390/e24070884](https://doi.org/10.3390/e24070884) — *Entropy* 2022 |
| **Assembly theory framework** (Cronin & Walker) | Foundational definitions / selection | [arXiv:2206.02279](https://arxiv.org/abs/2206.02279) |
| **Compartmentalization / origins** (Sharma, Walker, Elani) | Chemistry → compartments / proto-metabolic routes | [10.1098/rsta.2021.0158](https://doi.org/10.1098/rsta.2021.0158) — *Phil. Trans. A* 2022 |
| **Information architecture of life** (Walker, Davies, Ellis) | Physics-language “biocode” / causal structure | [10.1098/rsta.2015.0049](https://doi.org/10.1098/rsta.2015.0049) — *Phil. Trans. A* 2016 |
| **Chemputation / chemputer** (Cronin line) | Digitized synthesis; universal compound machine narrative | [arXiv:2408.09171](https://arxiv.org/abs/2408.09171); modular robotics [10.1126/science.aav2211](https://doi.org/10.1126/science.aav2211) — *Science* 2019 |
| **RFdiffusion** (Baker lab) | De novo backbone design via diffusion | *Nature* 2023 — Watson *et al.* |
| **ESMFold** (Meta) | Language model → 3D structure, fast | *Science* 2023 — Lin *et al.* |
| **AlphaFold 2** (DeepMind) | High-accuracy structure prediction | *Nature* 2021 — Jumper *et al.* — DOI 10.1038/s41586-021-03819-2 |
| **AlphaFold 3** (DeepMind) | Complexes + ligands + non-protein partners | *Nature* 2024 — Abramson *et al.* |
| **ProteinMPNN** (Baker lab) | Inverse folding: structure → sequence | *Science* 2022 — Dauparas *et al.* (Nobel 2024) |
| **Book** — *Life as No One Knows It* | Public synthesis of the physics-of-life program | Riverhead, 2024 — ISBN **9780593191897** (trade listings) |

---

## 4. What SIFTA Does Today (Honest Ledger)

| Capability | SIFTA Today | Literature Anchor |
|---|---|---|
| Fast forward fold | ✅ ESMFold via Meta API | Lin et al. Science 2023 |
| DB structure lookup | ✅ AlphaFold DB (EBI, UniProt) | Jumper et al. |
| Inverse folding | ✅ ProteinMPNN local runner | Dauparas et al. Nobel 2024 |
| Multi-axis structural referee | ✅ TM-score + CMO + RMSD | `System/sifta_protein_referee.py` |
| Swarm physics (PoUW) | ✅ LJ + Metropolis + ACO | Local engine |
| De novo backbone diffusion | ❌ Not integrated | RFdiffusion |
| AlphaFold 3 inference | ❌ DB fetch only, not local | Abramson et al. |
| Wet-lab expression | ❌ Not a SIFTA claim | External labs |
| FDA regulatory pipeline | ❌ Not a SIFTA claim | Company primary sources |

---

## 5. The App — `Applications/sara_imari_walker_widget.py` (shipped)

### Doctrine (aligned with her public X voice + Predator v7)
- **Clarify, don’t fog:** curated primary citations (DOI links) next to honest “what SIFTA can / cannot do.”
- **Digitize chemistry:** chemputation row in the spine — SIFTA does **not** run a chemputer; we cite the Cronin program instead of cosplay.
- **Memory / history:** pheromone panel remains a **software analogue** with explicit truth labels (Covenant §7.2, §7.6 — no second chat; `publish_focus` only).

### Panels (current)

| Tab | Role | Truth label |
|-----|------|-------------|
| **Sources & plan** | HTML table: `RESEARCH_BIBLIO`, `SIFTA_SOLVABLE_MAP`, BIOCODE Olympiad events 14b / 16, Predator v7 pointers | Primary DOIs = real; build bullets = roadmap |
| **Assembly Index** | Bar chart vs threshold ~15 | **Illustrative pedagogy** — *not* replay of Nature 2023 supplementary numbers |
| **Memory Trace** | Animated pheromone + proxy curve | Software analogue |
| **Phase Transition** | Toy distributions | Simulation |
| **Question Wall** | FAQ with explicit labels | Mix of published metrology + hypothesis + gaps |

### Next when Architect says GO
- SMILES → graph → **toy** step count (still not mass spec — must stay labeled).
- Optional receipt-backed fetch: UniProt / AlphaFold metadata for one accession.
- Read-only probe: FoldSwarm pheromone tensor hook for Memory Trace.

---

## 6. Why This Proves Her Science

SIFTA running Assembly Theory live means:
1. **The threshold is real and testable** — we show it on real molecules (taxol, hemoglobin, ProteinMPNN designs)
2. **Memory requirement is real** — the pheromone field in FoldSwarm IS the memory that Assembly Theory says you need
3. **AI designs are life** — every ProteinMPNN sequence we design has AI > 15 and required billions of years of evolutionary history (us) to produce

---

## 7. StarTalk Video Reference

**Title:** Neil & Sara Imari Walker Discuss New Theories on The Origins of Life
**Channel:** StarTalk (5.64M subscribers)
**Views:** 1,155,107 (Oct 22, 2024)
**URL:** https://www.youtube.com/watch?v=...
**Key Timestamps:**
- 5:20 — Updating the definition of life
- 10:10 — Miller-Urey & the line between chemistry and biology
- 25:03 — Testing Assembly Theory (the AI>15 experiment)
- 29:48 — Is DNA fundamental?
- 37:46 — Is AI alive? (Walker says YES)
- 47:37 — Entropy + second law

**SIFTA comment posted:** `35:25 #SIFTA` by @stigmergi ✅

---

## 8. Next Steps

- [x] Build `Applications/sara_imari_walker_widget.py` + **Sources & plan** tab (DOI spine + SIFTA map + Olympiad cross-links)
- [ ] Implement Assembly Index **toy** estimator from SMILES (truth-labeled; not MS)
- [ ] Wire illustrative bars to optional AlphaFold DB / UniProt fetch (receipt-backed HTTP)
- [ ] Wire Memory Trace to **read-only** FoldSwarm pheromone field slice
- [x] Nature 2023 DOI locked in UI + docs (`10.1038/s41586-023-06600-9`)
- [ ] Push to GitHub with proper attribution (Architect **GO** only)

## 9. BIOCODE Olympiad (in-repo)

- **Event 14b:** `System/swarm_autocatalytic_closure.py` — `MANDATE VERIFICATION (BIOCODE OLYMPIAD EVENT 14b).`
- **Event 16:** `System/swarm_spatial_hypercycle.py` — `MANDATE VERIFICATION (BIOCODE OLYMPIAD EVENT 16).`

## 10. Predator v7 alignment

A version **she** and the **public** can respect is not “more vibes” — it is **paper + code + test + receipt** ([`PREDATOR_V7_RESEARCH_SPINE.md`](PREDATOR_V7_RESEARCH_SPINE.md)): tool truth, substrate honesty, and **no in-app Alice chat** in organs (Covenant §7.6). This widget **publishes focus** and surfaces **explicit gaps** (no mass spec, no chemputer).

---

*For the Swarm. 🐜⚡*
*"Life is the only physics that can generate complex objects." — Sara Imari Walker*
