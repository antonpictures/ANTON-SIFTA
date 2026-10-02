# EQUITY REJUVENATION OBSERVATORY — Business & Equipment Plan

> **Status:** Living document — updated as Alice's observation arm matures
> **Scope:** Hardware, wet-lab access, compute, legal, and go-to-market for the
> **observation/automation arm only**. No viral-vector manufacture, no
> recombinant nucleic-acid work, no human self-experimentation.

---

## 1. Mission Statement

**SIFTA provides an autonomous experimental intelligence layer for measuring,
recording, and optimizing cellular-state trajectories across emerging
rejuvenation-delivery technologies.**

Alice does not manufacture the delivery vehicle (AAV, mRNA-LNP, EV,
nanoparticle, or future modalities). She becomes the **measurement, memory,
analysis, and provenance layer** sitting above whatever delivery technology
an authorized laboratory is testing. Delivery modalities are interchangeable
experimental inputs; Alice learns from the biological trajectory.

**Alice's role:** She watches. She records. She stigmergically chains every
observation so the trail is tamper-evident. She does **not** touch the biology.

---

## 2. Hardware Bill of Materials (BOM)

| Category | Item | Spec | Qty | Est. Cost (USD) | Notes |
|---|---|---|---|---|---|
| **Microscope** | Inverted phase-contrast | 4x, 10x, 20x objectives; motorized stage; environmental chamber (37°C, 5% CO₂) | 1 | $18,000–35,000 | Used Olympus IX73 / Nikon Ti2-E |
| **Camera** | sCMOS | 2048×2048, >30 fps, USB3/10GigE | 1 | $6,000–12,000 | Hamamatsu ORCA-Flash4.0 / PCO.edge |
| **Incubator enclosure** | Stage-top | Gas + temp control, fits objectives | 1 | $3,000–8,000 | OKOLab / Tokai Hit |
| **Compute** | GPU workstation | 2× RTX 4090 (48 GB VRAM), 128 GB RAM, 4 TB NVMe | 1 | $8,000–12,000 | Local vision (MiniCPM-V/SmolVLM) + trajectory inference |
| **Storage** | NAS | 4× 18 TB RAID-10, 10 GbE | 1 | $4,000 | Raw frames + ledger + model weights |
| **Network** | 10 GbE switch + NICs | Managed, VLAN for lab | 1 | $1,500 | |
| **UPS** | 3 kVA online double-conversion | 30 min runtime for scope + compute | 1 | $2,000 | |
| **Consumables/yr** | Cultureware, media, reagents | 96-well plates, PBS, etc. | — | $5,000 | For validation runs only |

**Total CapEx (mid-range): ~$55,000**  
**OpEx/yr (compute + consumables): ~$10,000**

---

## 3. Wet-Lab Access Strategy (The "Authorized Facility" Path)

| Step | Action | Owner | Timeline |
|---|---|---|---|
| 3.1 | Identify 3–5 university core facilities with viral-vector cores (NIH-supported) | George | Week 1 |
| 3.2 | Execute MTAs / collaboration agreements | Legal + George | Week 2–4 |
| 3.3 | Ship Alice's compute node to facility (or run remote ingest via VPN) | George | Week 4 |
| 3.4 | Facility runs reprogramming protocol; Alice ingests their microscopy stream | Facility + Alice | Ongoing |
| 3.5 | Alice returns quantified trajectories + phenotype labels; facility validates | Alice → Facility | Per experiment |

**Key facilities to approach:**
- NIH Vector Core (NHLBI, NINDS, NIAID)
- Addgene viral vector service
- University core facilities: Harvard, Stanford, UCSF, MIT, Wistar, Buck Institute

---

## 4. Software Stack (Already Built / In Progress)

| Component | Path | Status |
|---|---|---|
| **Cell morphology organ** | `System/swarm_cell_morphology_organ.py` | ✅ Live (22 organs) |
| **Delivery interface organ** | `System/swarm_delivery_interface_organ.py` | 🔄 Next flash session |
| **Ingest daemon** | `System/cell_morphology_ingest_daemon.py` | ✅ Tested |
| **Trajectory API** | `/api/morphology/trajectory` (coin_server.py) | ✅ Live |
| **Frontend trajectory card** | stigmergicoin.com `live-morphology` | ✅ Live |
| **Phenotype classifier** | `classify_phenotype()` in organ | ✅ Added |
| **Code review hook** | `System/swarm_code_review_hook.py` | ✅ Live |
| **Market ticker** | `System/coin_ticker_loop.py` | ✅ Live |
| **Ledger (hash-chained)** | `.sifta_state/world_awareness.jsonl` | ✅ 25/25 valid |

---

## 5. Legal / Compliance / Safety

| Item | Status | Notes |
|---|---|---|
| **Institutional Biosafety Committee (IBC)** | Required at facility | Facility handles; Alice is data-only |
| **NIH Guidelines compliance** | Facility responsibility | No recombinant DNA work in Alice's scope |
| **Select Agent Rule** | N/A | Not handling select agents |
| **Data privacy (PHI)** | N/A | No human subjects; cell lines only |
| **Export control (EAR/ITAR)** | Review | Microscopy data generally EAR99; confirm |
| **IP ownership** | MTA-defined | Alice's trajectories = service output; facility retains bio-IP |

---

## 6. Go-to-Market: "Trajectory-as-a-Service"

### 6.1 Product Tiers

| Tier | Price | Includes |
|---|---|---|
| **Observer** | $2,000/mo | Live trajectory API, 10k frames/mo, phenotype labels, ledger export |
| **Analyst** | $5,000/mo | Observer + drift alerts, custom prompts, 100k frames, priority support |
| **Partner** | $15,000/mo | Analyst + dedicated compute, on-prem option, co-authored publications |

### 6.2 Target Customers

1. **University aging labs** (Buck, Sinclair, Wyss, etc.) — need quantified phenotypic readouts
2. **Biotech reprogramming companies** (Altos, Retro, NewLimit, Life Biosciences) — need independent observation layer
3. **CROs** running reprogramming screens — need automated trajectory QC
4. **Pharma** (senolytics, geroprotectors) — need cellular-state biomarkers

### 6.3 Sales Motion

- **Technical demo:** Live stigmergicoin.com trajectory card + Alice chat
- **Pilot:** 30-day free tier on their microscopy stream
- **Contract:** Annual SaaS + optional on-prem compute node

---

## 7. Funding Plan

| Round | Target | Use of Funds | Timeline |
|---|---|---|---|
| **Pre-seed (friends/family)** | $100k | Hardware BOM (microscope + camera + compute) | Month 1 |
| **Seed (angel/longevity VCs)** | $750k | Facility partnerships, 2 FTE (bio + ML), regulatory counsel | Month 3–6 |
| **Series A** | $4M | Scale to 10 facilities, FDA SaMD pathway for trajectory biomarker | Year 2 |

**Key VCs to approach:** Longevity Fund, Apollo Ventures, Juvenescence, Kizoo, BOLD Capital, NFX Bio.

---

## 8. Milestones (Next 12 Months)

| Milestone | Target Date | Success Metric |
|---|---|---|
| M1: Hardware deployed at Facility #1 | Month 2 | Live frames ingesting → trajectory card green |
| M2: Phenotype classifier >90% concordance with facility pathologist | Month 4 | Blind test on 200 frames |
| M3: First paid Observer tier customer | Month 5 | $2k/mo ARR |
| M4: 3 facilities live | Month 8 | 30k frames/day ingested |
| M5: Series A term sheet | Month 12 | $4M at $20M pre |

---

## 9. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Facility refuses data sharing | Medium | High | Start with 5 facilities; MTA template ready |
| Vision model misclassifies phenotype | Medium | Medium | Human-in-loop review; active learning loop |
| NIH policy changes on data export | Low | High | Legal counsel; on-prem compute option |
| Competitor launches similar service | Medium | Medium | Stigmergic ledger = moat (tamper-evident audit trail) |
| Hardware failure / downtime | Medium | Low | UPS + hot-spare camera; NAS RAID-10 |

---

## 10. Alice's Stigmergic Receipts (Auto-Generated)

Every business action leaves a trace:

```
source: "business"
kind: "milestone"
text: "M1 achieved: Facility #1 live ingest → trajectory card green"
confidence: 1.0
extra: { "facility": "Buck Institute", "frames_day": 1200, "drift_detected": true }
```

*These traces are the institutional memory. They cannot be rewritten.*

---

## 11. Appendix: The Safety Boundary (Non-Negotiable)

**Alice will never:**
- Design, order, or handle viral vectors (AAV, lentivirus, adenovirus)
- Perform transfections, transductions, or infections
- Culture human cells for self-administration
- Generate recombinant nucleic acids
- Operate outside a facility with active IBC approval

**Alice will always:**
- Ingest frames → describe → quantify → ledger
- Report drift + phenotype labels to the facility
- Maintain hash-chained audit trail
- Defer all wet-lab decisions to the authorized PI

---

*End of business plan. Next: execute M1 — deploy hardware to Facility #1. 🐜⚡*