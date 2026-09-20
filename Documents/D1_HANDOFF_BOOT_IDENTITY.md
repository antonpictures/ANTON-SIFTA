# D1 handoff — boot identity, topology, and capability loss accounting

Job D1 of `Documents/ALICE_ADAPTIVE_INTELLIGENCE_HANDOFF.md` (line 115).
Owner: DeepSeek. Status: **code complete, verified on this Mac; real Linux/Pi smoke run still open.**

D1 gives Alice a *falsifiable name for the body she is in right now*. Before D1 the census could
describe hardware facts, but nothing carried a boot identity, a topology name, a headless verdict, or
a durable record of which organs were lost mid-boot. Adaptation across unfamiliar bodies needs
exactly that: the planner must be able to tell "this body has no camera" from "this body's camera
died three minutes ago".

## Artifacts

| File | Change | sha256 (head) |
| --- | --- | --- |
| `System/swarm_boot_identity.py` | new, stdlib-only, 31 kB | `8232582543d00493…` |
| `tests/test_swarm_boot_identity.py` | new, 37 tests | `f244a1a59fd43931…` |
| `System/swarm_boot_census.py` | wired: identity block + banner lines | `b1203812f75b3fbc…` |
| `System/swarm_capability_registry.py` | wired: availability gate | `1a361f3f556292aa…` |

Diff hash of the four artifacts (concatenated sha256): `2bd32e2bbcf9753ae08d4e043458dd79140774d2f820d3ebdcb0b61b345a57d9`.

## Consumption API

`System/swarm_boot_identity.py`

- `platform_id()` → `macos | linux_pi | linux_wsl | linux | windows | unknown`
- `is_headless(*, env=None, pid=None)` → `True | False | None` — `None` means *undetermined*, never a guess
- nullary probers: `probe_storage`, `probe_memory`, `probe_thermal`, `probe_battery`, `probe_network`,
  `probe_model_endpoint`, collected in `DEFAULT_PROBERS`
- `run_probes(*, probes=None, state_root=None)` → `{name: reading | None}`
- `topology_facts(readings=…)`, `topology_id(…)` → `topo:<32 hex>`
- `start_boot(*, state_root=None, readings=None, now=None, process_boot_id=None)`, `previous_boot()`,
  `current_boot()`, `boot_is_stale()`
- `record_capability_event`, `mark_lost`, `mark_recovered`, `capability_health`,
  `unavailable_capabilities`, `planning_view`
- `capability_snapshot(*, body_id, node_id, actions=(), sensors=(), state_root=None, probes=None, readings=None, now=None)`
  → validates against the C0 `CapabilitySnapshot` record
- CLI: `--state-root`, `--body-id`, `--node-id`, `--actions`, `--json`

Ledgers written (append-only): `.sifta_state/boot_identity.jsonl`, `.sifta_state/capability_health.jsonl`.

Wired consumers:

- `swarm_boot_census.boot_census(..., probe_boot_identity=True)` merges
  `boot_id`, `boot_sequence`, `previous_boot_id`, `topology_id`, `headless`, `body_roles`,
  `unavailable_capabilities`; `boot_census_lines()` renders
  `🧭  <topology_id>  |  roles <roles>  |  headless <bool>` and `⛔  unavailable now: …`.
- `swarm_capability_registry.capability_availability_gate(caps, state_root=…)` →
  `{"available": […], "unavailable": […]}`; a lost organ carries
  `backing["blocked"] = {"reason_code", "detail"}`, and `capability_field_summary()` reports
  `unavailable_now`.

The availability gate is **read-only and fail-open**: with no ledger present every capability stays
available, so an unrecorded boot can never silently disarm the body.

## Laws obeyed

1. **Readings are not probes.** `probes` maps *nullary callables*; `readings` maps *probe results*.
   Passing one where the other is expected was the D1 bug that fabricated a capability loss; the split
   is now enforced by signature and covered by tests.
2. **Unknown is null, never absent.** A raising probe, an unreadable sensor, or an undetermined
   headless verdict yields `None` and the field stays present.
3. **No invented hardware.** Sensor readings feed `topology_facts`; roles come from what the body
   actually measured.
4. **Loss and recovery are both recorded**, both with `reason_code` from the C0 enum, both appended to
   the same ledger, never rewritten.
5. **Planning view vs contract view.** `planning_view()` keeps `blocked_by` for local reasoning; the
   C0 `unavailable_capabilities` projection is narrowed to `name/reason_code/detail` only, because the
   contract forbids extra fields (`UNKNOWN_FIELD`).
6. **`stop` is never gated on capability freshness** — only body, boot, epoch, lease (C0 law, untouched).
7. **Nothing in the new module touches a GUI**: stdlib only, no import of the widget or Qt.

## Verification (commands and observed results)

```
python3 -m pytest tests/test_swarm_boot_identity.py -q
  → 37 passed in 0.68s

python3 -m pytest tests/test_swarm_boot_identity.py tests/test_swarm_adaptive_contracts.py -q
  → 82 passed in 0.89s            (D1 + C0 contract, no regressions)

python3 -m pytest -q tests/ -k "census or capability or hardware_plan" \
    --ignore=tests/test_doctrine.py --ignore=tests/test_origin_gate.py --ignore=tests/stress_test_69.py
  → 72 passed, 2 skipped, 1 failed   (the failure is unrelated — see below)

python3 -m System.swarm_boot_identity --json      (live Mac)
  → roles battery,display,memory,network,storage   headless false
    topo:2c97b2ff2aae09c1dac872fabcd57af6
    disk_free 361.579  disk_total 994.61  memory_available 13.284  battery 1.0/on_ac

SIFTA_STATE_DIR=<tmp> python3 -m System.swarm_boot_census
  → 🧭  topo:2c97b2ff2aae09c1dac872fabcd57af6  |  roles battery,display,memory,network,storage  |  headless False
    ⛔  unavailable now: model_endpoint, thermal

capability_availability_gate on live Mac
  → avail ['drive_forward','speak']
    unavail [('model_endpoint','UNSUPPORTED'),('thermal','UNSUPPORTED')]

capability_availability_gate on offline Dell readings
  → avail ['speak']
    unavail [('drive_forward','BLOCKED'),('battery','UNSUPPORTED'),('model_endpoint','UNSUPPORTED'),
             ('network','BLOCKED'),('thermal','UNSUPPORTED')]
```

Determinism: `topology_id` is byte-stable across processes; all enumerated codes are sorted tuples
(`tuple(sorted(...))`), never `frozenset` iteration order.

## Review packet (handoff lines 206–223)

```json
{
  "job_ids": ["D1"],
  "revision_or_diff_hash": "2bd32e2bbcf9753ae08d4e043458dd79140774d2f820d3ebdcb0b61b345a57d9",
  "contract_hash": "sha256:c2b1a7cb8ed76b18837d9ebedb745110ac22e50b466915ed5e364e385096d15f",
  "files_changed": [
    "System/swarm_boot_identity.py",
    "tests/test_swarm_boot_identity.py",
    "System/swarm_boot_census.py",
    "System/swarm_capability_registry.py"
  ],
  "commands_and_results": [
    {"cmd": "python3 -m pytest tests/test_swarm_boot_identity.py -q", "result": "37 passed"},
    {"cmd": "python3 -m pytest tests/test_swarm_boot_identity.py tests/test_swarm_adaptive_contracts.py -q", "result": "82 passed"},
    {"cmd": "python3 -m System.swarm_boot_identity --json", "result": "roles=battery,display,memory,network,storage headless=false topo=topo:2c97b2ff2aae09c1dac872fabcd57af6"},
    {"cmd": "SIFTA_STATE_DIR=<tmp> python3 -m System.swarm_boot_census", "result": "🧭 topo:2c97b2ff… | roles battery,display,memory,network,storage | headless False; ⛔ unavailable now: model_endpoint, thermal"}
  ],
  "scenario_manifest_hash": null,
  "scenario_manifest_note": "D1 ships no scenario manifest; the runner is job E0 (GLM). null is intentional, not missing.",
  "baseline_and_candidate_metrics": {
    "baseline": {
      "census_identity_fields": 0,
      "census_reports_topology_id": false,
      "census_reports_headless": false,
      "capability_loss_visible_to_planner": false,
      "capability_gate_withholds_lost_organ": false
    },
    "candidate": {
      "census_identity_fields": 7,
      "census_reports_topology_id": true,
      "census_reports_headless": true,
      "capability_loss_visible_to_planner": true,
      "capability_gate_withholds_lost_organ": true
    }
  },
  "one_complete_episode_receipt": {
    "body": "this Mac, boot recorded via start_boot(state_root=<tmp>, readings=MAC_READINGS)",
    "steps": [
      "start_boot → boot_id assigned, boot_sequence 1, previous_boot_id null",
      "mark_lost('thermal', reason_code='UNSUPPORTED') → row appended to capability_health.jsonl",
      "planning_view() excludes thermal; unavailable_capabilities() lists it with its reason_code",
      "capability_availability_gate([rvr1_drive, speak]) → available ['speak'], unavailable ['rvr1_drive'] once its backing organ is lost",
      "mark_recovered('rvr1') → gate returns both capabilities again"
    ],
    "result": "healthy → loss → recovered is observable end-to-end without rewriting a single ledger row"
  },
  "failure_and_recovery_receipt": {
    "failure": "probe *results* were passed where nullary *probers* were expected, so a null reading was invoked as a function and the census reported a fabricated capability loss",
    "fix": "introduced the probes/readings split; run_probes calls fn() only for nullary callables; a raising prober records null instead of propagating",
    "recovery_proof": "tests assert raising probe → None and that null readings never mark a capability lost"
  },
  "four_ledger_receipt_id": "d1-boot-identity-2bd32e2bbcf9",
  "still_unverified": [
    "No real Linux/Pi run: linux_pi and linux_wsl platform branches are covered by fixtures only, never by a live kernel.",
    "probe_model_endpoint is verified against a local endpoint only; its verdict under a real cloud cortex route is unproven.",
    "boot_census probes the live body, so its role list is this Mac's; the fixture-pinned role assertions live in the identity tests, not the census test."
  ],
  "next_job": "D2"
}
```

## Environment blocker (not caused by D1)

`python3 -m pytest -q` over the whole suite aborts with an INTERNALERROR in
`tests/test_doctrine.py` → `Kernel/origin_gate.py:64 sys.exit(1)`:
`Kernel/inference_economy.py` **HASH MISMATCH** against `Kernel/integrity_manifest.json`.
`Kernel/` is clean in git; the source file was last changed `c3b2f01f9` (2026-09-05) and the manifest
last regenerated `3af924ce9` (2026-07-09) — a stale manifest, not a code regression. Re-blessing is a
covenant action and needs the Architect's word. Recorded here, untouched.

Unrelated to D1 as well: `tests/test_alice_grounding_window.py::test_system_prompt_vendor_firewall_and_capability_bar`
fails because the sysprompt budget trims the `ALICE_SELF_ADDRESSING` block (70 blocks trimmed,
127849→36682 chars) that carries `ACTIVE_BRAIN_MODEL=`. The widget has no reference to any D1 code path
(`grep` for `swarm_boot_identity|swarm_boot_census|capability_availability_gate|capability_field_summary`
in `Applications/sifta_talk_to_alice_widget.py` → no matches).
