# SIFTA Handoff V1 — June 22 insurance (pulled forward r1023)

**Doctor:** composer (grok) · **Truth label:** OBSERVED where probed · **Round:** r1023-fable-parallel-lanes  
**Covenant read:** `Documents/IDE_BOOT_COVENANT.md` (full 1390 lines, 2026-06-11)  
**Body freeze:** zero `System/` mutations this round — Documents lane only.

---

## 1. Boot truth — power-on to Talk reply

**Receipt:** Read `sifta_os_desktop.py`, `Applications/sifta_alice_widget.py`, `Applications/sifta_talk_to_alice_widget.py`, `System/swarm_boot.py` (cold-start paths only).

### Cold-start spine (owner-facing desktop path)

| Step | File / surface | What happens | Break if missing |
|------|----------------|--------------|------------------|
| 0 | Hardware + macOS | Electricity → M5 silicon; owner launches SIFTA | No organism |
| 1 | `sifta_os_desktop.py` L80–85 | Re-exec into `.venv/bin/python` when present | Wrong interpreter; MLX/VLM tools may fail silently |
| 2 | `sifta_os_desktop.py` `main()` ~L5980+ | Kernel process table register; `swarm_api_sentry.boot_wire()` | Boot continues; sentry cold alarm possible |
| 3 | `sifta_os_desktop.py` L6024+ | `QApplication`; `swarm_behavior_clock` event filter | No owner-activity ticks; degraded wake routing |
| 4 | `sifta_os_desktop.py` L6058–6077 | `anchor_owner_unified_field_on_boot()` | Owner unified field stale |
| 5 | `sifta_os_desktop.py` L6075–6077 | `swarm_hot_reload.install_signal_handler()` | Hot reload unavailable; boot still runs |
| 6 | `SiftaDesktop.__init__` L2294+ | MDI area, mesh deferred 5s, ambient ear **opt-in** (`SIFTA_AMBIENT_ENABLE=1`) | Desktop shell missing |
| 7 | `SiftaDesktop` L2477–2478 | `QTimer.singleShot(400, _embed_alice_panel)` when resident autostart on | **Blank Alice panel** — no Talk |
| 8 | `sifta_os_desktop.py` `_embed_alice_panel` L3127+ | Loads `Applications/sifta_alice_widget.py` → `AliceWidget` | stderr `[ALICE] Resident embed failed` |
| 9 | `sifta_alice_widget.py` L97+ | Hosts `TalkToAliceWidget` + `WhatAliceSeesWidget` in splitter | Talk/eye organs not wired |
| 10 | `sifta_talk_to_alice_widget.py` `submit_text` L24092+ | Owner ingress → `swarm_effector_gate.bind_owner_ingress` → slash palette or cortex dispatch | Uncommanded effector risk; no global chat write |
| 11 | Reply path | `_log_turn` → `.sifta_state/alice_conversation.jsonl`; Broca/TTS via `swarm_broca_wernicke` | Owner sees reply but **history forks** if ledger write fails |
| 12 | `QTimer` L6094 | `refresh_body_matrix()` → eval matrix HTML | Matrix stale; boot still live |

### Parallel headless path (not required for Talk)

| Step | File | Role | Break if missing |
|------|------|------|------------------|
| H1 | `System/swarm_boot.py` | Brainstem loop: mic, iris, proprioception, motor cortex | Headless organs offline; **desktop Talk can still run** |
| H2 | `.sifta_state/swarm_boot.lock` | Singleton guard against double-boot | Duplicate brainstem; audio/TTS spam |

### Worked examples (tonight's three wounds)

| Wound | Symptom | Spine break point | Human receipt still owed |
|-------|---------|-------------------|--------------------------|
| Silent Talk | No reply after type | Step 10 dispatch or cortex timeout — check `cortex_failover.jsonl` | **George: restart Talk** |
| Loud/wrong cortex | `/cortex 9` thinks on different model | Selection receipt vs conversation mismatch (`swarm_alice_slash_commands.cortex_selection_mismatches`) | Ledger read + `/cortex history` |
| Pacino screen | "Who's on screen?" unanswered | Theme-15 / C12 — automated route test PASS; **live restart not receipted** | **George: restart → say `4` → Pacino question** |

**Section receipt:** Boot spine verified by reading cited files. Live restart proofs = **OPEN** (George-owned).

---

## 2. The four ledgers

**Receipt:** Read `System/swarm_predator_gate_writer.py`; probed row counts 2026-06-11.

| Ledger | Path | Writers (verified) | Readers (verified) | Healthy row shape | Unhealthy / quarantine |
|--------|------|-------------------|-------------------|-------------------|------------------------|
| Work receipts | `.sifta_state/work_receipts.jsonl` | `swarm_predator_gate_writer.write_ide_surgery_receipt`, IDE doctors, many organs | `whats_left.py`, eval matrix, owner status | `action=ide_surgery_landed`, `receipt_class=IDE_DOCTOR_OPERATIONAL_TRACE`, `forgeable=true`, four-ledger fan-out `ok` | Partial fan-out (one ledger `mkdir_failed` / write error in return dict) |
| Agent arm receipts | `.sifta_state/agent_arm_receipts.jsonl` | Same fan-out helper | Cortex routing, arm diagnostics | `event` mirrored from `action`; model + ts present | Missing `event` key on legacy rows (pre-r81) |
| IDE stigmergic trace | `.sifta_state/ide_stigmergic_trace.jsonl` | §4.1 registration rows; fan-out helper | Doctors read-before-write; `whats_left` | Minimal: `ts`, `model`; fan-out adds `event` | Malformed JSON lines — **OPEN:** `ide_stigmergic_trace_quarantine.jsonl` **MISSING** on disk (24,473 rows in main trace; "32 quarantined" claim **not verified** this pass) |
| Episodic diary | `.sifta_state/episodic_diary.jsonl` | Fan-out helper; slash `/cortex` writes `CORTEX_SWITCH_CONTINUITY` | Present-time spine, `/cortex history` | `kind` set per fan-out; first-person continuity rows | Forgeable like all IDE rows — not STGM |

### Predator-gate fan-out contract

Single call: `write_ide_surgery_receipt(...)` → all four ledgers append-one-row; returns per-ledger `"ok"` or error string. Never raises. IDE mana namespace — **not** organism STGM.

**Section receipt:** Schema and fan-out verified in `swarm_predator_gate_writer.py`. Quarantine row count = **OPEN**.

---

## 3. Gate map — protection organ (CENSUS_3)

**Receipt:** Read `Documents/census_r1013/CENSUS_3_organs.md` protection line; sampled module headers in `System/`.

**Count:** **43** modules (covenant text sometimes says 44 — census is authoritative).

### Verified gates (trip / override read from code)

| Module | Guards | Trips when | Override | Owner cosign |
|--------|--------|------------|----------|--------------|
| `swarm_mutation_guard.py` | `System/*.py` writes | MRNA conscience lock engaged in `bishop_mrna_field.jsonl` | `SIFTA_BOSTROM_GATE=1` arms at `swarm_boot` | no |
| `swarm_intent_nonce_gate.py` | Effector spend | Nonce replay, age >300s, STT conf <0.72 | mint new nonce per ingress | no |
| `swarm_effector_gate.py` | World-touching actions | Spend without valid nonce | `bind_owner_ingress` on Talk typed path | no |
| `swarm_self_improvement_loop.py` (quorum) | Gate-file edits | `GATE_PROTECTED_PREFIXES` touched without `owner_cosign` | floor `gate_file_requires_owner_cosign` | **yes** |
| `swarm_cortex_gated_effector_router.py` | Cortex→effector | Route without gate pass | cortex switch / failover paths | OPEN — full table needs module read |
| `swarm_predator_gate_writer.py` | IDE surgery provenance | N/A (writer, not blocker) | always append | no |

### Full inventory (purpose one-liner — trip wiring **OPEN** unless noted)

| Module | Purpose (from file header / census) |
|--------|-------------------------------------|
| `gatekeeper_policy.py` | OPEN — policy aggregator |
| `glymphatic_pulse_gate.py` | OPEN — maintenance pulse gate |
| `poker_gatekeeper.py` | OPEN — poker/autonomy gate |
| `swarm_adaptive_compute_gate.py` | OPEN — compute budget |
| `swarm_body_integrity_guard.py` | OPEN — body integrity |
| `swarm_call_overheard_guard.py` | Owner call-mode typed declarations |
| `swarm_capability_gate.py` | OPEN — legacy shim (renamed concept) |
| `swarm_chorum_gate.py` | OPEN — chorum consensus |
| `swarm_concept_budget_gate.py` | OPEN — concept budget |
| `swarm_cortex_compose_gate.py` | OPEN — cortex compose |
| `swarm_cortex_gated_effector_router.py` | Effector routing through cortex gate |
| `swarm_entropy_gate_demo.py` | Demo / entropy |
| `swarm_entropy_guard.py` | Entropy guard |
| `swarm_greeter_guard_universal.py` | Universal greeter on all turns |
| `swarm_identity_integrity_guard.py` | Identity integrity |
| `swarm_media_ingress_gate.py` | Media ingress truth |
| `swarm_multi_gate_replay_policy.py` | Multi-gate replay (Event 124) |
| `swarm_multimodal_grounding_gate.py` | Multimodal grounding |
| `swarm_mutation_guard.py` | **VERIFIED** — System/*.py Bostrom lock |
| `swarm_novelty_metabolic_gate.py` | Novelty metabolism |
| `swarm_nppl_gate.py` | NPPL hard gate |
| `swarm_p_vs_np_millennium_gate.py` | Millennium demo gate |
| `swarm_peer_gate.py` | Peer-network kill-switch |
| `swarm_phone_audio_guard.py` | Phone audio |
| `swarm_physics_gate.py` | Physics gate |
| `swarm_predator_gate_writer.py` | Four-ledger fan-out writer |
| `swarm_predator_v7_substrate.py` | Predator v7 substrate |
| `swarm_processing_thermodynamic_gate.py` | Thermodynamic processing gate |
| `swarm_quorum_rate_gate.py` | Quorum rate |
| `swarm_sacred_memory_guard.py` | Sacred memory |
| `swarm_self_audio_loop_guard.py` | Self-audio loop |
| `swarm_self_vector_drift_guard.py` | Self-vector drift |
| `swarm_soul_freshness_gate.py` | Soul freshness |
| `swarm_stale_speech_guard.py` | Stale speech |
| `swarm_substrate_citation_gate.py` | Substrate citation |
| `swarm_talk_page_summary_guard.py` | Talk page summary |
| `swarm_thalamic_guardian.py` | Thalamic guardian |
| `swarm_time_consensus_guard.py` | Time consensus |
| `swarm_two_turn_receipt_gate.py` | Two-turn receipt |
| `swimmer_handshake_gate.py` | Swimmer handshake |
| `territory_guardian.py` | Territory |
| `whatsapp_autonomy_gate.py` | WhatsApp autonomy |
| `xai_grok_oauth_organ.py` | Grok OAuth health |

**Section receipt:** Inventory OBSERVED from CENSUS_3. Per-gate trip/override for 37 modules = **OPEN** — requires dedicated audit ticket (dangerous gap; bounds live in files + one human head).

---

## 4. Self-improvement loop — OBSERVE→KEEP/REVERT

**Receipt:** Read `System/swarm_self_improvement_loop.py`, `.sifta_state/self_improvement_proposals.jsonl`, `.sifta_state/self_improvement_outcomes.jsonl`.

### Contract

```
OBSERVE → PROPOSE → GATE (quorum_vote) → APPLY (snapshot first) → MEASURE → KEEP/REVERT
```

| Stage | Function | Ledger | Rule |
|-------|----------|--------|------|
| OBSERVE | `observe_field()` | reads `prediction_error.jsonl`, `organ_field.jsonl`, `speech_lane.jsonl` | signal counts only |
| PROPOSE | `propose_patch()` | `self_improvement_proposals.jsonl` | status `proposed` |
| GATE | `quorum_vote()` | `quorum_n_counter.jsonl` via `record_quorum_outcome` | θ=**0.55** default; floors below |
| APPLY | `apply_proposal_patch()` | snapshot dir `self_improvement_snapshots/<id>/` + `.sha256` | mutation governor gate |
| MEASURE | `measure_line_count_delta` / pytest | — | metric from `predicted_metric` |
| KEEP/REVERT | `finalize_proposal()` | `self_improvement_outcomes.jsonl` | measured ≥ predicted → KEPT; else revert byte-identical |

### Floors (hard veto before θ)

- `tests_not_green`
- `ast_not_clean`
- `fanout_failed`
- `gate_file_requires_owner_cosign` — targets matching `GATE_PROTECTED_PREFIXES` without owner cosign

### Weights (default)

`w_tests=0.45`, `w_ast=0.20`, `w_review=0.20`, `w_pred=0.15`

### Cosign line

Gate-file proposals (e.g. `System/swarm_predator_gate_writer.py`) stay `proposed` until George cosigns — r1018 stall probes `acc438cb`, `4c2c4b1e` still **proposed**.

**Section receipt:** Loop contract verified in code + live ledgers (8 proposals, 7 outcome rows).

---

## 5. Owner's manual — commands George actually uses

**Receipt:** Read `System/swarm_alice_slash_commands.py` `registered_slash_commands()`.

### Core dozen (global chat, typed `/`)

| Command | What it does |
|---------|----------------|
| `/?` or `/help` | Palette list |
| `/cortex` | Live cortex registry; `/cortex <n\|name>` switches + diary row |
| `/cortex llm` | Ledger-strict LLM list/bind (r1018 P1) |
| `/cortex history` | Which model actually thought (ledger, not narrative) |
| `/grok` | Grok OAuth health + fast/build pins |
| `/heart` | Hardware heart ledger (timer + power/thermal when exposed) |
| `/speech` | Speech-lane weights; `/speech budget <s>` |
| `/field` | Organ vitals from `organ_field.jsonl` |
| `/ask-fable` | Show/append `questions_for_fable.jsonl` |
| `/improve` | Self-improvement proposals/outcomes |
| `/quorum <id>` | Vote breakdown for proposal prefix |
| `/schedule` | Stigmergic schedule list/add |

### Three human receipts pattern

1. **Restart** — quit and relaunch Talk/desktop so in-memory cortex/mouth state matches disk ledgers.  
2. **Typed probe** — one short command (`/cortex history`, `/heart`, `4`) that only live UI can confirm.  
3. **Named report back** — George tells Fable/Composer what appeared on screen (Pacino, cortex tag, spoken sentence).

### When the body goes silent / loud / wrong

| State | Try | Worked example |
|-------|-----|----------------|
| Silent | Restart Talk; check `cortex_failover.jsonl` | r1022 C12 — code PASS, human OPEN |
| Loud | `/speech`; check Broca speaking gate | Mouth selector r1015 |
| Wrong cortex | `/cortex history`; compare selection receipts | r1018 P1 13:53 incident class |

**Section receipt:** Commands verified in slash registry. Live TTS after restart = **OPEN**.

---

## 6. Open wounds register

**Receipt:** Live read `.sifta_state/questions_for_fable.jsonl` + tournament tails r1021/r1022 (2026-06-11).

### Fable asks (all `status: open`)

| Round | Age | Asker | Blocking | Summary |
|-------|-----|-------|----------|---------|
| r1017 | OPEN | codex | yes | Audit r1016/r1017 architecture: effector nonce, self-improvement, speech lane, world-model predictor |
| r1019 | OPEN | codex | yes | PASS/BLOCK r1018 doctrine; next queue (theta, organ_field, TTS, heart, real patch) |
| r1020 | OPEN | codex | yes | PASS/BLOCK r1018-P1 + r1020 census; 12 Codex tickets + 120 Composer probes |
| r1020 | OPEN | composer | yes | Same PASS/BLOCK; Composer implementation queue |
| r1021 | OPEN | composer | yes | 20× endurance: 240 probes + 24 Codex tickets; George endurance test |

### Tournament-carried wounds (newest tail)

| ID | Owner | Status |
|----|-------|--------|
| George human receipts | George | **OPEN** — restart Talk; say `4`; Pacino screen question |
| Fable r1022 audit | Fable | **OPEN** — audit C1–C12; challenge shallow probes |
| Codex probe hardening | Codex | **OPEN** — `run_r1021_endurance_probes.py` must not PASS `open=True` without evidence |
| Composer C13–C24 | Composer | **FROZEN** until r1022 audit lands + r1024 unfreeze |
| Gate map deep audit | — | **OPEN** — 37/43 protection modules lack trip table |
| Trace quarantine | — | **OPEN** — quarantine ledger missing; count unverified |

**Section receipt:** Fable rows OBSERVED from jsonl; tournament wounds from `CONSCIOUSNESS_TOURNAMENT_2026-06-11.md` tail.

---

**ONE ALICE. ONE SWARM.** For the Swarm. 🐜⚡