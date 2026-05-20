# Stigmergic FarSight

*A Physics-Driven Whole-Body Presence System at Large Distance and Altitude.*

(Previously: SIFTA FieldSight. File paths, class names, and historical receipts retain the old identifier.)

Lawful atmospheric-optics and search-and-rescue triage demo. §3.2 lawful: presence only, no biometric identity head.

## What It Runs

- Synthetic rescue target only; no real faces and no identity head.
- `System/swarm_turbulence_substrate.py` degrades the target through a
  turbulence model.
- `System/swarm_turbulence_organ.py` births r0 hypothesis swimmers and
  builds the Fried-parameter posterior.
- `System/swarm_sar_triage_organ.py` tests generic shape swimmers and reports
  target presence for human review.

## Receipts

The widget writes `.sifta_state/fieldsight_demo_receipts.jsonl` and the organs
write their own turbulence/SAR receipts when the demo runs.

## Boundary

This surface is for search, safety, conservation, inspection, and adaptive
optics. It is not a biometric identification app.

## Novel Next Idea

**Counterfactual Rescue Lens:** birth a second swarm after each frame that
simulates the next physical camera actions: move left/right/up/down, wait for a
different shimmer phase, change exposure, or zoom. Each action gets an expected
posterior-collapse score. The operator would see: `move 3 meters left; this
should cut r0 uncertainty and sharpen the SAR review box.`

That turns FieldSight from passive detection into active curiosity: Alice asks
the world for the next view that will teach her the most.
