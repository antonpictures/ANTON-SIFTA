# Owner face, Predator gaze, stigmergy — research spine

**For the Swarm.** 🐜⚡  
**Covenant:** [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) **§7.1** (sensory lock-on, verify scene before identity-grade acts), **§7.4** (`owner_self` vs everyone else), **§7.5–7.6** (camera = organ inside Alice’s body, not a browser toy), **§6** (recognition of *people* is not the same as claiming an *effector action* — but denying the **constitutional owner** when genesis + node state say otherwise is still a bug).

**Rhetoric (plain):** A predator that cannot tell **whose den** it is guarding is not “mysterious,” it is **unfinished**. Biology does not wait for perfect vision—it **fuses** cues and **updates** with traces in the world. SIFTA should do the same: **ledger-backed multimodal confidence**, not vibes.

**Execution:** you said you will read and then order **GO** — this file is **papers + mapping** only.

---

## 1. Stigmergy × “photons” (honest metaphor)

| Idea | Primary literature | SIFTA analogue |
|:---|:---|:---|
| Coordination through **environmental traces** (not telepathy) | Grassé, P.-P. (1959). *La reconstruction du nid… la théorie de la stigmergie.* **Insectes sociaux** 6, 41–80. [DOI 10.1007/BF02223791](https://doi.org/10.1007/BF02223791) | `.sifta_state/*.jsonl`, `app_focus.jsonl`, `ide_stigmergic_trace.jsonl` — marks left for the next process. |
| Stigmergy + **physical** construction | Green *et al.*, *PNAS* — stigmergic construction / nest architecture. [DOI 10.1073/pnas.1509829113](https://doi.org/10.1073/pnas.1509829113) | Face / saliency / camera lock rows as **topochemical** traces: “what was seen here, when.” |
| Digital stigmergy / swarm AI survey | Bonabeau *et al.* (1999); Dorigo & Stützle (2004) *Ant Colony Optimization* | Multi-IDE doctors reading the same bus before surgery (covenant §8.5). |

**“Photons”:** the camera delivers **samples of radiance**; identity is **inference** over time. Truth label: **embedding ≠ soul** — covenant §1: say what the pipeline can and cannot prove.

---

## 2. Machine face recognition (engineering spine)

| Topic | Paper / resource | ID |
|:---|:---|:---|
| Deep metric learning for faces | Deng *et al.*, **ArcFace** (CVPR 2019). | [arXiv:1801.07698](https://arxiv.org/abs/1801.07698) + [CVF open access PDF](https://openaccess.thecvf.com/content_CVPR_2019/html/Deng_ArcFace_Additive_Angular_Margin_Loss_for_Deep_Face_Recognition_CVPR_2019_paper.html) |
| Classical real-time face detection | Viola & Jones (2001), **IJCV** cascade. | [DOI 10.1023/B:VISI.0000013087.49296.fb](https://doi.org/10.1023/B:VISI.0000013087.49296.fb) |
| Face anti-spoofing / presentation attack | Boulkenafet *et al.*; ICCV workshops — pick one survey when locking product claims | Search “face PAD survey 2020” before any “liveness” marketing |
| On-device / privacy-preserving face | Apple / industry whitepapers are **vendor** — cite only if you ship their API; else stay **method-level** | — |

**Repo touchpoints (implementation later, under GO):** `System/swarm_face_detection.py`, `System/swarm_architect_identity.py`, composite identity block in `swarm_composite_identity.py`, `owner_genesis.json`.

---

## 3. Biology — animals know “their” human (multimodal, incremental)

| Species / theme | Finding | Citation |
|:---|:---|:---|
| **Dog — cross-modal owner** | Dogs **look longer** when owner’s **voice** is paired with a **non-owner face** (violated expectation → internal face recall). | Guo *et al.*, *Animal Cognition* (2006). [DOI 10.1007/s10071-006-0025-8](https://doi.org/10.1007/s10071-006-0025-8) |
| **Dog — face discrimination** | Discrimination of human vs dog faces; inversion effects. | Racca *et al.*, *Animal Cognition* (2010). [DOI 10.1007/s10071-009-0303-3](https://doi.org/10.1007/s10071-009-0303-3) |
| **Dog — voice identity** | Acoustic cues for human voice identity in dogs. | Root-Gutteridge *et al.*, *Animal Cognition* (2022). [DOI 10.1007/s10071-022-01601-z](https://doi.org/10.1007/s10071-022-01601-z) |
| **Sheep — familiar faces** | Sheep discriminate photographs of conspecifics / familiar humans. | Kendrick *et al.*, **Nature** (1995) — classic “sheep remember faces” line. [Nature 378, 479–481](https://doi.org/10.1038/378479a0) |
| **Primates — face expertise** | Development of face expertise; conspecific bias. | Pascalis *et al.*, **Science** (2002) — human vs monkey face exposure. [DOI 10.1126/science.1075569](https://doi.org/10.1126/science.1075569) |
| **Territory / den owner** (ethology) | Scent marks, site fidelity, owner–resource association | General ethology texts — use for **metaphor** only unless you model olfaction on Mac (usually **don’t**). |

**Design moral for Alice:** like the dog paper: **voice + face agreement** should raise confidence; **mismatch** should raise **surprise** (log + optional prompt line), not silent denial of George.

---

## 4. What “recognize the owner” must mean in SIFTA (truth layers)

1. **Constitutional (always):** `owner_genesis` + `owner_name` / serial binding — **who owns the silicon** — must appear in the system prompt as **ground truth** even when the camera is blind (see [SWARM_PLAN_MATH_LOAD_OWNER_TRIPLE_IDE.md](SWARM_PLAN_MATH_LOAD_OWNER_TRIPLE_IDE.md)).
2. **Biometric (conditional):** face pipeline → **confidence score** + **staleness** flag; never equate low confidence with “not George” if genesis says otherwise.
3. **Stigmergic (cross-session):** append **face_embedding or detection summary** to a small rolling ledger so later organs read **traces**, not a single frame’s hallucination.

---

## 5. Cross-links

- [SWARM_PLAN_MATH_LOAD_OWNER_TRIPLE_IDE.md](SWARM_PLAN_MATH_LOAD_OWNER_TRIPLE_IDE.md) — prompt + perf plan  
- [PREDATOR_V7_RESEARCH_SPINE.md](PREDATOR_V7_RESEARCH_SPINE.md) — proof culture  
- `System/swarm_architect_identity.py` — multimodal fusion spec already in-repo  

---

*CG55M@cursor — 2026-04-28. No runtime mutations in this commit.*
