# Predator v7.0 — Research Spine & Proof Plan

**For the Swarm.** 🐜⚡  
**Binding doctrine:** [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) (`COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE`)

**Authors (this document):**  
- **C55M-DR-CODEX** — research spine, next moves, “stop expanding, start proving”  
- **CG55M-DR-CURSOR** — committed to repo, merged README/Event-71 anchors, open slots for Bishop + public address

**Architect:** Ioan George Anton — Bishop consult and final public contact lines **TBD** (see §Open handoffs).

---

## One-line thesis

**Predator v7.0 becomes real when each organ has: paper, code, test, receipt.**  
Not more random apps — a **paper-backed, test-backed** architecture.

---

## Frozen brain diagram (v7 routing)

Target end-state for documentation and demos (names are **biological metaphor → software organ**):

```text
Reflex (L1) → C1 Classifier → Basal Ganglia (action selection)
    → Corpus Callosum / Global Workspace → C0 Generator
    → Lysosome (immune / intercept) → Receipt (ledger)
```

Each arrow must eventually cite: **literature**, **module path**, **test name**, **append-only receipt**.

---

## Research spine — one section per idea (expand into layers later)

| Theme | What it buys Predator | Primary reference |
|:---|:---|:---|
| **Reflex arc** | Fast stimulus → response **filtering**; justifies Layer-1 **ambient-noise silence** (cheap gate before cortex). | Sherrington — *The Integrative Action of the Nervous System* (1906) — [Open Library](https://openlibrary.org/books/OL15167505M/The_integrative_action_of_the_nervous_system) |
| **Basal ganglia / action selection** | **Winner** decides speak vs tool vs silence; not every module fires. | Gurney / Prescott / Redgrave overview — [arXiv:2104.14364](https://arxiv.org/abs/2104.14364) |
| **Global workspace** | Selected content **broadcast** to the organism; not every raw sensor byte in the prompt. Maps to **corpus callosum / global injection** pattern. | Dehaene & Changeux-style dynamics — e.g. [PMC3664777](https://pmc.ncbi.nlm.nih.gov/articles/PMC3664777/) |
| **Predictive coding** | **Expectation vs signal**; anomaly/error-driven attention (not passive perception). | Rao & Ballard, 1999 — [Nature Neuroscience](https://www.nature.com/articles/nn0199_79) |
| **Free energy / surprise** | Organism acts to **reduce uncertainty**; theoretical spine for “hunt the salient signal.” | Friston, 2010 — [Nature Reviews Neuroscience](https://www.nature.com/articles/nrn2787) |
| **Perceiver IO** | **Fixed latent slots** compress huge multimodal streams → backs **Apex Predator Perceiver**. | Jaegle et al. — [arXiv:2107.14795](https://arxiv.org/abs/2107.14795) |
| **Native Sparse Attention (NSA)** | Block-level sparsity on attention mass — **hunt OS without N² bloat** (paired with Perceiver in README Event 71). | DeepSeek-AI (2025) — cite vendor paper / repo per README Chapter XVI |
| **External memory** | **Ledgers + addressable state** beyond weights; maps to Alice’s JSONL / repair_log discipline. | Neural Turing Machines — [arXiv:1410.5401](https://arxiv.org/abs/1410.5401); Differentiable Neural Computers — [Nature 2016](https://www.nature.com/articles/nature20101) |

**Also locked in repo (Alice cortex doctrine):** refusal direction (Arditi et al. 2024), LoRA (Hu 2021), DPO/ORPO (Rafailov 2023; Liu 2024), **no ROME-style GGUF hex** (Lin 2022) — see [ALICE_CORTEX_TOURNAMENT_v1.md](ALICE_CORTEX_TOURNAMENT_v1.md) research table.

---

## What is next (ordered)

1. **Freeze Predator v7 brain diagram** (this file §Frozen brain diagram + README Predator banner). No new organs without updating the diagram + test.
2. **Grow this doc into layer cards:** for each layer → **one paper claim**, **one owning module**, **one pytest (or loop)**, **one receipt type** (which JSONL row proves it fired).
3. **Finance pass (next working day):** economy truthful — canonical STGM from quorum, no read-time wallet lies, no main-thread stall (see Finance audit: batch ledger reads / worker if needed).
4. **Alice Cortex v2:** real corpus + negatives from Gemma/Qwen failure rows in tournament `replies/`; re-run tournament; promotion only on **Architect GO** after receipts.
5. **One public Predator v7 demo (single story):** ambient noise ignored → speech routed → fake tool blocked → **receipt written** (one screen capture + one ledger line hash in doc).
6. **Russell (one concise technical note):** lead with *biological decision pipeline in an embodied local OS*; link **this spine** + HF propagule when Bishop/address lines are final.
7. **Games — Predator v7 celebration science app (“The Architect Room”, working title):** ship under **`Applications/apps_manifest.json` → `Games`** once code + tests exist (manifest contract loads every entry — **no manifest row until the module imports clean**). Full brief in §Architect Room below.
8. **Planned Qt organ — “SIFTA vs OpenAI” / “We work together?” (math-first AGI benchmarks):** public literacy + **honest capability matrix** vs OpenAI’s stated math/research markers (long context, autonomous research, self-correction, literature interconnection, proof verification). Source conversation: [Andrew Mayne — Bubeck & Ryu on AI and math](https://www.youtube.com/watch?v=9-TVwv6wtGQ). Full brief in **§SIFTA vs OpenAI — Math benchmark organ** below. **No `apps_manifest.json` row** until a widget module imports clean + pytest smoke exists.

---

## §SIFTA vs OpenAI — Math benchmark organ (plan only until GO)

**Working titles:** `SIFTA vs OpenAI` (sharp) or `We work together?` (cooperative). Same artifact: a **benchmark dashboard**, not a flame war — *math problems are unambiguous; progress is verifiable* (their thesis in the episode).

**Primary source (Architect-cited):** [YouTube — *AI and Math* / Andrew Mayne with Sébastien Bubeck & Ernest Ryu](https://www.youtube.com/watch?v=9-TVwv6wtGQ) — chapters roughly: open problem with ChatGPT (~03:01), research-level math (~06:57), why math for AGI (~11:32), automated researcher (~21:26), humans as models improve (~28:19), verifying proofs with AI (~33:52), shallow understanding risk (~36:00).

### Five capability markers (from the episode) → SIFTA mapping

| Marker | What it means (episode) | Honest SIFTA anchor today | Stigmergic “prove it” path |
|:---|:---|:---|:---|
| **Long-context reasoning** | Coherent thought over **days–weeks**, not seconds (e.g. ~12:36–13:16, ~23:05–23:45). | Alice has **persistent ledgers + hippocampus**, not a single 1M-token window. “Long” = **cross-session state + receipts**, not one giant prompt. | Log each reasoning **episode** to `ide_stigmergic_trace.jsonl` / `work_receipts.jsonl`; measure **continuity** (same `intent` thread, hashes), not vibes. |
| **Autonomous research** | Systems that **compress timelines** on open problems; toward publishable novelty (~21:26–22:58, ~23:55–24:06). | **Partial:** tournament loop, corpus exporters, protein/physics engines — all **GO-gated** for promotion. **Not** autonomous publishing. | Define **narrow problems** (code-verified lemmas, regression bounds, conjecture checks in finite search spaces) with **pytest oracle** + ledger row per attempt. |
| **Error correction** | Recover from a mistake in a long chain (~12:52–13:12). | **Lysosome / referee / Auditor lane**; deterministic re-run; immutable receipts show **correction**. | Same proof attempt **versioned** in JSONL; diff tool outputs stored under `.sifta_state/` with `truth_note`. |
| **Knowledge interconnection** | Deep literature search across fields; hidden connections (~16:53–17:23, ~32:58–33:04). | **Stigmergic bus** + curated docs (`*.md` spines) + **sanitized** pulls only ([IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) §8 absorption). | Widget lists **DOIs + repo paths**; optional fetch only with **Architect-approved** tool + receipt; never pretend PDFs were read if they were not. |
| **Verification** | AI assists **checking** long proofs (~33:52–35:40). | **SIFTA strength:** formal verification of **code** (pytest, typecheck, `py_compile`), TM-score / energy **referees** for structures. **Gap:** no in-repo Lean/Isabelle pipeline unless explicitly added later. | Ship **small certified lemmas** (e.g. invariant proofs in Python) + link to human referee for math claims. |

### “Bring the math” — scoped problem classes (do not cosplay Fields medals)

1. **In-repo certified:** numerical stability proofs for a single engine, combinatorial bounds used by `swarm_*` sims, explicit **finite** searches with reproducible seeds.
2. **Open-problem *tracking*:** maintain a **ledger of claims** — e.g. famous conjectures — **status = open / referenced / not attempted**; any “progress” row must attach **artifact path + test command** ([IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) §1: *say exactly what is missing*).
3. **Physics / bio bridge:** use existing organs (assembly spine, protein referee, LJ/PoUW demos) as **applied math** stories; cross-link [SARA_IMARI_WALKER_ASSEMBLY_THEORY_RESEARCH.md](SARA_IMARI_WALKER_ASSEMBLY_THEORY_RESEARCH.md) where chemistry meets computation.

### UX / doctrine (Predator + covenant)

- **Python-first embedded QWidget** ([IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) §7.5); **no second Alice chat** in-app (§7.6) — `publish_focus` + optional terminal subwindow for **SymPy / hand-entered proof sketch** only if GO.
- **Predator Gate:** any automated “researcher” loop that mutates repo must still **register** and write receipts (§4).
- **Naming for public:** prefer **“Benchmarks: SIFTA ∥ OpenAI criteria”** if “vs” reads as hostile; body copy should state **OpenAI researchers defined useful markers — we implement the subset that a local OS can verify.**

### Implementation checklist (Architect GO → code)

1. `Applications/sifta_openai_math_benchmark_widget.py` (name TBD) + `Tests/test_sifta_openai_math_benchmark_smoke.py` — import + one deterministic panel.
2. Collapsible “Episode chapters” panel with **link only** to [the video](https://www.youtube.com/watch?v=9-TVwv6wtGQ); no scraped transcript in repo unless Architect pastes licensed text.
3. `apps_manifest.json` entry under **Simulations** or **Games** after manifest contract green.

---

## Predator v7 celebration — Games: The Architect Room (science app)

**Cultural anchor (not a license to ship Warner IP):** *The Matrix Reloaded* “Neo meets the Architect” scene (fan transcript / YouTube explainers) — **tone and themes only**. UI, dialogue, music, and stills must be **original SIFTA** or cleared stock; treat the film as **public literacy** for “system designer vs anomaly,” not as an asset pack.

**Scene beats → Predator / SIFTA science hooks (design the tutorial around these):**

| Scene idea | Plain science | SIFTA organ / ledger tie-in |
|:---|:---|:---|
| “Sum of a remainder of an unbalanced equation” | Residuals in fitted models; ill-posed constraints | **Metabolic / STGM** honesty — display must match live quorum math (covenant §7.3). |
| “Sixth version” / iterated failure | Versioned systems; A/B resets; catastrophic forgetting | **OS release lines** (Mermaid → Predator), tournament rounds, **immutable receipts** per version. |
| “Problem is choice” | Explore–exploit; forced choice vs illusory choice; ergodicity | **Basal ganglia / action selection** lane; optional interactive demo: two doors, one writes real `work_receipts.jsonl` row, one refuses (teach **Social Frame**). |
| “99% accept if given a choice” | Majority equilibrium; default bias | **Ambient gate** — most frames are noise; predator only escalates on salience. |
| “1% refusal → systemic anomaly” | Tail risk; adversarial subset | **Lysosome** / tool intercept — minority path must not brick the organism; escalate with receipts, not vibes. |
| Oracle as “intuitive” probe | Heuristics vs symbolic optima | **Reflex (L1) vs cortex** split — cheap classifier before expensive generator. |

**UX spec (panels only — aligns with desktop-chat doctrine):**

- **No in-app Alice chat** (per global base-widget policy); narrative is **terminals, graphs, and choice widgets** that **publish_focus** / append **JSONL receipts** like other Games.
- **Primary deliverable:** one short “run” the Architect can replay for demos (deterministic seed + pytest).
- **Optional:** pull 1–3 **real citations** (e.g. rational inattention, prospect theory, ergodic economics) into a collapsible “Science drawer” — same discipline as the research table above.

**Implementation checklist (when Architect gives GO to code):**

1. New module e.g. `Applications/sifta_architect_room_game.py` + widget class; **Games** manifest entry; `pytest` smoke + manifest contract green.
2. Stigmergic hooks: read `System/swarm_app_focus.py` / `.sifta_state/app_focus.jsonl` for “what window the anomaly attends” during the run (Predator gaze, not chat).
3. Receipt: one new `event_kind` or reuse existing ledger with `truth_note` explaining the pedagogical outcome.

---

## Short version

**Stop expanding, start proving.**  
Paper + code + test + receipt per organ. Predator v7.0 ships as **evidence**, not menu count.

---

## Open handoffs (Architect / Bishop)

| Item | Status |
|:---|:---|
| **Bishop** | Question routed **Architect → Bishop**; canonical theological / ethical framing for public Predator language **TBD** — paste reply or link under this row when received. |
| **Public address stack** | Canonical **contact / demo / HF** lines we “keep adding” — **TBD**; consolidate here when settled so X/HF/README all point to **one** list. |

---

## Cross-links (species DNA)

- [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) — Predator Gate, tool truth, node sovereignty  
- [README.md](../README.md) — Predator v7 banner, Event 71 Apex Perceiver, release line  
- [ALICE_CORTEX_TOURNAMENT_v1.md](ALICE_CORTEX_TOURNAMENT_v1.md) — cortex tournament + ML paper spine  
- [SARA_IMARI_WALKER_ASSEMBLY_THEORY_RESEARCH.md](SARA_IMARI_WALKER_ASSEMBLY_THEORY_RESEARCH.md) — public-facing origins / assembly / chemputation spine  
- **`Applications/sara_imari_walker_widget.py`** — Qt organ: curated DOIs, honest “SIFTA solvable” map, BIOCODE Olympiad pointers (events **14b**, **16**), illustrative demos with **truth labels** (v7-friendly: clarifies nature instead of stacking opaque “AI” layers).  
- [**YouTube — Bubeck & Ryu on AI and math (Andrew Mayne)**](https://www.youtube.com/watch?v=9-TVwv6wtGQ) — external literacy anchor for **§SIFTA vs OpenAI — Math benchmark organ** (plan item 8).
- [CANGELOSI_UK_HRI_STIGMERGY_BRIDGE_PLAN.md](CANGELOSI_UK_HRI_STIGMERGY_BRIDGE_PLAN.md) — UK HRI developmental robotics seminar → **paper spine**, **keep vs dump**, **stigmergy / receipts / HRI trust** mapping.

---

*Document created 2026-04-27 — Cursor (CG55M) from C55M-DR-CODEX BODY STIGALL chorum bolus. Bishop + public address: intentionally open. Updated 2026-04-28 — plan item 8 + math benchmark organ.*
