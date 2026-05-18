# SIFTA FieldSight

Lawful atmospheric-optics and search-and-rescue triage demo.

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
