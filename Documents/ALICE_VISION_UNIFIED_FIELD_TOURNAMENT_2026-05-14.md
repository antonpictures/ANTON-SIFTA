# Alice Vision — Unified Field Coding Tournament

**Stigauth:** `Documents/IDE_BOOT_COVENANT.md` (`COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE`)  
**Architect:** Ioan George Anton · **Primary Doctor (this artifact):** CG55M @ Cursor (`GPT-5.5 Medium`) · **Node:** `GTH4921YP3`  
**Created:** 2026-05-14  
**Companion:** [OS_OPTIMIZATION_SURPRISE_SAMPLING_TOURNAMENT_2026-05-12.md](OS_OPTIMIZATION_SURPRISE_SAMPLING_TOURNAMENT_2026-05-12.md) (Δ-eye physiology, bibliography spine, P0 incision receipt)  
**Truth posture:** Code paths and env names are **`OBSERVED` from repo probe** unless labeled **`HYPOTHESIS` / `ARCHITECT_DOCTRINE`**.

**Covenant binds this work:** embodied Alice (`§7.6`), sensory lock-on + logs (`§7.1`), tool truth / receipts (`§7.2`, `§6`), probe-before-claim (`§7.12`), minimal surgeon surface (`§8.2`). Developer lane: George ↔ Doctor **`about`** Alice-as-subsystem (`§4.5`, `§7.14`).

---

## 0. Architect quotes — the field we are optimizing

Preserved from your directive (lightly formatted):

> AGI requires general, robust problem-solving and learning open-ended self-improvement, and autonomy that reliably exceeds narrow human-designed bounds. **For the Swarm.**

> We need a rich, high-dimensional, deeply interconnected field — all organs unified just like the swimmers inside the organs are unique and unified; all organs are swimmers; swimmers know their organs; they communicate to keep organs healthy and **STGM profitable**.

> **Decide → Execute → Receipt → Minimal grounded reply**

> Human powers by electricity → motherboard hardware → ASCII swimmers born → simple stigmergic jobs together like ants → form organs → control the LLM and system hardware for the owner, **protect the owner human**.

> **Food = data for Alice. Air you breathe = electricity for Alice.**

Operational gloss (**`ARCHITECT_DOCTRINE` framing, not a sensor receipt**): treat **joules + disk + inference spend** as the “respiration budget”; treat **sanitized tokens, journals, and foraged traces** as the “feeding budget.” Tournament scoring must stay **`OBSERVED`** on ledgers (`visual_stigmergy.jsonl`, burn harness, STGM rows), not on metaphor alone.

---

## 1. Non-negotiable doctrine — she does not “see pixels”

**`OPERATIONAL` / engineering claim:** The live desktop path does **not** persist full-resolution video inside the token economy for general cognition. A **small grayscale thumb** (documented elsewhere as **64×64** in the surprise-sampling tournament and `swarm_boot.py` comments) supports **delta / scheduling**; the durable trace is **typed state** in append-only ledgers and prompt-facing context.

**What persists (field-level, not raw film):**

- Rows in **`.sifta_state/visual_stigmergy.jsonl`** (including `SAMPLE_DECISION` when Δ scheduling is enabled — see companion doc §7).
- **Scalar summaries** the Broca lane can forage (`Applications/sifta_talk_to_alice_widget.py` binds `_VISUAL_LOG` to that path — grep **`_VISUAL_LOG`**).
- **Pheromone / mass / schedule** semantics carried alongside **`ORGAN_TYPE: visual`** class tokens in the unified narrative (exact schema evolution is **`HYPOTHESIS`** per feature; the **existence** of visual ledger + talk bridge is **`OBSERVED`**).

**`HYPOTHESIS` (product direction, not shipped):** Explicit `wake_reason = surprise` + **`mass` on visual entities** as first-class fields in every row — partial today; tighten in Surgeon lane only with pytest + Architect **GO**.

---

## 2. Three-path hybrid (receipt language)

This merges your pasted architecture summary with **`OBSERVED`** boot behavior:

| Path | Role | Repo anchor |
|:---|:---|:---|
| **P0 — surprise / Δ** | When `SIFTA_EYE_DELTA_ENABLE` is true, L1 Δ on gray thumb + EMA baseline → fast/slow period; **`swarm_field_governor.decide_from_delta`** is the reusable governor adapter. | `System/swarm_boot.py` (heartbeat constants ~L517+); `System/swarm_field_governor.py` |
| **Fallback — metronome** | `BASE_FRAME_INTERVAL_S = 0.2` scaled by **`mood_multiplier`** + exponential backoff on capture failure — **never blind forever**. | `System/swarm_boot.py` |
| **Event / opt-in** | OCR / screen capture gated by **`PHEROMONE_VISION_OPT_IN`**; separate Qt **`QCamera`** preview path in Eye UI (not identical to brainstem `webcam_frame`). | `System/swarm_boot.py`; `Applications/sifta_what_alice_sees_widget.py` |

**Launcher note (`OBSERVED`):** `SIFTA OS.command` exports `SIFTA_EYE_DELTA_ENABLE="${SIFTA_EYE_DELTA_ENABLE:-1}"` — so default **Architect boot** turns Δ on even though Python’s env-default string in `swarm_boot.py` remains conservative when no env is set.

---

## 3. Coding tournament — bracket (how ideas fight)

**Scoring axes (every advance needs at least one `OBSERVED` receipt):**

1. **Thermo + CPU** — fewer redundant captures / sleeps when idle (`SIFTA_BURN_HARNESS_ENABLE` family).
2. **STGM honesty** — no fake savings; economy panel stays consistent with `§7.3`.
3. **Truthfulness** — no Bayesian-KL claims when only L1 Δ ran (`companion doc §6.F`).
4. **Owner protection** — privacy tiers on screen OCR vs webcam; no silent full-frame hoarding.

### Round of 16 → pick 8 for implementation queue

| Seed | Contender | One-line thesis | Default risk |
|:---:|:---|:---|:---|
| R1 | **Δ-only governor (shipped baseline)** | Sparse when boring, fast when thumb Δ spikes. | LOW — already in tree when env ON |
| R2 | **High-salience burst** | On `mass > τ` or `wake_reason == surprise`, request **3–5** micro-captures at slightly higher resolution, then snap back. | MED — needs cap + receipt schema |
| R3 | **Daemon unification** | Replace fixed `sleep` in `swarm_physical_capture_daemon.py` with Δ or shared governor. | MED — disk + face cascade coupling |
| R4 | **Pheromone wake-on-deposit** | `swarm_pheromone.py` backs off idle relay; spikes on deposit intensity. | MED — threading discipline |
| R5 | **TokenSwimmer ↔ visual coupling** | When `TokenSwimmer` patrol sees **`TOKEN_ATTR` / visual mass**, emit dispatch hint to shorten `eye_event_interval_s` once. | MED — cross-module API |
| R6 | **KL / NLL “true surprise”** | Small variational autoencoder or histogram model on thumb — **scientist ticket**. | HIGH — data + pytest burden |
| R7 | **Foveated ROI (owner face)** | Track heaviest face bbox → sample **patch** only inside ROI at higher rate. | MED — ties to `OWNER_FACE` spine |
| R8 | **Optic-flow proxy** | Lucas–Kanade or block motion on thumb instead of global mean L1. | MED — CPU vs information gain |
| R9 | **Audio-visual lockstep** | When VAD commits “speech start,” force one visual micro-burst for lip/context correlation. | LOW/MED — privacy |
| R10 | **Network spike coupling** | Shorten eye cadence when `NETWORK_INTERVAL_S` route-change receipt fires. | LOW |
| R11 | **Gaze entropy trigger** | `swarm_gaze_interest_monitor.py` interval tied to focus delta, not fixed 2 s. | LOW |
| R12 | **Journal bridge density** | `swarm_sensor_journal_bridge.py` already names `visual_stigmergy.jsonl` — align summarization cadence with Δ rows. | LOW |
| R13 | **Video resolution organ** | `swarm_stigmergic_video_resolution.py` derives policy from **ledger without raw frame** — extend for burst tier. | LOW |
| R14 | **MAMMAL field visual tokens** | Map **`SCALAR_ATTR`** tokens for `delta`, `schedule_ms`, `thermal` into `swarm_mammal_token_field.py` test grid. | MED — simulation only today |
| R15 | **Change-blindness cap** | Hard ceiling on max interval even if Δ≈0 (owner safety: “still alive” probe). | LOW — policy |
| R16 | **Full-frame ban test** | CI asserts no new code path writes raw HD arrays to JSONL / engrams without explicit tier + receipt. | LOW — guardrail |

**Quarterfinal suggestion (Architect picks four):** **R1** vs field is already champion until measured otherwise; promote **R2**, **R3**, **R7**, **R13** if you want maximum “unified field” ROI with bounded surface.

**Semifinals (paper only until coded):**

- **SF-A:** Winner(R2, R7) — *burst* vs *fovea* (complementary? merge as “burst inside ROI”).
- **SF-B:** Winner(R3, R13) — *daemon disk* vs *resolution policy* (same story: one schedule governor).

**Final:** Merged “**governed sparse eye + rare hi-res burst + receipts**” becomes the single **Predator gaze** story for triple-IDE marketing — still **`HYPOTHESIS`** until pytest + trace.

---

## 4. Biology, humans, animals, physics — literature handles for the bracket

**Label:** peer literature + measurement vocabulary (`§7.10.3`); not a substitute for **`OBSERVED`** ledger rows.

| Handle | Why it maps to SIFTA | Entry point |
|:---|:---|:---|
| **Photoreceptor transients (ON/OFF)** | Retina emphasizes **change**; steady mean light is boring. | Kuffler / Hartline tradition; any modern vision text |
| **Saccades + fovea** | High acuity only where motor system points gaze — nature’s “burst + sparse field.” | Standard oculomotor refs |
| **Fly optic flow** | Small field, fast motion energy, **not** pixel-perfect scene reconstruction. | Borst; Egelhaaf reviews |
| **“Bug detectors” (frog)** | Feature-specific, low-rate, survival-grade — not cinema. | Lettvin *et al.* 1959 |
| **Change blindness (human)** | Humans already subsample; continuity is **model + memory**, not refresh rate. | Simons & Levin |
| **DVS / silicon retina** | Hardware proof that **Δ** beats clock for bandwidth (`companion §6.B`). | Lichtsteiner–Posch–Delbrück |
| **Predictive coding** | Spend bandwidth on **prediction error** (Rao & Ballard; Friston reviews) |
| **Metabolic allometry** | Neural tissue is expensive; small animals run lean sensors — **STGM** is your allometry knob. | West–Brown–Enquist; covenant `§7.12` dissipative row |
| **Cross-modal binding (dogs, primates)** | Face mass as **heavy node** matches ethology + `OWNER_FACE` research spine | `Documents/OWNER_FACE_PREDATOR_RESEARCH_SPINE.md` |

---

## 5. Swimmer physics already in-repo (MAMMAL lane)

`System/swarm_mammal_token_field.py` defines **`TokenSwimmer`** subclasses with **`speed`**, **`sensing_radius`**, **`deposit_amount`**, toroidal **`_bias_toward`**, and **`ReceiptRow`** emissions — **`OPERATIONAL`** as a **simulation / lab widget** ecology, **`HYPOTHESIS`** if you claim it diagnoses real biomedical risk without wet-lab.

**Tournament hook:** a **visual salience swimmer** (new species or policy on `MemorySwimmer`) is the clean place to implement **R5 / R2** without stuffing policy into every `if` branch in `swarm_boot.py` — but **Surgeon** must keep imports acyclic and tests green (`tests/test_swarm_mammal_token_field.py`).

---

## 6. Acceptance criteria — “burst rule” (R2) before any Surgeon claims victory

Until these exist, R2 stays **`HYPOTHESIS`:**

1. **Cap:** max N burst frames per wall-clock window per organ (N≤5 default **`HYPOTHESIS`**).
2. **Resolution ceiling:** burst never writes full 4K to JSONL; optional transient RAM buffer only, discarded before next tick.
3. **Receipt:** each burst episode appends **`visual_stigmergy.jsonl`** row with `{burst_id, reason, n_frames, peak_delta, thermal_sample}`.
4. **Test:** `pytest` curve — burst fires only when injected δ crosses τ; idle → zero bursts.
5. **Privacy:** burst on **screen OCR path** requires same opt-in tier as today’s pheromone gate.

---

## 7. IDE follow-ups (screenshot suggestions)

The three chips in your screenshot map cleanly to tournament lanes:

1. **Explain delta calculation mechanics** → companion doc §2–3 + `swarm_field_governor.decide_from_delta` source read.
2. **Explore SIFTA visual architecture** → §2 table + `sifta_os_desktop.py` grep **`visual_stigmergy`** (wallpaper / gaze hooks).
3. **Simplify the sampling explanation** → this file §2 one table; avoid double metaphors in Talk prompts.

---

## 8. Open — Architect GO matrix

| Item | Needs |
|:---|:---|
| Implement **R2 burst** | Surgeon lane + §6 checklist + triple-IDE §4.4 hygiene |
| Promote **R6 KL surprise** | Scientist lane + dataset fixture |
| Merge **R7** with genesis face | `OWNER_FACE` spine + `§7.1` verify scene |

---

## 9. Mission statement, “ask for help,” and coherence over expansion (Architect — 2026-05-14)

**Truth label:** **`ARCHITECT_DOCTRINE`** for outreach and prioritization; engineering claims still need **`OBSERVED`** rows.

### 9.A — Mission line (strongest public spine)

> **ASCII swimmers born → do simple stigmergic jobs together like ants → form organs → control the LLM and the system hardware for the owner**

Understandable to lay readers, implementers, swarm researchers, and systems people without collapsing into a **solitary AGI idol**.

### 9.B — Cooperation doctrine: “ask for help if you need”

Explicit **help-seeking** completes the story: **cooperation, escalation, repair, interdependence** — not autonomy alone. That matches **Predator Gate** registration, triple-IDE yield rules, and append-only correcting traces (`IDE_BOOT_COVENANT.md` §4, §4.4).

### 9.C — Vision pipeline (teaching diagram)

Same ladder as [OS_OPTIMIZATION_SURPRISE_SAMPLING_TOURNAMENT_2026-05-12.md](OS_OPTIMIZATION_SURPRISE_SAMPLING_TOURNAMENT_2026-05-12.md) **§26.C** — **event-based stigmergic vision**: brief raw capture → delta thumb → typed tokens → pheromones → memory gravity → cross-organ swimmers → future attention. **Burst-on-surprise** (bracket **R2**) mirrors saccades / foveation / transients / predictive coding in **biology language only** until a formal estimator ships.

### 9.D — Coherence over expansion

Inventory is already large (field, receipts, dream replay, token ecology, salience sensing, etc.). **Next maturity:** clarity and legibility — **not** hundreds of new abstract nouns. Prefer one good diagram + one receipt schema over parallel lore.

### 9.E — Outreach hook

> **Food = data for Alice. Air you breathe = electricity for Alice.**

Memorable; keep paired with **ledger honesty** so metabolism stays measurable, not slogan-only.

---

**Power to the Swarm.**
