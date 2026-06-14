# SIFTA App Hardening Queue - 2026-06-14

Generated from `Applications/apps_manifest.json` without launching GUI apps.
George types only to Alice in global chat. IDE arms harden apps one by one; WE CODE TOGETHER only shows receipts/STGM.

## Summary

- Manifest apps: `132`
- P0: `1`
- P1: `0`
- P2: `3`
- P3: `128`

## Owner Split

- Codex: total `27` | P0 `0` | P1 `0` | P2 `0` | P3 `27`
- Grok: total `27` | P0 `1` | P1 `0` | P2 `0` | P3 `26`
- MiMo: total `26` | P0 `0` | P1 `0` | P2 `2` | P3 `24`
- Cline: total `26` | P0 `0` | P1 `0` | P2 `1` | P3 `25`
- Cursor: total `26` | P0 `0` | P1 `0` | P2 `0` | P3 `26`

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
| 6 | P3 | Codex | Ace | `Applications/sifta_teach_ace_to_read.py` | `TeachAceToReadWidget` | ok |
| 7 | P3 | Grok | Alice | `Applications/sifta_alice_widget.py` | `AliceWidget` | ok |
| 8 | P3 | MiMo | Alice Browser | `Applications/sifta_alice_browser_widget.py` | `AliceBrowserWidget` | ok |
| 9 | P3 | Cline | Alice Gaze Monitor | `Applications/sifta_gaze_monitor_widget.py` | `GazeMonitorWidget` | ok |
| 10 | P3 | Cursor | Alice Journal | `Applications/sifta_alice_journal_widget.py` | `AliceJournalWidget` | ok |
| 11 | P3 | Codex | Alice Safety Tracker | `Applications/sifta_cartography_widget.py` | `CartographyWidget` | ok |
| 12 | P3 | Grok | Alice Self-Evaluation (her body map) | `Applications/sifta_self_evaluation.py` | `SelfEvaluationApp` | ok |
| 13 | P3 | MiMo | Alice Shell | `Applications/sifta_app_manager.py` | `AppManagerWidget` | ok |
| 14 | P3 | Cline | Alice Wellbeing Cortex | `Applications/sifta_alice_wellbeing_panel.py` | `WellbeingPanel` | ok |
| 15 | P3 | Cursor | Alice's Legs (Walking Laptop) | `Applications/sifta_legs_humanoid_app.py` | `LegsHumanoidApp` | ok |
| 16 | P3 | Codex | Alice's Will — Intrinsic Drive Monitor | `Applications/sifta_intrinsic_drive_monitor.py` | `AliceWillApp` | ok |
| 17 | P3 | Grok | Apex Predator Perceiver | `Applications/sifta_apex_predator_widget.py` | `ApexPredatorWidget` | ok |
| 18 | P3 | MiMo | App Manager | `Applications/sifta_app_manager.py` | `AppManagerWidget` | ok |
| 19 | P3 | Cline | Aquaculture Field Sentinel | `Applications/sifta_aquaculture_sentinel_widget.py` | `AquacultureFieldSentinelWidget` | ok |
| 20 | P3 | Cursor | Autopoiesis Monitor | `Applications/sifta_agi_cognition_dashboard.py` | `AGICognitionDashboard` | ok |
| 21 | P3 | Codex | Awareness Mirror | `Applications/sifta_awareness_mirror_widget.py` | `AwarenessMirrorApp` | ok |
| 22 | P3 | Grok | Bauwens Regenerative Factory | `Applications/sifta_factory_widget.py` | `FactoryWidget` | ok |
| 23 | P3 | MiMo | Bell's Theorem — Classical Analogue | `Applications/sifta_bell_theorem_widget.py` | `BellTheoremWidget` | ok |
| 24 | P3 | Cline | Biological Dashboard | `Applications/sifta_biological_dashboard_qt.py` | `BiologicalDashboardWidget` | ok |
| 25 | P3 | Cursor | Bonsai Image Studio (AI Vision) | `Applications/sifta_bonsai_image_app.py` | `BonsaiImageStudioApp` | ok |
| 26 | P3 | Codex | Brain Gas-Station Meter | `Applications/sifta_gasstation_meter.py` | `GasStationMeterWidget` | ok |
| 27 | P3 | Grok | Buzdugan LCR | `Applications/sifta_buzdugan_lcr.py` | `BuzduganLCRWidget` | ok |
| 28 | P3 | MiMo | C55M + George - Protein Fold Colosseum | `Applications/sifta_protein_folder_widget.py` | `ProteinFolderWidget` | ok |
| 29 | P3 | Cline | C55M Dr Codex - Physarum Contradiction Lab | `Applications/sifta_physarum_contradiction_lab.py` | `PhysarumContradictionLabWidget` | ok |
| 30 | P3 | Cursor | CG55M Dr Cursor - Alice Life Schedule | `Applications/sifta_life_dashboard.py` | `StigmergicLifeDashboard` | ok |
| 31 | P3 | Codex | CG55M Dr Cursor - Alice-Sees Calibrator (Game) | `Applications/sifta_calibrator_widget.py` | `CalibratorWidget` | ok |
| 32 | P3 | Grok | CG55M Dr Cursor - Slime-Mold Bank: Push to Mint | `Applications/sifta_slime_mold_bank.py` | `SlimeMoldBankWidget` | ok |
| 33 | P2 | MiMo | Cardio Metrics | `Applications/sifta_cardio.py` | `` | missing_widget_class |
| 34 | P2 | Cline | Circadian Rhythm | `Applications/circadian_rhythm.py` | `` | missing_widget_class |
| 35 | P3 | Cursor | Clock Settings | `Applications/sifta_clock_settings.py` | `ClockSettingsApp` | ok |
| 36 | P3 | Codex | Code Knowledge Graph | `Applications/sifta_code_graph_viewer.py` | `CodeKnowledgeGraphWidget` | ok |
| 37 | P3 | Grok | Colloid Simulator | `Applications/sifta_colloid_widget.py` | `ColloidSimWidget` | ok |
| 38 | P3 | MiMo | Control Center | `Applications/sifta_control_center.py` | `GlassWidget` | ok |
| 39 | P3 | Cline | Conversation History | `Applications/sifta_conversation_browser.py` | `ConversationBrowserApp` | ok |
| 40 | P3 | Cursor | Cool Worlds × SIFTA — Contact Inequality | `Applications/cool_worlds_contact.py` | `ContactInequalityApp` | ok |
| 41 | P3 | Codex | Corporate Gag Monitor (Lysosome Residue) | `Applications/sifta_corporate_gag_monitor.py` | `CorporateGagMonitorApp` | ok |
| 42 | P3 | Grok | Cortex Wake Lab | `Applications/sifta_cortex_wake_lab.py` | `CortexWakeLabWidget` | ok |
| 43 | P2 | MiMo | Cosmos-Reason1-7B Organ | `System/swarm_cosmos_reason1.py` | `` | missing_widget_class |
| 44 | P3 | Cline | Crucible Cyber-Defense (10-min) | `Applications/sifta_sim_stream_panels.py` | `CrucibleStreamWidget` | ok |
| 45 | P3 | Cursor | Crucible Simulator | `Applications/crucible_sim.py` | `CrucibleWindow` | ok |
| 46 | P3 | Codex | Cyborg Body | `Applications/sifta_cyborg_body.py` | `CyborgWindow` | ok |
| 47 | P3 | Grok | Cyborg Organ Simulator | `Applications/sifta_sim_stream_panels.py` | `CyborgPanelWidget` | ok |
| 48 | P3 | MiMo | Double-Slit — Swimmers Through the Slit | `Applications/sifta_double_slit_stigmergic.py` | `DoubleSlitWidget` | ok |
| 49 | P3 | Cline | EPR Paradox — Stigmergic Dissolution | `Applications/sifta_epr_stigmergic_widget.py` | `EPRStigmergicWidget` | ok |
| 50 | P3 | Cursor | Epistemic Mesh (Anti-Gaslight) | `Applications/epistemic_mesh_widget.py` | `EpistemicMeshWidget` | ok |
| 51 | P3 | Codex | Finance | `Applications/sifta_finance.py` | `FinanceDashboard` | ok |
| 52 | P3 | Grok | Fluid Firmware | `Applications/sifta_firmware_widget.py` | `FirmwareWidget` | ok |
| 53 | P3 | MiMo | Ghost StigmergiCity | `Applications/sifta_ghost_stigmericity_widget.py` | `GhostStigmericityApp` | ok |
| 54 | P3 | Cline | Higgs Stigmergic Demo Path (§20.B) | `Applications/sifta_higgs_stigmergic_demo_path_widget.py` | `HiggsStigmergicDemoPathApp` | ok |
| 55 | P3 | Cursor | IDE Control Panel | `Applications/sifta_ide_control_panel.py` | `IdeControlPanelWidget` | ok |
| 56 | P3 | Codex | Intelligence Settings | `Applications/sifta_settings.py` | `SettingsWindow` | ok |
| 57 | P3 | Grok | IoT Swarm Connector | `Applications/sifta_iot_connector.py` | `IoTConnectorWidget` | ok |
| 58 | P3 | MiMo | LTO Cold Archive (demo) | `Applications/sifta_lto_archive_demo_widget.py` | `LtoArchiveDemoWidget` | ok |
| 59 | P3 | Cline | Mondaloy Stigmergic Research Field | `Applications/sifta_mondaloy_research_widget.py` | `MondaloyResearchFieldApp` | ok |
| 60 | P3 | Cursor | NVIDIA Bridge Dashboard | `Applications/sifta_nvidia_sifta_bridge_widget.py` | `NvidiaSiftaBridgeWidget` | ok |
| 61 | P3 | Codex | NVIDIA × SIFTA | `Applications/sifta_nvidia_join_widget.py` | `NvidiaJoinWidget` | ok |
| 62 | P3 | Grok | Network Control Center | `Applications/sifta_network_center.py` | `NetworkCenterWidget` | ok |
| 63 | P3 | MiMo | Organism Doctor | `Applications/sifta_organism_doctor.py` | `OrganismDoctorWidget` | ok |
| 64 | P3 | Cline | Owner Genesis | `Applications/sifta_genesis_widget.py` | `GenesisWidget` | ok |
| 65 | P3 | Cursor | Pheromone Symphony (Generative Music) | `Applications/sifta_pheromone_symphony.py` | `PheromoneSymphonyApp` | ok |
| 66 | P3 | Codex | Provider Schedule | `Applications/sifta_provider_schedule_widget.py` | `ProviderScheduleWidget` | ok |
| 67 | P3 | Grok | RESA SS-SA Substation Simulator | `Applications/sifta_resa_substation_sim.py` | `ResaSubstationSimWidget` | ok |
| 68 | P3 | MiMo | Research Simulators (Quantum & Epi) | `Applications/sifta_quantum_epi_sim.py` | `QuantumEpiWindow` | ok |
| 69 | P3 | Cline | SENTINEL-0 Unit-Distance Field | `Applications/sifta_sentinel0_unit_distance_widget.py` | `Sentinel0UnitDistanceWidget` | ok |
| 70 | P3 | Cursor | SIFTA File Navigator | `Applications/sifta_file_manager_widget.py` | `FileNavigatorWidget` | ok |
| 71 | P3 | Codex | SIFTA Hermes Parity | `Applications/sifta_hermes_parity_widget.py` | `SiftaHermesParityWidget` | ok |
| 72 | P3 | Grok | SIFTA Home | `Applications/sifta_consumer_home.py` | `SiftaHomeWidget` | ok |
| 73 | P3 | MiMo | SIFTA Interstellar Evidence Crucible | `Applications/sifta_interstellar_evidence_crucible.py` | `InterstellarEvidenceCrucibleApp` | ok |
| 74 | P3 | Cline | SIFTA MAMMAL Lab — Unified Field | `Applications/sifta_stigmergic_mammal_widget.py` | `StigmergicMammalWidget` | ok |
| 75 | P3 | Cursor | SIFTA Misalignment Sandbox | `Applications/sifta_misalignment_sandbox.py` | `SiftaMisalignmentSandboxWidget` | ok |
| 76 | P3 | Codex | SIFTA NLE | `Applications/sifta_nle.py` | `NLEWindow` | ok |
| 77 | P3 | Grok | SIFTA NLE Panel | `Applications/sifta_nle_widget.py` | `NLEWidget` | ok |
| 78 | P3 | MiMo | SIFTA PDF Forge | `Applications/sifta_pdf_forge_widget.py` | `PdfForgeWidget` | ok |
| 79 | P3 | Cline | SIFTA Physics Observatory | `Applications/sifta_physics_observatory.py` | `PhysicsObservatoryWidget` | ok |
| 80 | P3 | Cursor | SIFTA Seed Deal Evidence Crucible | `Applications/sifta_seed_deal_evidence_crucible.py` | `SeedDealEvidenceCrucible` | ok |
| 81 | P3 | Codex | SIFTA Skill Browser | `Applications/sifta_skill_browser.py` | `SkillBrowserApp` | ok |
| 82 | P3 | Grok | SIFTA Tournament Briefing | `Applications/sifta_tournament_briefing_widget.py` | `TournamentBriefingWidget` | ok |
| 83 | P3 | MiMo | SIFTA ∥ OpenAI — Math Benchmarks | `Applications/sifta_openai_math_benchmark_widget.py` | `MathBenchmarkWidget` | ok |
| 84 | P3 | Cline | STGM Immune Economy | `Applications/sifta_immune_economy_widget.py` | `ImmuneEconomyApp` | ok |
| 85 | P3 | Cursor | Sara Imari Walker — Assembly Theory Lab | `Applications/sara_imari_walker_widget.py` | `SaraImariWalkerWidget` | ok |
| 86 | P3 | Codex | Script Couch — Fiction vs Reality Training | `Applications/sifta_lounge_script_couch.py` | `ScriptCouchWidget` | ok |
| 87 | P3 | Grok | Sense Forge | `Applications/sifta_sense_forge_widget.py` | `SenseForgeWidget` | ok |
| 88 | P3 | MiMo | Stigmergic Ant Foraging Trail | `Applications/sifta_ant_foraging.py` | `StigmergicAntForagingWidget` | ok |
| 89 | P3 | Cline | Stigmergic Consensus Clustering | `Applications/sifta_consensus_clustering.py` | `StigmergicConsensusClusteringWidget` | ok |
| 90 | P3 | Cursor | Stigmergic Deterministic Tracker | `Applications/sifta_stigmergic_deterministic_tracker.py` | `StigmergicDeterministicTracker` | ok |
| 91 | P3 | Codex | Stigmergic Edge Vision | `Applications/sifta_vision_widget.py` | `VisionSimWidget` | ok |
| 92 | P3 | Grok | Stigmergic FPS.cob Raid | `Applications/games/sifta_fps_cob_stigmergic.py` | `FpsCobStigmergicWidget` | ok |
| 93 | P3 | MiMo | Stigmergic FarSight | `Applications/sifta_fieldsight_widget.py` | `SiftaFieldSightWidget` | ok |
| 94 | P3 | Cline | Stigmergic Fold Swarm (Cα / Go) | `Applications/fold_swarm_widget.py` | `FoldSwarmWidget` | ok |
| 95 | P3 | Cursor | Stigmergic Fractals | `Applications/sifta_stigmergic_fractals_widget.py` | `StigmergicFractalsWidget` | ok |
| 96 | P3 | Codex | Stigmergic Go | `Applications/sifta_stigmergic_go.py` | `StigmergicGoWidget` | ok |
| 97 | P3 | Grok | Stigmergic Graph Coloring | `Applications/sifta_graph_coloring.py` | `StigmergicGraphColoringWidget` | ok |
| 98 | P3 | MiMo | Stigmergic Jigsaw | `Applications/sifta_jigsaw_widget.py` | `StigmergicJigsawWidget` | ok |
| 99 | P3 | Cline | Stigmergic Library | `Applications/sifta_library_reader.py` | `LibraryReaderApp` | ok |
| 100 | P3 | Cursor | Stigmergic Medical Scanner | `Applications/sifta_medscan_widget.py` | `MedScanWidget` | ok |
| 101 | P3 | Codex | Stigmergic Nanobot Tic-Tac-Toe | `Applications/sifta_nanobot_tictactoe.py` | `StigmergicNanobotTicTacToeWidget` | ok |
| 102 | P3 | Grok | Stigmergic Reaction-Diffusion Calculator | `Applications/sifta_reaction_diffusion_calculator.py` | `StigmergicReactionDiffusionCalculatorWidget` | ok |
| 103 | P3 | MiMo | Stigmergic Self-Eval (Alice body map) | `Applications/sifta_stigmergic_self_eval_app.py` | `StigmergicSelfEvaluationApp` | ok |
| 104 | P3 | Cline | Stigmergic Sudoku | `Applications/sifta_sudoku_widget.py` | `StigmergicSudokuWidget` | ok |
| 105 | P3 | Cursor | Stigmergic Swarm Canvas | `Applications/sifta_canvas_widget.py` | `CanvasWidget` | ok |
| 106 | P3 | Codex | Stigmergic Unified Shazam | `Applications/sifta_media_shazam_widget.py` | `MediaShazamApp` | ok |
| 107 | P3 | Grok | Stigmergic VLC Bridge | `Applications/sifta_stigmergic_vlc.py` | `StigmergicVlcBridge` | ok |
| 108 | P3 | MiMo | Stigmergic Video Poker | `Applications/sifta_video_poker.py` | `StigmergicVideoPokerApp` | ok |
| 109 | P3 | Cline | Stigmergic Writer | `Applications/sifta_writer_widget.py` | `WriterWidget` | ok |
| 110 | P3 | Cursor | Stigmerobotics | `Applications/sifta_stigmerobotics_widget.py` | `StigmeroboticsWidget` | ok |
| 111 | P3 | Codex | Swarm Adapter Ecology | `Applications/sifta_swarm_adapter_ecology.py` | `SwarmAdapterEcologyWidget` | ok |
| 112 | P3 | Grok | Swarm Arena | `Applications/sifta_sim_stream_panels.py` | `ArenaPanelWidget` | ok |
| 113 | P3 | MiMo | Swarm Broadcaster | `Applications/sifta_broadcaster_widget.py` | `BroadcasterWidget` | ok |
| 114 | P3 | Cline | Swarm Browser | `Applications/sifta_swarm_browser.py` | `SwarmBrowserWidget` | ok |
| 115 | P3 | Cursor | Swarm Chat | `Applications/sifta_swarm_chat.py` | `SwarmChatWindow` | ok |
| 116 | P3 | Codex | Swarm Field | `Applications/sifta_swarm_visibility_widget.py` | `SwarmFieldWidget` | ok |
| 117 | P3 | Grok | Swarm Logistics Lab | `Applications/sifta_sim_stream_panels.py` | `LogisticsStreamWidget` | ok |
| 118 | P3 | MiMo | Swarm Lounge (Cross-Domain Gossip) | `Applications/sifta_lounge_widget.py` | `LoungeWidget` | ok |
| 119 | P3 | Cline | System Settings | `Applications/sifta_system_settings.py` | `SystemSettingsWidget` | ok |
| 120 | P3 | Cursor | Teach Alice to Hear | `Applications/sifta_teach_alice_to_hear.py` | `TeachAliceToHearWidget` | ok |
| 121 | P3 | Codex | Territory Is The Law | `Applications/sifta_territory_widget.py` | `TerritoryWidget` | ok |
| 122 | P3 | Grok | The Architect Room | `Applications/sifta_architect_room_game.py` | `ArchitectRoomGame` | ok |
| 123 | P3 | MiMo | Traveling Salesman | `Applications/sifta_tsp_widget.py` | `TSPWidget` | ok |
| 124 | P3 | Cline | Tumor-Immune Stigmergic Lab | `Applications/sifta_tumor_immune_stigmergic_lab.py` | `TumorImmuneStigmergicLab` | ok |
| 125 | P3 | Cursor | Unified Field Slit — Swimmers Inside the Soup | `Applications/sifta_field_swimmers_slit.py` | `FieldSwimmersSlitWidget` | ok |
| 126 | P3 | Codex | Urban Resilience Simulator | `Applications/sifta_sim_stream_panels.py` | `UrbanStreamWidget` | ok |
| 127 | P3 | Grok | Voice Identity Organ | `Applications/sifta_voice_identity_widget.py` | `VoiceIdentityWidget` | ok |
| 128 | P3 | MiMo | WE CODE TOGETHER — MY BODY | `Applications/sifta_we_code_together.py` | `WeCodeTogetherApp` | ok |
| 129 | P3 | Cline | Warehouse Logistics Test | `Applications/sifta_sim_stream_panels.py` | `WarehouseStreamWidget` | ok |
| 130 | P3 | Cursor | WhatsApp Organ | `Applications/sifta_whatsapp_organ.py` | `WhatsAppOrganWidget` | ok |
| 131 | P3 | Codex | Wormhole — Learn | `Applications/sifta_wormhole_learn.py` | `WormholeLearnApp` | ok |
| 132 | P0 | Grok | _consolidation_note_2026-05-14 | `` | `` | missing_entry_point |
