# D2 handoff — belief snapshot from lived experience

Job D2 of `Documents/ALICE_ADAPTIVE_INTELLIGENCE_HANDOFF.md` (line 117).
Owner: DeepSeek. Status: **code complete, 21 tests green, C0-validated; live hardware episode still
open** (no rover/Dell on this Mac — see `still_unverified`).

D2 turns the append-only lived-experience ledger into a *queryable belief*: what Alice currently
thinks exists, where it is, how old that evidence is, how uncertain she is, and which observations
contradict each other. Adaptation needs this because a planner that cannot tell "the mug is here"
from "the mug *was* here two minutes ago" will re-aim at furniture.

## Artifacts

| File | Change | sha256 |
| --- | --- | --- |
| `System/swarm_lived_experience_bridge.py` | modified: D2 belief layer + C0 projection | `bb89973fbdf4b552…` |
| `tests/test_swarm_lived_experience_belief.py` | new, 21 tests | `07940d17ff29834c…` |

Diff hash of `System/swarm_lived_experience_bridge.py`: `23c267084e5be8d641052eed9c2aff0f393ebaa9b3dc5c87f9e235875dab61d6`.

Original surface of the module is untouched: `record_lived_event`, `lived_experience_snapshot`,
`EpistemicStatus`, `ACTION_POLICY = "context_only_no_effector_authority"`. The belief ledger is a
separate append-only file, `.sifta_state/belief_observations.jsonl`.

## Consumption API

- `observe_entity(entity_id, *, kind, source, label=None, aliases=(), pose=None, pose_uncertainty_m=None,
  attributes=None, relations=None, confidence=0.5, epistemic_status=…, evidence_links=(), ttl_s=900.0,
  observed_at=None, now=None, observer="alice", context_key="", observation_id=None, state_dir=None)`
  → one ledger row. Classifies the record honestly: `DUPLICATE_REPLAY` | `STALE_REPLAY` | `FRESH`,
  with `freshens: bool` and a human `replay_reason`.
- `entity_belief(entity_id, *, now=None, state_dir=None, conflict_uncertainty=0.15)`
  → `{known, revision, moved_count, identity, pose, pose_known, attributes, relations, conflicts,
  contested, uncertainty, uncertainty_components{evidence_age,source_confidence,open_conflicts},
  evidence_age_s, evidence_ttl_s, stale, supporting_observation_ids, expired_evidence_ids,
  superseded_observation_ids, rejected_observation_ids, observation_count}`.
- `target_is_stale(entity_id, *, target_observation_id=None, now=None, state_dir=None)`
  → `{target_stale, reason, current_observation_id}` — the planner's "is the thing I aimed at still there" question.
- `belief_snapshot(*, body_id, entity_ids=None, pose=None, frame=None, map_ref=None, hypotheses=None,
  resource_state=None, now=None, state_dir=None, max_entities=64)`
  → **exactly** the C0 `belief_state` record (`schema_version 1.0.0`), byte-validated by
  `BeliefState.from_dict(raw); record.verify()` before it is returned. No extra top-level key.
- `belief_content_hash(snapshot)` → sha256 of the canonical record excluding `belief_id`; two snapshots
  of the same evidence agree, while their `belief_id`s differ (each capture is its own record).
- `_canonical_pose`, `_pose_distance` remain internal.

## Laws obeyed

1. **A replay cannot freshen a belief.** Duplicate detection is by *content identity*, checked before
   staleness: the same evidence arriving again — even under a new `observation_id` — is
   `DUPLICATE_REPLAY`, while older evidence is `STALE_REPLAY`. Both are appended with
   `freshens: False` and never rewrite the history that precedes them.
2. **An absent pose is `null`, never `(0,0)`.** No observation without a pose, and no map identity,
   can produce coordinates.
3. **A pose without a map identity is refused, not invented.** `belief_snapshot` raises
   `ValueError("… has a pose but no map_ref was supplied …")`; `map_ref.map_revision` must be a real
   `sha256:` hash (71 chars) or the snapshot raises rather than emitting a plausible-looking map id.
4. **A moved object invalidates the old target.** Movement beyond `DEFAULT_MOVED_THRESHOLD_M = 0.25 m`
   bumps `revision` and `moved_count`, records the prior observation in `superseded_observation_ids`
   and `conflicting_evidence`, and attaches `moved_from {pose, distance_m, observation_id}` to the
   current pose. `target_is_stale` then answers *stale, "a later observation moved the entity"*.
5. **Contradictions stay visible.** Attribute, pose and relation disagreements are recorded with
   `resolution: "UNRESOLVED"` and *both* observation ids and *both* values; they are never averaged away.
6. **A frame change is incomparable, not contradictory.** `map` → `odom` re-expression advances
   `revision` but claims no distance and raises no conflict.
7. **Uncertainty is decomposed**, never a single opaque number:
   `max(evidence_age, source_confidence) + 0.15 × open_conflicts`, capped at 1.0.
8. **No effector authority.** The belief layer carries
   `action_policy: "context_only_no_effector_authority"` and `effectors_allowed: []`; the C0
   `belief_state` record has no action field at all, so nothing here can authorize motion.
9. **The frozen record is not extended.** All Alice-native belief metadata rides inside
   `entities[].attributes` under the reserved `belief.` prefix (`belief.uncertainty`,
   `belief.evidence_age_s`, `belief.stale`, `belief.pose_known`, `belief.attribute.<name>`, …).
10. **Hashes identify records, never semantic similarity**, and every enumerated code is a sorted
    tuple, so output is byte-stable across processes and `PYTHONHASHSEED` values.

## Verification (commands and observed results)

```
python3 -m pytest tests/test_swarm_lived_experience_belief.py -q
  → 21 passed in 0.35s
PYTHONHASHSEED=12345 python3 -m pytest tests/test_swarm_lived_experience_belief.py -q
  → 21 passed in 0.29s
PYTHONHASHSEED=1 python3 -m pytest tests/test_swarm_lived_experience_belief.py \
    tests/test_swarm_adaptive_contracts.py tests/test_swarm_boot_identity.py -q
  → 103 passed in 1.08s            (D2 + C0 + D1, no regressions)
PYTHONHASHSEED=7 python3 -m pytest tests/test_swarm_lived_experience_bridge.py \
    tests/test_swarm_boot_census.py tests/test_swarm_stationary_belief_r1744.py -q
  → 17 passed in 6.39s             (original bridge surface + adjacent suites)
```

Complete episode on a scratch state dir (nothing written to live state):

```
classes: FRESH DUPLICATE_REPLAY | an identical observation is already recorded
move: FRESH
belief revision 1  moved 1
pose {'frame': 'map', 'uncertainty_m': 0.05, 'x': 1.4, 'y': 0.0,
      'moved_from': {'pose': {...x 0.0...}, 'distance_m': 1.4, 'observation_id': 'obs-1'}}
uncertainty 0.9
target_is_stale(obs-1) → {'target_stale': True,
      'reason': 'a later observation moved the entity', 'current_observation_id': 'obs-3'}
belief_snapshot(...).verify() → None            (C0 record is valid)
snapshot pose → {'covariance': [0.0025, 0, 0, 0, 0.0025, 0, 0, 0, 2.4674],
      'frame_id': 'map', 'map_id': 'lab', 'map_revision': 'sha256:cccc…', 'x_m': 1.4, 'y_m': 0.0, 'yaw_rad': 0.0}
conflicting_evidence → ["mug_1 pose prior={...x 0.0...} new={...x 1.4...} unresolved distance_m=1.4"]
```

`yaw_rad` is `0.0` with variance `(π/2)² = 2.4674` because this body never measured heading: the slot
is filled so the contract is satisfiable, and the covariance says plainly it was not a measurement.

## Failure and recovery (this job's own defects)

The first D2 run was `13 failed, 7 passed`. Five defects survived the projection fix and were repaired
in the implementation, not by weakening the tests:

1. **Replays freshened beliefs.** Only the `observation_id` was compared, so re-delivered evidence under
   a new id was classified `STALE_REPLAY` and content-identical evidence could overwrite belief. Fixed by
   fingerprinting observation *content* and checking identity before staleness.
2. **A move was detected but not surfaced.** `moved_from` was attached to a throwaway local dict, so
   `entity_belief()["pose"]["moved_from"]` raised `KeyError`. Fixed by carrying the move onto the pose
   that is actually returned.
3. **A frame change silently advanced nothing.** Cross-frame poses are not comparable, so the revision
   counter never moved when a pose was re-expressed in a new frame. Fixed: revision advances, distance
   and conflict are withheld.
4. **`target_is_stale` crashed on empty support.** It indexed `supporting_observation_ids[-1]` →
   `IndexError` when every observation had expired. Fixed: answer `current_observation_id: null` instead.
5. **The determinism test compared two different histories.** Each `observe_entity` call mints a uuid, so
   two "identical" states held different records. Fixed by pinning explicit observation ids and comparing
   `belief_content_hash` — the honest statement of "same evidence ⇒ same belief".

## Review packet (handoff lines 206–223)

```json
{
  "job_ids": ["D2"],
  "revision_or_diff_hash": "23c267084e5be8d641052eed9c2aff0f393ebaa9b3dc5c87f9e235875dab61d6",
  "artifact_hashes": {
    "System/swarm_lived_experience_bridge.py": "bb89973fbdf4b55296aba1346dd83306e29c1410d4c722bd97c24a8846760f4c",
    "tests/test_swarm_lived_experience_belief.py": "07940d17ff29834c3411ea95042d7ae937e11c23236812a6e0e9518b2b4abe37"
  },
  "contract_hash": "sha256:c2b1a7cb8ed76b18837d9ebedb745110ac22e50b466915ed5e364e385096d15f",
  "files_changed": [
    "System/swarm_lived_experience_bridge.py",
    "tests/test_swarm_lived_experience_belief.py",
    "Documents/D2_HANDOFF_BELIEF_SNAPSHOT.md"
  ],
  "commands_and_results": [
    {"cmd": "python3 -m pytest tests/test_swarm_lived_experience_belief.py -q", "result": "21 passed"},
    {"cmd": "PYTHONHASHSEED=12345 python3 -m pytest tests/test_swarm_lived_experience_belief.py -q", "result": "21 passed"},
    {"cmd": "PYTHONHASHSEED=1 python3 -m pytest tests/test_swarm_lived_experience_belief.py tests/test_swarm_adaptive_contracts.py tests/test_swarm_boot_identity.py -q", "result": "103 passed"},
    {"cmd": "PYTHONHASHSEED=7 python3 -m pytest tests/test_swarm_lived_experience_bridge.py tests/test_swarm_boot_census.py tests/test_swarm_stationary_belief_r1744.py -q", "result": "17 passed"},
    {"cmd": "python3 - <<'PY' … observe/entity_belief/target_is_stale/belief_snapshot on a scratch state dir … PY", "result": "verify()→None; moved_from distance_m=1.4; target_stale=True; conflicting_evidence 1 entry"}
  ],
  "scenario_manifest_hash": null,
  "scenario_manifest_note": "D2 ships no scenario manifest; the adaptation scenario runner is job E0 (GLM). null is intentional, not missing.",
  "baseline_and_candidate_metrics": {
    "baseline": {
      "queryable_belief": false,
      "c0_belief_state_emitted": false,
      "replay_can_freshen_belief": true,
      "moved_object_invalidates_target": false,
      "conflicts_retained_with_both_ids": false,
      "pose_without_map_identity_refused": false,
      "belief_tests": 0
    },
    "candidate": {
      "queryable_belief": true,
      "c0_belief_state_emitted": true,
      "replay_can_freshen_belief": false,
      "moved_object_invalidates_target": true,
      "conflicts_retained_with_both_ids": true,
      "pose_without_map_identity_refused": true,
      "belief_tests": 21
    }
  },
  "one_complete_episode_receipt": {
    "kind": "belief_episode",
    "state_dir": "scratch tempdir, live state untouched",
    "sequence": [
      {"observation_id": "obs-1", "record_class": "FRESH"},
      {"observation_id": "obs-2", "record_class": "DUPLICATE_REPLAY", "replay_reason": "an identical observation is already recorded"},
      {"observation_id": "obs-3", "record_class": "FRESH", "movement": "1.4 m > 0.25 m threshold"}
    ],
    "belief": {"revision": 1, "moved_count": 1, "contested": true, "uncertainty": 0.9},
    "planner_answer": {"target_stale": true, "reason": "a later observation moved the entity", "current_observation_id": "obs-3"},
    "c0_record": {"schema_version": "1.0.0", "validated_by": "BeliefState.from_dict(...).verify() → None", "bytes": 2038}
  },
  "failure_and_recovery_receipt": {
    "kind": "self_repair",
    "first_run": {"passed": 7, "failed": 13},
    "defects_repaired": [
      "replay classified after staleness (content identity not compared)",
      "moved_from attached to a discarded local dict",
      "frame change did not advance revision",
      "target_is_stale IndexError on empty supporting evidence",
      "determinism test compared two separately-minted histories"
    ],
    "repaired_in": "implementation; no test was weakened to pass",
    "final_run": {"passed": 21, "failed": 0}
  },
  "four_ledger_receipt_id": "d2-belief-snapshot-1a9092029cf3",
  "still_unverified": [
    "No live hardware episode: this body has no rover or ROS 2 node, so D2's ledger has never been fed by real sensor telemetry — only by explicit observe_entity calls.",
    "Map identity is supplied by the caller; nothing yet verifies a ROS map_revision actually corresponds to the frame the pose came from (D4/D5 territory).",
    "Behaviour under a genuinely large entity set (>64) is capped, not measured."
  ],
  "next_job": "D3 — per handoff order (C0+E0 → D1+G1 → D2 → D3): extend the belief layer with the next declared capability. E0 (GLM) and G1 (GLM) remain open in parallel."
}
```

## Ledger receipt

```
round_id   : D2
doctor     : deepseek
receipt_id : d2-belief-snapshot-1a9092029cf3
ledgers    : work_receipts.jsonl, agent_arm_receipts.jsonl, ide_stigmergic_trace.jsonl, episodic_diary.jsonl
```
