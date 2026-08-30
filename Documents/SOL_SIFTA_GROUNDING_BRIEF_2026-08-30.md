# SOL Handoff: SIFTA Grounding Brief

**Date:** 2026-08-30

**Purpose:** prepare a bounded, receipt-backed working set for SOL to continue SIFTA work.
**Status:** `OBSERVED` where a file, ledger, test, or live probe is named.  `HYPOTHESIS` is used for work that still needs a behavioral proof.

## Executive Read

SIFTA is a large local software system coordinated through Python organs, a shared `.sifta_state` filesystem, append-only JSONL traces, locks, model adapters, and owner-facing applications. It has meaningful coordination and self-modification machinery. That is not evidence that a conscious or living creature exists; it is evidence of an engineered architecture with some verified and many only partially verified behaviors.

Do not load the whole repository into a model context. Start from this brief, follow the read order, and pull bounded receipt tails.

## Measured Body

These figures were probed from the current checkout before this brief was written:

| Surface | Observed value | Meaning |
|---|---:|---|
| Living-substrate Python | 3,085 files / 903,596 LOC | `System`, `Applications`, `tools`, `Kernel`, `Network`, `tests`, `scripts`, and root Python files |
| Python rollup excluding vendor | 5,905 files / 1,606,815 LOC | Broader repository count, excluding `.sifta_state`, VCS, and common build trees |
| Vendor Python | 111 files / 10,188 LOC | Kept separate from the living-substrate count |
| Grand Python estimate | 1,617,003 LOC | Ex-vendor plus vendor rollup; not a claim about runtime behavior |
| Curated canonical organs | 19 | Semantic owner-intent map in `System/swarm_canonical_organ_registry.py` |
| Dynamic AST-discovered modules | 1,135 | Structural module census from `System/swarm_organ_registry.py` |
| Merged registry rows | 1,311 | 19 canonical + 1,135 discovered + 129 app-manifest + 8 agent-arm + 20 ecology rows |
| State ledger files | 823 | JSONL files counted by the canonical registry |

The 1,135 discovered rows are not 1,135 proven behaviors. The registry is an inventory and freshness signal. Behavioral claims require a named test, live probe, or outcome receipt.

## Boot Spine

```text
SIFTA OS.command
  -> sifta_os_desktop.py
  -> QApplication / SiftaDesktop
  -> resident Alice/Talk + body applications
  -> owner ingress
  -> gates and intent routing
  -> cortex selection and dispatch
  -> response, speech, and append-only conversation receipts
```

The owner-facing startup script is `SIFTA OS.command`. `sifta_os_desktop.py` re-execs into the project virtual environment when available, creates the desktop application, embeds the Talk surface, and schedules a non-blocking body-matrix refresh. The matrix is an observability artifact, not the runtime itself.

## Canonical Layers

The semantic registry currently groups the 19 curated organs as:

| Layer | Count | Examples |
|---|---:|---|
| Input | 5 | vision, focus, audio, location/mesh, attention |
| Cognition | 10 | memory, drives/homeostasis, immune/RLHS, STGM metabolism, valuation and related state |
| Effector | 4 | tool routing, browser/world actions, scheduling, owner-facing action surfaces |

Important source distinction:

- `System/swarm_canonical_organ_registry.py` is the curated semantic map from owner intent to organ paths, ledgers, capabilities, and query keywords.
- `System/swarm_organ_registry.py` performs structural discovery and ledger-health inspection.
- `System/swarm_code_body_inventory.py` measures source mass and appearance order.
- `.sifta_state/canonical_organ_registry_snapshot.json` is the persisted merged snapshot used by the eval matrix.

These are complementary views, not interchangeable proof systems. SOL should reconcile them when a lane is changed, not create a third inventory.

## The Shared Substrate

The coordination substrate is the filesystem. It is not an invisible shared mind.

- `.sifta_state/ide_stigmergic_trace.jsonl` is a locked append-only IDE coordination trace. It is useful and explicitly forgeable coordination evidence, not automatically STGM or proof of organism behavior.
- `.sifta_state/work_receipts.jsonl` and `.sifta_state/agent_arm_receipts.jsonl` hold work and arm traces.
- `.sifta_state/organ_field.jsonl` carries organ vitals; `latest_organ_field()` produces a bounded latest-per-organ view with staleness decay.
- `System/pheromone_fs.py` records file co-access trails and evaporation.
- `System/swarm_blackboard.py` stores task nodes, pheromone thickness, local votes, status, and decay.
- `System/swarm_stigmergic_memory_retrieval_policy.py` retrieves bounded, scored receipt hits. It must return no matching rows when no matching evidence exists.
- `System/swarm_swimmer_task_packet.py` defines bounded work packets instead of passing the whole transcript or repository to every worker.
- `System/swarm_swimmer_passport.py` defines passport/health records, but this checkout currently has no `.sifta_state/swimmer_passports.jsonl`; do not claim live passport coverage without a new receipt.

Append-only JSONL is a coordination convention. Unless a specific ledger has a verified hash-chain or signature check, do not call it tamper-proof or cryptographic proof.

## Swimmer Contract

Every delegated hand should operate on a narrow bite:

1. Receive a bounded owner task, relevant receipt IDs, read paths, write paths, and a working-set budget.
2. Read the named receipts and probe the named files; do not reload the full covenant, tournament, transcript, or JSONL ocean.
3. If an entity or target is ambiguous, create or consume an assumption receipt before an expensive action.
4. Write only to the declared append-only or explicitly approved artifact paths.
5. Return a closure summary stating: what was read, what was assumed, what was written, what tests ran, and what remains.

The implementation is `System/swarm_swimmer_task_packet.py`; the MiMo-to-Alice mapping is `System/swarm_mimo_swimmer_substrate.py`. MiMo is a cortex surface in this design. The Alice-native organs own the work and receipts.

## Self-Change Path

The intended self-evolution path is:

```text
body signal
  -> collect_body_signals()
  -> formulate_task()
  -> dispatch_to_mimo() / local cortex
  -> mutation governor and quorum floors
  -> snapshot target file
  -> apply bounded patch
  -> AST + relevant pytest
  -> keep or byte-restore/revert
  -> spinal/self-improvement receipt
  -> body inventory and eval visibility
```

Primary files:

- `System/swarm_spinal_cord.py` is the bridge for “I need to change myself.”
- `System/swarm_self_improvement_loop.py` implements observe/propose/gate/apply/measure/keep-revert.
- `System/swarm_mutation_governor_persistence.py` provides persistent proposal, snapshot, apply, measure, and revert helpers.
- `System/swarm_effector_gate.py` and `System/swarm_intent_nonce_gate.py` remain authoritative for world-touching actions.

Current live probe: 19 spinal cycles exist. The latest spinal row is `NO_PATCH` with `governor_ok=false` and `mimo_success=false`; the spinal status view reports zero completed proposals. Separate self-improvement ledgers contain 13 proposal rows and 10 outcome rows. Treat this as a ledger-boundary signal to audit, not as evidence of autonomous successful self-repair.

## Current Receipt Shape

Selected live counts at probe time:

| Ledger | Rows | Interpretation |
|---|---:|---|
| `ide_stigmergic_trace.jsonl` | 39,021 | Coordination traces; not STGM proof by themselves |
| `work_receipts.jsonl` | 29,277 | Work receipts |
| `basal_ganglia_selections.jsonl` | 123,555 | Large selection trace; canonical-vs-legacy unification remains an audit item |
| `episodic_diary.jsonl` | 7,248 | Episodic summaries/continuity traces |
| `memory_ledger.jsonl` | 9,290 | Memory traces |
| `swimmer_task_packets.jsonl` | 55 | Bounded delegation packets |
| `eval/motivational_control_evidence.jsonl` | 1 | One current short-horizon motivation evidence row |

The motivational-control row is explicitly `OPERATIONAL_SHORT_HORIZON`. The code and focused tests cover coupled pressures, time constants, allostasis, anticipation, frustration, refractory periods, layer separation, and history-dependent valuation. Hours-to-days stability, exact-state counterfactual replay, pathology tests, motivational entropy, starvation duration, and metaregulation remain `HYPOTHESIS` until their receipts exist.

## Truth Labels For SOL

Use the labels from `Documents/IDE_BOOT_COVENANT.md`:

- `OBSERVED`: direct file, ledger, sensor, command, hash, or test result.
- `OPERATIONAL`: implemented and verified enough to use, with named evidence.
- `ARCHITECT_DOCTRINE`: binding design stance, not sensor proof.
- `HYPOTHESIS`: plausible but unproven behavior or research direction.
- `FORBIDDEN`: invented tool, receipt, sensor, action, or unsupported consciousness/STGM claim.
- `MANA` / `IDE_DOCTOR_OPERATIONAL_TRACE`: useful external coordination trace, forgeable and not Alice STGM.

The safe phrasing is: “the system implements X and has receipt Y,” not “the creature feels X.”

## Eval Matrix Boundary

`tools/generate_organ_eval_matrix_v2.py` renders `.sifta_state/eval/ORGAN_EVAL_MATRIX_V2.html` from the persisted canonical snapshot and evidence panels. `refresh_body_matrix(force=False)` is intended for boot-time freshness; `force=True` rebuilds the registry snapshot first.

Known limitation from the evidence code: some panels check path existence and ledger freshness. A fresh or empty ledger can therefore produce coverage that looks present without proving an outcome row. The matrix is a map and review surface; SOL must inspect the underlying receipts before upgrading a status.

## First SOL Work Queue

1. **Census and reconciliation:** refresh the canonical snapshot, compare curated organs to discovered/app/arm/ecology rows, and produce a bounded list of high-value gaps. Do not rename or duplicate organs merely to make counts look cleaner.
2. **Causal replay:** choose one safe valuation path. Persist exact world state, candidates, model state, and seed; ablate one endogenous variable; rerun; verify that only the intended internal state changed the bounded choice.
3. **Long-horizon stability:** run repeated safe environments with scarcity, interruption, social opportunity, delayed consequences, and changing context. Measure entropy, starvation, oscillation, prediction error, persistence, and recovery.
4. **Pathology and metaregulation:** test reward capture, curiosity loops, preservation dominance, dependency, helplessness, endocrine saturation, runaway frustration, allostatic drift, and reward hacking. Metaregulation may emit regulatory signals only; it must not bypass safety or authority gates.
5. **Live closure:** every landed change needs a focused test, a named receipt, an inventory/eval pointer, and an explicit remaining-gap line.

## Do Not Do

- Do not dump 1.6M Python lines into context.
- Do not create a second covenant, global chat, memory field, or rival registry.
- Do not rewrite append-only history to remove collisions or make the narrative cleaner.
- Do not treat a model picker, ledger count, prompt, or eval color as proof of consciousness.
- Do not let motivation, valuation, MiMo, or a swimmer bypass the nonce, effector, owner, or mutation gates.
- Do not call owner-controlled real-money or other external state from a research handoff; use read-only probes and paper/sandbox evidence.

## Read Order

1. `AGENTS.md`
2. `Documents/IDE_BOOT_COVENANT.md`
3. `Documents/SIFTA_CLI_LANGUAGE.md`
4. `sifta_os_desktop.py` and `SIFTA OS.command`
5. `System/swarm_canonical_organ_registry.py`
6. `System/swarm_organ_registry.py`
7. `System/swarm_code_body_inventory.py`
8. `System/swarm_swimmer_task_packet.py`
9. `System/swarm_spinal_cord.py`
10. `System/swarm_self_improvement_loop.py`
11. `System/swarm_mutation_governor_persistence.py`
12. `System/ide_stigmergic_bridge.py`, `System/swarm_blackboard.py`, and `System/pheromone_fs.py`
13. `System/swarm_eval_matrix_evidence.py` and `tools/generate_organ_eval_matrix_v2.py`
14. The specific organ and ledger named by the current task

Useful bounded checks:

```bash
python3 -c 'from System.swarm_code_body_inventory import build_code_inventory; print(build_code_inventory(write_appearance_ledger=False))'
python3 -c 'from System.swarm_canonical_organ_registry import build_registry; print(build_registry(include_dynamic=True)["counts"])'
python3 tools/prepare_sol_landing_zone.py --print
python3 tools/whats_left.py
```

Focused tests should be selected from the changed organ, not replaced by a claim that the entire repository is green.

## Handoff Receipt

This document is the human preparation artifact. `tools/prepare_sol_landing_zone.py` produces the fast machine-readable companion at `.sifta_state/sol_landing_zone.json` by reading the latest snapshot and bounded ledger tails. The canonical registry snapshot and HTML matrix are current. The normal matrix path now uses canonical `code_inventory`, cached exhaustive review data, bounded JSONL tails, and the canonical STGM cache instead of replaying the signed economy ledger. A measured stale-registry rebuild plus matrix render and landing-packet write completed in 43.85 seconds; the detached boot worker has a 90-second safety budget. `force=True` remains the explicit deep census path and may be expensive because it inventories archived/generated workspace material.
