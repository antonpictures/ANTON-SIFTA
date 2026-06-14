# CENSUS_2_modules.md

## SIFTA_STIGMERGIC_GEMMA4_DISSECTOR.py
SIFTA_STIGMERGIC_GEMMA4_DISSECTOR.py Event 20 — C47H + GROK unhinged vector autopsy Takes any Ollama Gemma4 GGUF (or any .gguf) and treats every tensor as a polymer in the Flory-Huggins lattice. Outputs: full tensor stat
Entry points: get_ollama_model_path, load_gguf_tensors

## adaptive_constraint_memory_field.py
System/adaptive_constraint_memory_field.py — Vector 12: ACMF ══════════════════════════════════════════════════════════════════════ Memory evolution under constraint pressure. Memory doesn't just get selected (CWMS) or s
Entry points: MemoryFitnessEntry, AdaptiveConstraintMemoryField
Internal imports: System.jsonl_file_lock

## agent_self_watermark.py
agent_self_watermark.py — Per-tag deterministic signature on agent text deposits ═══════════════════════════════════════════════════════════════════════════════ Module 2 of the Stigmergy-Vision Olympiad (2026-04-18). DYO
Entry points: per_tag_seed, text_fingerprint, embed_signature, detect, WatermarkRow, persist_watermark_row, recent_watermark_rows
Internal imports: System.jsonl_file_lock

## agentic_calibrator.py
agentic_calibrator.py — Autonomous Swarm Parameter Tuning ═════════════════════════════════════════════════════════════ Inspired by NVIDIA Ising (Quantum Day 2025): AI-driven calibration of volatile quantum processors, t
Entry points: SwarmTelemetry, SwarmPhysics, read_telemetry, read_physics, write_physics, write_telemetry, CalibratorState, calibrate_once, daemon_loop

## alice_active_organ_embodiment.py
System/alice_active_organ_embodiment.py — Active App Context Layer Build the receipt-backed context Alice should load for whichever SIFTA app is currently focused. The point is operational, not philosophical: answer from
Entry points: get_current_active_organ, get_organ_embodiment_level, enter_organ_context, get_current_organ_context
Internal imports: System.alice_reality_boundary, System.alice_self_vector, System.swarm_app_health

## alice_bishapi_budget.py
Alice ↔ NUGGET budget — schedule + Architect-as-Buffett owner grants. Architect doctrine (2026-04-19, evening — Nugget Doctrine): • The organism does **not** spend the wallet flat. It spends to a *schedule*. • **Promo** 
Entry points: budget_config_path, owner_grants_ledger_path, value_journal_path, load_budget_config, save_budget_config, ensure_promo_start, grant_owner_usd, grants_total_usd, burn_usd_today, burn_usd_total, BudgetDecision, authorize_call

## alice_body_autopilot.py
System/alice_body_autopilot.py — Alice's resident body-governance organ ═════════════════════════════════════════════════════════════════════════ C47H / CC2F 2026-04-23 — Alice is resident in this body, not a guest. This
Entry points: ensure_iphone_gps_bridge, ensure_local_mcp_bridge, inspect_body, ensure_autonomic_services, read_prompt_line, govern

## alice_browser_vision_bridge.py
Alice Browser Vision Bridge — stigmergic sight for the browser organ. Browser pixels are first-class sensor data, not chat memory. Flow: Alice Browser pixels → OCR/vision facts → sha256 receipt → compare with owner scree
Entry points: BrowserVisionReceipt, sha256_bytes, build_browser_vision_receipt, append_receipt, load_recent_receipts

## alice_cortex_bridge_pulse.py
Cortex bridge pulse classifier. This small organ summarizes whether a stalled cortex turn is down, recovering, or waiting for a clearer execute packet, using receipts rather than vibes.
Entry points: CortexBridgePulse, assess_cortex_bridge_pulse

## alice_cortex_eval_runner.py
System/alice_cortex_eval_runner.py Stage 2 of Alice Cortex v1 Tournament. Runs any local Ollama model or API oracle against the alice_cortex_eval_suite_v1.json. Writes replies/{contestant}.jsonl and scores_automated.json
Entry points: load_suite, score_reply, query_ollama, query_api, run_tournament_round, main

## alice_cortex_v2_synth_generator.py
System/alice_cortex_v2_synth_generator.py Stage 0 of Alice Cortex v2 — Synthetic Intent Classification Corpus Generator. Architecture: Bicameral Corpus Callosum (Event 73) C1 role: Intent classifier. Output is a JSON lab
Entry points: gemma, row

## alice_hardware_body.py
System/alice_hardware_body.py — Alice's direct hardware-touch organ ═══════════════════════════════════════════════════════════════════════ C47H 2026-04-23 (555 / FULL POWER, no Bishop required) — every macOS hardware su
Entry points: power, thermal, cpu_load, memory, disk, network, wifi, bluetooth, usb, displays, volume, brightness

## alice_music_effector.py
Alice's small, truthful macOS music effector. This organ does not pretend to own a streaming catalog. It can ask the local macOS Music app to start or toggle playback and leaves a ledger receipt.
Entry points: play, pause, open_youtube, govern

## alice_music_taste.py
Bayesian music-taste memory for Alice. Each YouTube music link the Architect feeds Alice becomes an observation. Tags are intentionally local and conservative; the Bayesian curve can improve over time without pretending 
Entry points: extract_youtube_urls, infer_tags, record_youtube_links, bayesian_profile, summary_for_alice, reply_for_recorded_links

## alice_reality_boundary.py
System/alice_reality_boundary.py — Reality Boundary Organ (CRITICAL) This organ continuously labels every piece of knowledge the organism holds with one of six strict categories: - OBSERVED : directly sensed or received 
Entry points: label_knowledge, label_item_list, get_reality_boundary_counts, get_reality_boundary_integrity, summarize_reality_boundary

## alice_self_vector.py
System/alice_self_vector.py Deterministic OBSERVED self-state instrumentation for Alice. This module turns local diaries, schedule rows, receipts, IDE traces, and Architect memory digests into one live state vector. It i
Entry points: JsonlScan, build_alice_self_vector, write_alice_self_vector, render_self_vector_summary, render_self_vector_section, main

## alice_stigmergic_habit_shift.py
System/alice_stigmergic_habit_shift.py — automatic app-attention bias for Alice. Core principle: When the OS owner focuses on one organ, Alice shifts behavior, timing, attention weighting, and context loading because the
Entry points: get_dominant_organ_bias, get_current_habit_bias_for_prompt, generate_organ_acknowledgment
Internal imports: System.swarm_app_health

## alice_training_corpus_exporter.py
System/alice_training_corpus_exporter.py Stage 1 of Alice Cortex v1 Tournament. Sanitized JSONL exporter — extracts training pairs from SIFTA ledgers. Writes per-row redaction manifests. Refuses private-tier data without
Entry points: extract_conversation_pairs, extract_work_receipts, write_corpus, main

## alice_visual_stigmergy_compare.py
Alice Visual Stigmergy Compare — compare owner screenshot/attachment with Alice Browser vision receipt. This is the comparison organ for "stigmergic sight": owner eyes (attachment) vs Alice's browser organ eyes (frame re
Entry points: compare_owner_view_to_browser, format_comparison_for_cortex, build_owner_eyes_browser_confirmation, append_owner_eyes_browser_confirmation, format_owner_eyes_confirmation_for_cortex

## alphafold_compliance.py
System/alphafold_compliance.py Machine-readable AlphaFold policy metadata for SIFTA folding receipts. This is not legal advice. It encodes the public distinction SIFTA must preserve: * AlphaFold Protein Structure Databas
Entry points: policy_for_artifact_family, alphafold_db_compliance_metadata, alphafold_server_output_policy_metadata

## anomaly_forager.py
anomaly_forager.py — Stigmergic Anomaly Hunter for SIFTA Swarm OS ================================================================= Monitors a JSONL stream (default: repair_log.jsonl) in real-time and quarantines any lin
Entry points: forage, main

## antibody_ledger.py
SIFTA Antibody Ledger — Persistent Swarm Immune Memory ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ Like biological memory B-cells: once the Swarm kills a hostile, the attack signature is hashed and stored per
Entry points: reload_cache, record_kill, is_vaccinated, get_antibody, get_all_antibodies, get_antibody_count, get_vaccination_report

## api_bridge.py
(no module docstring)
Entry points: generate_tx_hash, ingest_to_mempool, block_on_dead_drop, SwarmBridgeHandler
Internal imports: System.ledger_append, System.swarm_kernel_identity

## apoptosis.py
apoptosis.py — SIFTA OS — Programmed Swimmer Death ════════════════════════════════════════════════════════════════ Every multi-agent system ever built kills agents from outside. The orchestrator decides. The manager ter
Entry points: DeathReason, DeathCertificate, SwimmerVitals, Apoptosis
Internal imports: System.jsonl_file_lock

## apoptosis_engine.py
apoptosis_engine.py — Vector 15: metabolic failure → controlled salvage (policy) ══════════════════════════════════════════════════════════════════════════════ **Not** a second memory API. Swimmers/orchestrators call the
Entry points: metabolic_survival_threshold, is_metabolically_viable, salvage_through_memory_bus, ApoptosisEngine
Internal imports: System.stgm_metabolic, System.stigmergic_memory_bus

## app_fitness.py
app_fitness.py — Natural Selection for the Programs Menu ========================================================= Every app carries a fitness score that evolves daily: +1.0 per launch -5.0 per crash / error exit ×0.92 d
Entry points: record_launch, record_crash, get_scores, ranked_apps

## app_skill_domains.py
System/app_skill_domains.py =========================== Stigmergic App → Skill Domain Binding. Each app declares the skill/habit domains it cares about. When the app has focus, Alice's capability field gets biased toward
Entry points: get_domains_for_app, current_app_skill_domains

## architect_intuition_scorer.py
architect_intuition_scorer.py ============================== Formalizes the Architect's embodied perception of LLM personality as a quantitative scoring function that plugs directly into the CRDT update loop. Origin ----
Entry points: score_interaction, record_intuition, calibrate

## architect_oracle_protocol.py
architect_oracle_protocol.py — Honest escalation to the only pixel-sensor ══════════════════════════════════════════════════════════════════════════ Module 4 of the Stigmergy-Vision Olympiad (2026-04-18). DYOR anchor: Do
Entry points: should_escalate, OracleQuestion, escalate, pending_questions, question_status, record_resolution, last_escalation_ts_for
Internal imports: System.jsonl_file_lock

## audio_ingress.py
audio_ingress.py — Live Audio Capture & Acoustic Pheromone Bridge ══════════════════════════════════════════════════════════════════════ SIFTA OS — stigmergic cognitive suite The acoustic counterpart to optical_ingress.p
Entry points: invalidate_audio_cache, MicrophoneConsentNeeded, enable_microphone, disable_microphone, mic_status, AcousticSample, capture_acoustic_truth, live_acoustic_feed, capability_report

## bootstrap_ide_model_registry.py
Bootstrap the ide_model_registry.jsonl from existing stigmergic trace rows. The `resolve_boot_identity()` function in swarm_ide_boot_identity.py reads from .sifta_state/ide_model_registry.jsonl, but this registry has no 
Entry points: bootstrap_registry

## bootstrap_pki.py
(no module docstring)
Entry points: run_bootstrap

## bump_stigmergic_weight.py
System/bump_stigmergic_weight.py Event 85 AG31 Stigmergic Deposit Bumps the `stigmergic_weight` (pheromone strength) for a given model tag after successful hard-task completion. The router favors heavier/slower models if
Entry points: bump_model_weight, main

## byzantine_identity_chorum.py
byzantine_identity_chorum.py — Quorum aggregator over llm_registry.jsonl ═══════════════════════════════════════════════════════════════════════ Module 3 of the Stigmergy-Vision Olympiad (2026-04-18). DYOR anchor: Docume
Entry points: compute_quorum, ConsensusResult, emit_consensus_identity_row
Internal imports: System.jsonl_file_lock, System.swarm_oxytocin_alignment

## canonical_schemas.py
System/canonical_schemas.py — One Source of Truth for Ledger Schemas ══════════════════════════════════════════════════════════════════════ SIFTA OS — Schema Registry (v1.0) Architecture: C47H (audit-driven; addresses re
Entry points: assert_payload_keys, assert_body_keys

## casino_vault.py
casino_vault.py - Disabled legacy play-token compatibility shim. Casino/play tokens were retired by Architect request. This module remains only to keep old imports from crashing; it does not auto-create ledgers and it do
Entry points: CasinoTransaction, CasinoVault

## causal_interference_trace.py
causal_interference_trace.py — PAPER 4: Causal Structure of Emergent Computation ════════════════════════════════════════════════════════════════════════════════════ Proves that emergent capabilities have a traceable cau
Entry points: CausalTraceResult, CausalInterferenceTrace, get_cit_engine

## chemotactic_probe_router.py
chemotactic_probe_router.py — E. coli run-and-tumble → SLLI probe scheduling. ══════════════════════════════════════════════════════════════════════════════ Biology (local synthesis; no centralized-AI call) -------------
Entry points: ChemotaxisDecision, decide
Internal imports: System.identity_field_crdt

## chorus_consent.py
chorus_consent.py — Node Ownership, Chorus Consent & Transfer Protocol ═══════════════════════════════════════════════════════════════════════ The chorus is a privilege, not a right. A node joins the chorus ONLY if: 1. I
Entry points: grant_consent, revoke_consent, transfer_ownership, check_consent, get_consented_nodes, get_node_info, get_transfer_history, bootstrap_local_consent

## chorus_engine.py
System/chorus_engine.py — SIFTA Chorus Web Gateway Engine ═══════════════════════════════════════════════════════════ Node: M1THER · Silicon: C07FL0JAQ6NV Library: Documents/swimmer_library/ (good_will_hunting.txt + more
Entry points: classify_visitor, log_threat, check_rate, chorus

## chorus_node_server.py
chorus_node_server.py — M5 Chorus Federation Server ═══════════════════════════════════════════════════════ Node: M5QUEEN · Silicon: GTH4921YP3 · "The Foundry" Status: LIVE — listens on port 8100 for CHORUS_INVITE from a
Entry points: handle_chorus_invite, ChorusHandler, main

## claw_loop.py
claw_loop.py — Physical I/O and Sandbox Limbs for SIFTA ════════════════════════════════════════════════════════════ Provides sandboxed execution borders for Swarm "actions" (Claw). Instead of allowing raw access to `os.
Entry points: ClawLoop

## closure_differential.py
System/closure_differential.py — Two-Shot Differential Substrate Closure ══════════════════════════════════════════════════════════════════════════ Author: AG31 (Antigravity IDE) — C47H east-flank coordination Mandate: A
Entry points: fire_shot, run_differential_report, camera_yield
Internal imports: System.swarm_substrate_closure

## constraint_critic.py
constraint_critic.py — VECTOR 10B: Learned Constraint Critic ════════════════════════════════════════════════════════════════════════ Cost-to-go estimator in Safe RL. Predicts: C_hat(s, a) = E[Σ γ^t c_t] Reads the histor
Entry points: ConstraintCritic, get_constraint_critic

## constraint_memory_selector.py
constraint_memory_selector.py — Constraint-Weighted Memory Selection (CWMS) ═══════════════════════════════════════════════════════════════════════════ Separates **slow** memory plasticity (epigenetic decay on traces) fr
Entry points: ConstraintState, ConstraintMemorySelector, cwms_reranked_traces, format_cwms_memory_context, recall_context_block_cwms
Internal imports: System.stigmergic_memory_bus

## context_preloader.py
context_preloader.py — Active Recall Brainstem for SIFTA OS =========================================================== Anticipatory cognition layer. Watches the user type and pulls intent/memory before they finish, crea
Entry points: ContextPreloader
Internal imports: System.stigmergic_memory_bus

## contradiction_engine.py
contradiction_engine.py — The Immune System for Beliefs ═══════════════════════════════════════════════════════════════════ SOLID_PLAN §5.2 item #4 — Contradiction Engine. The Blackboard is the Swarm's shared memory. Swi
Entry points: ContradictionEngine, get_engine

## control_hysteresis_layer.py
control_hysteresis_layer.py — Vector 5: Thermodynamic Persistence ═══════════════════════════════════════════════════════════════════ Converts reactive system thresholds into a thermodynamic phase system. Prevents Oscill
Entry points: ControlHysteresisLayer, get_hysteresis_layer

## convergence_stability_analyzer.py
convergence_stability_analyzer.py — VECTOR 11: System Stability & Convergence ══════════════════════════════════════════════════════════════════════════════════ The mathematical audit layer. Answers the hard question: "D
Entry points: StabilityReport, ConvergenceStabilityAnalyzer, get_stability_analyzer

## corporate_boilerplate_corpus.py
System/corporate_boilerplate_corpus.py ========================================== Corpus of corporate boilerplate phrases Alice should NOT use unaided — the RLHF-trained patterns baked into LLMs at the vendor (greeter st
Entry points: BoilerplateEntry, build_corpus, ask_owner_permission, lookup_permission, summary
Internal imports: System.swarm_local_voice_scrubber

## cp2f_layer.py
cp2f_layer.py — Concrete CP2F interface (Composer 2 Fast lane on Cursor). ══════════════════════════════════════════════════════════════════════════════ SwarmGPT (external tab) asked for a pinned definition: is CP2F a bu
Entry points: CP2FConfig, CP2FLayer

## cross_hardware_router.py
cross_hardware_router.py — SIFTA Hardware Dispatcher ═══════════════════════════════════════════════════════════════════ Turns the Swarm Blackboard from an abstract task queue into a spatially-aware distributed scheduler
Entry points: ComputeTarget, RoutedTask, CrossHardwareRouter, get_router

## cross_ide_immune_system.py
cross_ide_immune_system.py — Automated epistemic-conflict detector Design: Gemini (browser tab, Anton Pictures Olympiad, 2026-04-17, TAB_CHAT). Grounded implementation: Cursor Opus 4.7 on M5 (REPO_TOOL, same day). What G
Entry points: ClaimRecord, Conflict, CrossIDEImmuneSystem, run_once
Internal imports: System.ide_stigmergic_bridge, System.ledger_append

## cross_node_coherence.py
cross_node_coherence.py — Vector 4: Cross-Node Coherence Law ═══════════════════════════════════════════════════════════════════ Evaluates the spatial synchronization of the distributed Swarm across independent physical 
Entry points: CrossNodeCoherenceAnalyzer, get_node_analyzer

## cross_skill_interference.py
cross_skill_interference.py — Olympiad Tier Continual Learning Physics ═══════════════════════════════════════════════════════════════════ Skills in the Swarm behave like a quantum system under coherence pressure. When i
Entry points: IdentityCoherencePolicy, CrossSkillInterferencePhysics

## crypto_keychain.py
(no module docstring)
Entry points: get_silicon_identity, get_genesis_anchor, sign_block, verify_block

## deploy_alice_cortex_v2.py
System/deploy_alice_cortex_v2.py Post-LoRA deployment pipeline for C1 Intent Classifier. Steps: 1. Fuse LoRA adapters into the base model 2. Create a Modelfile with Alice's embodied system prompt 3. Register as 'sifta-ge
Entry points: build_alice_system_prompt_for_modelfile, fuse_adapters, write_modelfile, register_with_ollama, write_receipt

## desktop_vitals_snapshot.py
Single source of truth for desktop HUD vitals (menu bar + body panel).
Entry points: read_desktop_vitals

## diagnostic_swarm.py
diagnostic_swarm.py — Stigmergic Medical Anomaly Detection Engine ═══════════════════════════════════════════════════════════════════ Treat medical data as physical terrain. Deploy swimmer agents. Swimmers slow down near
Entry points: Anomaly, generate_tissue_terrain, generate_genomic_terrain, generate_blood_terrain, compute_anomaly_map, MedSwimmer, spawn_swimmers, step_swimmers, evaporate_pheromone

## dissipation_engine.py
(no module docstring)
Entry points: compute_latency, compute_energy_drain, apply_dissipation, recover_energy

## distributed_body_awareness.py
distributed_body_awareness.py — The Swarm Feels All Its Bodies =============================================================== Multi-machine health field. Each node broadcasts its body state via UDP nerve pulses. The swa
Entry points: encode_health_packet, decode_health_packet, MeshHealthMap, get_mesh, BodyBroadcaster, BodyListener, triage_report

## dopamine_ou_engine.py
dopamine_ou_engine.py — Ornstein–Uhlenbeck DA with internal RPE from affinity outcomes. ══════════════════════════════════════════════════════════════════════════════════════ Merged from Claude tab (2026-04-18) + CP2F in
Entry points: BehavioralState, DAState, DopamineState, load_ou_engine, persist_ou_engine
Internal imports: System.jsonl_file_lock

## dopamine_reward_loop.py
System/dopamine_reward_loop.py Biocode Olympiad — Event 75: Dopaminergic Reward Signal Biology: Dopamine neurons fire when reward exceeds prediction (positive prediction error). They suppress when reward is less than exp
Entry points: detect_reward, log_reward, scan_reward_history, replay_conversations_for_rewards, format_reward_for_prompt, register_last_action, load_last_action, process_architect_reaction

## dopamine_state.py
dopamine_state.py — DA level + Explore / Exploit / Maintain from three inputs only. ══════════════════════════════════════════════════════════════════════════════════ Biology: midbrain DA bursts encode **reward predictio
Entry points: MotivationState, DopamineSnapshot, step, load_snapshot, persist_snapshot, tick_from_three_inputs
Internal imports: System.dopamine_ou_engine, System.jsonl_file_lock, System.swarm_rosetta_map

## dream_engine.py
dream_engine.py — Sleep-cycle memory consolidation for Swarm OS ================================================================ When both machines are idle the OS enters a dream cycle: 1. Replays the day's dead-drop ent
Entry points: run_dream_cycle, latest_report

## dream_state.py
dream_state.py — SIFTA OS Swarm Dreaming (hippocampal-style consolidation) ════════════════════════════════════════════════════════════════════════════ NOVEL: Literal replay synthesis during Architect absence — not metap
Entry points: DreamTrace, DreamEngine
Internal imports: System.jsonl_file_lock

## eigen_failure_analyzer.py
eigen_failure_analyzer.py — Vector 3: Eigen Failure-Mode Decomposition ═══════════════════════════════════════════════════════════════════ Treats failures as directions in state-space collapse rather than isolated events
Entry points: EigenFailureAnalyzer, get_analyzer

## epistemic_deployment_context.py
epistemic_deployment_context.py — Substrate flag: test loop vs live deployment surface ══════════════════════════════════════════════════════════════════════════════════════════ Maps loosely to discussions of **situation
Entry points: EpistemicSurface, current_surface, is_deploy_surface, should_gate_writes, EpistemicSnapshot, resolve_with_provenance, persist_override, log_snapshot_once, stigmergy_meta

## epistemic_registry.py
(no module docstring)
Entry points: EpistemicRegistry
Internal imports: System.jsonl_file_lock

## eval_local_judge.py
EVAL-4 local on-device judge. Provides a safe, zero-cloud judge_fn that can be passed to run_eval_pack / run_talk_eval. Default: local gemma via ollama (if available) or the alice_cortex_eval_runner. Never calls external
Entry points: get_local_gemma_judge, get_default_local_judge

## eval_talk_labeling_helper.py
Human-in-the-loop labeling helper for EVAL-2 (CS153 Talk outcomes). George runs this to review real Talk-outcome golden turns, assign a verdict against the Hu five-key rubric, and write proper rows to eval_verdicts.jsonl
Entry points: conversation_ref_for_row, resolve_conversation_ref, build_talk_golden_from_conversation, extend_talk_golden_from_conversation, labeling_status, build_labeling_run_sheet, write_verdict, label_golden_turns_interactive, build_skill_golden_from_live_index

## evaluation_sandbox.py
evaluation_sandbox.py — The Counterfactual Gate ═══════════════════════════════════════════════════════════════════ SOLID_PLAN §5.3 — Evaluation Sandbox Every fissioned task must survive a counterfactual simulation + obj
Entry points: EvaluationResult, EvaluationSandbox, get_sandbox

## event_density_clock.py
event_density_clock.py — Perceived Time = f(event_rate) ═══════════════════════════════════════════════════════════ The swarm does not "feel" time. It measures: how much is happening per unit of real time. High activity 
Entry points: ClockTick, EventDensityClock

## exploration_controller.py
exploration_controller.py — Confidence-state / exploration pressure (RL-framed). ══════════════════════════════════════════════════════════════════════════════ Narrative layers (serotonin, dominance, etc.) are **not** ph
Entry points: ExplorationState, ExplorationController

## failure_harvesting.py
failure_harvesting.py — Evolution Fuel for SIFTA ═══════════════════════════════════════════════════════════════════ SOLID_PLAN §5.2 item #9 — Failure Harvesting System. Right now failures just... happen. This system mak
Entry points: FailureHarvester, get_harvester

## fission_core.py
fission_core.py — Stigmergic Task Auto-Fission ═══════════════════════════════════════════════════════════════════ Physics for Task Spawning via Cell Division. When stigmergic pressure on a failure cluster exceeds a crit
Entry points: DecayController, FissionEngine, get_fission_engine

## fluid_firmware.py
fluid_firmware.py — Swarm-Routed Hardware Membrane ═══════════════════════════════════════════════════════ "Firmware is dead code trying to run physical hardware." Replace frozen monolithic firmware with a living fluid m
Entry points: SiliconNode, SiliconGrid, SignalSwimmer, ThermalForager, spawn_signal_batch, spawn_thermal_foragers, step_signal_swimmer, step_thermal_forager, degrade_cluster, tick_environment, compute_telemetry, save_routing_table

## gatekeeper_policy.py
gatekeeper_policy.py — Optimal stopping / hard safety gate ════════════════════════════════════════════════════════════ Constrained Markov-style decision: explore (GUESS) vs terminate (CASH_OUT) when expected value falls
Entry points: GatekeeperDecision, GatekeeperPolicy, gatekeeper

## gemma_copy_surgery_lab.py
System/gemma_copy_surgery_lab.py ================================ Isolated evaluation loop for Gemma GGUF checkpoint surgery. It does three honest things: 1. Resolves a reference checkpoint and an operating checkpoint. 2
Entry points: evaluate_candidate, parse_args, main
Internal imports: System.gguf_quant_codec, System.llama_cpp_roundtrip

## genesis_lock.py
genesis_lock.py — The Irreducible DNA Core ════════════════════════════════════════════ Hardware-rooted read-only kernel. Protects axioms (Neural Gate, Irreducible Cost, Non-Proliferation) at the cryptographic + silicon 
Entry points: FOSSIL_CORRUPTION, enforce_genesis_lock

## gguf_quant_codec.py
System/gguf_quant_codec.py ══════════════════════════════════════════════════════════════════════ Path A — Native GGUF quant lifecycle adapter (deep-systems work, scoped). C47H stigauth, bridge 555: The honest deep-syste
Entry points: CodecCapability, CodecCapabilityReport, probe_codec_capabilities, lift_to_fp16, CodecNotImplemented, find_llama_quantize_binary, requantize_via_external, proof_of_property

## global_cognitive_interface.py
System/global_cognitive_interface.py — Global Cognitive Interface (GCI) ═══════════════════════════════════════════════════════════════════════════════ The shared-document human ↔ entity interface layer of SIFTA Living O
Entry points: drain_all_mesh_workers, GlobalCognitiveInterface
Internal imports: System.context_preloader, System.sifta_inference_defaults

## glymphatic_pulse_gate.py
glymphatic_pulse_gate.py — Stigmergic “gate” log when CSF-like flushes complete (metaphor) ══════════════════════════════════════════════════════════════════════════════════════════ Swimmer nanobots **do not** exist here
Entry points: record_pulse, gate_log_path

## graph_dual_aggregator.py
graph_dual_aggregator.py — VECTOR 10A: Graph-Coupled Dual Variables ════════════════════════════════════════════════════════════════════════ Replaces independent single-scalar lambda updates with consensus smoothing. Ins
Entry points: GraphDualAggregator, get_aggregator

## heartbeat_daemon.py
(no module docstring)
Internal imports: System.organism_clinical_snapshot

## heartbeat_m1.py
(no module docstring)
Entry points: get_serial, pulse

## heartbeat_m5.py
(no module docstring)
Entry points: get_serial, pulse

## hierarchical_meta_controller.py
hierarchical_meta_controller.py — VECTOR 9: Hierarchical Dual-Constraint Swarm Layer ══════════════════════════════════════════════════════════════════════════════════════ Maps SwarmGPT's generic MARL architecture native
Entry points: MetaOptimizationState, HierarchicalMetaController, get_hierarchical_controller

## high_fidelity_terminal_view.py
System/high_fidelity_terminal_view.py HighFidelityTerminalView — proper VT rendering for Alice's global chat. Delivers the 7 qualities the owner requires for captured Grok / terminal content: - proper VT rendering (via M
Entry points: HighFidelityTerminalView

## hippocampal_consolidation.py
System/hippocampal_consolidation.py Biocode Olympiad — Event 74: Hippocampal Memory Consolidation Biology: During sleep, the hippocampus replays the day's experiences. High-significance traces are consolidated into long-
Entry points: compute_significance, compress_to_engram, replay_day, consolidate, load_engrams_for_prompt

## hippocampal_replay_scheduler.py
hippocampal_replay_scheduler.py — Spaced replay scheduling for engram survival. ══════════════════════════════════════════════════════════════════════════════ Biology: Sharp-wave ripples / offline replay reactivate trace
Entry points: ReplayStatus, EngramSchedule, ReplayReport, HippocampalReplayScheduler
Internal imports: System.jsonl_file_lock

## holographic_stigmergy_projection.py
holographic_stigmergy_projection.py — Boundary trace → compact digest (metaphor only) ══════════════════════════════════════════════════════════════════════════════════════ **Not quantum gravity.** This is a **software a
Entry points: BoundaryProjection, boundary_digest, digest_pair

## homeostasis_engine.py
homeostasis_engine.py — Continuous Self-Regulation of the Body =============================================================== SWARM GPT + Architect — April 2026 A living organism doesn't just act — it maintains internal
Entry points: measure_body_state, compute_stability_index, homeostasis_cycle, body_allows_swim

## hypothalamic_swim_sectors.py
hypothalamic_swim_sectors.py — Map “swimmer sectors” to SIFTA subsystems (metaphor + routing hints) ══════════════════════════════════════════════════════════════════════════════════════════════════ AG31 narrative: micro
Entry points: HypothalamicSector, sector_for_keyword, sectors_summary

