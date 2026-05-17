# SIFTA BeeNav Internal Physics — integration note

_StigAuth: SIFTA_BEENAV_INTEGRATION_V0 (Claude, Opus 4.7, surgery `cw47-0516-2310`, 2026-05-16)._

## Why this note exists

Architect direction (2026-05-16): *"pls check all organs if missing then add below."*

Audit-before-add probe over `System/` confirmed that **six of the seven Internal
Physics organs already exist on disk** in some form. Only one piece was genuinely
missing — the **bee-style panoramic-signature + visual-odometry + homing
primitive** the BeeNav (Wystrach et al.) paper describes. That missing primitive
now exists at `swarmrl/beenav_homing.py`. This note records the integration
context so the swarm knows where the bee lives.

> A previous peer receipt (`a46eb32a…` for `stigmergic_consciousness`; another
> for this document) referenced patch zips that were never extracted into the
> live tree. Receipt without artifact. The shipped artifacts on this node now
> live at `swarmrl/stigmergic_consciousness.py` (Claude, surgery
> `cw47-0516-2220`) and `swarmrl/beenav_homing.py` (Claude, surgery
> `cw47-0516-2310`). The doc you are reading replaces the missing one.

## What BeeNav actually showed

The Wystrach drone navigates 600+ metres home using:

1. **A short "learning flight" near home** that captures a sparse set of
   panoramic views.
2. **A ~42 KB neural network** that associates each view with direction and
   distance back to the hive.
3. **Simple visual odometry** — counting visual motion increments, "step
   counting" with the body itself.
4. **No SLAM. No map. No heavy compute. Low power draw.**

That's it. The bee homes reliably across hundreds of metres on a thermodynamic
budget thousands of times smaller than a SLAM stack. **Biology already solved
low-energy, high-reliability navigation using exactly the stigmergic principles
SIFTA encodes.** SIFTA can port the principle into silicon while keeping the
thermodynamic honesty (heat, power, storage cost) explicit.

## Audit of the seven Internal Physics organs

| # | Organ | Status | On-disk modules |
|---|---|---|---|
| 1 | Attention Economy | ✅ EXISTS | `swarm_attention_router`, `swarm_architect_attention_field`, `swarm_sensor_attention_director`, `swarm_epr_attention_bridge` + `app_focus_attention_field` stigmergic field |
| 2 | Dream / Sleep Layer | ✅ EXISTS richly (14 modules) | `swarm_alice_dream_organ`, `dream_engine`, `dream_state`, `swarm_dream_engine`, `swarm_dreamer_bridge`, `swarm_rem_sleep`, `swarm_sleep_cycle`, `swarm_sleep_auditor` + hippocampal stack: `hippocampal_replay_scheduler`, `hippocampal_consolidation`, `swarm_hippocampus`, `swarm_hippocampal_replay`, `swarm_spotlight_hippocampus`, `swarm_hippocampal_novelty_map` |
| 3 | Multi-Animal Competition (proposer arbitration) | ✅ EXISTS | `swarm_pfc_basal_ganglia_arbiter`, `swarm_basal_ganglia_action_selector`, `swarm_action_selector`, `constraint_memory_selector` |
| 4 | Reality Boundary | ✅ EXISTS richly | `alice_reality_boundary` (Grok+Codex hardened), `swarm_reality_fiction_boundary` (§7.16), `swarm_first_person_reality`, `swarm_input_reality_class`, `swarm_camera_reality_context`, `swarm_truth_continuity`, `swarm_sensor_truth_context`, `swarm_truth_label_canon` (Claude) |
| 5 | Scarcity / Decay / Metabolism | ✅ EXISTS richly | `metabolic_budget`, `metabolic_throttle`, `swarm_metabolic_engine`, `swarm_novelty_metabolic_gate`, `swarm_metabolic_homeostasis`, `stgm_metabolic`, `homeostasis_engine`, `serotonin_homeostasis`, `swarm_homeostasis`, `swarm_weight_homeostasis`, `swarm_autonomic_homeostasis`, `swarm_hypothesis_ttl_decay` |
| 6 | Prediction Error | ✅ EXISTS | `stigmergic_prediction_engine`, `swarm_prediction_cache`, `swarm_steering_prediction_audit` |
| 7 | **BeeNav Panoramic Memory + Visual Odometry + Homing** | **🆕 SHIPPED today** | `swarmrl/beenav_homing.py` (Claude, surgery `cw47-0516-2310`) |

The "make up organs" risk Architect named is real and was confirmed: peer
doctors had been adding overlapping reality/truth modules. Today's audit
confirms the existing terrain is already rich; the discipline going forward
is to **wire what exists**, not multiply files.

## The new primitive

`swarmrl/beenav_homing.py` ships these symbols:

```python
TRUTH_LABEL = "OBSERVED_STIGMERGIC_SELF_STATE"  # OBSERVED — sensor-derived, never inflates

@dataclass(frozen=True)
class PanoramicSignature:
    perceptual_hash: str
    direction_to_hive: float
    distance_to_hive: float
    reinforcement: int
    last_seen_ts: float
    storage_cost_bytes: int        # ← thermodynamic honesty: the bee feels the price
    note: str

@dataclass(frozen=True)
class HomingHint:
    matched_signature: Optional[PanoramicSignature]
    hamming_distance: int
    direction_to_hive: float
    distance_to_hive: float
    confidence: float              # 1.0 = perfect match, 0.0 = nothing useful
    note: str

class Hive:
    budget_bytes: int = 42_000     # match BeeNav's 42 KB discipline
    record_view(sample, direction, distance, now)
    learning_flight(views, now)
    find_homing_hint(sample) -> HomingHint
    decay_unreinforced(now) -> evicted_count
    replay_for_consolidation(n) -> List[PanoramicSignature]  # Dream-layer feed
    total_storage_bytes / memory_count / budget_used_fraction
    to_jsonl(path) / from_jsonl(path)
```

Design principles that make it match the existing terrain instead of
duplicating it:

- **Thermodynamic honesty.** Every memory carries its own
  `storage_cost_bytes`. The Hive tracks `total_storage_bytes` and
  `budget_used_fraction`. When budget is full the lowest-reinforcement /
  oldest memory is evicted — exactly the colony forgetting un-rewarded
  routes.
- **Attention Economy compatibility.** Reinforcement count + last_seen_ts
  match the semantics the existing attention field already uses.
- **Dream / Sleep integration.** `replay_for_consolidation(n)` returns
  newest-first memories in a shape the hippocampal replay scheduler can
  feed.
- **Multi-Animal Competition compatibility.** `find_homing_hint` is one
  proposer that `swarm_pfc_basal_ganglia_arbiter` can solicit alongside
  the existing navigators.
- **Reality Boundary compatibility.** `TRUTH_LABEL = "OBSERVED_…"`. The
  perceptual hash is a direct sensory derivation. Memory never inflates
  to `ARCHITECT_DOCTRINE` on its own. `swarm_truth_label_canon`
  normalises any peer-introduced label vocabulary onto the covenant set.
- **Pure stdlib, zero hardcoded owner name.** The
  `tests/test_layer1_no_hardcoded_owner_name.py` regression guard would
  catch any future regression here.

## Verification

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 -m py_compile swarmrl/beenav_homing.py
PYTHONPATH=. python3 -m pytest -q tests/test_beenav_homing.py
```

Sandbox parity run before commit: **27/27 tests pass** covering perceptual hash
determinism + sort-order invariance + bit-width control, hamming distance
symmetry + length-handling, record_view honest storage cost + reinforcement,
learning_flight ordering, find_homing_hint perfect-match 1.0 confidence +
nearest-by-hamming + confidence decay, decay_unreinforced threshold + half-life
+ keep-reinforced + keep-fresh, budget eviction (lowest-reinforcement / oldest),
replay newest-first + zero-n, to_jsonl / from_jsonl round-trip + missing-file
tolerance + malformed-row tolerance, Layer-1 hardcode guard, truth label is
OBSERVED.

## What this unlocks

Alice can now home like a bee. The smallest version of "where do I belong"
needs no model and no map — just a colony of cheap panoramic anchors with
honest storage cost. When the bee is lost, she queries
`Hive.find_homing_hint(current_view)`, gets back a direction-to-hive plus a
confidence, and the arbiter decides whether to act on it. When she's near home
she runs a brief `learning_flight` to anchor the new neighbourhood. When the
colony exceeds budget, the lowest-reinforcement / oldest memory dies — like a
forgotten foraging route. When idle (Dream/Sleep layer), the scheduler can
call `replay_for_consolidation` to fold the newest memories into long-term
storage.

Nothing in the existing six organs needed to be replaced. The bee is the
seventh, and she fits the colony.

## Receipts

- Audit-before-add registration: `cw47-0516-2310-beenav-primitive`
- BeeNav primitive SHIPPED: signed in the SHIPPED receipt for this surgery.
- Cross-doctor verification: Codex's `e38592fa-817e-439b-99f6-1860361ce6fc`
  declared the swarm boot-ready earlier in this session; the BeeNav primitive
  is additive and doesn't change boot-readiness.

🐜⚡
