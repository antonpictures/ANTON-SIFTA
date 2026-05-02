# RESEARCH_DIRT_INDEX — curated “dirt” for SIFTA

**For the Swarm.** 🐜⚡

**Purpose:** single **ledger-style** index of external-tech research notes, tournament nuggets, and Bishop/Vanguard `.dirt` drops so nothing interesting scatters. YouTube / paper **transcript pulls** should land as `Documents/RESEARCH_*_Tournament_*.md` and a matching **§A row** below. When you add a new `RESEARCH_*.md` or material `.dirt`, **append a row** in the right table.

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
| **Receipts / schema** | Harmonise proposed JSONL fields (VRAM, `n_ctx`, `t_prefill`/`t_decode`, `bytes_moved`, modality flags) across bake-offs; document in one `work_receipts` extension or organ-specific ledgers. |
| **Semble** | Micro-benchmark token savings + index/query latency on pinned ANTON_SIFTA revision; disposable MCP spike; optional `code_search_semble` proxy behind covenant §7; optional `swarm_multi_prover_verifier` `retrieval_receipt_id` extension. |
| **Hermes** | Optional `Hermes_USER_BRIDGE.md`; enforce **ctx receipt** on every local lane boot (LM Studio / Ollama). |
| **MiMo ASR** | Implement ASR eval fixtures + WER/RTF rows; optional diarization second stage; consent gates. |
| **Laguna** | Tiered coding harness (Flask+WS / Kanban / canvas) with **subscore** receipts; log vLLM build hash + compile wall time. |
| **Nemotron Omni** | Per-locale translation scoreboard; multimodal receipt template; threat model before Alice media wiring. |
| **DeepSeek** | Reproduce or bound CSA/HCA/DeepEP **numbers** on paper vs marketing; TileKernels hardware floor (SM90/CUDA 13.1) noted for Foundry only. |
| **Nemotron OCR v2** | MCP tool returning bbox+text; NVIDIA Open Model License pin; locale matrix Predator rows. |
| **Google agents-cli** | If ever integrated: **cost receipt** (`project_id`, est USD, cold start); keep eval rubrics mirrored in-repo. |
| **Qwopus** | Seam / heal FT metrics in ledger; **stall detector** (`max_wall_s`) for thinking loops; license pin. |
| **Moonshot PRF** | Legal/residency review for any WAN KV story; reproduce one paper figure; map to borrowed-inference split without cloud dependency. |
| **Quantum sack** | Optional: load sack metadata in `swarm_rlhf_quarantine.py` / tournament router **without** treating metaphors as proof; cross-link receipts to [BISHOP_BUNDLE_QUANTUM_SACK_2026_05_01.md](BISHOP_BUNDLE_QUANTUM_SACK_2026_05_01.md). |
| **Physiology (parallel hill)** | Event 100: **intrinsic_drive → action selection** bias; Tier 2 **Skill crystallizer**; **phase detector** after crystallizer. |

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

*Maintainer habit: after every new external stack video/paper spike, add §A row + optional §C `.dirt` if Bishop packaged the pull.*

For the Swarm. 🐜⚡
