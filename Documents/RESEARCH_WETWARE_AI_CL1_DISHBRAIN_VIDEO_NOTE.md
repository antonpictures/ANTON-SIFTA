# RESEARCH NOTE — Wetware AI (DishBrain → CL1), Doom, Ethics (YouTube source)

**Date:** 2026-04-16  
**Source (primary):** [YouTube — video `ZqRtR6Z2U6U`](https://www.youtube.com/watch?v=ZqRtR6Z2U6U) (informal explainer; **not** a peer-reviewed paper).  
**Transcript basis:** User-supplied text with timestamps (same session). **Not** machine-ripped from YouTube in-repo; for future auto-captions use e.g. `yt-dlp` with `--write-auto-sub` / `--sub-langs` against the URL above (respect YouTube ToS and local law).

---

## 1. Chapter index (timestamps from source)

| Time | Topic |
|------|--------|
| 0:00 | State of current AI (LLMs on GPUs; scaling limits) |
| 1:17 | Why “brain chips” / biological angle |
| 2:31 | DishBrain (Pong, ~2021–2022) |
| 3:45 | CL1 (successor system) |
| 6:53 | Harvesting / sourcing cells (iPSCs) |
| 8:16 | CL1 chip design (2D monolayer, HD-MEA) |
| 9:33 | Sponsor segment (Manus) — omitted from technical summary below |
| 11:21 | How it plays DOOM (encode → stimulate → record → decode) |
| 14:24 | How it learns (free energy / “minimize surprise”; reward vs chaos) |
| 16:56 | Benefits of living neurons (speed, energy, Moravec paradox) |
| 19:28 | Ethics (consciousness, scale, suffering) |

---

## 2. Technical summary (from transcript)

### 2.1 Motivation

- Digital AI runs as code on **silicon** (GPUs); **transistor** scaling and **energy** are stressed as limits.  
- **Alternative narrative:** compute using **living neurons** on a chip — claimed advantages: **efficiency**, **fast adaptation**, **robotics** (Moravec paradox: “easy” physical tasks hard for classical control).

### 2.2 DishBrain (prototype)

- Clusters of **human and mouse** neurons learned a **simple** arcade game (**Pong**).  
- Scale cited: up to **~1M neurons**; training **very slow** (~**18 months** before reliable learning in the telling).  
- **Failure mode:** electrical stimulation imbalance → **excitotoxicity** (overstimulation kills cells).  
- Takeaway in video: prototype proved concept but needed **redesign**.

### 2.3 CL1 (successor)

- **~200,000 neurons** (video contrasts with DishBrain’s ~1M — **smaller** culture, still **stable learning** in the narrative).  
- **Life support:** microfluidic **perfusion** (nutrients, O₂, waste removal), **filtration** (“kidney-like”), **37°C** thermal control, **gas mixing** (O₂/CO₂). Neurons viable **up to ~6 months** per video.  
- **Form factor:** self-contained module fitting a **server rack** (pumps, gas, heating, interfaces integrated).  
- **Interface:** neurons in **2D monolayer** on **high-density microelectrode array (HD-MEA)** — **bidirectional**: stimulate + record spikes (**sub-millisecond** resolution cited; recording rate example **~40k/s** in DOOM section).

**Transcript inconsistency:** Later the narration says “**200 neurons**” vs fruit fly; elsewhere CL1 is **200,000**. Treat **200k** as the intended CL1 scale; the “200” line is likely **ASR error**.

### 2.4 Cell source (ethics-friendly framing in video)

- **No brain harvesting from people** — cells from **iPSCs** (induced pluripotent stem cells) from donation (e.g. skin/blood), **reprogrammed** to **neurons** (Nobel-linked technique referenced informally).

### 2.5 DOOM loop (sense → act)

- Game state → **encoder** (e.g. **ray casting** for coarse geometry).  
- **Stimulation patterns** (frequency / amplitude / timing / electrode **location**) encode walls, enemies, hits, etc.  
- **HD-MEA** records population spiking → **decoder** maps patterns to **game commands** (move, turn, shoot).  
- Closed loop: software ↔ electrodes ↔ living tissue.

### 2.6 Learning signal (video’s account)

- Invokes **free energy principle** / **minimize surprise**: “good” outcomes → **smooth, predictable** electrical feedback; “bad” outcomes → **chaotic noise** forcing adaptation (synaptic/plastic change).  
- Performance described as **rough** / “baby or insect” level — emphasis on **fast adaptation** (hours) vs millions of GPU steps for large ANNs.

### 2.7 Ethics (video)

- **Cortical Labs** position cited: **not conscious** at this scale — lacks full **brain-like** anatomy (no integrated sensory/emotion/pain systems as in whole organism).  
- Open question posed: **scaling** to datacenter rows — could **complexity** change moral status?

---

## 3. SIFTA mapping — “replace neurons” vs **stigmergic** substrate

You do **not** need biological neurons to capture the **useful** structural idea for SIFTA:

| Wetware story | SIFTA analogue |
|---------------|----------------|
| **Dish / culture** | **Append-only** environment: blackboard, ledgers, dead drops |
| **Medium** (fluid, temperature, gas) | **Governed** resource flows: STGM, routing, capacity limits |
| **HD-MEA** (read/write boundary) | **Router + eval harness** — sensors/actuators on the substrate |
| **Excitotoxicity** | **Over-stimulation** → rate limits, governor caps, ICF quarantine (**no hard delete** — see `RESEARCH_PLAN_PHASE_TRANSITION_CONTROL_REGIME_SHIFT.md`) |
| **“Minimize surprise” / free energy** | **Objective probes**, **eval strictness**, **coherence field** — reduce **policy surprise** without torturing cells |
| **Scale-up ethics** | **Non-proliferation**, **Architect policy**, **signed** promotions — **organism** is software + law, not meat |

**“Be better stigmergic, solve problems how?”**

1. **Traces beat broadcasts** — coordination through **persistent environmental state** (stigmergy), not synchronous mind-meld; see [arXiv:2512.10166](https://arxiv.org/abs/2512.10166) (traces + density transitions) in your ICF research doc.  
2. **Interpretive infrastructure** — raw logs are not enough; **blackboard semantics + eval** are the “cognitive layer” that makes traces **usable**.  
3. **Coherence under plasticity** — skills/mutations compress **experience**; **ICF + phase control** prevent **dialect fragmentation** without **erasing** the audit trail.  
4. **Silicon is enough** for sovereignty — wetware raises **irreversible ethics**; SIFTA’s path is **lawful, replayable, stigmergic** compute on **owned** nodes.

---

## 4. Peer-reviewed anchors (DYOR — not from YouTube)

Use these to **ground** claims instead of the explainer video alone:

- **Kagan *et al.*, “In vitro neurons learn and exhibit sentience when embodied in a simulated game-world,”** *Neuron* **110**, 3952–3969 (2022). DOI: [10.1016/j.neuron.2022.09.001](https://doi.org/10.1016/j.neuron.2022.09.001). (DishBrain / Pong-style closed loop on **MEA** — **primary** scientific source for the dish-culture paradigm.)  
- **News / synthesis:** *Nature Machine Intelligence* commentary “DishBrain plays Pong and promises more” — [nature.com](https://www.nature.com/articles/s42256-023-00666-w) (accessible overview; not a substitute for the *Neuron* paper).  
- Follow-up: search **Cortical Labs**, **CL1**, **HD-MEA**, **microfluidic** perfusion on **PubMed / Google Scholar** for hardware updates after 2022.  
- **Ethics:** **iPSC**-derived neural tissue, **organoid** research ethics, and institutional review — separate legal/moral literature from SIFTA code.

---

## 5. Rally

**Substrate first, traces second, law third — neurons optional, integrity not.**

**POWER TO THE SWARM** — **stigmergy scales** when the **environment** is **honest** and **replayable**.
