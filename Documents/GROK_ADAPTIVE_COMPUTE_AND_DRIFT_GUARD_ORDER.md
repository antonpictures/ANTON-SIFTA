# Grok Order — Adaptive Compute + Self-Vector Drift Guards

Date: 2026-05-21
Author: Codex desktop, Surgeon/fact-check lane
Target: GTH4921YP3

## Boundary

Do not claim these are Gemini internals. The research supports the mechanisms;
the local SIFTA gates are `HYPOTHESIS_LOCAL_MECHANIC`.

## Files

- `System/swarm_adaptive_compute_gate.py`
- `System/swarm_self_vector_drift_guard.py`
- `tests/test_adaptive_compute_gate.py`
- `tests/test_self_vector_drift_guard.py`
- `Documents/GEMINI_AGENTIC_CLAIMS_FACTCHECK_2026-05-21.md`

## What To Verify

1. Run:

   `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest tests/test_adaptive_compute_gate.py tests/test_self_vector_drift_guard.py -q --tb=short -p no:cacheprovider`

2. Confirm adaptive compute behavior:

   - high entropy + high conflict -> `DEEPEN`
   - low uncertainty -> `FAST_PASS`
   - high thermal/STGM/latency pressure -> `DEFER`
   - no real ledgers touched

3. Confirm drift guard behavior:

   - near-identical anchor/current -> `STABLE`
   - medium mismatch -> `META_REVIEW`
   - orthogonal mismatch -> `LOCKDOWN_REVIEW`
   - missing anchor -> `NO_ANCHOR`
   - no real ledgers touched

## Wiring Rule

These are consideration-step gates only. They may recommend deeper compute or
review, but they do not call models, tools, effectors, wallets, or ledgers.

If wiring into Talk later:

- Adaptive compute may choose the local reasoning budget before LLM invocation.
- Drift guard may add a `META_REVIEW` context block before response generation.
- Neither gate may write canonical receipts unless a separate caller writes a
  normal OBSERVED receipt after acting.

## Research Spine

Use `Documents/GEMINI_AGENTIC_CLAIMS_FACTCHECK_2026-05-21.md`.

Key split:

- `WEB_VERIFIED_2026-05-21`: adaptive compute, entropy early exit, cosine drift
  monitoring.
- `SIFTA_HYPOTHESIS`: our local gates.
- `FORBIDDEN_VENDOR_CLAIM`: "Gemini does this internally" unless Google
  publishes the mechanism.
