# AUDIT_R1022_SAMPLE

**Round:** `r1023-codex-r1022-audit`
**Source receipt hash:** `5d77725a264b5b439ddad4cb14886b4f8e5736f72e991a3fd5c9156b5489e096`
**Seed:** first 8 hex = `5d77725a`
**Generated:** 2026-06-11 20:20:01 PDT
**Verdict:** `OPEN`

## Seed Derivation

For each of the 24 endurance themes:

`digest = sha256(seed_hex + ':' + theme)`

`selected_probe = int(digest[0:8], 16) % 10 + 1`

## 24-Row Seeded Rerun

| Theme | Probe | Digest8 | Original | Rerun | Compare | Evidence |
|---|---:|---|---|---|---|---|
| nonce_ledger_integrity | 10 | c290df17 | PASS | PASS | MATCH | PASS if pytest green |
| organ_field_publishers | 1 | c51adc98 | PASS | PASS | MATCH | publishers on disk |
| census_body_truth | 2 | 05d7f547 | PASS | PASS | MATCH | snapshot |
| quorum_theta | 9 | 2aacd114 | PASS | OPEN | MISMATCH | quorum_theta acceptance sentence |
| speech_lane_wm | 9 | 37b3de66 | PASS | OPEN | MISMATCH | speech_lane_wm acceptance sentence |
| apoptosis_cosign | 2 | 6d57dd27 | PASS | PASS | MATCH | .sifta_state present |
| cortex_hierarchy | 8 | da578121 | PASS | OPEN | MISMATCH | cortex_hierarchy stale-history check |
| bypass_detector | 10 | 05e06ce3 | PASS | OPEN | MISMATCH | bypass_detector pending live George |
| grok_timeout | 2 | 34ad60c3 | PASS | PASS | MATCH | .sifta_state present |
| cowork_gateway | 6 | d81d51ef | PASS | PASS | MATCH | append-only |
| codec_traffic | 10 | 230601a7 | PASS | OPEN | MISMATCH | codec_traffic pending live George |
| watched_memory | 6 | b529d4dd | PASS | PASS | MATCH | append-only |
| typed_turn_queue | 7 | 0b62d9dc | PASS | PASS | MATCH | IDE mana not STGM |
| residue_feed | 3 | 5517ea82 | PASS | PASS | MATCH | tests dir |
| metabolic_gov | 8 | 33905c9b | PASS | OPEN | MISMATCH | metabolic_gov stale-history check |
| consciousness_bridge | 6 | 0e6c17cd | PASS | PASS | MATCH | append-only |
| eval_evidence | 8 | 48cab7cd | PASS | OPEN | MISMATCH | eval_evidence stale-history check |
| trace_quarantine | 7 | 8b9a1778 | PASS | PASS | MATCH | IDE mana not STGM |
| fable_ager | 3 | fb10141e | PASS | PASS | MATCH | tests dir |
| snapshot_integrity | 9 | baa63e54 | PASS | OPEN | MISMATCH | snapshot_integrity acceptance sentence |
| pacino_e2e | 2 | ddbdde9f | PASS | PASS | MATCH | .sifta_state present |
| mutation_governor | 7 | 08355cb2 | PASS | PASS | MATCH | IDE mana not STGM |
| tournament_anchor | 4 | 2151ac6b | PASS | PASS | MATCH | grep tournament_anchor |
| todo_inventory | 7 | b86bab7c | PASS | PASS | MATCH | IDE mana not STGM |

### Sample Summary

- MATCH: 16
- MISMATCH: 8
- ORIGINAL_MISSING: 0
- Reopened lanes: 8

## STT Confidence Histogram

Source: `.sifta_state/alice_conversation.jsonl`
Target local day: `2026-06-11`
Rows counted: 197
Mean: 0.7020659898477157
Min: 0.077
Max: 1.0

| Bucket | Count |
|---|---:|
| [0.00,0.25) | 4 |
| [0.25,0.50) | 69 |
| [0.50,0.75) | 32 |
| [0.75,1.00] | 92 |

- Exact 0.24 in Talk ledger: True
- Exact 0.41 in Talk ledger: True

Lowest Talk rows:

| Confidence | Text |
|---:|---|
| 0.077 | and we can let it rest on our own! This is how I'm going to target our own path because we can just take that and take t |
| 0.182 | I'm going to go to the bathroom. |
| 0.209 | I'll be right back. |
| 0.241 | Got him. |
| 0.252 | Thanks for watching! |
| 0.261 | Oh, no. |
| 0.262 | W-w-w-w-w? |
| 0.292 | That's it. |
| 0.296 | Okay. |
| 0.296 | Oh. |
| 0.297 | You |
| 0.298 | Oh |

Lowest wider STT rows (<0.50) across small .sifta_state ledgers:

| Ledger | Confidence | Text |
|---|---:|---|
| rlhf_self_cure_training.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |
| stt_empty_text.jsonl | 0.000 |  |

## C2 Mutation Governor Round Trip

- Status: `PASS`
- Restart method: `fresh_python_interpreter`
- Limitation: No long-lived mutation governor PID was found; the persistence contract is file-backed and was verified across a new Python process.
- Ledger: `.sifta_state/eval/r1022_c2_round_trip.jsonl`

## C12 Relabel

- Status: `OPEN`
- New label: `OPEN_BLOCKED_ON_GEORGE`
- Blocked on: Restart Talk, Say bare '4' after restart, Ask the Pacino screen question
- Ledger: `.sifta_state/eval/r1022_c12_relabel.jsonl`

## Fan-Out Arithmetic

- Expected: 48 rows (C1-C12 across 4 ledgers)
- Observed: 1 rows
- Status: `OPEN`

| Ledger | Count | Gap To 12 |
|---|---:|---:|
| work_receipts.jsonl | 1 | 11 |
| agent_arm_receipts.jsonl | 0 | 12 |
| ide_stigmergic_trace.jsonl | 0 | 12 |
| episodic_diary.jsonl | 0 | 12 |

## Final Audit Verdict

`r1022` remains `OPEN` under this audit.

Reasons:
- Seeded rerun reopened 8 probe lane(s).
- C12 is owner-blocked and cannot be closed by code.
- C1-C12 fan-out count is not 48 on disk.
