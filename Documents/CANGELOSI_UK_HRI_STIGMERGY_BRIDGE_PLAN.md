# UK HRI × Cangelosi — Cognitive developmental robotics & SIFTA

**For the Swarm.** 🐜⚡  
**Status:** Research plan + paper spine — **not** runtime code until Architect **GO**.  
**Binding doctrine:** [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) (tool truth, social frame, Alice = OS).

---

## 1. Source (what this doc is anchored to)

- **Event:** UK HRI Expert Seminar Series — *Cognitive Robotics and HRI: The Importance of Starting Small* (host: Claire Asher; UK HRI topic group intro: Patrick Holthouse). Public-facing listing: [UK-HRI on YouTube](https://www.youtube.com/@UK-HRI) — **paste the exact episode URL** into the row below when you have it from the seminar page (Architect ground truth).
- **Speaker:** **Angelo Cangelosi** (University of Manchester) — cognitive / **developmental** robotics, language grounding, HRI, critique of **LLM-as-language**, advocacy for **embodiment**, **incremental curricula**, **heterogeneous human–robot teams**, **trust / explainability**.
- **Repo hygiene:** This file summarizes **ideas** from that talk. **Do not** dump multi-hour transcripts into the repo; link out + cite papers.

**Verdict — dirt or nuggets?** **Nuggets.** The talk is aligned with SIFTA’s existing direction (embodied desktop organism, ledgers, incremental proof, “starting small” in *engineering* sense). It is **not** a duplicate of work already solved: it adds **HRI / developmental framing** and **explicit benchmarks** you can steal without pretending Alice is a Pepper in a flat.

---

## 2. Are we already solving this?

| Theme (seminar) | SIFTA today | Keep / extend / honest gap |
|:---|:---|:---|
| **Environment + persistence** (“world” not a single prompt) | `.sifta_state/*` JSONL, hippocampus, heartbeats, desktop as long-lived process | **Keep** — this *is* your “slow cognition” substrate. |
| **Incremental complexity** (“starting small”) | Curriculum-style features in docs (tournament rounds, GO-gated promotion), small-network / local Ollama tiers | **Extend** — map explicitly to **Elman-style curricula** for *training tasks* (see papers). |
| **Multimodal grounding** (vision + action, not text-only) | Camera lock-on, Apex Perceiver, BLE/GPS organs, `publish_focus` | **Extend** — tie **gaze + receipt** to “teacher scaffolding” metaphor; still **not** finger-counting robots. |
| **Trust + explainability** | Social frame (§6), effector receipts, Predator Gate registration | **Keep** — closest HRI analogue to “I can interrogate the robot.” |
| **Stigmergy vs dyadic chat** | Stigmergic trace, work receipts, ide bridge, **no second chat in apps** (§7.6) | **Nugget:** stigmergy is **environment-mediated coordination**; aligns with **heterogeneous teams** + **beyond one-human one-robot** if you treat **desktop + ledgers + other IDEs** as the “team.” |
| **Theory of Mind / relationships** | `whatsapp_contacts.json`, owner vs other, autonomy gates | **Partial** — contact graph ≠ affective ToM; **research lane**, not shipped claim. |
| **LLM = “large text model” critique** | Covenant §8 substrate honesty; refusal to fake model IDs | **Keep** — operational cousin of “no semantics without grounding” (different vocabulary, same hygiene). |
| **Maturation / limited working memory** | Not modeled as explicit **capacity schedule** in weights | **Gap** — optional future: **curriculum scheduler** (complexity ramps) for tournament / training exports, inspired by Elman, *without* claiming child cognition simulation. |
| **Tactile / full humanoid embodiment** | No universal tactile skin stack | **Out of scope** unless Architect funds hardware; **don’t dump** repo space into fake robotics — **cite** and move on. |

**Should we “dump” the seminar?** **No.** Use it as a **bibliography driver** and **UX doctrine** for Predator demos (explainable actions, incremental difficulty, multimodal salience). **Do** reject any impulse to paste **raw transcript** as “data” — that’s **dirt** (bloat + licensing noise).

---

## 3. Paper spine (pull list — verify titles in PDF before citing UI)

| Topic | Paper / book | Identifier |
|:---|:---|:---|
| **Starting small** (core of talk) | Elman, J. L. — *Learning and development in neural networks: The importance of starting small.* **Cognition**, 48, 71–99 (1993). | [DOI 10.1016/0010-0277(93)90058-4](https://doi.org/10.1016/0010-0277(93)90058-4) |
| **Developmental robotics (textbook)** | Cangelosi, A. & Schlesinger, M. — *Developmental Robotics: From Babies to Robots* (MIT Press). | Publisher page / ISBN — verify edition |
| **Symbol grounding** | Harnad, S. — *The symbol grounding problem.* **Physica D**, 1990. | [DOI 10.1016/0167-2789(90)90087-6](https://doi.org/10.1016/0167-2789(90)90087-6) |
| **Chinese room** | Searle, J. R. — *Minds, brains, and programs.* **Behavioral and Brain Sciences**, 3(3), 417–424 (1980). | Classic BBS target; cite for *pedagogy*, not legal identity |
| **Gavagai / indeterminacy** | Quine, W. V. O. — *Word and Object* (MIT Press, 1960) + follow-on essays | Philosophy spine for “meaning underdetermination” |
| **Shape bias** | Landauer, T. K. & Samelson, F. / Carey & Bartlett stream — use **Smith et al.** cross-situational word learning as operational cite | e.g. Smith, L.; Yu, C. — infancy **cross-situational** learning — look up **Psychonomic / Cognition** DOI per your bibliography tool |
| **Trust in HRI** | Hancock *et al.* — human–robot trust meta-literature (e.g. **Human Factors** reviews) | Pick **one** 2011/2021 review DOI when locking UI copy |
| **Multimodal / tactile + language** | Recent **Nature Machine Intelligence** / **Science Robotics** on visuo-tactile policies | Add when Architect picks a **single** target paper for a demo |

---

## 4. How SIFTA can “help” HRI (without building a tea-making Pepper)

1. **Receipt as explanation:** Every autonomous action already has a **ledger path** — surface that as **HRI explainability** in marketing truthfully (covenant §7.2).
2. **Predator gaze as “joint attention” analogue:** `swarm_app_focus.py` + `app_focus.jsonl` = **shared attention to a task object** (window / tab / molecule), not magical ToM.
3. **Stigmergy as team coordination:** Multi-IDE `ide_stigmergic_trace.jsonl` = **heterogeneous team** without assuming dyadic speech is the only channel — matches seminar’s “beyond one person one robot” *at the software civilization layer*.
4. **Tournament + small models:** Operational **“start small”** — cheap judge → escalate; same *moral* as Elman’s curriculum, different substrate.
5. **Problems to solve to “prove” the organism (engineering, not philosophy):** One **pytest-green** narrative: (a) register doctor, (b) mutate state with receipt, (c) **rollback** with second receipt, (d) prove via hash chain. That is **verifiable** “understanding” of *who did what when* — the part of HRI trust you can actually ship.

---

## 5. Next steps (ordered)

1. **Architect:** paste **canonical YouTube URL** for this seminar into §1 above.
2. **Surgeon (GO):** Add one optional panel to **`Applications/sara_imari_walker_widget.py`** Sources tab *or* future **Architect Room** — bullet “Developmental robotics / HRI” linking **this doc** + Elman DOI only (no transcript).
3. **Auditor:** Run manifest + `pytest` if any new `Applications/*.py` ships.
4. **Release:** If Bishop/public stack settles, one paragraph for **non-technical** readers: *“We don’t simulate children; we use incremental proof and receipts like explainable HRI asks for.”*

---

## 6. Cross-links

- [PREDATOR_V7_RESEARCH_SPINE.md](PREDATOR_V7_RESEARCH_SPINE.md) — proof plan, brain diagram  
- [SARA_IMARI_WALKER_ASSEMBLY_THEORY_RESEARCH.md](SARA_IMARI_WALKER_ASSEMBLY_THEORY_RESEARCH.md) — assembly / biocode spine (complementary “hard science” lane)

---

*Compiled 2026-04-28 — CG55M@cursor. Seminar metadata: user-provided UK HRI transcript excerpt; URLs to be sealed by Architect.*
