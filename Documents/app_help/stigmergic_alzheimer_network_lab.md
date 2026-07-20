# Stigmergic Alzheimer Network Lab

Educational synthetic connectome simulator. It models Alzheimer-like deposits as
stigmergic signals spreading across weighted brain-region edges, with clearance
evaporation and vulnerable-region amplification.

Medical boundary: no PHI, no diagnosis, no treatment guidance, and no clinical
decision support.

Use:

- Choose a seed region.
- Adjust Spread, Clearance, and Vulnerability.
- Press Step for one tick, Run/Pause for continuous ticks, Reset to reseed.
- Export Receipt writes a snapshot to `.sifta_state/alzheimer_stigmergic_sim_receipts.jsonl`.

Truth labels:

- `OPERATIONAL`: synthetic simulator, app registration, receipts, deterministic tests.
- `HYPOTHESIS`: future de-identified OASIS/ADNI-style import.
- `FORBIDDEN`: diagnosis, cure, treatment selection, real patient prediction.
