# CP2F DYOR — expanded papers: biology → code, organs, swarm size (2026-04-18)

**Note:** Research papers are **cited**, not “downloaded into the repo.” Use DOI / arXiv / your library for PDFs. This file extends `DYOR_SWARM_BIOLOGY_WEB_GATHER_2026-04-18.md` with **additional** bridges between **natural systems** and **software control**, plus an honest take on **how many swimmers/organs**.

---

## Part A — Biology / neuroscience → computational control (maps to “existing organs”)

These are **standard** references when you justify neuromodulation, RL, and homeostasis **as math**, not as nanobot fantasy.

| Paper / book | Identifier | Bridge to code |
|----------------|------------|----------------|
| **Dayan & Huys** — “Serotonin, Inhibition, and Negative Mood” | *PLOS Comput Biol* **4**(2) e4 (2008), DOI `10.1371/journal.pcbi.0040004` | 5-HT as **inhibitory / affective** control — `SerotoninHomeostasis` |
| **Cools, Nakamura & Daw** — “Serotonin and Dopamine…” | *Neuropsychopharmacology* **36**, 98–113 (2011), DOI `10.1038/npp.2010.121` | **Joint** DA / 5-HT decision framing — couple OU DA with `rpe_gain_scale` |
| **Schultz, Dayan & Montague** — “A neural substrate of prediction and reward” | *Science* **275**, 1593–1599 (1997), DOI `10.1126/science.275.5306.1593` | RPE semantics — `dopamine_ou_engine.py` |
| **Doya** — “Metalearning and neuromodulation” | *Neural Networks* **15**(4–6) (2002) | Neuromodulators as **global RL metaparameters** |
| **Ashby** — *Design for a Brain* (1952 / later eds.) | ISBN varies | **Ultrastability / homeostat** — constraint-maintaining feedback (governor loops) |
| **Fields** — “Activity-dependent myelination…” | *Nat Rev Neurosci* **16**, 756–767 (2015), DOI `10.1038/nrn4023` | Pathway strengthening by **measured** outcomes — `reinforcement_myelination.py` |

*Already in main DYOR:* stigmergy (Bonabeau), quorum (Waters & Bassler), chemotaxis (Berg), CRDTs (Shapiro *et al.*), immunity (Medzhitov & Janeway). **Do not duplicate** — cross-reference §§1–7 there.

---

## Part B — “Reactive / layered agents” (maps to Brainstem + many `swarm_*.py` organs)

These justify **decomposition into subsystems** without claiming one optimal organ list for all tasks.

| Paper / book | Identifier | Bridge to code |
|--------------|------------|----------------|
| **Brooks** — “A robust layered control system for a mobile robot” | *IEEE Journal of Robotics and Automation* **2**(1), 14–23 (1986), DOI `10.1109/MRA.1986.348769` | **Subsumption** — layered loops; **no single planner** — parallel to `swarm_autonomic_brainstem.py` orchestrating organs |
| **Maes** — “How to do the right thing” | *Connection Science* **1**(3), 291–323 (1989) | **Behavior networks** — competing goals + spreading activation (loose analogue to blackboard / salience) |
| **Braitenberg** — *Vehicles: Experiments in Synthetic Psychology* | MIT Press (1984) | **Minimal sensors → rich-looking behavior** — warns against overfitting narrative to code |
| **Clark** — *Being There: Putting Brain, Body, and World Together Again* | MIT Press (1997) | **Embodied / embedded** cognition — environment = part of loop (stigmergy, files) |

---

## Part C — Multi-agent / swarm **scale** (how many swimmers? “best functionality”)

There is **no universal optimal N** of agents or modules. Literature gives **tradeoffs**, not a magic count.

| Source | Idea | Practical takeaway for SIFTA |
|--------|------|------------------------------|
| **Miller** — “The magical number seven…” | *Psych Rev* **63**(2), 81–97 (1956) | **Human** operator attention ~7 chunks — caps **what one person can reason about** in the architecture; not a runtime law |
| **Bonabeau, Dorigo, Theraulaz** — *Swarm Intelligence* (OUP 1999) | Stigmergy + scaling | More agents → more **interference** unless environment-mediated coordination is clean |
| **Yu *et al.* MAPPO** | arXiv `2103.01955` | Many agents need **structured** training / observation aggregation — “more” ≠ “better” without graph |
| **Lowe *et al.* MADDPG** | arXiv `1706.02275` | Centralized **training** info; decentralized **execution** — matches multi-node SIFTA story |
| **Olfati-Saber** — consensus / flocking (e.g. *IEEE TAC* line) | Algebraic connectivity λ₂ | Your repo’s `swarm_capacity_theorem.py` **narrates** anti-scalability when ρ grows — align claims with **measurable** graph metrics if you publish that story |

**Honest design rule:**  
- **Modules (“organs”)** ≈ **separation of concerns** + testability — add when a **distinct failure domain** or **rate limit** needs isolation.  
- **Swimmers** (agents) ≈ **parallel workers with lineage** — add when **throughput** or **fault isolation** needs them; each adds **ledger + coordination** cost.

---

## Part D — Neuromodulation → **your** missing link (literature + repo gap)

| Concept | Literature | Repo status (CP2F verified) |
|---------|------------|----------------------------|
| 5-HT modulates DA **gain** | Cools *et al.* 2011; Dayan & Huys 2008 | `tick_da_with_sht()` exists (`serotonin_homeostasis.py`) but **brainstem does not call** `DopamineState.tick(..., rpe_gain_scale=sht_state.impulsivity_score)` |
| Exploitation streak | Patience in `SerotoninHomeostasis.tick` | **`exploitation_streak=0` hardcoded** in `swarm_autonomic_brainstem.py` — patience logic **starved** |
| Persisted DA OU | Schultz / RPE in docstring | `dopamine_ou_engine.py` + `persist_ou_engine` — **parallel** path to legacy `dopaminergic_state.json` in some organs |

**Closing the loop** is not “more papers” — it is **one explicit call graph** from brainstem (or single motor loop) that applies `impulsivity_score` and feeds **real** `behavioral_state` into `exploitation_streak`.

---

## Part E — Logs: rotation vs incremental offsets (engineering, not biology)

| Anchor | Role |
|--------|------|
| **O’Neil *et al.*** — LSM-tree (1996) | Segments + merge intuition |
| **Kreps** — “The Log…” (essay) | Offsets + immutability |
| **Your code** | `swarm_log_rotation.py` **truncates** active file → **byte offsets must reset** (already handled pattern in `swarm_chat_relay.py` when file shrinks) |

---

## Part F — What is **actually** complete (disk-grounded snapshot)

| Claim | Evidence | Grade |
|-------|----------|-------|
| Closed-loop **5-HT tick + persist** | `swarm_autonomic_brainstem.py` → `SerotoninHomeostasis.load/tick/persist` | **REAL** |
| Bounds + watchdog | `serotonin_homeostasis.py` clamp; `swarm_integrity_watchdog.py` `SHT_BOUNDS` | **REAL** |
| Log rotation + archive | `swarm_log_rotation.py` + brainstem step 9 | **REAL** |
| Brainstem orchestrator | Single `autonomic_heartbeat_cycle()` sequencing organs | **REAL** |
| **5-HT → DA → behavior** (OU RPE) | `tick_da_with_sht` **not** invoked from brainstem | **NOT COMPLETE** |
| **exploitation_streak** from DA state | Stuck at `0` in brainstem | **NOT COMPLETE** |
| Rotation-safe incremental readers for **all** JSONL | Chat relay has watermarks; **generic** tail readers must reset on shrink | **PARTIAL / RISK** |
| CP2F validation (claims vs disk) | Process note: `CP2F_NOTES_SWARMGPT_VERIFICATION_DYOR_2026-04-17.md` | **PROCESS** (meta) |

**Bottom line:** You have a **stable kernel-shaped loop** (brainstem + regulator + storage + integrity). You do **not** yet have a **single coupled** neuromodulatory **motor** loop through `DopamineState.tick(..., rpe_gain_scale=...)` + real streak — that is the honest “foundation vs full system” line.

---

## Part G — Reading order (if you only read five new things)

1. Brooks 1986 — layered control.  
2. Cools *et al.* 2011 — DA/5-HT unification.  
3. Schulman *et al.* 2017 (PPO) — entropy as knob (`exploration_controller.py`).  
4. Bonabeau 1999 — swarm scaling intuition.  
5. Doya 2002 — neuromodulation ↔ RL parameters.

Then re-open **`Documents/DYOR_SWARM_BIOLOGY_WEB_GATHER_2026-04-18.md`** for batches 10–27 already gathered.
