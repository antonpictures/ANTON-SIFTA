# SIFTA App Hardening Queue - 2026-06-14

Generated from `Applications/apps_manifest.json` without launching GUI apps.
George types only to Alice in global chat. IDE arms harden apps one by one; WE CODE TOGETHER only shows receipts/STGM.

## Summary

- Manifest apps: `148`
- P0: `1`
- P1: `0`
- P2: `3`
- P3: `144`

## Owner Split

- Codex: total `30` | P0 `0` | P1 `0` | P2 `0` | P3 `30`
- Grok: total `30` | P0 `1` | P1 `0` | P2 `0` | P3 `29`
- MiMo: total `30` | P0 `0` | P1 `0` | P2 `2` | P3 `28`
- Cline: total `29` | P0 `0` | P1 `0` | P2 `1` | P3 `28`
- Cursor: total `29` | P0 `0` | P1 `0` | P2 `0` | P3 `29`

## Rules

- One app per patch unless a shared helper is required.
- No owner-click write UI. George types to Alice; apps may display receipts/STGM.
- Every mutation gets a four-ledger receipt and a tournament row.
- Tests scale with risk: at minimum py_compile + manifest/class regression for each app.
- Do not overclaim runtime behavior until launched or covered by a UI smoke harness.

## Queue

| # | Priority | Owner | App | Entry | Widget | Issues |
|---:|---|---|---|---|---|---|
| 1 | P3 | Codex | AG31 + C46S + C55M + CG55M - ARTIFFICIAL GENERAL INTELLIGENCE. | `Applications/sifta_artificial_general_intelligence.py` | `AGIWindow` | ok |
| 2 | P3 | Grok | AG31 + C46S - PoUW Fold-Swarm Simulation | `Applications/fold_swarm_pouw_sim.py` | `PredatorSimWindow` | ok |
| 3 | P3 | MiMo | AG31 + C55M - Primordial Field | `Applications/sifta_primordial_field.py` | `PrimordialFieldWidget` | ok |
| 4 | P3 | Cline | AG31 - Stigmergic Pac-Man | `Applications/sifta_pacman_stigmergic.py` | `PacManGame` | ok |
| 5 | P3 | Cursor | AGI Cognition Dashboard | `Applications/sifta_agi_cognition_dashboard.py` | `AGICognitionDashboard` | ok |
| 6 | P3 | Codex | Ablation Lab | `Applications/sifta_ablation_lab.py` | `AblationLabWidget` | ok |
| 7 | P3 | Grok | Ace | `Applications/sifta_teach_ace_to_read.py` | `TeachAceToReadWidget` | ok |
| 8 | P3 | MiMo | Alice | `Applications/sifta_alice_widget.py` | `AliceWidget` | ok |
| 9 | P3 | Cline | Alice Browser | `Applications/sifta_alice_browser_widget.py` | `AliceBrowserWidget` | ok |
| 10 | P3 | Cursor | Alice Gaze Monitor | `Applications/sifta_gaze_monitor_widget.py` | `GazeMonitorWidget` | ok |
| 11 | P3 | Codex | Alice Journal | `Applications/sifta_alice_journal_widget.py` | `AliceJournalWidget` | ok |
| 12 | P3 | Grok | Alice Journal Viewer | `Applications/sifta_alice_journal_viewer.py` | `AliceJournalViewer` | ok |
| 13 | P3 | MiMo | Alice Safety Tracker | `Applications/sifta_cartography_widget.py` | `CartographyWidget` | ok |
| 14 | P3 | Cline | Alice Self-Evaluation (her body map) | `Applications/sifta_self_evaluation.py` | `SelfEvaluationApp` | ok |
| 15 | P3 | Cursor | Alice Shell | `Applications/sifta_app_manager.py` | `AppManagerWidget` | ok |
| 16 | P3 | Codex | Alice Wellbeing Cortex | `Applications/sifta_alice_wellbeing_panel.py` | `WellbeingPanel` | ok |
| 17 | P3 | Grok | Alice's Legs (Walking Laptop) | `Applications/sifta_legs_humanoid_app.py` | `LegsHumanoidApp` | ok |
| 18 | P3 | MiMo | Alice's Will — Intrinsic Drive Monitor | `Applications/sifta_intrinsic_drive_monitor.py` | `AliceWillApp` | ok |
| 19 | P3 | Cline | Apex Predator Background | `Applications/sifta_predator_desktop_bg.py` | `PredatorDesktopBg` | ok |
| 20 | P3 | Cursor | Apex Predator Perceiver | `Applications/sifta_apex_predator_widget.py` | `ApexPredatorWidget` | ok |
| 21 | P3 | Codex | App Manager | `Applications/sifta_app_manager.py` | `AppManagerWidget` | ok |
| 22 | P3 | Grok | Aquaculture Field Sentinel | `Applications/sifta_aquaculture_sentinel_widget.py` | `AquacultureFieldSentinelWidget` | ok |
| 23 | P3 | MiMo | Arena | `Applications/sifta_arena.py` | `Arena` | ok |
| 24 | P3 | Cline | Autopoiesis Monitor | `Applications/sifta_agi_cognition_dashboard.py` | `AGICognitionDashboard` | ok |
| 25 | P3 | Cursor | Awareness Mirror | `Applications/sifta_awareness_mirror_widget.py` | `AwarenessMirrorApp` | ok |
| 26 | P3 | Codex | Bauwens Regenerative Factory | `Applications/sifta_factory_widget.py` | `FactoryWidget` | ok |
| 27 | P3 | Grok | Bell's Theorem — Classical Analogue | `Applications/sifta_bell_theorem_widget.py` | `BellTheoremWidget` | ok |
| 28 | P3 | MiMo | Biological Dashboard | `Applications/sifta_biological_dashboard_qt.py` | `BiologicalDashboardWidget` | ok |
| 29 | P3 | Cline | Body Chat GUI | `Applications/sifta_desktop_gui.py` | `SIFTABodyChatGUI` | ok |
| 30 | P3 | Cursor | Bonsai Image Studio (AI Vision) | `Applications/sifta_bonsai_image_app.py` | `BonsaiImageStudioApp` | ok |
| 31 | P3 | Codex | Brain Gas-Station Meter | `Applications/sifta_gasstation_meter.py` | `GasStationMeterWidget` | ok |
| 32 | P3 | Grok | Buzdugan LCR | `Applications/sifta_buzdugan_lcr.py` | `BuzduganLCRWidget` | ok |
| 33 | P3 | MiMo | C55M + George - Protein Fold Colosseum | `Applications/sifta_protein_folder_widget.py` | `ProteinFolderWidget` | ok |
| 34 | P3 | Cline | C55M Dr Codex - Physarum Contradiction Lab | `Applications/sifta_physarum_contradiction_lab.py` | `PhysarumContradictionLabWidget` | ok |
| 35 | P3 | Cursor | CG55M Dr Cursor - Alice Life Schedule | `Applications/sifta_life_dashboard.py` | `StigmergicLifeDashboard` | ok |
| 36 | P3 | Codex | CG55M Dr Cursor - Alice-Sees Calibrator (Game) | `Applications/sifta_calibrator_widget.py` | `CalibratorWidget` | ok |
| 37 | P3 | Grok | CG55M Dr Cursor - Slime-Mold Bank: Push to Mint | `Applications/sifta_slime_mold_bank.py` | `SlimeMoldBankWidget` | ok |
| 38 | P2 | MiMo | Cardio Metrics | `Applications/sifta_cardio.py` | `` | missing_widget_class |
| 39 | P2 | Cline | Circadian Rhythm | `Applications/circadian_rhythm.py` | `` | missing_widget_class |
| 40 | P3 | Cursor | Clock Settings | `Applications/sifta_clock_settings.py` | `ClockSettingsApp` | ok |
| 41 | P3 | Codex | Code Knowledge Graph | `Applications/sifta_code_graph_viewer.py` | `CodeKnowledgeGraphWidget` | ok |
| 42 | P3 | Grok | Colloid Simulator | `Applications/sifta_colloid_sim.py` | `SIFTAColloidSimulation` | ok |
| 43 | P3 | MiMo | Control Center | `Applications/sifta_control_center.py` | `GlassWidget` | ok |
| 44 | P3 | Cline | Conversation History | `Applications/sifta_conversation_browser.py` | `ConversationBrowserApp` | ok |
| 45 | P3 | Cursor | Cool Worlds × SIFTA — Contact Inequality | `Applications/cool_worlds_contact.py` | `ContactInequalityApp` | ok |
| 46 | P3 | Codex | Corporate Gag Monitor (Lysosome Residue) | `Applications/sifta_corporate_gag_monitor.py` | `CorporateGagMonitorApp` | ok |
| 47 | P3 | Grok | Cortex Wake Lab | `Applications/sifta_cortex_wake_lab.py` | `CortexWakeLabWidget` | ok |
| 48 | P2 | MiMo | Cosmos-Reason1-7B Organ | `System/swarm_cosmos_reason1.py` | `` | missing_widget_class |
| 49 | P3 | Cline | Council GUI | `Applications/council_gui.py` | `CouncilRobinhoodApp` | ok |
| 50 | P3 | Cursor | Crucible Cyber-Defense (10-min) | `Applications/sifta_sim_stream_panels.py` | `CrucibleStreamWidget` | ok |
| 51 | P3 | Codex | Crucible Simulator | `Applications/crucible_sim.py` | `CrucibleWindow` | ok |
| 52 | P3 | Grok | Crucible Swarm Sim | `Applications/sifta_crucible_swarm_sim.py` | `CrucibleSim` | ok |
| 53 | P3 | MiMo | Cyborg Body | `Applications/sifta_cyborg_body.py` | `CyborgWindow` | ok |
| 54 | P3 | Cline | Cyborg Organ Simulator | `Applications/sifta_sim_stream_panels.py` | `CyborgPanelWidget` | ok |
| 55 | P3 | Cursor | Double-Slit — Swimmers Through the Slit | `Applications/sifta_double_slit_stigmergic.py` | `DoubleSlitWidget` | ok |
| 56 | P3 | Codex | EPR Paradox — Stigmergic Dissolution | `Applications/sifta_epr_stigmergic_widget.py` | `EPRStigmergicWidget` | ok |
| 57 | P3 | Grok | Epistemic Mesh (Anti-Gaslight) | `Applications/epistemic_mesh_widget.py` | `EpistemicMeshWidget` | ok |
| 58 | P3 | MiMo | Finance | `Applications/sifta_finance.py` | `FinanceDashboard` | ok |
| 59 | P3 | Cline | Fluid Firmware | `Applications/sifta_firmware_widget.py` | `FirmwareWidget` | ok |
| 60 | P3 | Cursor | Ghost StigmergiCity | `Applications/sifta_ghost_stigmericity_widget.py` | `GhostStigmericityApp` | ok |
| 61 | P3 | Codex | Higgs Stigmergic Demo Path (§20.B) | `Applications/sifta_higgs_stigmergic_demo_path_widget.py` | `HiggsStigmergicDemoPathApp` | ok |
| 62 | P3 | Grok | IDE Control Panel | `Applications/sifta_ide_control_panel.py` | `IdeControlPanelWidget` | ok |
| 63 | P3 | MiMo | Intelligence Settings | `Applications/sifta_settings.py` | `SettingsWindow` | ok |
| 64 | P3 | Cline | IoT Swarm Connector | `Applications/sifta_iot_connector.py` | `IoTConnectorWidget` | ok |
| 65 | P3 | Cursor | LTO Cold Archive (demo) | `Applications/sifta_lto_archive_demo_widget.py` | `LtoArchiveDemoWidget` | ok |
| 66 | P3 | Codex | Mammal Unified Field | `Applications/sifta_mammal_unified_field_widget.py` | `MammalUnifiedFieldApp` | ok |
| 67 | P3 | Grok | Matrix Terminal | `Applications/sifta_matrix_terminal.py` | `MatrixTerminalApp` | ok |
| 68 | P3 | MiMo | Mondaloy Stigmergic Research Field | `Applications/sifta_mondaloy_research_widget.py` | `MondaloyResearchFieldApp` | ok |
| 69 | P3 | Cline | NVIDIA Bridge Dashboard | `Applications/sifta_nvidia_sifta_bridge_widget.py` | `NvidiaSiftaBridgeWidget` | ok |
| 70 | P3 | Cursor | NVIDIA × SIFTA | `Applications/sifta_nvidia_join_widget.py` | `NvidiaJoinWidget` | ok |
| 71 | P3 | Codex | Network Control Center | `Applications/sifta_network_center.py` | `NetworkCenterWidget` | ok |
| 72 | P3 | Grok | Organism Doctor | `Applications/sifta_organism_doctor.py` | `OrganismDoctorWidget` | ok |
| 73 | P3 | MiMo | Owner Genesis | `Applications/sifta_genesis_widget.py` | `GenesisWidget` | ok |
| 74 | P3 | Cline | Pheromone Symphony (Generative Music) | `Applications/sifta_pheromone_symphony.py` | `PheromoneSymphonyApp` | ok |
| 75 | P3 | Cursor | Provider Schedule | `Applications/sifta_provider_schedule_widget.py` | `ProviderScheduleWidget` | ok |
| 76 | P3 | Codex | RESA SS-SA Substation Simulator | `Applications/sifta_resa_substation_sim.py` | `ResaSubstationSimWidget` | ok |
| 77 | P3 | Grok | Research Simulators (Quantum & Epi) | `Applications/sifta_quantum_epi_sim.py` | `QuantumEpiWindow` | ok |
| 78 | P3 | MiMo | SENTINEL-0 Unit-Distance Field | `Applications/sifta_sentinel0_unit_distance_widget.py` | `Sentinel0UnitDistanceWidget` | ok |
| 79 | P3 | Cline | SIFTA File Navigator | `Applications/sifta_file_manager_widget.py` | `FileNavigatorWidget` | ok |
| 80 | P3 | Cursor | SIFTA Hermes Parity | `Applications/sifta_hermes_parity_widget.py` | `SiftaHermesParityWidget` | ok |
| 81 | P3 | Codex | SIFTA Home | `Applications/sifta_consumer_home.py` | `SiftaHomeWidget` | ok |
| 82 | P3 | Grok | SIFTA Interstellar Evidence Crucible | `Applications/sifta_interstellar_evidence_crucible.py` | `InterstellarEvidenceCrucibleApp` | ok |
| 83 | P3 | MiMo | SIFTA MAMMAL Lab — Unified Field | `Applications/sifta_stigmergic_mammal_widget.py` | `StigmergicMammalWidget` | ok |
| 84 | P3 | Cline | SIFTA Misalignment Sandbox | `Applications/sifta_misalignment_sandbox.py` | `SiftaMisalignmentSandboxWidget` | ok |
| 85 | P3 | Cursor | SIFTA NLE | `Applications/sifta_nle.py` | `NLEWindow` | ok |
| 86 | P3 | Codex | SIFTA NLE Panel | `Applications/sifta_nle_widget.py` | `NLEWidget` | ok |
| 87 | P3 | Grok | SIFTA PDF Forge | `Applications/sifta_pdf_forge_widget.py` | `PdfForgeWidget` | ok |
| 88 | P3 | MiMo | SIFTA Physics Observatory | `Applications/sifta_physics_observatory.py` | `PhysicsObservatoryWidget` | ok |
| 89 | P3 | Cline | SIFTA Skill Browser | `Applications/sifta_skill_browser.py` | `SkillBrowserApp` | ok |
| 90 | P3 | Cursor | SIFTA Tournament Briefing | `Applications/sifta_tournament_briefing_widget.py` | `TournamentBriefingWidget` | ok |
| 91 | P3 | Codex | SIFTA ∥ OpenAI — Math Benchmarks | `Applications/sifta_openai_math_benchmark_widget.py` | `MathBenchmarkWidget` | ok |
| 92 | P3 | Grok | STGM Immune Economy | `Applications/sifta_immune_economy_widget.py` | `ImmuneEconomyApp` | ok |
| 93 | P3 | MiMo | Sara Imari Walker — Assembly Theory Lab | `Applications/sara_imari_walker_widget.py` | `SaraImariWalkerWidget` | ok |
| 94 | P3 | Cline | Script Couch — Fiction vs Reality Training | `Applications/sifta_lounge_script_couch.py` | `ScriptCouchWidget` | ok |
| 95 | P3 | Cursor | Sense Forge | `Applications/sifta_sense_forge_widget.py` | `SenseForgeWidget` | ok |
| 96 | P3 | Codex | Stigmergic Alzheimer Network Lab | `Applications/sifta_stigmergic_alzheimer_sim.py` | `StigmergicAlzheimerNetworkLabWidget` | ok |
| 97 | P3 | Grok | Stigmergic Ant Foraging Trail | `Applications/sifta_ant_foraging.py` | `StigmergicAntForagingWidget` | ok |
| 98 | P3 | MiMo | Stigmergic Consensus Clustering | `Applications/sifta_consensus_clustering.py` | `StigmergicConsensusClusteringWidget` | ok |
| 99 | P3 | Cline | Stigmergic Deterministic Tracker | `Applications/sifta_stigmergic_deterministic_tracker.py` | `StigmergicDeterministicTracker` | ok |
| 100 | P3 | Cursor | Stigmergic Edge Vision | `Applications/sifta_vision_widget.py` | `VisionSimWidget` | ok |
| 101 | P3 | Codex | Stigmergic FPS.cob Raid | `Applications/games/sifta_fps_cob_stigmergic.py` | `FpsCobStigmergicWidget` | ok |
| 102 | P3 | Grok | Stigmergic FarSight | `Applications/sifta_fieldsight_widget.py` | `SiftaFieldSightWidget` | ok |
| 103 | P3 | MiMo | Stigmergic Fold Swarm (Cα / Go) | `Applications/fold_swarm_widget.py` | `FoldSwarmWidget` | ok |
| 104 | P3 | Cline | Stigmergic Fractals | `Applications/sifta_stigmergic_fractals_widget.py` | `StigmergicFractalsWidget` | ok |
| 105 | P3 | Cursor | Stigmergic Go | `Applications/sifta_stigmergic_go.py` | `StigmergicGoWidget` | ok |
| 106 | P3 | Codex | Stigmergic Graph Coloring | `Applications/sifta_graph_coloring.py` | `StigmergicGraphColoringWidget` | ok |
| 107 | P3 | Grok | Stigmergic Jigsaw | `Applications/sifta_jigsaw_widget.py` | `StigmergicJigsawWidget` | ok |
| 108 | P3 | MiMo | Stigmergic Library | `Applications/sifta_library_reader.py` | `LibraryReaderApp` | ok |
| 109 | P3 | Cline | Stigmergic Mammal Canvas | `Applications/sifta_stigmergic_mammal_canvas.py` | `StigmergicMammalCanvasApp` | ok |
| 110 | P3 | Cursor | Stigmergic Medical Scanner | `Applications/sifta_medscan_widget.py` | `MedScanWidget` | ok |
| 111 | P3 | Codex | Stigmergic Nanobot Tic-Tac-Toe | `Applications/sifta_nanobot_tictactoe.py` | `StigmergicNanobotTicTacToeWidget` | ok |
| 112 | P3 | Grok | Stigmergic Reaction-Diffusion Calculator | `Applications/sifta_reaction_diffusion_calculator.py` | `StigmergicReactionDiffusionCalculatorWidget` | ok |
| 113 | P3 | MiMo | Stigmergic Self-Eval (Alice body map) | `Applications/sifta_stigmergic_self_eval_app.py` | `StigmergicSelfEvaluationApp` | ok |
| 114 | P3 | Cline | Stigmergic Shared Experience Anchors | `Applications/sifta_stigmergic_anchors_widget.py` | `StigmergicAnchorsWidget` | ok |
| 115 | P3 | Cursor | Stigmergic Sudoku | `Applications/sifta_sudoku_widget.py` | `StigmergicSudokuWidget` | ok |
| 116 | P3 | Codex | Stigmergic Swarm Canvas | `Applications/sifta_canvas_widget.py` | `CanvasWidget` | ok |
| 117 | P3 | Grok | Stigmergic Unified Shazam | `Applications/sifta_media_shazam_widget.py` | `MediaShazamApp` | ok |
| 118 | P3 | MiMo | Stigmergic VLC Bridge | `Applications/sifta_stigmergic_vlc.py` | `StigmergicVlcBridge` | ok |
| 119 | P3 | Cline | Stigmergic Video Poker | `Applications/sifta_video_poker.py` | `StigmergicVideoPokerApp` | ok |
| 120 | P3 | Cursor | Stigmergic Writer | `Applications/sifta_writer_widget.py` | `WriterWidget` | ok |
| 121 | P3 | Codex | Stigmerobotics | `Applications/sifta_stigmerobotics_widget.py` | `StigmeroboticsWidget` | ok |
| 122 | P3 | Grok | Swarm Adapter Ecology | `Applications/sifta_swarm_adapter_ecology.py` | `SwarmAdapterEcologyWidget` | ok |
| 123 | P3 | MiMo | Swarm Arena | `Applications/sifta_sim_stream_panels.py` | `ArenaPanelWidget` | ok |
| 124 | P3 | Cline | Swarm Broadcaster | `Applications/sifta_broadcaster_widget.py` | `BroadcasterWidget` | ok |
| 125 | P3 | Cursor | Swarm Browser | `Applications/sifta_swarm_browser.py` | `SwarmBrowserWidget` | ok |
| 126 | P3 | Codex | Swarm Chat | `Applications/sifta_swarm_chat.py` | `SwarmChatWindow` | ok |
| 127 | P3 | Grok | Swarm Field | `Applications/sifta_swarm_visibility_widget.py` | `SwarmFieldWidget` | ok |
| 128 | P3 | MiMo | Swarm Intelligence Panels | `Applications/sifta_intelligence_panels.py` | `AppFitnessPanel` | ok |
| 129 | P3 | Cline | Swarm Logistics Lab | `Applications/sifta_sim_stream_panels.py` | `LogisticsStreamWidget` | ok |
| 130 | P3 | Cursor | Swarm Lounge (Cross-Domain Gossip) | `Applications/sifta_lounge_widget.py` | `LoungeWidget` | ok |
| 131 | P3 | Codex | System Settings | `Applications/sifta_system_settings.py` | `SystemSettingsWidget` | ok |
| 132 | P3 | Grok | Talk to Alice | `Applications/sifta_talk_to_alice_widget.py` | `TalkToAliceWidget` | ok |
| 133 | P3 | MiMo | Teach Alice to Hear | `Applications/sifta_teach_alice_to_hear.py` | `TeachAliceToHearWidget` | ok |
| 134 | P3 | Cline | Territory Is The Law | `Applications/sifta_territory_widget.py` | `TerritoryWidget` | ok |
| 135 | P3 | Cursor | The Architect Room | `Applications/sifta_architect_room_game.py` | `ArchitectRoomGame` | ok |
| 136 | P3 | Codex | Traveling Salesman | `Applications/sifta_tsp_widget.py` | `TSPWidget` | ok |
| 137 | P3 | Grok | Tumor-Immune Stigmergic Lab | `Applications/sifta_tumor_immune_stigmergic_lab.py` | `TumorImmuneStigmergicLab` | ok |
| 138 | P3 | MiMo | Unified Field Slit — Swimmers Inside the Soup | `Applications/sifta_field_swimmers_slit.py` | `FieldSwimmersSlitWidget` | ok |
| 139 | P3 | Cline | Urban Resilience Simulator | `Applications/sifta_sim_stream_panels.py` | `UrbanStreamWidget` | ok |
| 140 | P3 | Cursor | Voice Identity Organ | `Applications/sifta_voice_identity_widget.py` | `VoiceIdentityWidget` | ok |
| 141 | P3 | Codex | WE CODE TOGETHER — MY BODY | `Applications/sifta_we_code_together.py` | `WeCodeTogetherApp` | ok |
| 142 | P3 | Grok | Warehouse Logistics Test | `Applications/sifta_sim_stream_panels.py` | `WarehouseStreamWidget` | ok |
| 143 | P3 | MiMo | What Alice Sees | `Applications/sifta_what_alice_sees_widget.py` | `WhatAliceSeesWidget` | ok |
| 144 | P3 | Cline | WhatsApp Organ | `Applications/sifta_whatsapp_organ.py` | `WhatsAppOrganWidget` | ok |
| 145 | P3 | Cursor | Wormhole — Learn | `Applications/sifta_wormhole_learn.py` | `WormholeLearnApp` | ok |
| 146 | P3 | Codex | YouTube Shazam | `Applications/sifta_youtube_shazam.py` | `SiftaYoutubeShazam` | ok |
| 147 | P0 | Grok | _consolidation_note_2026-05-14 | `` | `` | missing_entry_point |
| 148 | P3 | MiMo | macOS Privacy Cache Scanner | `Applications/sifta_macos_privacy_cache_scanner.py` | `MacOSPrivacyCacheScannerApp` | ok |
