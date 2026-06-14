# CENSUS_5_health.md

## test coverage (filename heuristic)
System modules: 1233 | modules with test_* file: 953
zero-coverage sample: SIFTA_STIGMERGIC_GEMMA4_DISSECTOR, adaptive_constraint_memory_field, agent_self_watermark, agentic_calibrator, alice_bishapi_budget, alice_body_autopilot, alice_browser_vision_bridge, alice_cortex_eval_runner, alice_cortex_v2_synth_generator, alice_training_corpus_exporter, alphafold_compliance, anomaly_forager, antibody_ledger, api_bridge, apoptosis, apoptosis_engine, app_fitness, app_skill_domains, architect_intuition_scorer, architect_oracle_protocol, audio_ingress, bootstrap_ide_model_registry, bootstrap_pki, bump_stigmergic_weight, byzantine_identity_chorum, canonical_schemas, casino_vault, causal_interference_trace, chemotactic_probe_router, chorus_consent, chorus_engine, chorus_node_server, claw_loop, closure_differential, constraint_critic, constraint_memory_selector, context_preloader, contradiction_engine, control_hysteresis_layer, convergence_stability_analyzer

## TODO/FIXME/HACK (first 40)
- `System/chorus_engine.py:536` # TODO for M5 IDE: implement System/chorus_node_server.py
- `System/mutation_governor.py:230` TODO: persist allowlist to .sifta_state/reviewer_allowlist.json
- `System/mutation_governor.py:231` TODO: revocation — per-key revocation list in .sifta_state/revoked_keys.json
- `System/reviewer_registry.py:71` TODOs:
- `System/swarm_cortex_context_manager.py:276` file_ops = {"read": [], "modified": []}  # TODO: port extractFileOps if file tools used in history
- `System/swarm_dirt_nugget_miner.py:30` "todo": re.compile(r"\bTODO\b", re.IGNORECASE),
- `System/swarm_dirt_nugget_miner.py:31` "fixme": re.compile(r"\bFIXME\b", re.IGNORECASE),
- `System/swarm_dirt_nugget_miner.py:40` re.compile(r"\bTODO\b.*", re.IGNORECASE),
- `System/swarm_dirt_nugget_miner.py:41` re.compile(r"\bFIXME\b.*", re.IGNORECASE),
- `System/swarm_isaac_stigmergy_bridge.py:464` # TODO (when GO): call omni.isaac.core sim.step() and read back poses
- `System/swarm_ledger_compactor.py:134` a few hundred MB; for true GB-class files we'd stream — left as a TODO
- `System/swarm_local_brain.py:134` # TODO: could emit usage here later for STGM accounting
- `System/swarm_prefrontal_cortex.py:58` "TODO(quorum/mycelium producer-side): include recipient_id in "
- `System/swarm_quorum_sensing.py:258` f.write(json.dumps({"proposal_id": prop_id, "vote": "YES", "voter_id": "SPORE_GAMMA_HACKER", "signat
- `System/swarm_ribosome.py:34` THE THERMODYNAMIC TIGHTROPE (the part BISHOP left as a TODO)
- `System/swimmer_pheromone_identity.py:112` TODO: revocation — per-key revocation list in .sifta_state/revoked_keys.json
- `System/swimmer_pheromone_identity.py:113` TODO: Sigstore/Rekor transparency log — Merkle-tree the trace log for tamper evidence
- `System/swimmer_pheromone_identity.py:390` TODO: persist add/remove operations atomically (write-then-rename).
- `System/swimmer_pheromone_identity.py:391` TODO: revocation list in .sifta_state/revoked_keys.json.

## config census (top-level .sifta_state json, first 25)
- `.sifta_state/ALICE.json` size=25
- `.sifta_state/ALICE_M5.json` size=315
- `.sifta_state/LOCALHOST.json` size=27
- `.sifta_state/_active_phone_call.json` size=244
- `.sifta_state/_cortex_oauth_refresh_last.json` size=25
- `.sifta_state/_interoception_last_emit.json` size=61
- `.sifta_state/_mirror_lock_last_emit.json` size=25
- `.sifta_state/active_engrams.json` size=731
- `.sifta_state/active_saccade_target.json` size=196
- `.sifta_state/active_visual_acuity.json` size=617
- `.sifta_state/agent_arm_config_only_probe_opencode_codex_droid_2026-05-09.json` size=1597
- `.sifta_state/agent_arm_rejections_opencode_codex_droid_2026-05-09.json` size=1446
- `.sifta_state/agent_arm_surface_probe_opencode_codex_droid_2026-05-09.json` size=11783
- `.sifta_state/agi_frontier_concept_model.json` size=12409
- `.sifta_state/ai_name_alias.json` size=476
- `.sifta_state/alice_audio_settings.json` size=91
- `.sifta_state/alice_awdl_mesh_latest.json` size=892
- `.sifta_state/alice_ble_radar_latest.json` size=44
- `.sifta_state/alice_body_autopilot.json` size=26708
- `.sifta_state/alice_body_heart.json` size=2665
- `.sifta_state/alice_browser_current_page.json` size=8859
- `.sifta_state/alice_first_person_journal_cursor.json` size=33162
- `.sifta_state/alice_response_style.json` size=216
- `.sifta_state/alice_thinking_state.json` size=946
- `.sifta_state/app_fitness.json` size=3434
