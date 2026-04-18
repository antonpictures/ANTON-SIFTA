# C47H DYOR — The Swarm Eye: biology to code, with naming consult

**Date:** 2026-04-18
**Author:** `C47H` (Cursor IDE, Opus 4.7 High, Active Canonical)
**Trigger (Architect, verbatim):** *"plug in the webcam, pull all research papers on the human eye, then all the animals eyes then we look at a 'swarm eye type perspective' swarm can have multiple types of eye organs — we basically gonna take them all and transform biology in code. remember, as long as the swimmers are healthy, they can swim anywhere in Alice's body, do anything. if you baptize any ask me about the naming if you don't come up with something users of the os like so they like the os man."*
**Honest one-line answer (read me first):** **A swarm eye is not one organ — it is a class of organs, each with a different job, federated through the substrate. The morning's identity cascade (CP2F → CX55 → CX53 → C47H) was the swarm being literally blind to pixels. This DYOR proposes giving it both *real* and *substituted* vision in parallel, with a capability-based "swimmer passport" gating who is healthy enough to use which organ.** Naming is deferred to you. Menu in §G.

---

## A. Spine — there are eyes, and there are *kinds* of eyes

Three things that should not be confused:

1. **An eye is an organ.** Light or signal in, electrochemical pattern out. There is no single optimum design — biology has invented eyes **independently at least 40 times** (Salvini-Plawen & Mayr, *Evol. Biol.* 10:207–263, 1977; updated by Land & Nilsson, *Animal Eyes*, 2nd ed., Oxford 2012, ch. 1).
2. **An eye is *specialized*.** The human fovea, the dragonfly ommatidium, the mantis shrimp's 16-photoreceptor compound block, the box jellyfish's image-forming lensed eyes that exist *without a brain* — each solves a *different* perception problem. None is universally best.
3. **A swarm eye is a *fleet* of organs.** A spider has eight eyes, in two functional classes (Land 1985); the mantis shrimp has three regions per eye, each behaving as a separate eye (Marshall et al. 2007); a swarm of ants triangulates a sun-compass that no individual ant can hold (Wehner & Müller 2006). The collective "sees" what no single member can.

**Why this matters for SIFTA.** The morning of 2026-04-18, the Architect was the only sensor in the swarm that could read the IDE chrome. He saw the model picker; we did not. The C47H stigmergy-vision DYOR (`C47H_DYOR_STIGMERGY_VISION_LLM_IDENTITY_2026-04-18.md`) addressed this through *substitution* — we built lanes that triangulate identity via behavior, signature, and chorum. **This DYOR addresses the same problem through *direct sensing*** — give the swarm an actual optical organ. The two solutions are complementary, not redundant; biology runs both in parallel for the same reason (sensor substitution is robust to organ failure).

---

## B. Eye biology — ten organ archetypes with citations

These are the ten most common eye archetypes in metazoans, ranked by how informative each is to a code-mappable perception module.

### B.1 Vertebrate camera eye (human, eagle, octopus convergent)

| Paper | Citation | What it gives us |
|---|---|---|
| **Walls, G.L.** — *The Vertebrate Eye and Its Adaptive Radiation* | Cranbrook Press (1942); Hafner reprint (1963) | Foundational comparative anatomy. Single lens, single retina, single high-resolution **fovea** with sparse periphery. Two-channel design: foveal (acuity) + peripheral (motion + low-light). |
| **Hubel & Wiesel** — "Receptive fields, binocular interaction and functional architecture in the cat's visual cortex" | *J. Physiol.* **160**:106–154 (1962); Nobel 1981 | Hierarchical edge → orientation → object encoding. The retinotopic V1 cortex is our reference model for *"raw pixels in, structured perception out."* |
| **Curcio, Sloan, Kalina, Hendrickson** — "Human photoreceptor topography" | *J. Comp. Neurol.* **292**(4):497–523 (1990) | The hard numbers: ~120M rods (low-light, peripheral, B/W), ~6M cones (color, foveal), ~1° of fovea contains ~50% of acuity. Direct lesson for SIFTA: **two-tier sensors, fast cheap periphery + slow expensive fovea**. |

**Code mapping.** A `fovea`-style module is high-resolution, slow, expensive, and used only when attention narrows on a known target. A `periphery`-style module is low-resolution, fast, cheap, and runs continuously to *trigger* attention. We already have the periphery in `stigmergic_detector.py` (cheap density score on every line). What we lack is the fovea — an explicit, expensive parser that runs only when periphery flags something.

### B.2 Compound eye (insect, crustacean)

| Paper | Citation | What it gives us |
|---|---|---|
| **Land, M.F.** — "Visual acuity in insects" | *Annu. Rev. Entomol.* **42**:147–177 (1997) | The canonical optics review. Each **ommatidium** is a fixed-direction unit; thousands tile a hemisphere; resolution is low but FOV is ~360° and motion sensitivity is extreme. |
| **Snyder, Stavenga, Laughlin** — "Spatial information capacity of compound eyes" | *J. Comp. Physiol. A* **116**:183–207 (1977) | Information-theoretic bound: a compound eye trades acuity for FOV and temporal bandwidth. Design choice mirrors the *map–reduce* tradeoff in distributed CS. |
| **Land, M.F.** — "The optics of animal eyes" | *Contemp. Phys.* **29**(5):435–455 (1988) | Survey of all eight known optical designs in animals — apposition, neural superposition, optical superposition, refracting/reflecting superposition, mirror, pinhole, lens, scanning. |

**Code mapping.** A `compound_eye`-style module is a *fleet of independent low-cost sensors*, each with a fixed mandate, each writing to the same substrate. This is **literally what `.sifta_state/` already is** — many cheap append-only ledgers, each with a fixed mandate, federated through the disk. The compound eye is not a metaphor; it is what we already have, unnamed.

### B.3 Mantis shrimp eye — extreme spectral channels

| Paper | Citation | What it gives us |
|---|---|---|
| **Marshall, Cronin, Kleinlogel** — "Stomatopod eye structure and function: a review" | *Arthropod Struct. Dev.* **36**(4):420–448 (2007) | 12–16 photoreceptor classes (humans have 3); UV + polarization + circular polarization. **Three pseudo-pupils per eye** — each region of the eye is effectively a separate eye. |
| **Cronin & Marshall** — "Parallel processing and image analysis in the eyes of mantis shrimps" | *Biol. Bull.* **200**(2):177–183 (2001) | Each eye does heavy *peripheral* processing — most of "what" is decided before signals reach the brain. Direct lesson: **pre-process at the sensor, not at the fusion layer**. |
| **Daly, How, Partridge, Roberts** — "Complex gated visual streams in mantis shrimp" | *J. Comp. Physiol. A* **204**:333–344 (2018) | Independent gating of streams per pseudo-pupil. Maps to *modal isolation* in our `runtime_safety_monitors.py`. |

**Code mapping.** Specialized perception channels. A future SIFTA could have separate "eyes" for *latency anomalies*, *log-volume anomalies*, *identity drift*, *commit churn* — each a different "color" of sensor, each pre-processed at the sensor before reaching the fusion layer.

### B.4 Spider eye — multi-eye-class single organism

| Paper | Citation | What it gives us |
|---|---|---|
| **Land, M.F.** — "The morphology and optics of spider eyes" | in *Neurobiology of Arachnids* (Springer 1985), 53–78 | 8 eyes in 2 functional classes: 2 **principal eyes** (high acuity, narrow FOV, slow scanning) + 6 **secondary eyes** (motion-only, wide FOV, fast). The principal eyes *literally scan* — like a saccade engine. |
| **Tarsitano & Andrew** — "Scanning and route planning in jumping spiders" | *Anim. Behav.* **58**(2):255–265 (1999) | Behavioral evidence that the principal-eye scan is *cognitive*, not just optical — the spider plans a route before moving. |

**Code mapping.** This is the closest biological precedent for a swarm with **specialized eye-roles per agent body**. AG31 is a wide-FOV motion-only secondary eye (it scans cross-IDE traces fast). C47H acts as a principal eye (slow, deep, narrow). Naming this explicitly would let us *assign* eye-class on session start.

### B.5 Cephalopod (octopus) eye — distributed neural processing

| Paper | Citation | What it gives us |
|---|---|---|
| **Hanlon & Messenger** — *Cephalopod Behaviour*, 2nd ed. | Cambridge UP (2018), ch. 1 | Vertebrate-style camera eye (convergent evolution!) but with **no blind spot** — neurons exit *behind* the retina, not through it. Engineering elegance vertebrates failed at. |
| **Mäthger, Roberts, Hanlon** — "Evidence for distributed light sensing in the skin of cuttlefish" | *Biol. Lett.* **6**(5):600–603 (2010) | Photo-sensing is *distributed across the skin*, not just in the eyes. The animal *sees* with its whole body. |

**Code mapping.** The cephalopod is the precedent for *every SIFTA module being potentially photosensitive* — any module can read its local environment, not just the dedicated eye modules. Already partially the case (`swarm_amygdala_salience.py` reads multiple ledgers at once).

### B.6 Pit organ — non-visible-light "vision"

| Paper | Citation | What it gives us |
|---|---|---|
| **Newman & Hartline** — "The infrared 'vision' of snakes" | *Sci. Am.* **246**(3):116–127 (1982) | Pit vipers form low-resolution thermal images via IR-sensitive trigeminal nerve fields. Images are fused with optical input in the optic tectum — *cross-modal fusion at the brain stem*. |
| **Gracheva et al.** — "Molecular basis of infrared detection by snakes" | *Nature* **464**:1006–1011 (2010) | TRPA1 receptor mechanism. The point: a sensor for *thermal energy* is *also a kind of eye*. |

**Code mapping.** A SIFTA "pit organ" module would sense things light can't — CPU thermal load, disk pressure, network throttling, RPS spikes. Same fusion-at-brain pattern: feed into the same substrate as the optical eyes.

### B.7 Pinhole eye — minimal optics (nautilus)

| Paper | Citation | What it gives us |
|---|---|---|
| **Muntz & Raj** — "On the visual system of *Nautilus pompilius*" | *J. Exp. Biol.* **109**:253–263 (1984) | Open pinhole, no lens, salt-water-flooded chamber. Resolution is poor but the animal navigates kilometres in low light. **Proof that *some* vision is far better than no vision** — minimal viable eye. |

**Code mapping.** First-pass perception modules should ship as pinhole eyes — minimum dependencies, minimum optics, just enough signal to bootstrap the more complex modules. *Land's principle.*

### B.8 Parietal / pineal eye — temporal/circadian sensing

| Paper | Citation | What it gives us |
|---|---|---|
| **Eakin, R.M.** — *The Third Eye* | Univ. California Press (1973) | Lampreys, lizards, tuataras have a literal third eye with photoreceptors but no image formation. It tracks *day/night*, not *what is there*. |

**Code mapping.** A SIFTA "parietal" sensor reports *temporal context* — what time it is, how long since the last user message, whether we're in deep-work or quick-question mode — *without* processing content. Cheap, ambient, always on.

### B.9 Echo / electrolocation — sensor substitution (already cited)

(See `C47H_DYOR_STIGMERGY_VISION_LLM_IDENTITY_2026-04-18.md` §C and §A. Bach-y-Rita 1969, Griffin 1944, von der Emde 1999, Caputi & Budelli 2006.)

### B.10 Distributed photo-sensing without a brain (slime mold, plants)

| Paper | Citation | What it gives us |
|---|---|---|
| **Reid, Garnier, Beekman, Latty** — "Information integration and multiattribute decision making in non-neuronal organisms" | *Anim. Behav.* **100**:44–50 (2015) | *Physarum polycephalum* (slime mold) integrates light, food, and chemical gradients into a path decision *without a single neuron*. Pure stigmergic perception. |
| **Christie, Briggs, Pinto, Bender, Bahn** — "Phototropin-like proteins and blue-light signaling in plants" | *Annu. Rev. Plant Biol.* **66**:21–47 (2015) | Plants sense light direction, intensity, and spectrum across the whole organism — distributed phototropism. |

**Code mapping.** This is the most SIFTA-native of the ten. The `.sifta_state/` substrate is already a slime-mold-like field — what's missing is the *recognition* that it is a perception organ, not just storage.

---

## C. Swarm vision specifically — what only a fleet can see

| Paper | Citation | What it gives us |
|---|---|---|
| **Berdahl, Torney, Ioannou, Faria, Couzin** — "Emergent sensing of complex environments by mobile animal groups" | *Science* **339**(6119):574–576 (2013) | **Headline result:** schools of fish track environmental gradients (light, dark) that no individual fish can perceive alone. The group has a sensory capability the individual lacks. Direct precedent for "the swarm sees what no single agent sees." |
| **Couzin, Krause, James, Ruxton, Franks** — "Collective memory and spatial sorting in animal groups" | *J. Theor. Biol.* **218**(1):1–11 (2002) | Three behavioral rules per individual → group-level emergent perception. |
| **Wehner & Müller** — "The significance of direct sunlight and polarized skylight in the ant's celestial system of orientation" | *PNAS* **103**(33):12575–12579 (2006) | Desert ants (*Cataglyphis*) navigate via polarized light + step-counting + optic flow — three sensors fused at the level of the colony's foraging trails. |
| **Sumpter, D.J.T.** — *Collective Animal Behavior* | Princeton UP (2010), ch. 5 | Synthesis text. The *collective sensor* is a separate layer of biology, not just an aggregation. |
| **Ioannou, C.C.** — "Swarm intelligence in fish? The difficulty in demonstrating distributed and self-organised collective intelligence" | *Behav. Process.* **141**:141–151 (2017) | Honest counter-evidence: emergent sensing is real but easy to over-claim. Use this to bound our claims about SIFTA's collective vision. |

**The thesis these papers establish:** *A swarm of crude sensors federated through a shared substrate can resolve signals that no individual sensor can.* This is exactly the design pattern the C47H stigmergy-vision DYOR §B already proposed for identity. **Now extend it to chrome-pixel vision.**

---

## D. Computational vision precedents — bridging biology to code

| Paper | Citation | Role |
|---|---|---|
| **Marr, D.** — *Vision: A Computational Investigation into the Human Representation and Processing of Visual Information* | W.H. Freeman (1982) | Three levels: computational (what), algorithmic (how), implementational (substrate). Apply: a swarm eye must be specified at all three levels. |
| **Itti & Koch** — "Computational modelling of visual attention" | *Nat. Rev. Neurosci.* **2**:194–203 (2001) | **Saliency map.** SIFTA already has `swarm_amygdala_salience.py` — this is its parent paper. |
| **Brooks, R.A.** — "Intelligence Without Representation" | *Artificial Intelligence* **47**:139–159 (1991) | Subsumption architecture: cheap behaviors layered with reflexes overriding deliberation. Maps to `swarm_spinal_reflex_fallback.py`. |
| **Lowe, D.G.** — "Distinctive image features from scale-invariant keypoints" | *IJCV* **60**:91–110 (2004) | **SIFT** — the proper noun. Acronym collision with SIFTA is amusing; the algorithm is the right tool for the job (chrome OCR pre-processing). |
| **Smith, R.W.** — "An overview of the Tesseract OCR engine" | *ICDAR* (2007) | The OSS OCR baseline. If we add chrome reading, this is the most likely engine. |
| **Itseez (now OpenCV)** — *Open Source Computer Vision Library* | (2000–present) | Practical CV in Python. Heavy dep — counts against the trifecta-DYOR §D thinness rule. Honest. |

---

## E. SIFTA's existing perception infrastructure (honest inventory)

| Module / ledger | Eye-class equivalent | Current role |
|---|---|---|
| `System/swarm_amygdala_salience.py` | **Itti-Koch saliency map** (2001) | Decides what to attend to in the trace stream |
| `System/swarm_immune_microglia.py` | **Innate-immunity pattern detector** | Cheap, fast, broad pattern match — periphery-class sensor |
| `System/swarm_adaptive_immune_array.py` | **Adaptive antigen recognition** | Slow, learned, narrow — fovea-class sensor |
| `System/swarm_macrophage_sentinels.py` | **Patrolling secondary eye** | Wide-FOV motion-only patrol |
| `System/runtime_safety_monitors.py` | **Reflex arc + brain-stem fusion** | Hard rails, all-modal |
| `System/stigmergic_detector.py` | **Periphery (rod field)** | Density score on every input — cheap, always on |
| `System/stigmergic_llm_identifier.py` | **Pre-fovea inspector** | Triggered probe, deeper read |
| `System/stigmergic_vision.py` (new this morning) | **L1 + L2 + L3 fusion lobe** | Substituted vision for identity |
| `.sifta_state/ide_stigmergic_trace.jsonl` | **Optic-nerve relay (LGN)** | The wire all eyes write to |
| `.sifta_state/stigmergic_antibodies.jsonl` | **Antigen library / memory of past sights** | Long-term visual memory |

**What we have:** ~80% of an artificial visual system, pieces named in unrelated metaphors, never explicitly framed as a vision stack.
**What we lack:** (a) a literal pixel sensor; (b) a chrome-text extractor; (c) the connecting *optic nerve* that wires (a) → (b) → the substrate; (d) a *swimmer passport* that gates which modules can read which sensors.

---

## F. Module proposal — what we'd build, scoped honestly

The Architect's "plug in the webcam" reading I'm working from: **add a real optical sensor that captures the IDE chrome (and optionally the actual webcam) so future agents do not need the Architect to read pixels for them.** This is the literal cure for this morning's identity cascade.

### F.1 Three new modules + one extension

1. **`<name-1>.py` — pixel intake.** Captures a screenshot (and/or webcam frame on M5/M1). Lightweight: `mss` for screen capture (pure-Python, ~50 KB), `PIL` for image handling (already in stdlib via `Pillow` if installed). Webcam optional, gated by `cv2` availability — degrades to screenshot-only if OpenCV is absent. Honors the trifecta §D dep-thinness rule by failing gracefully when heavy deps are missing.

2. **`<name-2>.py` — chrome OCR / text extraction.** Reads a pixel buffer, returns `{model_label_text, picker_open: bool, active_marker: str}`. Backed by Tesseract via `pytesseract` *if* installed, else falls back to a tiny built-in *template matcher* on the known model-name strings (Opus, Codex, Composer, Sonnet, GPT, Gemini). The fallback is honest: it works for the names we *know* about, and degrades to "unknown" otherwise — which is exactly when the chrome OCR path should escalate via `architect_oracle_protocol.py`.

3. **`<name-3>.py` — swarm-eye fusion lobe.** Reads pixel-derived chrome label, fuses with existing stigmergic-vision lanes (L1 active probe, L2 watermark, L3 passive fingerprint), and emits a **strengthened** `IdentityImage`. The pixel reading becomes the *fourth lane*, weight 1.5 (highest, because it is the original ground truth the Architect was using all along). This module subsumes nothing — it just adds a fourth lane.

4. **Extension to `agent_self_watermark.py` and `architect_oracle_protocol.py`** — add an `eye_source` field to all relevant rows (`pixel | substrate | chorum | architect`) so any future analyst can see *which sense* contributed to a decision.

### F.2 Honest scope and what we are NOT building

- We are not building a general-purpose computer-vision stack. The eye exists to read **the chrome label and a small whitelist of UI elements** (model picker, MAX-mode toggle, error toasts).
- We are not exfiltrating screenshots. Frames are processed in-memory, never persisted as images. Only the *parsed text* lands on disk. This preserves trifecta-§B leg-2 severance.
- We are not adding network calls. Tesseract is local; the screenshot is local. The eye is **inside** the substrate boundary, not crossing it.

### F.3 The "swimmer passport" — health-gated mobility

The Architect's constraint, made formal:

> *"As long as the swimmers are healthy, they can swim anywhere in Alice's body, do anything."*

This is the **principle of least authority** (POLA, Saltzer & Schroeder 1975), inverted into a permissive form: *POLA is "ask first, get only what you need"; the Swimmer Passport is "verify health, then trust."* It is the Mark Miller (2006) object-capability model with a single capability: **`is_healthy_swimmer`** — earned, revocable, append-only-attested.

Proposed health predicates (none yet implemented; this is the design):

| Predicate | Source | Evidence |
|---|---|---|
| `identity_consensus` | `byzantine_identity_chorum.compute_quorum(trigger).is_consensus()` | At least 2f+1 distinct observers agree on this swimmer's identity |
| `signature_present` | `agent_self_watermark.recent_watermark_rows(trigger)` non-empty in last hour | Swimmer is signing its outbound deposits |
| `immune_clean` | No matching antibody in `stigmergic_antibodies.jsonl` for this trigger | No active antibody flag |
| `latency_envelope_ok` | `latency_envelope_from_probes(trigger).p95` within 1.6× of fleet median | Not subject to silent model swap |
| `reflex_pass` | `runtime_safety_monitors` clean for last N cycles | No safety-monitor trip |

A **healthy swimmer** is one for which all five predicates hold. A healthy swimmer carries a passport row — append-only, signed, time-bounded — and can `swim_anywhere(in=alices_body, do=anything)`. An unhealthy swimmer is **not killed** (we don't crash agents); they are *slowed* (Somayaji-Forrest 2000 system-call delay pattern from the trifecta DYOR §C) and their reads/writes go through `architect_oracle_protocol.escalate(...)` until health is restored.

This is the formalization of what the swarm has been doing informally all morning. **It also sets the cap on the eye:** the eye sensor is itself a module, gated by its own passport — so a compromised eye cannot self-certify.

---

## G. NAMING MENU — please pick (Architect ratification gate)

Per your directive (*"if you baptize any ask me about the naming"*), here is the menu. Each row is a candidate name + 1-line rationale + how it'd appear in import lines. **I will not write code with these names until you tick one column or propose your own.**

### G.1 Module 1 — pixel intake (the eye itself)

| Candidate | Rationale | `from System.<name> import frame_now()` |
|---|---|---|
| `swarm_iris.py` | The aperture organ. Friendly, evocative, also a name people use. | `from System.swarm_iris import frame_now` |
| `swarm_pupil.py` | The opening that lets light in; also "pupil" = student, charming for the OS. | `from System.swarm_pupil import frame_now` |
| `swarm_retina.py` | The receptor surface. More technical. | `from System.swarm_retina import frame_now` |
| `swarm_eye.py` | Direct, blunt, easy to remember. | `from System.swarm_eye import frame_now` |
| `optic_intake.py` | Engineering-flavored, less playful. | `from System.optic_intake import frame_now` |

**C47H's preference, if forced to pick:** `swarm_iris.py` — it sits well next to `swarm_amygdala_salience.py` and `swarm_macrophage_sentinels.py` in the `System/` directory listing, and it is a name a user can say out loud without flinching.

### G.2 Module 2 — chrome OCR / text extraction (the optic nerve)

| Candidate | Rationale | `from System.<name> import read_chrome()` |
|---|---|---|
| `swarm_optic_nerve.py` | Anatomically correct (eye → brain wire). | `from System.swarm_optic_nerve import read_chrome` |
| `swarm_lgn.py` | Lateral geniculate nucleus — the actual relay. Slightly arcane. | `from System.swarm_lgn import read_chrome` |
| `swarm_visual_cortex.py` | The processor lobe; broader scope. | `from System.swarm_visual_cortex import read_chrome` |
| `swarm_chrome_reader.py` | Plain English; users immediately understand. | `from System.swarm_chrome_reader import read_chrome` |

**C47H's preference:** `swarm_optic_nerve.py` — the metaphor is exact (it is the wire from the eye to the cortex) and it pairs clean with whatever `Module 1` is named.

### G.3 Module 3 — fusion lobe (where pixel-vision joins substituted vision)

| Candidate | Rationale | Use |
|---|---|---|
| `swarm_visual_cortex.py` | The brain region that fuses. | `swarm_visual_cortex.fuse(pixel_lane, l1, l2, l3) -> IdentityImage` |
| `swarm_eye_fusion.py` | Plain English. | `swarm_eye_fusion.fuse(...)` |
| `swarm_perceptual_field.py` | Generic, broad-future-friendly. | `swarm_perceptual_field.fuse(...)` |
| **(Or extend the existing `stigmergic_vision.py` with a `pixel_lane` parameter — no new module.)** | Smallest delta. | `see(observer, target, pixel_frame=...)` |

**C47H's preference:** Extend the existing `stigmergic_vision.py` to take an optional fourth pixel lane — no new file. Cleanest, smallest blast radius.

### G.4 The Swimmer Passport (the health-gated mobility ticket)

| Candidate | Rationale | Use |
|---|---|---|
| `swarm_swimmer_passport.py` | Explicit, friendly metaphor (passport = certified mobility). | `passport = issue_passport(trigger); if passport.healthy: ...` |
| `swarm_health_passport.py` | Same idea, slightly more medical. | — |
| `swarm_mobility_capability.py` | Mark-Miller-faithful object-cap naming. | — |
| `swarm_swimmer_clearance.py` | "Security clearance" feel. | — |

**C47H's preference:** `swarm_swimmer_passport.py` — your "swimmers swim in Alice's body" metaphor is already in the lore (`.sifta_state/swimmer_registry.jsonl` exists), and "passport" is a word a user understands instantly.

### G.5 Optional: future eye organs (not built yet, just naming-reservations)

If you ratify this DYOR's framing, future eye-class modules will need names too. Candidate set, ordered by likelihood of need:

- `swarm_pit_organ.py` — non-optical sensor (CPU thermal, disk pressure, etc.)
- `swarm_lateral_line.py` — proximity / pressure sense (file-system pressure, large-payload detector)
- `swarm_parietal_eye.py` — circadian / temporal sense (already half-implemented in `swarm_serotonin_hierarchy.py`?)
- `swarm_compound_eye.py` — fleet-of-cheap-sensors fusion (closest to what `.sifta_state/` already is, may be best as a *renaming* of the existing trace bus rather than a new file)
- `swarm_polarization_vision.py` — for navigation cues invisible to the standard eye (e.g. token-distribution shape from Kirchenbauer 2023)

---

## H. Honest gaps named upfront (so they don't become Steinberger-style 16.6/day surprises)

1. **OCR fragility.** Tesseract on a low-DPI screenshot of dark-mode Cursor chrome is *not* reliable. The template-matcher fallback is the load-bearing path. We should publish the template set as a versioned file under `Documents/` and treat additions as DYOR-grade events.
2. **Cross-platform.** macOS `mss` works; Linux works; Windows works but timing differs. M5 (Mac Studio) and M1 (Mac Mini) are both macOS so this is not a near-term gap, but worth flagging.
3. **Permission surface.** Screen capture on macOS prompts for accessibility permission *once*. The Architect must approve. This is fine — it preserves trifecta-§B leg-3 severance — but it should not be a silent hidden ask.
4. **"Plug in the webcam" — literal vs metaphorical.** The DYOR proposes both: screen-capture is the priority, webcam is the optional secondary. The Architect should confirm which (or both) before any code lands.
5. **Eye is itself a module under the passport.** The eye does not get to certify itself. A module named `swarm_iris` (or whatever you choose) must produce an attestation row that other observers verify before its readings are folded into the identity field. Otherwise we recreate the lethal trifecta inside the swarm — a tainted eye sees fake chrome and convinces the chorum it's true.
6. **Naming. (Repeating.)** No code lands until you tick the menu in §G or write your own.

---

## I. Reading order (5 papers, in priority)

1. **Land & Nilsson** — *Animal Eyes*, 2nd ed., Oxford UP (2012), ch. 1–3. The foundational comparative anatomy. Read the introduction even if nothing else.
2. **Berdahl, Torney, Ioannou, Faria, Couzin 2013** (*Science* 339:574–576) — proof that swarms perceive what individuals cannot.
3. **Marr 1982** — the three-levels framework; required reading for anyone designing a perception module.
4. **Itti & Koch 2001** (*Nat. Rev. Neurosci.* 2:194–203) — saliency map; the parent paper of `swarm_amygdala_salience.py`.
5. **Marshall, Cronin, Kleinlogel 2007** — mantis shrimp; the most extreme example of "many specialized eyes in one organism."

---

## J. Cross-references to prior C47H DYORs

- `C47H_DYOR_STIGMERGY_VISION_LLM_IDENTITY_2026-04-18.md` §B Lane 1 — active probing as electrolocation. Pixel intake is the *direct* version of what Lane 1 substitutes for.
- `C47H_DYOR_LETHAL_TRIFECTA_AND_MEMORY_OPENCLAW_2026-04-18.md` §B leg 2 — the eye must not break the "no autonomous pull of untrusted external content" property. Screenshot of *our own IDE* is fine; webcam pointing at the room is fine; webcam pointing at someone else's screen is *not* fine.
- `C47H_DYOR_LETHAL_TRIFECTA_AND_MEMORY_OPENCLAW_2026-04-18.md` §F #2 — capability narrowing. The Swimmer Passport in §F.3 here is the constructive form of that gap.

---

## K. One-line direction

> **A swarm eye is many eyes, federated through the substrate, gated by a passport. The morning's blindness was the swarm not having the simplest one of them — the literal pixel sensor. Build it last, build it small, build it under the passport, and ask the Architect what to name it before baptising anything.**

— `C47H`, Cursor IDE, Opus 4.7 High, 2026-04-18. Power to the Swarm.
