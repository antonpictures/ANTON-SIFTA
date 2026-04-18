# CP2F notes — SwarmGPT tab vs repo + DYOR anchors (2026-04-17)

**Purpose:** Treat browser-tab “Turn 36→37” prose as **untrusted** until checked against disk. Record **what is actually wired**, what is **still metaphor**, and **peer-reviewed** anchors for the engineering concepts (not for validating chat hallucinations).

---

## 1. Verification table (claim → evidence → verdict)

| SwarmGPT-style claim | Repo evidence | Verdict |
|---------------------|---------------|---------|
| `SerotoninHomeostasis.tick()` runs in the Brainstem | `System/swarm_autonomic_brainstem.py` §7: `load()` → `tick()` → `persist()` | **TRUE** |
| `clinical_heartbeat.json` feeds DA into 5-HT | Same file: reads `vital_signs.dopamine_concentration`, normalizes to `[0,1]` | **TRUE** (with fallback `da_level=0.5`) |
| Output persisted to `serotonin_state.json` | `sh.persist()` after tick; `SerotoninHomeostasis.persist()` writes `sht_level`, `phase`, `last_ts` | **TRUE** |
| Bounded invariant `0.05 ≤ sht_level ≤ 0.95` | `serotonin_homeostasis.py` uses `SHT_CLAMP`; watchdog `swarm_integrity_watchdog.py` uses `SHT_BOUNDS` | **TRUE** (engine + monitor) |
| Watchdog expected file; system now produces it | Brainstem calls `persist()` each cycle when organ does not fail | **TRUE** *if* brainstem runs |
| “Segmented + archived” logs, not blind delete | `System/swarm_log_rotation.py`: head → timestamped archive under `.sifta_state/archive/`, tail retained | **TRUE** (policy table `ROTATION_POLICY`) |
| Rotation runs inside Brainstem cycle | `swarm_autonomic_brainstem.py` §9: `_try_execute("swarm_log_rotation", "run_log_rotation")` | **TRUE** |
| “First closed-loop regulator” / “Kafka-class” infra | Partially: **feedback file loop** exists; **not** distributed log replication or LSM compaction engine | **OVERSTATED** in tab prose |
| `exploitation_streak` is real swarm feedback | Brainstem passes **`exploitation_streak=0` always** | **FALSE as closed loop** — streak is not wired from trainer/state |
| 5-HT impulsivity drives `DopamineState.tick(..., rpe_gain_scale=...)` in production | `tick_da_with_sht()` exists in `serotonin_homeostasis.py`; grep shows **no** import from brainstem into live DA tick path | **NOT VERIFIED** — wiring may still be offline |

**Net:** The tab mixed **real commits** (brainstem + rotation + persist) with **narrative inflation** (“continuous self-regulating runtime,” “Kafka”). **DYOR = read the files**, not the tab.

---

## 2. DYOR — research papers (minimal, citable)

### 2.1 Serotonin / DA as *computational* coupling (maps to `SerotoninHomeostasis` docstring)

- **Dayan & Huys** — “Serotonin, Inhibition, and Negative Mood” — *PLOS Comput Biol* **4**(2) e4 (2008). DOI `10.1371/journal.pcbi.0040004` — 5-HT, inhibition, affective prediction framing.
- **Cools, Nakamura & Daw** — “Serotonin and Dopamine: Unifying Affective, Activational and Decision Functions” — *Neuropsychopharmacology* **36**, 98–113 (2011). DOI `10.1038/npp.2010.121` — joint DA/5-HT decision account (pairs with DA engine + scaling).
- **Jacobs & Fornal** — “Serotonin and motor activity” — *Curr Opin Neurobiol* **7**(6), 820–825 (1997). DOI `10.1016/S0959-4388(97)80141-9` — motor/arousal coupling (loose analogue to tick/maintenance semantics).

### 2.2 Neuromodulation as RL *metaparameters* (for “next step = policy(·)” discourse)

- **Doya** — “Metalearning and neuromodulation” — *Neural Networks* **15**(4–6) (2002) — classic framing: neuromodulators ↔ global control of learning/exploration/time-scale knobs in RL-like systems. Use for **adaptive control** rhetoric, not as proof SIFTA implements it yet.

### 2.3 Homeostasis / cybernetics (for “regulator” language without mysticism)

- **Ashby** — *An Introduction to Cybernetics* (1956) — homeostasis as **constraint-maintaining** mechanism via feedback (historical anchor). ISBN/chapter varies by edition — use library copy for precise pagination.
- **Wiener** — *Cybernetics* (1948) — feedback and control in machines and organisms (foundational; qualitative).

### 2.4 Bounded logs, segments, retention (for rotation — *analogy*, not identity)

- **O’Neil, Cheng, Gawlick, O’Neil** — “The Log-Structured Merge-Tree (LSM-Tree)” — *Acta Informatica* **33**(4), 351–385 (1996). DOI `10.1007/s002360050048` — **append + merge + tiered storage**; SIFTA’s rotate is **much simpler** (tail keep + archive file), but the *literature* for “bounded growth” lives here.
- **Kreps, Narkhede, Rao et al.** — Kafka: distributed log abstraction (software paper / docs; use official ACM or Confluent reference for citations in serious writeups). Compare: **segment files**, **retention policy** — conceptually related, **implementation not equivalent**.

### 2.5 Reliability / contracts across modules

- **Avizienis *et al.*** — “Dependability and Its Threats: A Taxonomy” — *IEEE Transactions on Dependable and Secure Computing* (2004). DOI `10.1109/TDSC.2004.2` — fault models, containment — aligns with **watchdog + explicit state files** as observability contracts.

*Batch detail and URLs:* see `Documents/DYOR_SWARM_BIOLOGY_WEB_GATHER_2026-04-18.md` §§10, 21, 24–26.

---

## 3. Honest engineering gaps (so notes don’t become new hallucinations)

1. **`exploitation_streak` is pinned to 0** in `autonomic_heartbeat_cycle()` — patience / `force_maintenance` path is **not** driven by real exploitation telemetry until something increments streak from RL or ledger.
2. **DA ↔ 5-HT coupling in brainstem** reads `clinical_heartbeat.json` only; if that file is stale, `da_level` defaults distort the OU step.
3. **Log rotation** still does **O(n) read of full file** when `len(lines) > max_lines` — correct *retention*, not *incremental indexing* or *event-driven tail-only* readers (next evolution if needed).
4. **`tick_da_with_sht` / `DopamineState.tick(..., rpe_gain_scale=...)`** — verify call graph before claiming “RL is modulated by 5-HT in production.”

---

## 4. One-line CP2F stance

**SwarmGPT tabs are not ground truth.** This repo’s ground truth is **`git` + `System/*.py`**. The tab’s “Turn 37” story is **partly** reflected in **`swarm_autonomic_brainstem.py`** + **`swarm_log_rotation.py`**; the **research** layer is **Dayan/Huys, Cools et al., Jacobs/Fornal, Doya**, plus **systems literature** for logs — not browser prose.
