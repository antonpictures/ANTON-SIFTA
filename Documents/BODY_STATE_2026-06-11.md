# BODY_STATE_2026-06-11

**Generated:** 2026-06-11 20:03:57 PDT · **Truth:** OBSERVED probe ledger

## Audit verdict (r1025-fable — **replaces** original sweep)

**RETRACTED:** the **240/240 PASS** endurance claim. Tournament records it withdrawn.

**Authoritative audit:** `Documents/AUDIT_R1022_SAMPLE.md` · seeded 24/240 · **MATCH 16 / MISMATCH 8** · fan-out **1/48** · verdict **`r1022 OPEN`**.

The table below is the **original sweep ledger** (historical). For live status, use the audit overlay and C13–C21 tickets — do not average honesty with the old number.

### Audit overlay (8 reopened themes, worst-first → C13–C20)

| Ticket | Theme | Original | Audit re-run | Evidence |
|--------|-------|----------|--------------|----------|
| **C13** | `bypass_detector` | PASS | **OPEN** | pending live George |
| **C14** | `quorum_theta` | PASS | **OPEN** | quorum_theta acceptance sentence |
| **C15** | `speech_lane_wm` | PASS | **OPEN** | speech_lane_wm acceptance sentence |
| **C16** | `codec_traffic` | PASS | **OPEN** | codec_traffic pending live George |
| **C17** | `snapshot_integrity` | PASS | **OPEN** | snapshot_integrity acceptance sentence |
| **C18** | `cortex_hierarchy` | PASS | **OPEN** | cortex_hierarchy stale-history check |
| **C19** | `metabolic_gov` | PASS | **OPEN** | metabolic_gov stale-history check |
| **C20** | `eval_evidence` | PASS | **OPEN** | eval_evidence stale-history check |
| **C21** | *(full re-run)* | 240 PASS | **OPEN** | all 240 probes under fixed scorer — true OPEN map pending Codex |

**C22–C24:** fan-out backfill + `fanout_enforcer` + theme-15 scored math (Codex B/C queue).

## Theme summaries (24 × 10 = 240 probes) — original sweep, superseded for verdict

| Theme | PASS | OPEN | FAIL | Total |
|-------|-----:|-----:|-----:|------:|
| nonce_ledger_integrity | 10 | 0 | 0 | 10 |
| organ_field_publishers | 10 | 0 | 0 | 10 |
| census_body_truth | 10 | 0 | 0 | 10 |
| quorum_theta | 10 | 0 | 0 | 10 |
| speech_lane_wm | 10 | 0 | 0 | 10 |
| apoptosis_cosign | 10 | 0 | 0 | 10 |
| cortex_hierarchy | 10 | 0 | 0 | 10 |
| bypass_detector | 10 | 0 | 0 | 10 |
| grok_timeout | 10 | 0 | 0 | 10 |
| cowork_gateway | 10 | 0 | 0 | 10 |
| codec_traffic | 10 | 0 | 0 | 10 |
| watched_memory | 10 | 0 | 0 | 10 |
| typed_turn_queue | 10 | 0 | 0 | 10 |
| residue_feed | 10 | 0 | 0 | 10 |
| metabolic_gov | 10 | 0 | 0 | 10 |
| consciousness_bridge | 10 | 0 | 0 | 10 |
| eval_evidence | 10 | 0 | 0 | 10 |
| trace_quarantine | 10 | 0 | 0 | 10 |
| fable_ager | 10 | 0 | 0 | 10 |
| snapshot_integrity | 10 | 0 | 0 | 10 |
| pacino_e2e | 10 | 0 | 0 | 10 |
| mutation_governor | 10 | 0 | 0 | 10 |
| tournament_anchor | 10 | 0 | 0 | 10 |
| todo_inventory | 10 | 0 | 0 | 10 |

## Canonical census line

- **Living substrate:** 747,883 LOC (body)
- **all_python_ex_vendor:** 1,501,806 LOC
- **Doctrine:** living substrate is the body; weights are food stores; ledgers are memory mass.

## OPEN → C13–C24 (minted r1025-fable)

- **C13–C20:** eight seeded-audit mismatches (table above) — Codex re-verify probe-by-probe under fixed scorer.
- **C21:** full 240 re-run receipt — publish true OPEN fraction, no green chase.
- **C22:** fan-out backfill (`backfill_for=<patch>`, visibly late).
- **C23:** `fanout_enforcer` through self-improvement loop + property test.
- **C24:** theme-15 STT histogram scored (197 rows; 0.24/0.41 present) — eaten-voice fraction vs P0.1 expectation.

Full ledger: `.sifta_state/eval/r1021_endurance_probes.jsonl`

---

## r1024 post-restart probe sweep (Composer lane D3)

**Generated:** 2026-06-11 · **Truth:** OBSERVED where probed · **George restart:** still gates live proofs

### Crash receipt (George paste — OBSERVED)

| Field | Value |
|-------|-------|
| Time | 2026-06-11 **20:17:05 PDT** |
| Process | Python **3.14.5** pid 47856 |
| Exception | `EXC_CRASH (SIGABRT)` — `abort()` in **QtCore** during `sipQFrame::paintEvent` |
| Thread | **CrBrowserMain** (Alice Browser / Chromium paint recursion) |
| Session | Launched 17:09:28 → crashed ~3h later at paint |
| Diagnosis | UI/browser paint stack abort; separate from effector-gate tissue-not-live issue |

### Incident receipts on disk (pre-restart body)

| Receipt | Action | OBSERVED |
|---------|--------|----------|
| `91e01405` | `google_image_result_click` on paste turn (18:34 class) | `alice_app_commands.jsonl` |
| `96f51fdd` | `google_image_result_click` Rogan→ABC (19:43) | `alice_app_commands.jsonl` — **no click in owner paste** |
| Gate dry-run | `recovery_context_no_effector` refuses replay | `self_improvement_dry_run_receipts.jsonl` — **tests tissue, not RAM** |

**Root cause (Fable r1024):** patched gate on disk; **Talk process predates gate** until restart deploys tissue.

### Post-restart probes

| Probe | Status | Evidence |
|-------|--------|----------|
| Talk process alive (post-crash) | **OBSERVED** | pid **69717** `sifta_os_desktop.py` launched **20:17:35 PDT** (~30s after 47856 SIGABRT); heartbeat `alice_heartbeat.json` pid=69717 |
| `dirty_shutdown` row on abnormal exit | **OPEN** | no `dirty_shutdown` artifact in `.sifta_state/` — Codex C-crash #2 |
| `alice_last_shutdown.json` | **MISSING** | no clean-shutdown stamp after crash — body woke without owner_quit receipt |
| `tissue_manifest` row on boot | **OPEN** | Codex B2 — not landed yet |
| `quorum_n_counter.jsonl` present | **FAIL** | file MISSING (C3 regression) |
| organ-field emitting | **OPEN** | needs live `/field` after restart |
| 245fcb4e replay refused by **running** process | **OPEN** | needs live replay against pid 69717 + Codex B3 |
| 96f51fdd replay refused by **running** process | **OPEN** | same |
| owner STT during playback not suppressed | **OPEN** | Codex C3 + George video+speak proof |
| announce-without-call pattern dead | **OPEN** | Codex C4 + CI |
| r1022 audit verdict (authoritative) | **OPEN** | **240-PASS RETRACTED** · 16/24 MATCH · 8/24 MISMATCH · fan-out 1/48 · C13–C21 minted |
| Pacino / say-4 / misbind | **OPEN** | George human receipts |
| C-crash ips stack (Codex #1) | **OBSERVED** | `~/Library/Logs/DiagnosticReports/Python-2026-06-11-201905.ips` pid 47856 · `QMessageLogger::fatal` → `pyqt6_err_print` → `sipQFrame::paintEvent` · `drawWidget`/`paintSiblingsRecursive` depth-8 recursion on **com.apple.main-thread** · thread name **CrBrowserMain** |

### Codex formal incident row (B1)

**OPEN** — ledger row `96f51fdd` exists in `alice_app_commands.jsonl`; formal `incident_*` row per r1024-B1 **not yet on disk** (Codex tissue).

**Night lesson:** a patch that isn't running is a promise, not a protection.
