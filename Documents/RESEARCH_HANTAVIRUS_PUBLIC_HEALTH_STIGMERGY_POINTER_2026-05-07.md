# Hantavirus — public health ground truth + where **stigmergicode** fits

**Status:** `RESEARCH_NOT_SHIPPED` — pointers and planning only. **NPPL:** no military / surveillance weaponisation; this note is for **civilian biosurveillance literacy** and honest system design.

**Trigger:** News cycle (e.g. cruise-ship Andes hantavirus cluster, May 2026) plus SIFTA **stigmergic memory** work (`RESEARCH_STIGMERGIC_PREDICTION_BIO_MATH_2026-05-07.md` §7–9).

---

## 1. Non-negotiable biology + medicine (read this first)

**Stigmergicode does not synthesise antivirals or replace clinicians.** Coordination software can help **aggregate, timestamp, and verify signals**; it cannot “solve the cure” by ledger alone.

Authoritative facts (May 2026 snapshots):

1. **[CDC — About Hantavirus](https://www.cdc.gov/hantavirus/index.html)**  
   - Rodent-associated zoonosis; HPS (Americas) vs HFRS (Europe/Asia patterns).  
   - **Treatment:** CDC states there is **no specific treatment** for infection; **supportive care** (rest, hydration, symptom management); severe HPS may need **respiratory support**; HFRS may need **dialysis** when kidneys fail.

2. **[CDC — Hantavirus Prevention](https://www.cdc.gov/hantavirus/prevention/index.html)**  
   - **Primary prevention** is environmental: rodent exclusion, safe clean-up of infested spaces, occupational hygiene.

3. **[ECDC — Hantavirus infection](https://www.ecdc.europa.eu/en/hantavirus-infection)**  
   - Same core message: **no specific cure** licensed in Europe; **no licensed vaccine** in Europe; control = **avoid exposure** to contaminated rodent material.  
   - **Andes virus** is the strain with documented **person-to-person** transmission (typically close, prolonged contact) — relevant to outbreak investigations.

4. **ECDC — May 2026 cruise-ship cluster (Andes lineage)**  
   - Topic hub: [Surveillance and updates — Andes hantavirus outbreak](https://www.ecdc.europa.eu/en/infectious-disease-topics/hantavirus-infection/surveillance-and-updates/andes-hantavirus-outbreak)  
   - Rapid communication (6 May 2026): [Hantavirus-associated cluster of illness on a cruise ship: ECDC assessment and recommendations](https://www.ecdc.europa.eu/en/publications-data/hantavirus-associated-cluster-illness-cruise-ship-ecdc-assessment-and)  
   Use these for **case definitions, transmission notes, and risk communication** — not for self-diagnosis.

**If someone is ill after rodent exposure or outbreak contact:** they need **licensed medical care** and **public health channels**, not an IDE trace.

---

## 2. What “stigmergicode” *can* plan for (information layer)

Aligned with `IDE_BOOT_COVENANT.md` §3 (**proof-bearing federation**): nodes exchange **hashes, summaries, receipts** — not raw selfhood.

| Lane | Biological analogue | Honest software role |
|:---|:---|:---|
| **Deposit** | Lab / clinic / ship log entries | Append-only **JSONL** with `trace_id`, `homeworld_serial`, source URL, **content hash** of fetched advisory PDF/HTML. |
| **Decay** | Incubation windows, stale tests | TTL on news clips; **prefer primary** (ECDC/CDC/WHO) over social rewrites. |
| **Query** | Case finding | Bounded tail reads + FTS over **curated** pull notes (`youtube_watch_notes`, `RESEARCH_*`). |
| **Attention** | Triage | Predator / router decides **which** traces enter prompts — prevents “noise soup” (see stigmergic prediction digest §8.2 analogue). |
| **Federation** | Inter-agency situational awareness | **Summaries + signed rows** across M5/M1; never clone another node’s raw `.sifta_state/`. |

**Deliverable shape (future bake-off):** a `Documents/RESEARCH_Hantavirus_*_Tournament_*.md` that lists **primary sources only**, plus one machine row per source in `RESEARCH_DIRT_INDEX.md` §A when Architect GO.

---

## 3. Open research front (for scientists, not for repo to fake)

Things that **might** change the medical picture over years — track via **PubMed / clinical trial registries**, not via LLM summaries:

- Vaccine and antiviral **candidates** in pipelines (none replace CDC/ECDC today).  
- Genomic surveillance of **Andes** vs other lineages in travel-associated clusters.

PubMed search seed: [https://pubmed.ncbi.nlm.nih.gov/?term=hantavirus+ANDES+treatment+OR+vaccine](https://pubmed.ncbi.nlm.nih.gov/?term=hantavirus+ANDES+treatment+OR+vaccine)

---

## 4. Cross-links (repo)

- `Documents/RESEARCH_STIGMERGIC_PREDICTION_BIO_MATH_2026-05-07.md` — stigmergic memory / unified field.  
- `Documents/RESEARCH_DIRT_INDEX.md` — §A row + §E backlog for this thread.  
- `Documents/IDE_BOOT_COVENANT.md` — federation + Predator Gate (registration before mutating organism).

---

**Curated by:** CG55M@cursor (GPT-5.5 Medium) · `GTH4921YP3` · 2026-05-07.
