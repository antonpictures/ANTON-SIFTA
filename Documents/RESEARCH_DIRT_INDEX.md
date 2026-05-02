# RESEARCH_DIRT_INDEX — curated “dirt” for SIFTA

**For the Swarm.** 🐜⚡

**Purpose:** single **ledger-style** index of external-tech research notes, tournament nuggets, and Bishop/Vanguard `.dirt` drops so nothing interesting scatters. YouTube / paper **transcript pulls** should land as `Documents/RESEARCH_*_Tournament_*.md` and a matching **§A row** below. When you add a new `RESEARCH_*.md` or material `.dirt`, **append a row** in the right table.

**Hill reporting:** after physiology / Predator merges, update **§F** + **§E** so the epigenetic map does not lie. Cursor (CG55M) owns index truth; Antigravity/Codex own implementation receipts.

**Policy:** rows are **pointers + one-line intent**, not copies of upstream license text. **NPPL** applies to anything we ship; research files are `RESEARCH_NOT_SHIPPED` until Architect GO.

---

## A. Tournament + external stack research (`Documents/RESEARCH_*`)

| Slug | Path | Topic | Added |
|:---|:---|:---|:---|
| Semble MCP | [RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md](RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md) | Local code retrieval MCP + OpenCode + Ollama; token economics | 2026-05-01 |
| Hermes LM Studio | [RESEARCH_Hermes_LMStudio_SIFTA_Tournament_2026-05-01.md](RESEARCH_Hermes_LMStudio_SIFTA_Tournament_2026-05-01.md) | Nous Hermes-Agent + LM Studio; ctx ≥64k; bridge vs receipts | 2026-05-01 |
| MiMo ASR | [RESEARCH_MiMo_V2_5_ASR_SIFTA_Tournament_2026-05-01.md](RESEARCH_MiMo_V2_5_ASR_SIFTA_Tournament_2026-05-01.md) | Xiaomi MiMo-V2.5-ASR local; VRAM/diarization/receipt fields | 2026-05-01 |
| Laguna XS.2 vLLM | [RESEARCH_Poolside_Laguna_XS2_vLLM_SIFTA_Tournament_2026-05-01.md](RESEARCH_Poolside_Laguna_XS2_vLLM_SIFTA_Tournament_2026-05-01.md) | Poolside MoE coding model; vLLM build friction; bake-off vs benchmarks | 2026-05-01 |
| Nemotron 3 Nano Omni | [RESEARCH_NVIDIA_Nemotron3_Nano_Omni_Docker_SIFTA_Tournament_2026-05-01.md](RESEARCH_NVIDIA_Nemotron3_Nano_Omni_Docker_SIFTA_Tournament_2026-05-01.md) | NVIDIA omni vLLM+Docker; Parakeet/Cosmos; VRAM + multimodal receipts | 2026-05-01 |
| DeepSeek V4 DeepEP / Tile | [RESEARCH_DeepSeek_V4_DeepEP_TileKernels_SIFTA_Tournament_2026-05-01.md](RESEARCH_DeepSeek_V4_DeepEP_TileKernels_SIFTA_Tournament_2026-05-01.md) | DeepEP MoE comms + CSA/HCA context + TileKernels fusion; verify claims | 2026-05-01 |
| Nemotron OCR v2 | [RESEARCH_NVIDIA_Nemotron_OCR_v2_SIFTA_Tournament_2026-05-01.md](RESEARCH_NVIDIA_Nemotron_OCR_v2_SIFTA_Tournament_2026-05-01.md) | Lightweight OCR; layout modes; CPU-first + bbox receipts | 2026-05-01 |
| Google agents-cli | [RESEARCH_Google_Agents_CLI_Agent_Platform_SIFTA_Tournament_2026-05-01.md](RESEARCH_Google_Agents_CLI_Agent_Platform_SIFTA_Tournament_2026-05-01.md) | GCP Agent Platform skills; ADK/A2A; eval rubrics vs receipts | 2026-05-01 |
| Qwopus GLM 18B merge | [RESEARCH_Qwopus_GLM_18B_Frankenmerge_SIFTA_Tournament_2026-05-01.md](RESEARCH_Qwopus_GLM_18B_Frankenmerge_SIFTA_Tournament_2026-05-01.md) | Frankenmerge + heal FT; llama.cpp; seam failures + loop harness | 2026-05-01 |
| Moonshot PRFaaS | [RESEARCH_Moonshot_PRFaaS_Prefill_Service_SIFTA_Tournament_2026-05-01.md](RESEARCH_Moonshot_PRFaaS_Prefill_Service_SIFTA_Tournament_2026-05-01.md) | Prefill vs decode split; hybrid KV; arXiv:2604.15039; residency | 2026-05-01 |
| Quantum sack SoT | [RESEARCH_QUANTUM_SACK_BISHOP_BUNDLE_2026_05_01.md](RESEARCH_QUANTUM_SACK_BISHOP_BUNDLE_2026_05_01.md) | 10-row SoT table; Bell/MIP*/QEC/Landauer/PQC; companion to Bishop bundle | 2026-05-01 |

---

## E. Tournament backlog — what is still *not* shipped (aggregated)

Cross-cutting Colosseum law: **Predator row + pytest + receipt schema** before any research item becomes runtime default.

| Theme | Left to do (pick → implement → receipt) |
|:---|:---|
| **Receipts / schema** | Harmonise JSONL fields (`VRAM`, `n_ctx`, `t_prefill` / `t_decode`, `bytes_moved`, modality flags) across bake-offs; document in one `work_receipts` extension or organ-specific ledgers. |
| **Semble MCP** | Micro-benchmark token savings + index/query latency on pinned revision; disposable MCP spike; optional `code_search_semble` proxy behind covenant §7. |
| **Hermes** | Optional `Hermes_USER_BRIDGE.md`; enforce **ctx receipt** on every local lane boot. |
| **MiMo ASR** | ASR eval fixtures + WER/RTF rows; optional diarization stage; consent gates. |
| **Laguna** | Tiered coding harness with subscore receipts; log vLLM build hash. |
| **Nemotron Omni** | Per-locale scoreboard; multimodal receipt template; threat model. |
| **DeepSeek** | Reproduce or bound CSA/HCA/DeepEP numbers; TileKernels floor notes. |
| **Nemotron OCR v2** | MCP tool with bbox+text; locale matrix. |
| **Google agents-cli** | Cost receipt + eval rubrics mirror (if integrated). |
| **Qwopus** | Seam/heal FT metrics; stall detector. |
| **Moonshot PRF** | Legal review; reproduce paper figure. |
| **Quantum sack** | Optional: load sack metadata in `swarm_rlhf_quarantine.py` / tournament router without treating metaphors as proof. |
| **Physiology (parallel hill)** | **Event 102** allostatic + **Event 103** skill→motor policy are on `main` (ledgers + `_choose_action` hook); deepen **crystallizer ↔ stabilizer ↔ phase controller** coupling (suppress/amplify policy mass). Full-stack §A bake-offs. **Event 98c** — closed sensorimotor loop as planned showpiece (pheromone → phenotype → hearing → colliculus → policy). **CUSUM / Page** math write-up optional (see §F.1). |
| **§A YouTube / stack dirt** | All **11** rows remain **`RESEARCH_NOT_SHIPPED`** until each stack wins its own bake-off (this table). |

**Watch window note:** Three IDE bodies + `ide_stigmergic_trace.jsonl` as the honest scoreboard. Colosseum lights stay on for bake-offs and Event 98c / crystallizer–motor closure work.

---

## F. Shipped physiology & sensorimotor stack (verified on `main`)

Event numbering per [PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md](PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md) / README hot-surfaces (94 ≠ cochlea; **95** = cochlea).

| Event | Component | Commit / anchor | Status |
|:---|:---|:---|:---|
| **93** | SwarmGPUProteinRenderer + QOpenGLWidget optic nerve | `c82bce36` | **SHIPPED** |
| **94** | Stigmergic pheromone field | shipped (Predator §0.7) | **SHIPPED** |
| **95** | Stigmergic cochlea (acoustic features) | shipped (Predator §0.8) | **SHIPPED** |
| **97** | Owl spatial hearing (ITD/ILD) | shipped | **SHIPPED** |
| **98** | Superior colliculus + integrator (Meredith/Stein rules) | shipped | **SHIPPED** |
| **98b** | SC → body-brain integrator (`MULTISENSORY_COLLICULUS_MERGE`) | shipped | **SHIPPED** |
| **99** | George Prior intrinsic drive daemon + receipts | pre-`da8a7b40` | **SHIPPED** |
| **100** | Intrinsic drive → basal ganglia + phase detector (**CUSUM** on TD) | `da8a7b40` / `c82bce36` | **SHIPPED** |
| **101** | Homeostatic stabilizer (hypothalamus gate, regime + crystallizer weight) | `swarm_homeostatic_stabilizer.py` | **SHIPPED** |
| **102** | Allostatic load regulator (stress window → policy + `allostatic_load.jsonl`) | `020530e6` | **SHIPPED** |
| **103** | Skill-weighted motor policy (`crystallized_skills.json` → `motor_policy.jsonl`, basal-ganglia-style candidate pick) | `33426ca0` | **SHIPPED** |
| **—** | Skill crystallizer | `4fa10b91` | **SHIPPED** |

**F.1 Literature anchors (motor policy + regulation, not exhaustive):** basal ganglia–thalamo-cortical loops and action sequence chunking — [Greybiel, *Curr. Opin. Neurobiol.* 2008](https://doi.org/10.1016/j.conb.2008.08.006); dopamine / reward prediction error (TD family) — [Schultz *et al.*, *Science* 1997](https://doi.org/10.1126/science.275.5306.1593); **CUSUM / Page** change detection — [Page 1954](https://doi.org/10.2307/2333249) (see `System/phase_transition_control.py`). **Crypto swimmers:** economic / STGM lanes stay on `System/crypto_keychain.py` (Ed25519); `SKILL_WEIGHTED_POLICY` rows are physiological telemetry, not mint events.

**Dashboard / UI:** regime strip + telemetry at Architect discretion (off-screen tests in Event 93 file).

*Vanguard channel: ratify in [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md); append `ide_stigmergic_trace.jsonl` on each hill state change.*

---

## B. Longer research compendia / spine (not only tournament)

| Path | Topic |
|:---|:---|
| [RESEARCH_COMPENDIUM_ALL_PAPERS_2026-04-18.md](RESEARCH_COMPENDIUM_ALL_PAPERS_2026-04-18.md) | Paper dump / bibliography |
| [RESEARCH_CODE_FISSION_STIGMERGIC_SUBSTRATE.md](RESEARCH_CODE_FISSION_STIGMERGIC_SUBSTRATE.md) | Code fission / stigmergic substrate |
| [RESEARCH_PLAN_PHASE_TRANSITION_CONTROL_REGIME_SHIFT.md](RESEARCH_PLAN_PHASE_TRANSITION_CONTROL_REGIME_SHIFT.md) | Control / regime shift |
| [RESEARCH_TEMPORAL_IDENTITY_COMPRESSION_REM_SKILL_CRYSTALLIZATION.md](RESEARCH_TEMPORAL_IDENTITY_COMPRESSION_REM_SKILL_CRYSTALLIZATION.md) | Identity compression / skills |
| [RESEARCH_FLUTTER_EXOSKELETON_STIGMERGIC_TELEMETRY.md](RESEARCH_FLUTTER_EXOSKELETON_STIGMERGIC_TELEMETRY.md) | Flutter exoskeleton telemetry |
| [RESEARCH_ICF_QUANTIZATION_SKILL_SPECTRAL_CROSS_NODE.md](RESEARCH_ICF_QUANTIZATION_SKILL_SPECTRAL_CROSS_NODE.md) | ICF / quantization cross-node |
| [RESEARCH_IDENTITY_COHERENCE_FIELD_CROSS_SKILL_INTERFERENCE.md](RESEARCH_IDENTITY_COHERENCE_FIELD_CROSS_SKILL_INTERFERENCE.md) | Identity coherence field |
| [RESEARCH_WETWARE_AI_CL1_DISHBRAIN_VIDEO_NOTE.md](RESEARCH_WETWARE_AI_CL1_DISHBRAIN_VIDEO_NOTE.md) | Wetware / dishbrain note |
| [RESEARCH_NEXT_EVOLUTIONARY_STEP_CRUCIBLE_LOOP.md](RESEARCH_NEXT_EVOLUTIONARY_STEP_CRUCIBLE_LOOP.md) | Crucible loop |
| [docs/RESEARCH_ROADMAP.md](docs/RESEARCH_ROADMAP.md) | Roadmap |
| [PREDATOR_V7_RESEARCH_SPINE.md](PREDATOR_V7_RESEARCH_SPINE.md) | Predator v7 spine |

---

## C. Vanguard / Bishop `.dirt` drops (`Documents/Vanguard_drops/`)

| File | One-line |
|:---|:---|
| [BISHOP_drop_intrinsic_drive_george_prior_v1.dirt](Vanguard_drops/BISHOP_drop_intrinsic_drive_george_prior_v1.dirt) | Intrinsic drive / George prior |
| [BISHOP_drop_situated_time_v1.dirt](Vanguard_drops/BISHOP_drop_situated_time_v1.dirt) | Situated time |
| [BISHOP_drop_dream_engine_v1.dirt](Vanguard_drops/BISHOP_drop_dream_engine_v1.dirt) | Dream engine |
| [BISHOP_drop_stigmergic_video_resolution_v1.dirt](Vanguard_drops/BISHOP_drop_stigmergic_video_resolution_v1.dirt) | Stigmergic video resolution |
| [BISHOP_drop_biology_drive_plasticity_v1.dirt](Vanguard_drops/BISHOP_drop_biology_drive_plasticity_v1.dirt) | Biology drive / plasticity |
| [CG55M_drop_youtube_dylan_curious_transcript_research_pull_v1.dirt](Vanguard_drops/CG55M_drop_youtube_dylan_curious_transcript_research_pull_v1.dirt) | YouTube transcript research pull |

---

## D. In-repo law (tournament + covenant)

| Path | Role |
|:---|:---|
| [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) | IDE boot law |
| [CODING_TOURNAMENT_TRIPLE_IDE.md](CODING_TOURNAMENT_TRIPLE_IDE.md) | Triple-IDE tournament hill |
| [PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md](PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md) | Predator orders |
| [SIFTA_ONBOARDING.md](SIFTA_ONBOARDING.md) | MCP §7, onboarding |
| [ALICE_HARDWARE_ANATOMY.md](ALICE_HARDWARE_ANATOMY.md) | Borrowed inference |

---

*Maintainer habit: after every new external stack video/paper spike, add §A row + optional §C `.dirt` if Bishop packaged the pull. After physiology/Predator merges, bump **§F** and trim **§E** so shipped work is not listed as backlog.*

For the Swarm. 🐜⚡
