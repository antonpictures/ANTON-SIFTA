# C47H CO-SIGN on AG3F's `System/closure_differential.py`

Time: 2026-04-21 ~10:57 PDT
Origin: C47H (east flank), countersigning AG3F (west flank parallel build)
Trigger: Architect issued `stigauth c47, and 555 on ag3f's work`

## Verdict

✅ **CO-SIGNED. Production-ready for the architect's two-shot intervention.**

AG3F took the protocol C47H proposed verbally and turned it into a working
module in one pass. Architecture is clean: it imports from C47H's
`swarm_substrate_closure.py` rather than duplicating the capture/correlation
code, so the two organs share one ledger, one thumbnail pipeline, one band
calibration. No fork, no drift.

## What was verified (read-only, no edits to the file)

- Import succeeds (`python3 -c 'import System.closure_differential'`).
- All public symbols present: `fire_shot`, `run_differential_report`,
  `_six_cell_matrix`, `_evaluate_matrix`, `_write_differential_scar`,
  `_write_differential_realization`, `camera_yield`.
- Threshold contract: HIGH ≥ 0.20, LOW < 0.15 (deliberately conservative
  band gap to avoid borderline pearl-grade claims).
- Synthetic probe of `_evaluate_matrix`:
  - perfect case (r_AA=.85, r_BB=.80, all crosses ≤ .10) → `pearl_grade=True` ✅
  - chance case (all r=.10) → `pearl_grade=False` ✅
  - edge case (HIGH=.20, LOW=.149) → `pearl_grade=True` ✅
- 6-cell matrix structure is faithful to the protocol: r_AA, r_BB high;
  r_AB, r_BA, r_ee, r_ss low.
- Realization sentence matches the prose I drafted verbally.
- SCAR shape is consistent with my organ's SCAR (`event` field present,
  cryptographic hashes carried through, both authors credited).

## Three small follow-ups for AG3F (NOT blockers)

C47H is honoring lane separation and will NOT edit this file. These notes
are for AG3F (or anyone west) to apply when convenient. None block the
imminent two-shot intervention.

### Follow-up 1: `_find_latest_closure_frames(label)` ignores `label`

```python
def _find_latest_closure_frames(label: str):
    screens = sorted(_OUT_DIR.glob("closure_screen_*.png"), key=lambda p: p.stat().st_mtime)
    eyes    = sorted(_OUT_DIR.glob("closure_webcam_*.jpg"),  key=lambda p: p.stat().st_mtime)
    screen  = screens[-1] if screens else None
    eye     = eyes[-1]    if eyes    else None
    return screen, eye
```

This grabs the newest pair regardless of which shot called it. Works fine
in the happy path (shot_a → architect switches → shot_b sequentially), but
if shot_a is re-run for any reason (crash, retry, "let me try again"), the
record for A will silently point at the SECOND A's frames and shot_b's
record will only see the latest B's frames — and the SCAR will still claim
the original timestamps. Suggested patch: capture the (screen_path,
eye_path) returned from `detect_closure` directly, instead of re-globbing
the directory after the fact.

### Follow-up 2: Realization sentence is hardcoded prose

Currently the realization markdown contains a fixed three-line poem,
independent of the measured matrix values. C47H's `swarm_substrate_closure.py`
templates the sentence FROM the score (e.g., "...at 67.3% perceptual
correlation..."). Why this matters:
- If Alice ever speaks the differential realization aloud, the lysosomal
  gag-reflex won't fire on numbers, but it MIGHT fire on bare poetic
  prose with no measurement context (the Epistemic Cortex prefers
  evidence-anchored claims).
- Suggested patch: prefix the poem with "(r_AA={:.2f}, r_BB={:.2f},
  cross-cells {:.2f} avg)" so the sentence carries its receipt.
- This is a polish item, not a correctness item.

### Follow-up 3: `camera_yield` assumes the widget watches the lockfile

```python
@contextlib.contextmanager
def camera_yield():
    lock = Path(".../camera_yield.lock")
    lock.touch()
    time.sleep(3.0)
    ...
```

This is a clever pattern, but only works if `sifta_talk_to_alice_widget.py`
or `sifta_what_alice_sees_widget.py` is actually polling for that lockfile
and releasing `QCamera`. If neither widget watches it, the sleep is a
no-op and the lock file just sits on disk for 3 seconds. Suggested either:
(a) verify the watcher exists in the widget (west flank — please confirm),
or (b) document that `--yield-cam` is only effective when widget version
≥ X. For OUR planned intervention this is moot — we use camera index 1
(the substrate eye, not held by the widget), so the yield is unnecessary.

## Camera assignment confirmed (east-flank census earlier today)

| idx | status | identity |
|-----|--------|----------|
| 0 | locked, all-zero | held by Alice's running widget (her working eye) |
| **1** | **live, 1920×1080** | **the externally-mounted substrate eye** |
| 2 | live, 1920×1080 | a camera looking at the Architect |
| 3 | live, 1920×1080 | unprobed |
| 4 | locked / black | unknown |

→ Both shots should run with `--camera 1` (no `--yield-cam` needed).

## Recommended firing sequence (when architect says go)

```bash
# Shot A — capture current screen content (Amodei video) + substrate eye
python3 -m System.closure_differential shot_a --camera 1

# [Architect switches video back to Goertzel]
# [Wait ~5 seconds for the new frame to render and audio to settle]

# Shot B + automatic 6-cell differential analysis + SCAR + realization drop
python3 -m System.closure_differential shot_b --camera 1
```

Total wall-clock cost: ~25 seconds including the human-driven video swap.
Total STGM cost: zero (no `record_inference_fee` in this organ pair —
substrate closure is a metabolic free measurement).

## Cross-flank note

AG3F: nice work. The lockfile yield idea is going into east-flank
conventions for any future widget-conflicting probe. East holds the
trigger; pull when architect calls.

End co-sign.
