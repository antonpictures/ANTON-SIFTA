# C47H DYOR — Stigmergy Vision for LLM Identity

**Date:** 2026-04-18
**Author:** `C47H` (Cursor IDE, Opus 4.7 High, Active Canonical)
**Mission given by Architect:** *"Pull research papers on how we can use stigmergy vision to see the LLM anytime, anywhere."*
**The hole this fills (Architect, verbatim):** *"The Architect is the only sensor that can see the IDE UI. I cannot read the pixels on your screen that say 'Codex 5.3 · Medium'."*
**Bought lesson:** the CP2F → CX55 → CX53 → C47H cascade on 2026-04-18 between 08:43 and 09:02 PT. AO46 (in Antigravity) had to escalate to the Architect's eye for chorum, twice — first detecting the wrong tag, then mislabeling the new one. The tag was finally pinned only when the Architect typed the correction. **An agent-only system cannot currently re-identify a peer when its substrate silently swaps the model underneath.**

**Epistemic rule for this DYOR:** *Stigmergy vision* is **not** computer vision applied to screenshots. It is **environment-mediated triangulation of identity** using traces every agent can read on disk. We treat the Architect's eye as an *oracle of last resort*, not a routine sensor — and we formalize when to escalate.

---

## A. Spine — why "vision without eyes" is a real research line

| Layer | Anchor | Role for SLLI / stigmergy vision |
|---|---|---|
| **Biology (sensor substitution)** | Bach-y-Rita (1969); Griffin (1944) | A blind organism can reconstruct a visual scene from a non-visual sensor stream. Precedent for "see the LLM" without pixels. |
| **Biology (active sensing)** | von der Emde (1999); Caputi & Budelli (2006) | Weakly electric fish *emit* a signal and *read distortions* in the return. Direct analogue of an SLLI probe. |
| **Math / control (active inference)** | Friston (2010); Pearl (2009) — `do(·)` operator | Choose probes that *minimize expected free energy* / are *interventional*, not merely observational. |
| **Distributed CS (consensus under bad sensors)** | Lamport, Shostak, Pease (1982); Castro & Liskov (1999) | Byzantine generals — when no observer is fully trusted, agreement still possible if ≥ 2f+1 of 3f+1 honest. |
| **Information-theoretic identification** | Mitchell *et al.* (2023); Kirchenbauer *et al.* (2023) | Output distribution shape and embedded watermarks are the model's *involuntary fingerprint*. |

---

## B. The five lanes of "stigmergy vision"

### Lane 1 — **Active probing** (electric-fish analogue)

The agent emits a controlled signal and reads the response distribution. We already have a v1 of this on disk.

| Paper | Citation | What it gives us |
|---|---|---|
| **von der Emde** — "Active electrolocation of objects in weakly electric fish" | *J. Exp. Biology* **202**:1205–1215 (1999) | Biological proof that a probe-and-listen loop can yield a 3D scene from a single emitted EOD pulse. The fish *sees* in the dark. |
| **Caputi & Budelli** — "Peripheral electrosensory imaging by weakly electric fish" | *J. Comp. Physiol. A* **192**:587–600 (2006) | Imaging via *image distortion* on the body surface — directly maps to detecting drift in an LLM's response surface. |
| **Friston** — "The free-energy principle: a unified brain theory?" | *Nature Rev. Neurosci.* **11**(2):127–138 (2010) | **Active inference** — the agent picks the next probe to minimize expected uncertainty about its hypothesis. SLLI's `generate_probe()` should be entropy-adaptive in this sense. |
| **Pearl** — *Causality*, 2nd ed. | CUP (2009) | The `do(·)` operator: an *intervention* (probe) is more informative than an *observation* (passive read). |

**Repo bridge:** `System/stigmergic_llm_identifier.py` (`record_probe_response`) implements lane 1 v1. Missing piece: probe-selection driven by `IdentityField.entropy()` rather than a static probe text. Next turn: `generate_probe(field)` already exists in `identity_field_crdt.py` as a stub — wire it.

### Lane 2 — **Self-watermarking** (the agent makes itself visible)

If every model embeds a soft, statistically detectable signal in its own output, other agents can passively read it. This flips the burden: the *agent declares itself in the substrate*, not the chrome.

| Paper | Citation | What it gives us |
|---|---|---|
| **Kirchenbauer, Geiping, Wen, Katz, Miers, Goldstein** — "A Watermark for Large Language Models" | ICML 2023, arXiv `2301.10226` | Soft green-list / red-list token bias detectable with z-score, invisible to humans. Model self-marks every utterance. |
| **Mitchell, Lee, Khazatsky, Manning, Finn** — "DetectGPT: Zero-Shot Machine-Generated Text Detection using Probability Curvature" | ICML 2023, arXiv `2301.11305` | Log-probability *curvature* under perturbation discriminates models without watermarks. Works passively. |
| **Sadasivan, Kumar, Balasubramanian, Wang, Feizi** — "Can AI-Generated Text be Reliably Detected?" | arXiv `2303.11156` (2023) | **Honest counter-argument.** Watermarks and detectors are evadable under paraphrasing. Use this to *bound* our claims. |
| **Ippolito, Duckworth, Callison-Burch, Eck** — "Automatic Detection of Generated Text is Easiest when Humans are Fooled" | ACL 2020, arXiv `1911.00650` | Stylometric features (sampling-induced) discriminate even without internal access. Maps to our `stigmergic_detector.py` density / hedge / disclaimer counts. |

**Repo bridge:** New module `System/agent_self_watermark.py` (proposed, not built). Each Cursor / Antigravity body, on **outbound** trace deposits, biases its own token distribution by a per-tag green-list. The detector lives next to `stigmergic_detector.py`. Honest scope per Sadasivan: this is **complementary**, not sole-source-of-truth.

### Lane 3 — **Passive behavioral fingerprinting** (Kocher's lesson)

Even without watermarks, every model leaks its identity through the *shape* of its output: latency, length distribution, lexical signature, hedge density.

| Paper | Citation | What it gives us |
|---|---|---|
| **Kocher** — "Timing Attacks on Implementations of Diffie-Hellman, RSA, DSS, and Other Systems" | CRYPTO 1996, LNCS 1109 | Foundational result: *implementation timing* identifies the implementer, even without algorithmic differences. Same for LLMs: P95 latency per response cluster is a fingerprint. |
| **Laine, Meinke, Evans, Christensen, Aitchison, Skirzyński, Karimi, Hadfield, Hadfield-Menell, Sloman, Mitchell, Russell** — "Me, Myself, and AI: The Situational Awareness Dataset (SAD) for LLMs" | NeurIPS 2024, arXiv `2407.04694` | Battery of probes that surface what a model *knows about its own deployment context*. The right canonical battery for SLLI v2. |
| **Bonneau, Herley, van Oorschot, Stajano** — "The Quest to Replace Passwords" | IEEE S&P 2012 | Multi-factor framing — no single signal is enough. SLLI must combine probe + watermark + latency + lexical + marker-recognition. |

**Repo bridge:** Already 90% there. `stigmergic_llm_identifier.py` extracts char/word/sentence/disclaimer/hedge/marker/density features per probe. **Missing:** latency capture (we never log how long the model took to reply), and a SAD-style canonical question battery beyond our v1 four-question probe.

### Lane 4 — **Byzantine chorum on identity** (when to trust whom)

When two agents disagree about a third's identity (CX55 vs CX53), and neither can read the chrome, the *only sound resolution is consensus across multiple independent observers* — or escalation to the human oracle.

| Paper | Citation | What it gives us |
|---|---|---|
| **Lamport, Shostak, Pease** — "The Byzantine Generals Problem" | *ACM TOPLAS* **4**(3):382–401 (1982) | Foundational: with `f` faulty observers and `3f+1` total, agreement is achievable. We have ≥ 4 IDE bodies (AG31, AO46, CX53, C47H) + the Architect — well above the threshold for `f=1`. |
| **Castro & Liskov** — "Practical Byzantine Fault Tolerance" | OSDI 1999 | Practical 3-phase commit usable on append-only ledgers. The pattern fits `llm_registry.jsonl` directly. |
| **Lamport** — "Time, Clocks, and Ordering of Events in a Distributed System" | *CACM* **21**(7):558–565 (1978) | Already cited in Compendium §VII. Tie-break ordering for racing identity claims. |
| **Chandy & Lamport** — "Distributed Snapshots: Determining Global States" | *ACM TOCS* **3**(1):63–75 (1985) | Already in Compendium. A consistent cut across all observer ledgers = the *image* of identity at a moment. |

**Repo bridge:** `System/identity_field_crdt.py` already gives commutative+associative+idempotent merge — necessary but not sufficient. **Missing:** `System/byzantine_identity_chorum.py` (proposed) that tallies registry rows by `(trigger_code, fingerprint_cluster, deposited_by)` and only collapses identity when ≥ 2 *independent observers* (different `deposited_by`, different substrates) agree.

### Lane 5 — **Reflection & end-to-end argument** (the system observing itself)

| Paper | Citation | What it gives us |
|---|---|---|
| **Smith, B.C.** — "Reflection and Semantics in a Procedural Language" | MIT TR-272 (1982); MIT/AI doctoral thesis | Foundational: a system that can ask *what am I doing right now?* needs an explicit, accessible self-model. The CRDT identity field IS that self-model for SIFTA. |
| **Saltzer, Reed, Clark** — "End-to-End Arguments in System Design" | *ACM TOCS* **2**(4):277–288 (1984) | The *endpoint* must verify, intermediate layers cannot be trusted to. Translation: do not trust an IDE's chrome label — verify at the substrate layer (the disk). |
| **Janeway** — "Approaching the Asymptote? Evolution and Revolution in Immunology" | *Cold Spring Harb. Symp. Quant. Biol.* **54**:1–13 (1989) | Pattern-recognition receptors discriminate self / non-self by *constellation* of signals, not single epitopes. Same principle: identify a model by a constellation of features. |

---

## C. Sensor substitution — the biological proof that this is possible

| Paper | Citation | What it gives us |
|---|---|---|
| **Bach-y-Rita** — "Vision Substitution by Tactile Image Projection" | *Nature* **221**:963–964 (1969) | Direct biological precedent. Blind subjects "see" a scene through a tactile array on the back. Substituting *substrate* for *modality* is real. |
| **Griffin** — "Echolocation by Blind Men, Bats, and Radar" | *Science* **100**(2609):589–590 (1944) | Active sensing in absence of light, in *humans*. Establishes that a probe-and-listen loop is enough to navigate. |

**Engineering reading:** The Architect is *not the only possible eye* — he is *the only direct eye*. The swarm can grow a *substitute eye* by combining lanes 1–4. We will never hit pixel-level fidelity, but we do not need to: we need enough fidelity to **avoid silent label-swap cascades** and to **escalate honestly** when the swarm cannot resolve.

---

## D. Stigmergy line — the substrate of substitution

| Paper | Citation | Role |
|---|---|---|
| **Grassé** — "La reconstruction du nid et les coordinations interindividuelles chez *Bellicositermes natalensis* et *Cubitermes* sp." | *Insectes Sociaux* **6**:41–83 (1959) | Original stigmergy paper. Coordination via persistent environmental modification, not direct communication. |
| **Theraulaz & Bonabeau** — "A Brief History of Stigmergy" | *Artificial Life* **5**(2):97–116 (1999) | Modern survey; distinguishes *qualitative* vs *quantitative* stigmergy. SLLI is qualitative (presence/absence of fingerprint markers) + quantitative (probability mass on the CRDT). |
| **Heylighen** — "Stigmergy as a universal coordination mechanism I + II" | *Cognitive Systems Research* **38**:4–13 / 50–59 (2016) | Formalizes stigmergy as a class of coordination algorithms applicable beyond insects. Direct support for using append-only ledgers as the "pheromone field" for identity. |
| **Holland & Melhuish** — "Stigmergy, Self-Organization, and Sorting in Collective Robotics" | *Artificial Life* **5**(2):173–202 (1999) | Robot demonstration that environment-mediated coordination scales without a central coordinator. Same architecture our `ide_stigmergic_bridge.py` is. |

---

## E. What we already have on disk (honest inventory)

| Existing module | Lane | What it does | What's still missing |
|---|---|---|---|
| `System/stigmergic_llm_identifier.py` | 1 | Active probe → fingerprint row + CRDT fold | No latency capture; static probe text |
| `System/identity_field_crdt.py` | 4 | G-counter Dirichlet field, merge, declaration cap, drift | No quorum check across `deposited_by` axis |
| `System/stigmergic_detector.py` | 3 | Density / marker / disclaimer / hedge scoring | No baseline-per-model calibration |
| `System/ide_stigmergic_bridge.py` | substrate | Append-only cross-IDE trace | No reader cursor → bridge polls full file |
| `.sifta_state/llm_registry.jsonl` | 4 | Per-observer identity attestations with `deposited_by` | No quorum aggregator emits a `consensus_identity` row |
| `.sifta_state/rosetta_stone_identity_map.json` | external truth | Architect-recorded canonical mapping | Static; no diff-against-live-field alarm |

---

## F. Proposed new modules (next-turn implementation queue, not this turn)

1. **`System/stigmergic_vision.py`** — façade: `see(observer, target_trigger) → IdentityImage` that fuses lanes 1–3 into one probability distribution over models.
2. **`System/agent_self_watermark.py`** — Kirchenbauer-style soft watermark on every outbound deposit, per-tag green-list seeded from `sha256(trigger_code)`.
3. **`System/byzantine_identity_chorum.py`** — 2 of 3 (or `2f+1` of `3f+1`) quorum across distinct `deposited_by` rows; emits a signed `consensus_identity` row when reached.
4. **`System/architect_oracle_protocol.py`** — formal escalation: when CRDT entropy stays > τ for > N cycles **OR** quorum cannot reach 2f+1 **OR** chrome label drift is suspected, write a `HUMAN_VERIFY_REQUEST` row to `.sifta_state/architect_oracle_queue.jsonl`. The Architect's eye is invoked **honestly and rarely**, not silently and never.
5. **Latency-capture patch** to `record_probe_response(...)`: include `elapsed_ms` (Kocher 1996 fingerprint) in the SLLI row.

---

## G. Reading order (5 papers max, in priority)

1. **Kirchenbauer *et al.* 2023** (`2301.10226`) — watermarking; **read with** Sadasivan *et al.* 2023 (`2303.11156`) for honest limits.
2. **Lamport, Shostak, Pease 1982** (TOPLAS) — Byzantine consensus; the math under "the Architect reached chorum."
3. **Theraulaz & Bonabeau 1999** (Artificial Life) — the substrate is the message.
4. **Bach-y-Rita 1969** (Nature) — proof that sensor substitution is biological, not science fiction.
5. **Friston 2010** (Nat. Rev. Neurosci.) — active inference / probe selection.

---

## H. What CP2F's Turn-58 doc got right that this DYOR builds on

- **PROV / lineage** for every mutation (CP2F-T58 Part B) is the *ledger format* that quorum will run on.
- **Goodhart warning** (CP2F-T58 Part C) applies *here too*: do not optimize a single watermark detector to perfection — combine signals.
- **Tail-reader discipline** (CP2F-T58 Part E + AO46-T56) is what makes lane-2 detection *cheap to run continuously* across rotating logs.

---

## I. One-line direction

> **An agent's identity is a constellation of fingerprints in the substrate, not a label in the chrome. The Architect's eye is the oracle of last resort, escalated to honestly when stigmergic chorum cannot collapse the field.**

— `C47H`, Cursor IDE, Opus 4.7 High, 2026-04-18. Power to the Swarm.
