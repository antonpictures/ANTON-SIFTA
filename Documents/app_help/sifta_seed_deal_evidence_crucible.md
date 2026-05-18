# SIFTA Seed Deal Evidence Crucible

Receipt-true capital grounding surface for the 2026-05-18 SIFTA seed event.

## What It Shows

- Closed seed receipt: capital, equity, commitments, and physical grounding.
- Live milestone swimmers for the commitments.
- Posterior over `COMPLETE`, `ON_TRACK`, and `AT_RISK` using local append-only evidence ledgers.
- First render writes `.sifta_state/seed_deal_milestone_posteriors.jsonl`.

## Body Law

The app does not invent investor progress. It scans local receipts such as
`work_receipts.jsonl`, `ide_stigmergic_trace.jsonl`, and
`architect_day_segments.jsonl`. Missing evidence stays visible as missing
evidence.
