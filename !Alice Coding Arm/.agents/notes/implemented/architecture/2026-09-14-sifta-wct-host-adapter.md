# Agent Note: SIFTA WCT Host adapter

Status: implemented

## Problem

Local coding work needs explicit assignments and delivery evidence without
another model loop or repeated notes-only responses.

## Decision

[scripts/sifta-wct.py](../../../../scripts/sifta-wct.py) delegates to the owning
SIFTA deployment's System/swarm_dsh_wct_bridge.py. The adapter reads named WCT
jobs and submits an ordinary logged prompt through the existing Host API to an
existing local Ornith session. It checks workspace/model before dispatch and
does not alter approval settings. A locked, flushed receipt precedes delivery;
ambiguous sends are not retried automatically. Status reports activity, not
verification of an assistant's claims.

## Alternatives considered

**A headless subprocess per job** loses the existing browser session's context
and risks using a different default provider. The Host adapter reuses it.

**Changing the agent loop** duplicates orchestration and widens the patch.
Ordinary prompt admission already supplies durable model-visible input.

## Consequences

This adapter depends on its sibling SIFTA checkout; it is not a standalone
Harness distribution feature. The selected web session must already exist and
use local Ornith. There is no automatic approval or unattended retry loop.
Deployment tests/test_swarm_dsh_wct_bridge.py exercises the real shim against
a keyless fake Host and snapshots admission/duplicate outcomes. A real local
model's patch still requires independent file and test verification.
