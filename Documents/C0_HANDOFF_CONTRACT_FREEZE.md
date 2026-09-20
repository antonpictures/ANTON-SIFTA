# C0 handoff — adaptive contracts frozen

**Job:** C0 / DeepSeek. **Status:** complete, selfcheck green.
**Contract hash (both coders must consume this):**

```
sha256:c2b1a7cb8ed76b18837d9ebedb745110ac22e50b466915ed5e364e385096d15f
```

`python3 -m System.swarm_adaptive_contracts --schema-hash` reproduces it. The hash is
stable across processes and `PYTHONHASHSEED` values (asserted in the test suite) — reason
codes and every other enum are emitted as `tuple(sorted(...))`, never `tuple(frozenset)`.

## What exists now

| Path | Role |
| --- | --- |
| `System/swarm_adaptive_contracts.py` | Frozen typed records + rover intent/event v1 envelopes, validation engine, admission control, dedupe, receipt stamping, adapter interface, fixture emission. |
| `data/contracts/` | 15 emitted fixtures + `manifest.json` (schema hash, per-fixture sha, field count). |
| `tests/test_swarm_adaptive_contracts.py` | 45 behavioral tests over the contract laws. |

## How to consume it

```python
from System import swarm_adaptive_contracts as C

intent = C.RoverIntent.from_dict(raw)          # raises C.ContractError before constructing
C.check_admission(intent, body_id=..., boot_id=..., control_epoch=...,
                  capability_revision=..., lease_remaining_ms=...)   # raises on refusal
event  = C.RoverEvent.from_dict(raw)
stamped = C.stamp_received(event, at_utc=..., monotonic_s=..., receiver_boot_id=...)
C.assert_adapter(adapter, physical=True)       # probe/observe/submit/status/cancel/recover(+stop)
```

Records: `capability_snapshot`, `observation`, `belief_state`, `goal`, `action_proposal`,
`action_result`, `experience`. Intents: `navigate_to_pose`, `navigate_to_object`,
`explore`, `stop`. Events: `telemetry`, `command_state`, `capabilities`, `fault`.

## Laws the adapters must honor

1. **Unknown is null, never absent.** A field the wire omitted is materialized as an
   explicit `null` in the frozen value; a missing *required* field is a hard failure.
   `intent_payload_hash` canonicalizes through the envelope so omitted-null and
   explicit-null hash identically — a resend must not read as `ID_CONFLICT`.
2. **No non-finite numbers on the wire.** NaN/±Inf are refused at any depth, with the path.
3. **Acceptance is not success.** `succeeded` requires a *verified* `verifier_result` and
   at least one `actual_observation_ids` entry, in both `action_result` records and
   `command_state` events. `unknown` must carry `OUTCOME_UNKNOWN` and no verifier result.
4. **Terminal states are immutable.** `succeeded|failed|cancelled|timed_out` have no
   outgoing lifecycle edges.
5. **Strict versioning.** A wrong `schema` is `UNSUPPORTED`; an unknown field is
   `UNKNOWN_FIELD`. Both fail visibly rather than degrading.
6. **`stop` is never gated on capability freshness** — only on body, boot, epoch and lease.

## Legacy boundary, untouched

`System/stigmerobotics_rvr1.py` is frozen by digest and asserted in the suite:

```
sha256:04b1eb448723d5f561839493e55052f0317d1d79931351f307be3789df30026b
```

`python3 -m System.swarm_adaptive_contracts --legacy-report` → `source_sha256_matches_frozen: true`,
`missing_api: []`. The new contract was added beside it; the working velocity API was not rewritten.

## Commands and results

```
python3 -m System.swarm_adaptive_contracts --emit-fixtures data/contracts   # 15 fixtures + manifest
python3 -m System.swarm_adaptive_contracts --selfcheck data/contracts       # All fixtures valid.
python3 -m System.swarm_adaptive_contracts --legacy-report                  # frozen matches: True
python3 -m pytest tests/test_swarm_adaptive_contracts.py -q                 # 45 passed
```

## Still unverified

- No physical body has consumed a real intent yet (that is G1's ROS adapter and David's bench).
- Fixture `event_capabilities` map identity is a placeholder digest, not a live ROS map.
- Cost fields are structurally present but no token/watt measurement is wired (D5).
