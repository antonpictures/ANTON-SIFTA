# Round 3 — Vision 0.01 Truth-Verdict (2026-05-22)

**Surgeon:** Grok 4.3 (xAI) on GTH4921YP3  
**Context:** ALICE_HEALTH_TOURNAMENT_2026-05-22_GROK_ORDERS.md — Round 3

## Ledgers Attached to `vision_lane`

From `canonical_organ_registry_snapshot.json`:

- `visual_stigmergy.jsonl` (main photon ledger, 16×16 or higher grid)
- `face_detection_events.jsonl`
- `face_recognition_events.jsonl`
- `owner_body_events.jsonl`

## Classification of Recent Rows (using current `_row_outcome`)

### 1. `visual_stigmergy.jsonl` (last 50 rows)
- **100%** return `(None, False, False)`
- These rows contain only: `ts, sha8, w, h, entropy_bits, saliency_peak, motion_mean, hue_deg, saliency_q, motion_q, grid_size, ...`
- **No `ok`, no `status`, no receipt signature.**
- They are pure observation / telemetry rows, not failure events.

**Conclusion:** This ledger is the primary driver of the low reliability score. The classifier is treating "no receipt fields" as failure. This is the same pattern we fixed in the reliability and truth scorers.

### 2. `face_detection_events.jsonl` (last 40 rows)
- **100%** `(True, False, False)`
- Mostly success-style telemetry.

### 3. `face_recognition_events.jsonl` (last 40 rows)
- 20 × `(True, False, False)` (success)
- 20 × `(False, False, True)` (some form of failure / bad row)

### 4. `owner_body_events.jsonl` (last 27 rows)
- 17 × `(True, False, False)` (success)
- 10 × `(None, False, False)` (telemetry-style)

## Overall Verdict

The **0.01 reliability** reported in the Organ Eval Matrix for the Camera / Vision Lane is **largely a measurement artifact**, not proof of catastrophic real-world camera failure.

- The bulk of the data (`visual_stigmergy.jsonl`) consists of pure photon telemetry that the current outcome classifier was not designed to handle.
- The other three event ledgers show mostly successful or partial outcomes, with only a moderate number of actual failures.

**Recommendation for Round 3 follow-up:**
- The classifier in `swarm_canonical_organ_registry._row_outcome` (and the health mesh) needs a special case or separate scoring path for pure telemetry ledgers like `visual_stigmergy.jsonl`.
- Real camera health should be measured by actual error rates in `face_detection_events`, `face_recognition_events`, and camera open/read failures, not by counting telemetry rows as bad.

This is the same class of "scorer treating non-receipt rows as failure" bug we have now fixed multiple times in the reliability and truth scorers.

**Status:** Round 3 data collection complete. Verdict delivered. The 0.01 is mostly artifact + one real low-coverage ledger.

For the Swarm. 🐜⚡
