# Alice rover intent contract v1 — proposed boundary

Status: `HYPOTHESIS`, ready for schema implementation and simulator tests; not yet
accepted by David or verified on his hardware. Companion to
[the coding handoff](ALICE_ADAPTIVE_INTELLIGENCE_HANDOFF.md), under
[the canonical covenant](IDE_BOOT_COVENANT.md).

## Placement and compatibility

```text
Alice goal/capability/tool router
    -> authenticated intent transport -> Dell mission adapter
    -> local ROS 2/Nav2/SLAM -> chassis controller -> ESP32/RVR1
    <- observation + lifecycle + independently verified outcome <-
```

Reuse `stigmerobotics_remote_link.py` pairing, scope and transport where compatible.
The existing velocity queue has exact fields and short lifetimes; v1 mission intents
need a separate versioned queue/route and journal. Do not stretch a millisecond velocity
command into a long-running navigation mission or remove the current RVR1 limits.
Legacy velocity and new mission modes share one local control owner; switching modes
cancels/reconciles the prior owner before accepting new movement.

V1 is planar ground navigation. Goals express outcomes, not wheel/motor commands. The
Dell owns localization, controller configuration, kinematics and reflexes. Its manifest
advertises actual actions, sensor coverage, body dimensions, turning radius, velocity
limits, localization quality and map identity. Unsupported actions return structured
errors. `navigate_to_object` and `explore` may initially be advertised unavailable.

## Common intent envelope

Strict JSON; required fields below; unknown fields rejected except inside `extensions`.
IDs are nonempty strings; UUIDs for command/event IDs. Numbers must be finite. Bounds,
message size and deadline limits belong to the published schema/manifest. Credentials
belong to authenticated transport, never logged message payloads.

```json
{
  "schema": "sifta.rover.intent/1",
  "command_id": "uuid",
  "goal_id": "uuid",
  "body_id": "david-rover",
  "expected_boot_id": "uuid",
  "control_epoch": 7,
  "capability_revision": "sha256:...",
  "issued_at_utc": "2026-09-20T09:30:00Z",
  "admission_ttl_ms": 3000,
  "execution_timeout_ms": 60000,
  "kind": "navigate_to_pose",
  "args": {
    "map_id": "bench-map",
    "map_revision": "sha256:...",
    "frame_id": "map",
    "x_m": 1.2,
    "y_m": 0.4,
    "yaw_rad": 0.0,
    "position_tolerance_m": 0.1,
    "yaw_tolerance_rad": 0.15
  },
  "extensions": {}
}
```

The example values are simulator fixtures, not measured hardware limits. Use metres,
seconds and radians with body x forward, y left, z up; maintain `map → odom → base_link`
transforms. See [ROS REP 103](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0103.rst)
and [REP 105](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0105.rst).

| `kind` | Exact `args` fields and semantics |
| --- | --- |
| `navigate_to_pose` | `map_id`, `map_revision`, `frame_id="map"`, `x_m`, `y_m`, `yaw_rad`, positive `position_tolerance_m`, positive `yaw_tolerance_rad`. Fresh localization and matching map revision required. |
| `navigate_to_object` | `object_id`, `observation_id`, `max_observation_age_ms`, positive `standoff_m`, positive `position_tolerance_m`. Resolve a grounded object track into an approach pose on the Dell; revalidate before movement and on target changes. Return `TARGET_UNKNOWN`, `TARGET_STALE` or `UNSUPPORTED` when needed. A language label alone is insufficient. |
| `explore` | `map_id`, `map_revision`, `frame_id="map"`, `boundary_xy_m` (simple polygon of at least 3 `[x,y]` vertices), positive `max_distance_m`, `coverage_target` in `(0,1]`. Dell chooses frontiers within this region and the execution timeout. Report coverage method, achieved coverage and termination reason; exhausted budget is a partial result, not target success. |
| `stop` | `reason` (bounded string). Stops all motion for this body and cancels pending/running missions for the current control session. Locally idempotent; no map, sensor or capability availability dependency. Hardware emergency stop remains independently effective. |

Object standoff and tolerances must fit the measured footprint and localization
uncertainty. Ackermann planning must honor curvature and swept volume; a differential
controller may rotate in place only where its footprint/clearance permits. Identical
intent shapes do not imply identical reachable goals or performance.

## Delivery, lifecycle and recovery

- Admission time is separate from mission runtime. Stamp ingress and queue residence
  with the receiving clock; the client subtracts the entire poll/request duration
  conservatively from remaining admission TTL, as the existing gateway does. UTC is
  for audit, not the sole freshness clock. Never compare monotonic clocks across hosts.
  Each transport hop must preserve consumed lifetime; a retry never starts a fresh TTL.
- Authenticate scope and body/session first. Normal movement requires matching boot,
  control epoch, capability revision and current control lease. Reboot creates a new boot
  ID and expires old motion. Reconnect does not silently re-arm an old mission.
- `stop` still requires authenticated body control but bypasses map/capability checks and
  ordinary work queues. A delayed valid stop may stop current work; it cannot restore
  motion. Physical emergency stop does not depend on network authentication or software.
- Journal `(body_id, boot_id, control_epoch, command_id, payload_hash)` before dispatch.
  Same ID/same payload returns the current stored outcome; same ID/different payload is
  `ID_CONFLICT`. Retain dedupe records through the replay window. No claim of exactly-once
  physical effects: after a crash between send and acknowledgment, query/reconcile; if
  unresolved, stop and report unknown, never blindly resend movement.
- States: `received -> accepted -> running -> succeeded|failed|cancelled|timed_out`;
  admission can end `rejected`. Terminal outcomes are immutable. `unknown` describes an
  unresolved delivery/execution observation; later evidence may resolve it. Append any
  correction with provenance rather than rewriting history.
- One active movement mission per body. A second receives `BUSY`; replacing it requires
  cancelling/stopping and observing quiescence before submitting a new command. Stop is
  prioritized even under a full queue or slow model/HTTP response.
- Heartbeats, mission deadline and local motor watchdog are separate. Configure and bench
  measure heartbeat period, lease expiry, sensor freshness, stopping distance and watchdog
  bound as a body profile. Link/lease loss causes a local controlled stop and checkpoint.
  The ESP32 watchdog handles Dell failure. Simulation defaults do not qualify hardware.
- Stop success requires zero-motion evidence from fresh odometry/controller state over
  the configured dwell period. A stop packet acknowledgment alone is `STOP_REQUESTED`.
  If the sensors cannot verify rest, publish `STOP_UNVERIFIED` and retain the local stop.

## Observation and result envelope

One `sifta.rover.event/1` schema with required fields:

```text
event_id, body_id, boot_id, control_epoch, seq,
command_id (nullable for body health), kind,
source_time {value, domain}, source_age_ms,
payload, evidence_refs
```

The receiving side appends its own `received_at_utc`, `received_monotonic_s` and
`receiver_boot_id`. Source/transport age and local time since receive must be accounted
for; receipt time alone cannot make a cached sensor sample fresh. Sequence is monotonic
within `(body_id,boot_id)`; reordered historical samples may be retained without rolling
back current state. New boots invalidate former freshness and motion assumptions.

`kind` is `capabilities`, `telemetry`, `command_state` or `fault`:

- `capabilities`: the `CapabilitySnapshot` body profile, ROS distribution/package versions,
  firmware hash/version, schema versions, map identity and available actions.
- `telemetry`: `pose` nullable (`map_id`, `map_revision`, `frame_id`, `x_m`, `y_m`,
  `yaw_rad`, row-major 3×3 x/y/yaw covariance); `twist` nullable (`linear_m_s`,
  `angular_rad_s`); `battery_fraction` nullable; `localization_status`;
  `active_command_id` nullable; `sensors` map of health, coverage, age and source IDs;
  `estop_active`, `control_lease_remaining_ms`, and `faults` list. Unknown is null.
- `command_state`: `state`, `reason_code`, `progress` nullable, `result` nullable,
  `effect_receipt_id` nullable. Result contains `postcondition_verified`,
  `verifier`, `observation_ids`, actual duration/distance/cost where measured,
  and structured diagnostics. Progress is an estimate, not success proof.
- `fault`: stable `code`, affected capability, evidence and recovery status.

Base reason codes: `UNSUPPORTED`, `INVALID_ARGUMENT`, `ID_CONFLICT`, `WRONG_BODY`,
`STALE_BOOT`, `STALE_CAPABILITY`, `EXPIRED`, `BUSY`, `LEASE_LOST`, `MAP_MISMATCH`,
`LOCALIZATION_LOST`, `TARGET_UNKNOWN`, `TARGET_STALE`, `SENSOR_STALE`, `BLOCKED`,
`CONTROLLER_FAILED`, `CANCELLED`, `TIMEOUT`, `OUTCOME_UNKNOWN`, `STOP_UNVERIFIED`.
Successful/partial terminal reasons include `ARRIVED`, `COVERAGE_REACHED`,
`BUDGET_EXHAUSTED` and `STOPPED_VERIFIED`; budget exhaustion is `timed_out` or `failed`
with achieved coverage attached, never `succeeded` unless the target predicate was met.

For navigation, success requires the local navigator result plus fresh pose within the
requested tolerances, valid map/localization and a measured rest dwell. Keep the
raw navigator outcome and independent verifier result distinguishable. Nav2 exposes
navigation, cancellation, feedback and result methods; pin David's installed distribution
and use its matching API. See [Nav2 Simple Commander](https://docs.nav2.org/rolling/configuration_and_development/simple_commander_api/simple_commander_api/).

## First integration and chassis-swap proof

1. DeepSeek publishes schema and fixtures; GLM implements SIFTA transport and fake Dell.
2. David supplies OS/ROS versions, actual firmware/protocol revision, body dimensions,
   sensor coverage, odometry and actuator semantics. Record them in the body profile.
3. GLM connects the Dell adapter; validate pose feedback and stop with the bench setup.
4. Run one `navigate_to_pose`: same command ID reaches both journals; independent pose
   verification reaches Alice's experience path and receipts.
5. Repeat fault cases: network loss, sensor loss, duplicate command, delayed acknowledgment,
   reconnect, restart, obstacle, cancellation and full queue.
6. Change Ackermann to differential via Dell driver/controller/body profile only. Keep
   the SIFTA intent schema and planning source hash unchanged. Rerun the same reachable
   goal suite; document goals that are infeasible on one body. This is the contract proof.
